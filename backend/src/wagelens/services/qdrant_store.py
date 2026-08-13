from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer
except Exception:  # noqa: BLE001
    _SentenceTransformer = None  # type: ignore

from wagelens.agents.pattern import score_pair
from wagelens.config import settings
from wagelens.models.schemas import CompleteComplaintExtraction

logger = logging.getLogger(__name__)


class QdrantStore:
    def __init__(self) -> None:
        self.client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
        self.collection = settings.qdrant_collection
        self.model = None
        self._initialized = False
        self._initialize()

    def _initialize(self) -> None:
        try:
            logger.info("Initializing Qdrant: %s", settings.qdrant_url)
            collection_ready = self._ensure_collection()
            if not collection_ready:
                self._initialized = False
                return
            self._initialized = True
            logger.info(
                "Qdrant initialized successfully (collection: %s)", self.collection
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant initialization failed: %s", exc)
            self._initialized = False

    def _ensure_collection(self) -> bool:
        for attempt in range(3):
            try:
                if self.client.collection_exists(self.collection):
                    return True
                logger.info("Creating Qdrant collection: %s", self.collection)
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=qmodels.VectorParams(
                        size=384,
                        distance=qmodels.Distance.COSINE,
                        on_disk=False,
                    ),
                )
                return True
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    logger.error(
                        "Failed to ensure Qdrant collection after 3 attempts: %s", exc
                    )
                    return False
                wait_time = (attempt + 1) * 1
                logger.warning(
                    "Qdrant connection attempt %d failed, retrying in %ds: %s",
                    attempt + 1,
                    wait_time,
                    exc,
                )
                time.sleep(wait_time)
        return False

    def is_available(self) -> bool:
        if not self._initialized:
            return False
        try:
            self.client.get_collection(self.collection)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Qdrant availability check failed: %s", exc)
            return False

    def _load_model(self):
        if self.model is None and _SentenceTransformer is not None:
            try:
                if settings.hf_token:
                    logger.debug("Loading SentenceTransformer with HF_TOKEN configured")
                self.model = _SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:  # noqa: BLE001
                self.model = None
        return self.model

    def _embed(self, text: str) -> list[float]:
        model = self._load_model()
        if model is None:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            expanded = (digest * 16)[:384]
            return [((byte / 255.0) * 2.0) - 1.0 for byte in expanded]
        return model.encode(text).tolist()

    def _location_signature(self, extraction: CompleteComplaintExtraction) -> str:
        return f"{extraction.pickup_location} -> {extraction.drop_location}"

    def search_similar(
        self, extraction: CompleteComplaintExtraction, limit: int = 8
    ) -> list[dict[str, Any]]:
        if not self.is_available():
            return []

        location_vector = self._embed(self._location_signature(extraction))
        try:
            response = self.client.query_points(
                collection_name=self.collection,
                query=location_vector,
                limit=limit,
                score_threshold=0.15,
            )
            hits = response.points
        except Exception as exc:  # noqa: BLE001
            logger.error("Qdrant search failed: %s", exc)
            return []

        results: list[dict[str, Any]] = []
        for hit in hits:
            payload = hit.payload or {}
            confidence, location_score, platform_score, time_score = score_pair(
                extraction, payload, float(hit.score)
            )
            results.append(
                {
                    "score": hit.score,
                    "composite_score": confidence,
                    "location_score": location_score,
                    "platform_score": platform_score,
                    "time_score": time_score,
                    "payload": payload,
                }
            )

        results.sort(key=lambda item: item["composite_score"], reverse=True)
        logger.debug("Qdrant search found %d weighted candidates", len(results))
        return results

    def upsert_complaint(
        self,
        complaint_id: str,
        extraction: CompleteComplaintExtraction,
        cluster_id: str,
        cluster_size: int,
    ) -> None:
        if not self.is_available():
            logger.debug("Qdrant not available, skipping upsert for %s", complaint_id)
            return

        route = self._location_signature(extraction)
        point_id = int(hashlib.sha256(complaint_id.encode()).hexdigest()[:15], 16)
        payload: dict[str, Any] = {
            "complaint_id": complaint_id,
            "route": route,
            "time_window": extraction.trip_time,
            "platform": extraction.platform,
            "pickup_location": extraction.pickup_location,
            "drop_location": extraction.drop_location,
            "cluster_id": cluster_id,
            "cluster_size": cluster_size,
            "discrepancy_pct": round(
                (
                    (extraction.quoted_amount - extraction.paid_amount)
                    / extraction.quoted_amount
                )
                * 100,
                1,
            ),
        }

        try:
            self.client.upsert(
                collection_name=self.collection,
                points=[
                    qmodels.PointStruct(
                        id=point_id,
                        vector=self._embed(route),
                        payload=payload,
                    )
                ],
            )
            self._refresh_cluster_size(cluster_id, cluster_size)
            logger.debug(
                "Qdrant upserted complaint %s into cluster %s", complaint_id, cluster_id
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to upsert complaint to Qdrant: %s", exc)

    def _refresh_cluster_size(self, cluster_id: str, cluster_size: int) -> None:
        """Keep cluster_size in sync across points that share a cluster."""
        try:
            points, _ = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="cluster_id",
                            match=qmodels.MatchValue(value=cluster_id),
                        )
                    ]
                ),
                limit=200,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = dict(point.payload or {})
                payload["cluster_size"] = cluster_size
                self.client.set_payload(
                    collection_name=self.collection,
                    payload={"cluster_size": cluster_size},
                    points=[point.id],
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not refresh cluster_size for %s: %s", cluster_id, exc)


_qdrant_store: QdrantStore | None = None


def get_qdrant_store() -> QdrantStore:
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantStore()
    return _qdrant_store

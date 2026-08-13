from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from wagelens.config import settings
from wagelens.models.schemas import (
    CompleteComplaintExtraction,
    ComplaintRecord,
    DashboardPattern,
    DashboardStats,
    PatternResult,
)
from wagelens.agents.pattern import (
    CLUSTER_JOIN_THRESHOLD,
    cluster_id_for_extraction,
    match_extractions,
)

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class ComplaintRow(Base):
    __tablename__ = "complaints"

    complaint_id = Column(String, primary_key=True)
    driver_id_hash = Column(String, nullable=True)
    platform = Column(String, nullable=False)
    trip_timestamp = Column(String, nullable=True)
    pickup_location = Column(String, nullable=True)
    drop_location = Column(String, nullable=True)
    quoted_amount = Column(Float, nullable=True)
    paid_amount = Column(Float, nullable=True)
    discrepancy = Column(Float, nullable=True)
    discrepancy_pct = Column(Float, nullable=True)
    raw_transcript = Column(Text, nullable=False)
    cluster_id = Column(String, nullable=True)
    cluster_size = Column(Integer, default=0)
    cluster_confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def _ensure_sqlite_dir(url: str) -> bool:
    """Ensure SQLite directory exists. Returns True if successful."""
    if url.startswith("sqlite:///"):
        db_path = url.replace("sqlite:///", "")
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Database directory ensured: {Path(db_path).parent}")
            return True
        except OSError as exc:
            logger.error(f"Failed to create database directory: {exc}")
            return False
    return True


def _initialize_database() -> bool:
    """Initialize database and create tables. Returns True if successful."""
    try:
        logger.info(f"Initializing database: {settings.database_url}")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to initialize database: {exc}")
        return False


_ensure_sqlite_dir(settings.database_url)
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
_db_initialized = _initialize_database()


def _sync_cluster_sizes(session, cluster_id: str) -> int:
    """Update cluster_size on all rows sharing a cluster_id."""
    rows = (
        session.query(ComplaintRow).filter(ComplaintRow.cluster_id == cluster_id).all()
    )
    count = len(rows)
    for row in rows:
        row.cluster_size = count
    return count


def reconcile_cluster_ids() -> None:
    """Group complaints by fuzzy route/platform/time similarity."""
    if not _db_initialized:
        return
    try:
        with SessionLocal() as session:
            rows = session.query(ComplaintRow).all()
            normalized_rows: list[tuple[ComplaintRow, CompleteComplaintExtraction]] = []
            for row in rows:
                try:
                    complete = CompleteComplaintExtraction(
                        trip_time=row.trip_timestamp,
                        pickup_location=row.pickup_location,
                        drop_location=row.drop_location,
                        quoted_amount=row.quoted_amount,
                        paid_amount=row.paid_amount,
                        platform=row.platform,
                    )
                except Exception:  # noqa: BLE001
                    continue
                normalized_rows.append((row, complete))

            cluster_groups: dict[str, list[ComplaintRow]] = {}
            representatives: dict[str, CompleteComplaintExtraction] = {}

            for row, normalized in normalized_rows:
                best_cluster: str | None = None
                best_score = 0.0
                for cluster_id, rep in representatives.items():
                    confidence, _, _, _ = match_extractions(normalized, rep)
                    if confidence > best_score:
                        best_score = confidence
                        best_cluster = cluster_id

                if best_cluster and best_score >= CLUSTER_JOIN_THRESHOLD:
                    row.cluster_id = best_cluster
                    cluster_groups.setdefault(best_cluster, []).append(row)
                else:
                    cluster_id = cluster_id_for_extraction(normalized)
                    row.cluster_id = cluster_id
                    cluster_groups.setdefault(cluster_id, []).append(row)
                    representatives[cluster_id] = normalized

            for cluster_id, members in cluster_groups.items():
                size = len(members)
                for row in members:
                    row.cluster_size = size
            session.commit()
        logger.info("Reconciled cluster IDs for %d complaints", len(rows))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cluster reconciliation failed: %s", exc)


def save_complaint(
    complaint_id: str,
    transcript: str,
    extraction: CompleteComplaintExtraction,
    pattern: PatternResult,
) -> None:
    """Save complaint to database. Logs errors internally."""
    if not _db_initialized:
        logger.warning(
            f"Database not initialized. Skipping save for complaint {complaint_id}"
        )
        return

    cluster_id = pattern.cluster_id
    discrepancy = extraction.quoted_amount - extraction.paid_amount
    discrepancy_pct = round((discrepancy / extraction.quoted_amount) * 100, 1)

    try:
        with SessionLocal() as session:
            row = ComplaintRow(
                complaint_id=complaint_id,
                driver_id_hash=None,
                platform=extraction.platform,
                trip_timestamp=extraction.trip_time,
                pickup_location=extraction.pickup_location,
                drop_location=extraction.drop_location,
                quoted_amount=extraction.quoted_amount,
                paid_amount=extraction.paid_amount,
                discrepancy=discrepancy,
                discrepancy_pct=discrepancy_pct,
                raw_transcript=transcript,
                cluster_id=cluster_id,
                cluster_size=pattern.similar_complaint_count,
                cluster_confidence=pattern.confidence_score,
            )
            session.add(row)
            session.flush()
            cluster_size = _sync_cluster_sizes(session, cluster_id)
            session.commit()
        logger.info(
            "Complaint saved: %s (cluster: %s size=%d)",
            complaint_id,
            cluster_id,
            cluster_size,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to save complaint {complaint_id}: {exc}")


def list_complaints(limit: int = 50) -> list[ComplaintRecord]:
    """List complaints from database. Returns empty list if database not initialized."""
    if not _db_initialized:
        logger.warning("Database not initialized. Returning empty complaint list")
        return []

    try:
        with SessionLocal() as session:
            rows = (
                session.query(ComplaintRow)
                .order_by(ComplaintRow.created_at.desc())
                .limit(limit)
                .all()
            )
            result = [
                ComplaintRecord(
                    complaint_id=row.complaint_id,
                    driver_id_hash=row.driver_id_hash,
                    platform=row.platform,
                    trip_timestamp=row.trip_timestamp,
                    pickup_location=row.pickup_location,
                    drop_location=row.drop_location,
                    quoted_amount=row.quoted_amount,
                    paid_amount=row.paid_amount,
                    discrepancy=row.discrepancy,
                    discrepancy_pct=row.discrepancy_pct,
                    raw_transcript=row.raw_transcript,
                    cluster_id=row.cluster_id,
                    cluster_size=row.cluster_size or 0,
                    cluster_confidence=row.cluster_confidence or 0.0,
                    created_at=row.created_at,
                )
                for row in rows
            ]
            logger.debug(f"Retrieved {len(result)} complaints")
            return result
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to list complaints: {exc}")
        return []


def dashboard_stats() -> DashboardStats:
    """Get dashboard statistics. Returns empty stats if database not initialized."""
    if not _db_initialized:
        logger.warning("Database not initialized. Returning empty dashboard stats")
        return DashboardStats(total_complaints=0, pattern_clusters=0, top_patterns=[])

    reconcile_cluster_ids()

    try:
        complaints = list_complaints(limit=200)
        clusters: dict[str, dict] = {}
        for c in complaints:
            if not c.cluster_id:
                continue
            route = f"{c.pickup_location or '?'} -> {c.drop_location or '?'}"
            entry = clusters.setdefault(
                c.cluster_id,
                {
                    "cluster_id": c.cluster_id,
                    "count": 0,
                    "route": route,
                    "time_window": c.trip_timestamp or "unknown",
                    "avg_discrepancy_pct": [],
                },
            )
            if c.discrepancy_pct is not None:
                entry["avg_discrepancy_pct"].append(c.discrepancy_pct)

        for entry in clusters.values():
            entry["count"] = sum(
                1 for c in complaints if c.cluster_id == entry["cluster_id"]
            )

        top_patterns = [
            DashboardPattern(
                cluster_id=entry["cluster_id"],
                count=entry["count"],
                route=entry["route"],
                time_window=entry["time_window"],
                avg_discrepancy_pct=round(
                    sum(vals) / len(vals), 1
                )
                if (vals := entry.pop("avg_discrepancy_pct"))
                else 0.0,
            )
            for entry in sorted(clusters.values(), key=lambda x: x["count"], reverse=True)[
                :5
            ]
        ]

        stats = DashboardStats(
            total_complaints=len(complaints),
            pattern_clusters=len(clusters),
            top_patterns=top_patterns,
        )
        logger.debug(
            f"Dashboard stats: {len(complaints)} complaints, {len(clusters)} clusters"
        )
        return stats
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to generate dashboard stats: {exc}")
        return DashboardStats(total_complaints=0, pattern_clusters=0, top_patterns=[])

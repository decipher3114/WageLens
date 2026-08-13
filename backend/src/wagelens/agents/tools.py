import json
import logging

try:
    from crewai.tools import tool
except Exception:  # pragma: no cover - optional dependency fallback

    def tool(*args, **kwargs):
        def decorator(func):
            return func

        return decorator


from pydantic import ValidationError

from wagelens.agents.pattern import detect_pattern
from wagelens.models.schemas import CompleteComplaintExtraction
from wagelens.services.qdrant_store import get_qdrant_store

logger = logging.getLogger(__name__)


def _parse_extraction_json(extraction_json: str) -> CompleteComplaintExtraction:
    if not extraction_json or not extraction_json.strip():
        raise ValueError("extraction_json is empty")
    try:
        raw = json.loads(extraction_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"extraction_json is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("extraction_json must be a JSON object")
    return CompleteComplaintExtraction.model_validate(raw)


@tool("Search Qdrant for similar complaint patterns")
def qdrant_pattern_search_tool(extraction_json: str) -> str:
    """Search for similar complaints. Input MUST be extraction JSON."""
    try:
        extraction = _parse_extraction_json(extraction_json)
    except (ValueError, ValidationError) as exc:
        logger.warning("qdrant_pattern_search_tool rejected input: %s", exc)
        return json.dumps({"error": str(exc), "is_pattern": False})

    logger.debug(
        "Tool qdrant_pattern_search_tool: platform=%s route=%s->%s time=%s",
        extraction.platform,
        extraction.pickup_location,
        extraction.drop_location,
        extraction.trip_time,
    )
    hits = get_qdrant_store().search_similar(extraction)
    pattern = detect_pattern(extraction, hits)
    logger.info(
        "Pattern search result: hits=%d is_pattern=%s cluster_id=%s confidence=%.3f similar=%d",
        len(hits),
        pattern.is_pattern,
        pattern.cluster_id,
        pattern.confidence_score,
        pattern.similar_complaint_count,
    )
    return pattern.model_dump_json()

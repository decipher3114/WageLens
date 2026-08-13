import logging
from uuid import uuid4

from wagelens.agents.crew_orchestrator import run_complaint_crew
from wagelens.config import settings
from wagelens.logging_config import truncate
from wagelens.models.schemas import (
    ComplaintStatus,
    ServiceStatus,
    VoiceComplaintResponse,
    to_complete,
)
from wagelens.services.database import save_complaint
from wagelens.services.qdrant_store import get_qdrant_store
from wagelens.services.tts_feedback import feedback_with_audio

logger = logging.getLogger(__name__)


async def _build_service_status() -> ServiceStatus:
    qdrant_available = False
    try:
        qdrant_available = get_qdrant_store().is_available()
    except Exception:  # noqa: BLE001
        qdrant_available = False

    return ServiceStatus(
        rime="configured" if settings.rime_api_key else "not_configured",
        qdrant="available" if qdrant_available else "unavailable",
        pattern_source="qdrant_search",
    )


async def process_text_complaint(transcript: str) -> VoiceComplaintResponse:
    logger.info(
        "Pipeline started: transcript_len=%d preview=%r",
        len(transcript),
        truncate(transcript, 80),
    )

    try:
        result = await run_complaint_crew(transcript)
    except Exception as exc:
        logger.exception("Crew pipeline failed")
        raise RuntimeError("Complaint analysis failed. Please try again.") from exc

    service_status = await _build_service_status()
    feedback, audio_base64, audio_mime = await feedback_with_audio(result.feedback)

    if result.status == ComplaintStatus.DISCARDED:
        logger.info(
            "Complaint discarded: missing_fields=%s extraction=%s",
            result.missing_fields,
            result.extraction.model_dump(exclude_none=True),
        )
        return VoiceComplaintResponse(
            status=ComplaintStatus.DISCARDED,
            transcript=transcript,
            feedback=feedback,
            audio_base64=audio_base64,
            audio_mime=audio_mime,
            extraction=result.extraction,
            missing_fields=result.missing_fields,
            pattern=None,
            complaint_id=None,
            service_status=service_status,
        )

    complaint_id = result.complaint_id or str(uuid4())
    pattern = result.pattern
    if pattern is None:
        logger.error("Accepted complaint missing pattern analysis")
        raise RuntimeError("Accepted complaint is missing pattern analysis.")

    logger.info(
        "Complaint accepted: id=%s platform=%s route=%s->%s is_pattern=%s cluster_id=%s confidence=%.3f",
        complaint_id,
        result.extraction.platform,
        result.extraction.pickup_location,
        result.extraction.drop_location,
        pattern.is_pattern,
        pattern.cluster_id,
        pattern.confidence_score,
    )

    complete = to_complete(result.extraction)

    try:
        save_complaint(
            complaint_id,
            transcript,
            complete,
            pattern,
        )
    except Exception as exc:
        logger.exception("Failed to save complaint id=%s", complaint_id)
        raise RuntimeError("Complaint was analyzed but could not be saved.") from exc

    try:
        get_qdrant_store().upsert_complaint(
            complaint_id=complaint_id,
            extraction=complete,
            cluster_id=pattern.cluster_id,
            cluster_size=pattern.similar_complaint_count,
        )
    except Exception as exc:
        logger.warning(
            "Complaint saved but Qdrant upsert failed for id=%s: %s",
            complaint_id,
            exc,
        )

    logger.info(
        "Complaint persisted: id=%s cluster_id=%s", complaint_id, pattern.cluster_id
    )

    return VoiceComplaintResponse(
        status=ComplaintStatus.ACCEPTED,
        transcript=transcript,
        feedback=feedback,
        audio_base64=audio_base64,
        audio_mime=audio_mime,
        extraction=result.extraction,
        missing_fields=[],
        pattern=pattern,
        complaint_id=complaint_id,
        service_status=service_status,
    )

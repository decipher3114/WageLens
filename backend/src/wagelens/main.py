import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from wagelens.config import settings
from wagelens.logging_config import setup_logging, truncate
from wagelens.middleware import RequestLoggingMiddleware
from wagelens.models.schemas import (
    ComplaintRecord,
    DashboardStats,
    TextComplaintRequest,
    VoiceComplaintResponse,
)
from wagelens.startup import reset_runtime_data

reset_runtime_data()

setup_logging(
    level=settings.log_level,
    log_format=settings.log_format,  # type: ignore[arg-type]
    log_file=settings.log_file,
)

from wagelens.services.database import (
    dashboard_stats,
    list_complaints,
    reconcile_cluster_ids,
)
from wagelens.services.pipeline import process_text_complaint
from wagelens.services.qdrant_store import get_qdrant_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "WageLens API starting up (model=%s, log_level=%s)",
        settings.openai_model,
        settings.log_level,
    )

    try:
        qdrant = get_qdrant_store()
        if qdrant.is_available():
            logger.info("Qdrant vector store initialized successfully")
        else:
            logger.warning(
                "Qdrant vector store not available - pattern search disabled"
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialize Qdrant: %s", exc)

    try:
        reconcile_cluster_ids()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cluster reconciliation on startup failed: %s", exc)

    logger.info(
        "WageLens API startup complete (services: openai=%s rime=%s qdrant=%s)",
        "configured" if settings.openai_api_key else "missing",
        "configured" if settings.rime_api_key else "missing",
        "configured" if get_qdrant_store().is_available() else "unavailable",
    )
    yield
    logger.info("WageLens API shutting down")


app = FastAPI(
    title="WageLens API",
    description="Voice-first wage discrepancy evidence system — WageLens",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a clean API error instead of leaking tracebacks to clients."""
    logger.exception(
        "Unhandled error: %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


@app.get("/")
def root() -> dict:
    return {
        "name": "WageLens API",
        "version": "0.2.0",
        "endpoints": {
            "submit_complaint": "POST /api/complaints/voice",
            "complaints": "GET /api/complaints",
            "dashboard": "GET /api/dashboard/stats",
        },
    }


@app.post("/api/complaints/voice", response_model=VoiceComplaintResponse)
async def submit_voice_complaint(body: TextComplaintRequest) -> VoiceComplaintResponse:
    """Accept browser speech-to-text transcript and run the complaint pipeline."""
    if not settings.openai_api_key:
        logger.error("Complaint rejected: OpenAI API key not configured")
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    if not settings.rime_api_key:
        logger.error("Complaint rejected: Rime API key not configured")
        raise HTTPException(status_code=500, detail="Rime API key not configured")

    transcript = body.transcript.strip()
    if len(transcript) < 3:
        logger.warning(
            "Complaint rejected: transcript too short (len=%d)", len(transcript)
        )
        raise HTTPException(status_code=400, detail="Transcript too short")

    logger.info(
        "Text complaint received: length=%d preview=%r",
        len(transcript),
        truncate(transcript, 80),
    )

    try:
        response = await process_text_complaint(transcript)
    except RuntimeError as exc:
        logger.error("Complaint pipeline failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected complaint processing failure")
        raise HTTPException(
            status_code=500,
            detail="Failed to process complaint. Please try again.",
        ) from exc

    logger.info(
        "Complaint processed: status=%s complaint_id=%s missing_fields=%d",
        response.status.value,
        response.complaint_id,
        len(response.missing_fields),
    )
    return response


@app.get("/api/complaints", response_model=list[ComplaintRecord])
def get_complaints() -> list[ComplaintRecord]:
    complaints = list_complaints()
    logger.info("Listed complaints: count=%d", len(complaints))
    return complaints


@app.get("/api/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats() -> DashboardStats:
    stats = dashboard_stats()
    logger.info(
        "Dashboard stats: total_complaints=%d pattern_clusters=%d top_patterns=%d",
        stats.total_complaints,
        stats.pattern_clusters,
        len(stats.top_patterns),
    )
    return stats

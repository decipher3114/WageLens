from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

REQUIRED_EXTRACTION_FIELDS = frozenset(
    {
        "quoted_amount",
        "paid_amount",
        "platform",
        "trip_time",
        "pickup_location",
        "drop_location",
    }
)


def _field_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


class ComplaintExtraction(BaseModel):
    """Partial extraction returned while validation is incomplete."""

    model_config = ConfigDict(ser_json_exclude_none=True)

    trip_time: str | None = None
    pickup_location: str | None = None
    drop_location: str | None = None
    quoted_amount: float | None = None
    paid_amount: float | None = None
    platform: str | None = None


class VerifiedExtraction(ComplaintExtraction):
    """LLM-validated extraction with missing-field report."""

    missing_fields: list[str] = Field(default_factory=list)


class CompleteComplaintExtraction(BaseModel):
    """All six fields present — used after validation passes."""

    model_config = ConfigDict(ser_json_exclude_none=True)

    trip_time: str
    pickup_location: str
    drop_location: str
    quoted_amount: float
    paid_amount: float
    platform: str


def finalize_verified(
    verified: VerifiedExtraction,
) -> tuple[ComplaintExtraction, list[str]]:
    """Drop empty values; required gaps go to missing_fields only."""
    missing = {f for f in verified.missing_fields if f in REQUIRED_EXTRACTION_FIELDS}
    present: dict[str, object] = {}

    for name in REQUIRED_EXTRACTION_FIELDS:
        value = getattr(verified, name)
        if _field_empty(value):
            missing.add(name)
            continue
        present[name] = value

    return ComplaintExtraction(**present), sorted(missing)


def to_complete(extraction: ComplaintExtraction) -> CompleteComplaintExtraction:
    return CompleteComplaintExtraction.model_validate(
        extraction.model_dump(exclude_none=True)
    )


class PatternResult(BaseModel):
    is_pattern: bool = False
    cluster_id: str
    similar_complaint_count: int = 0
    common_route: str
    common_time_window: str
    confidence_score: float = 0.0
    location_score: float = 0.0
    platform_score: float = 0.0
    time_score: float = 0.0


class ComplaintStatus(str, Enum):
    ACCEPTED = "accepted"
    DISCARDED = "discarded"


class ServiceStatus(BaseModel):
    rime: str = "not_configured"
    qdrant: str = "unavailable"
    pattern_source: str = "qdrant_search"


class TextComplaintRequest(BaseModel):
    transcript: str = Field(..., min_length=3)


class VoiceComplaintResponse(BaseModel):
    model_config = ConfigDict(ser_json_exclude_none=True)

    status: ComplaintStatus
    transcript: str
    feedback: str
    audio_base64: str | None = None
    audio_mime: str | None = None
    extraction: ComplaintExtraction | None = None
    missing_fields: list[str] = Field(default_factory=list)
    pattern: PatternResult | None = None
    complaint_id: str | None = None
    service_status: ServiceStatus = Field(default_factory=ServiceStatus)


class ComplaintRecord(BaseModel):
    complaint_id: str
    driver_id_hash: str | None = None
    platform: str
    trip_timestamp: str | None
    pickup_location: str | None
    drop_location: str | None
    quoted_amount: float | None
    paid_amount: float | None
    discrepancy: float | None
    discrepancy_pct: float | None
    raw_transcript: str
    cluster_id: str | None
    cluster_size: int
    cluster_confidence: float
    created_at: datetime


class DashboardPattern(BaseModel):
    cluster_id: str
    count: int
    route: str
    time_window: str
    avg_discrepancy_pct: float


class DashboardStats(BaseModel):
    total_complaints: int
    pattern_clusters: int
    top_patterns: list[DashboardPattern]

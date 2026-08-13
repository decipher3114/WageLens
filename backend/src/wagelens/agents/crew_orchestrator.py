"""CrewAI orchestration — LLM extraction, LLM validation, pattern search."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import uuid4

try:
    from crewai import Agent, Crew, LLM, Process, Task
except Exception:  # pragma: no cover - optional dependency fallback
    Agent = Crew = LLM = Process = Task = None  # type: ignore[assignment]
from pydantic import BaseModel

from wagelens.agents.feedback_messages import (
    build_accepted_feedback,
    build_discard_feedback,
)
from wagelens.agents.platforms import supported_platforms_hint
from wagelens.agents.tools import qdrant_pattern_search_tool
from wagelens.config import settings
from wagelens.models.schemas import (
    ComplaintExtraction,
    ComplaintStatus,
    PatternResult,
    REQUIRED_EXTRACTION_FIELDS,
    VerifiedExtraction,
    finalize_verified,
    to_complete,
)

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = sorted(REQUIRED_EXTRACTION_FIELDS)

_EXTRACTION_RULES = f"""
The driver speaks Hindi (may include some English words). Return a JSON object with ONLY these keys:
- trip_time: English 12-hour time like "5:30 PM"
- pickup_location: English place name (e.g. "Sector 12", "Ghaziabad")
- drop_location: English place name
- quoted_amount: JSON number — fare shown/promised/expected
- paid_amount: JSON number — fare actually received
- platform: one of ({supported_platforms_hint()}) in English

Rules:
- All extracted values MUST be English. Amounts MUST be JSON numbers, not strings.
- quoted_amount = promised/shown fare; paid_amount = amount actually received.
- Do NOT copy one amount into both fields unless the driver explicitly says they are equal.
- Omit any key you cannot fill from the transcript. Do NOT use null.
- Do NOT include any keys beyond the six fields above.
"""

_VERIFICATION_RULES = f"""
Review the Hindi driver transcript and the extraction JSON from the previous task.

Return a JSON object with ONLY these keys:
- trip_time
- pickup_location
- drop_location
- quoted_amount
- paid_amount
- platform
- missing_fields

Rules:
- Correct any extraction mistakes using the transcript.
- Include a field key ONLY when you have a valid English value (amounts as JSON numbers).
- Omit keys for unknown or invalid values. Do NOT use null.
- platform must be one of ({supported_platforms_hint()}) when included.
- missing_fields: required field names still missing after validation.
  Required fields: {", ".join(_REQUIRED_FIELDS)}.
- Do NOT include is_complete, notes, explanations, or any other keys.
"""


@dataclass
class CrewPipelineResult:
    status: ComplaintStatus
    extraction: ComplaintExtraction
    missing_fields: list[str]
    pattern: PatternResult | None
    feedback: str
    complaint_id: str | None


def _build_llm() -> LLM:
    if not settings.openai_api_key or LLM is None:
        raise RuntimeError("OPENAI_API_KEY is required to run the CrewAI pipeline.")
    return LLM(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0.1,
    )


def _parse_task_output(task: Task, model: type[BaseModel]) -> BaseModel:
    if task.output and getattr(task.output, "pydantic", None):
        return task.output.pydantic

    raw = getattr(task.output, "raw", None) if task.output else None
    if not raw:
        logger.error("Empty or missing task output for task: %s", task.description)
        raise ValueError(f"Empty or missing task output for task: {task.description}")

    try:
        return model.model_validate_json(raw)
    except Exception:
        logger.warning("Task output JSON parse failed, attempting dict validation")
        return model.model_validate(json.loads(raw))


async def run_complaint_crew(transcript: str) -> CrewPipelineResult:
    """Extract fields via LLM, validate via LLM, then run pattern search when complete."""
    logger.info("Crew pipeline starting: transcript_len=%d", len(transcript))
    if (
        not settings.openai_api_key
        or LLM is None
        or Agent is None
        or Crew is None
        or Task is None
    ):
        raise RuntimeError(
            "OPENAI_API_KEY and CrewAI dependencies are required to run the CrewAI pipeline."
        )

    llm = _build_llm()

    extraction_agent = Agent(
        role="Complaint Extraction Specialist",
        goal="Extract structured fare-discrepancy facts from Hindi voice transcripts",
        backstory=(
            "You parse spoken gig-worker complaints into clean JSON. "
            "You output English text and numeric amounts only."
        ),
        llm=llm,
        verbose=settings.crew_verbose,
        allow_delegation=False,
    )

    verification_agent = Agent(
        role="Complaint Verification Specialist",
        goal="Validate and finalize extracted complaint JSON against the original transcript",
        backstory=(
            "You verify extracted complaint data. You return ONLY the validated JSON fields "
            "and a missing_fields list. You never add extra keys or commentary."
        ),
        llm=llm,
        verbose=settings.crew_verbose,
        allow_delegation=False,
    )

    pattern_agent = Agent(
        role="Pattern Detection Analyst",
        goal="Detect recurring cross-driver discrepancy patterns via weighted Qdrant search",
        backstory=(
            "You analyze complaint signatures using Qdrant vector search. "
            "You MUST call qdrant_pattern_search_tool with the extraction JSON "
            "and return the tool output unchanged."
        ),
        tools=[qdrant_pattern_search_tool],
        llm=llm,
        verbose=settings.crew_verbose,
        allow_delegation=False,
    )

    extraction_task = Task(
        description=(
            "Extract structured complaint facts from this Hindi driver transcript:\n\n"
            "{transcript}\n\n"
            f"{_EXTRACTION_RULES}"
        ),
        expected_output=(
            "Valid JSON with keys: trip_time, pickup_location, drop_location, "
            "quoted_amount, paid_amount, platform"
        ),
        agent=extraction_agent,
        output_pydantic=ComplaintExtraction,
    )

    verification_task = Task(
        description=(
            "Validate the extraction from the previous task against the transcript:\n\n"
            "{transcript}\n\n"
            f"{_VERIFICATION_RULES}"
        ),
        expected_output=(
            "Valid JSON with keys: trip_time, pickup_location, drop_location, "
            "quoted_amount, paid_amount, platform, missing_fields"
        ),
        agent=verification_agent,
        context=[extraction_task],
        output_pydantic=VerifiedExtraction,
    )

    intake_crew = Crew(
        agents=[extraction_agent, verification_agent],
        tasks=[extraction_task, verification_task],
        process=Process.sequential,
        verbose=settings.crew_verbose,
    )
    await intake_crew.kickoff_async(inputs={"transcript": transcript})

    verified: VerifiedExtraction = _parse_task_output(  # type: ignore[assignment]
        verification_task, VerifiedExtraction
    )
    extraction, missing_fields = finalize_verified(verified)

    logger.info(
        "Crew validation complete: platform=%s route=%s->%s quoted=%s paid=%s trip_time=%s missing=%s",
        extraction.platform,
        extraction.pickup_location,
        extraction.drop_location,
        extraction.quoted_amount,
        extraction.paid_amount,
        extraction.trip_time,
        missing_fields,
    )

    if missing_fields:
        feedback = build_discard_feedback(missing_fields)
        logger.info(
            "Crew pipeline discarded complaint: missing_fields=%s feedback_len=%d",
            missing_fields,
            len(feedback),
        )
        return CrewPipelineResult(
            status=ComplaintStatus.DISCARDED,
            extraction=extraction,
            missing_fields=missing_fields,
            pattern=None,
            feedback=feedback,
            complaint_id=None,
        )

    complete = to_complete(extraction)
    extraction_json = complete.model_dump_json()
    logger.info("Crew verification passed — running pattern search")
    pattern_task = Task(
        description=(
            "Search for similar complaints using qdrant_pattern_search_tool.\n"
            f"Pass this extraction JSON verbatim as a single string argument:\n{extraction_json}\n\n"
            "Return the tool JSON output unchanged. Do NOT invent pattern scores."
        ),
        expected_output=(
            "JSON with is_pattern, cluster_id, similar_complaint_count, common_route, "
            "common_time_window, confidence_score, location_score, platform_score, time_score"
        ),
        agent=pattern_agent,
        output_pydantic=PatternResult,
    )

    pattern_crew = Crew(
        agents=[pattern_agent],
        tasks=[pattern_task],
        process=Process.sequential,
        verbose=settings.crew_verbose,
    )
    await pattern_crew.kickoff_async(inputs={"transcript": transcript})

    pattern: PatternResult = _parse_task_output(pattern_task, PatternResult)  # type: ignore[assignment]
    feedback = build_accepted_feedback(complete)
    logger.info(
        "Crew pipeline accepted complaint: is_pattern=%s cluster_id=%s similar_count=%d confidence=%.3f",
        pattern.is_pattern,
        pattern.cluster_id,
        pattern.similar_complaint_count,
        pattern.confidence_score,
    )

    return CrewPipelineResult(
        status=ComplaintStatus.ACCEPTED,
        extraction=extraction,
        missing_fields=[],
        pattern=pattern,
        feedback=feedback,
        complaint_id=str(uuid4()),
    )

import hashlib
import logging

from wagelens.config import settings
from wagelens.models.schemas import CompleteComplaintExtraction, PatternResult

logger = logging.getLogger(__name__)

CLUSTER_JOIN_THRESHOLD = 0.45
MATCH_DIMENSION_THRESHOLD = 0.5


def _slug(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _collapse(value: str) -> str:
    return " ".join(value.lower().split())


def _payload_text(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _signature_text(extraction: CompleteComplaintExtraction) -> str:
    route = f"{extraction.pickup_location} -> {extraction.drop_location}"
    discrepancy = extraction.quoted_amount - extraction.paid_amount
    return (
        f"{route} | {extraction.trip_time} | platform={extraction.platform} | "
        f"discrepancy={discrepancy}"
    )


def _cluster_id(signature: str) -> str:
    return hashlib.sha256(signature.encode()).hexdigest()[:12]


def route_cluster_key(extraction: CompleteComplaintExtraction) -> str:
    pickup = _collapse(extraction.pickup_location)
    drop = _collapse(extraction.drop_location)
    platform = _slug(extraction.platform)
    return f"{platform}|{pickup}|{drop}"


def cluster_id_for_extraction(extraction: CompleteComplaintExtraction) -> str:
    return _cluster_id(route_cluster_key(extraction))


def _platform_score(left: str, right: str | None) -> float:
    if right is None:
        return 0.0
    left_slug = _slug(left)
    right_slug = _slug(right)
    if left_slug == right_slug:
        return 1.0
    if left_slug in right_slug or right_slug in left_slug:
        return 0.75
    return 0.0


def _hour_token(value: str) -> str | None:
    token = value.split(":")[0].strip()
    digits = "".join(ch for ch in token if ch.isdigit())
    return digits or None


def _time_score(left: str, right: str | None) -> float:
    if right is None:
        return 0.0
    left_norm = _collapse(left)
    right_norm = _collapse(right)
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.8

    left_hour = _hour_token(left_norm)
    right_hour = _hour_token(right_norm)
    if left_hour and right_hour and left_hour == right_hour:
        left_meridiem = "pm" if "pm" in left_norm else "am" if "am" in left_norm else None
        right_meridiem = "pm" if "pm" in right_norm else "am" if "am" in right_norm else None
        if left_meridiem == right_meridiem:
            return 0.55
    return 0.0


def _sector_number(value: str) -> str | None:
    lowered = _collapse(value)
    if "sector" not in lowered:
        return None
    after = lowered.split("sector", 1)[1].strip(" -")
    digits: list[str] = []
    for ch in after:
        if ch.isdigit() or (ch.isalpha() and digits):
            digits.append(ch)
        elif digits:
            break
    joined = "".join(digits)
    return joined or None


def _location_token_score(left: str, right: str | None) -> float:
    if right is None:
        return 0.0
    left_norm = _collapse(left)
    right_norm = _collapse(right)
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.85

    left_sector = _sector_number(left_norm)
    right_sector = _sector_number(right_norm)
    if left_sector and right_sector and left_sector == right_sector:
        return 0.75
    return 0.0


def _route_score(
    extraction: CompleteComplaintExtraction,
    payload: dict,
    vector_score: float = 0.0,
) -> float:
    pickup_score = _location_token_score(
        extraction.pickup_location, _payload_text(payload, "pickup_location")
    )
    drop_score = _location_token_score(
        extraction.drop_location, _payload_text(payload, "drop_location")
    )

    route_string_score = 0.0
    if pickup_score and drop_score:
        route_string_score = (pickup_score + drop_score) / 2
    elif pickup_score or drop_score:
        route_string_score = max(pickup_score, drop_score) * 0.8

    payload_route = _payload_text(payload, "route")
    if route_string_score == 0.0 and payload_route:
        left_route = f"{extraction.pickup_location} -> {extraction.drop_location}"
        route_string_score = _location_token_score(left_route, payload_route)

    vector_component = max(0.0, min(1.0, vector_score))
    return max(route_string_score, vector_component * 0.9)


def score_pair(
    extraction: CompleteComplaintExtraction,
    payload: dict,
    vector_score: float = 0.0,
) -> tuple[float, float, float, float]:
    route_score = _route_score(extraction, payload, vector_score)
    platform_score = _platform_score(extraction.platform, _payload_text(payload, "platform"))
    time_score = _time_score(extraction.trip_time, _payload_text(payload, "time_window"))

    weighted = (
        route_score * settings.qdrant_location_weight
        + platform_score * settings.qdrant_platform_weight
        + time_score * settings.qdrant_time_weight
    )
    best = max(route_score, platform_score, time_score)

    confidence = weighted
    if best >= MATCH_DIMENSION_THRESHOLD:
        confidence = max(weighted, best * 0.88)
    if best >= 0.75:
        confidence = max(confidence, best * 0.92)

    return (
        round(min(confidence, 1.0), 3),
        round(route_score, 3),
        round(platform_score, 3),
        round(time_score, 3),
    )


def _qualifies_as_match(route: float, platform: float, time: float) -> bool:
    return (
        route >= MATCH_DIMENSION_THRESHOLD
        or platform >= MATCH_DIMENSION_THRESHOLD
        or time >= MATCH_DIMENSION_THRESHOLD
    )


def _route_label(extraction: CompleteComplaintExtraction) -> str:
    return f"{extraction.pickup_location} -> {extraction.drop_location}"


def detect_pattern(
    extraction: CompleteComplaintExtraction, qdrant_hits: list[dict]
) -> PatternResult:
    fallback_cluster = cluster_id_for_extraction(extraction)
    route_label = _route_label(extraction)
    logger.debug(
        "Detecting pattern: hits=%d signature=%r",
        len(qdrant_hits),
        _signature_text(extraction),
    )

    scored_hits: list[tuple[float, float, float, float, dict]] = []
    for hit in qdrant_hits:
        payload = hit.get("payload") or {}
        confidence, route_score, platform_score, time_score = score_pair(
            extraction, payload, float(hit.get("score", 0))
        )
        if not _qualifies_as_match(route_score, platform_score, time_score):
            continue
        scored_hits.append(
            (confidence, route_score, platform_score, time_score, payload)
        )

    if not scored_hits:
        logger.debug(
            "No qualifying hits — returning non-pattern cluster=%s", fallback_cluster
        )
        return PatternResult(
            is_pattern=False,
            cluster_id=fallback_cluster,
            similar_complaint_count=1,
            common_route=route_label,
            common_time_window=extraction.trip_time,
            confidence_score=0.0,
        )

    scored_hits.sort(key=lambda item: item[0], reverse=True)
    confidence, route_score, platform_score, time_score, payload = scored_hits[0]

    matched_cluster = _payload_text(payload, "cluster_id")
    cluster_id = (
        matched_cluster
        if matched_cluster and confidence >= CLUSTER_JOIN_THRESHOLD
        else fallback_cluster
    )

    matched_clusters = {
        _payload_text(hit[4], "cluster_id") or fallback_cluster
        for hit in scored_hits
        if hit[0] >= CLUSTER_JOIN_THRESHOLD
    }
    similar_count = max(
        sum(
            int(hit[4].get("cluster_size", 0))
            for hit in scored_hits
            if hit[0] >= CLUSTER_JOIN_THRESHOLD
        ),
        len(matched_clusters) + 1,
        int(payload.get("cluster_size", 0)) + 1,
    )

    is_pattern = (
        confidence >= settings.qdrant_pattern_threshold
        and similar_count >= settings.qdrant_min_cluster_size
    )

    logger.debug(
        "Pattern scored: cluster=%s confidence=%.3f route=%.3f plat=%.3f time=%.3f is_pattern=%s similar=%d",
        cluster_id,
        confidence,
        route_score,
        platform_score,
        time_score,
        is_pattern,
        similar_count,
    )

    return PatternResult(
        is_pattern=is_pattern,
        cluster_id=cluster_id,
        similar_complaint_count=similar_count,
        common_route=_payload_text(payload, "route") or route_label,
        common_time_window=_payload_text(payload, "time_window") or extraction.trip_time,
        confidence_score=confidence,
        location_score=route_score,
        platform_score=platform_score,
        time_score=time_score,
    )


def match_extractions(
    left: CompleteComplaintExtraction, right: CompleteComplaintExtraction
) -> tuple[float, float, float, float]:
    payload = {
        "platform": right.platform,
        "time_window": right.trip_time,
        "pickup_location": right.pickup_location,
        "drop_location": right.drop_location,
        "route": _route_label(right),
    }
    return score_pair(left, payload, vector_score=0.0)

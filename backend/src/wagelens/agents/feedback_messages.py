"""Fixed Hindi Devanagari spoken feedback templates for Rime TTS."""

from __future__ import annotations

from wagelens.models.schemas import CompleteComplaintExtraction

_MISSING_LABELS: dict[str, str] = {
    "quoted_amount": "बताई गई राशि",
    "paid_amount": "मिली हुई राशि",
    "platform": "प्लेटफ़ॉर्म",
    "trip_time": "यात्रा का समय",
    "pickup_location": "पिकअप स्थान",
    "drop_location": "ड्रॉप स्थान",
}


def _format_rupees(amount: float) -> str:
    if amount == int(amount):
        value = str(int(amount))
    else:
        value = f"{amount:.2f}".rstrip("0").rstrip(".")
    return f"₹{value}"


def _join_missing_labels(fields: list[str]) -> str:
    labels = [_MISSING_LABELS.get(field, field.replace("_", " ")) for field in fields]
    if not labels:
        return "ज़रूरी जानकारी"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} और {labels[1]}"
    return ", ".join(labels[:-1]) + f" और {labels[-1]}"


def _spoken_hour(trip_time: str) -> str:
    token = trip_time.split(":")[0].strip()
    digits = "".join(ch for ch in token if ch.isdigit())
    return digits if digits else trip_time


def build_accepted_feedback(extraction: CompleteComplaintExtraction) -> str:
    hour = _spoken_hour(extraction.trip_time)
    quoted = _format_rupees(extraction.quoted_amount)
    paid = _format_rupees(extraction.paid_amount)

    return (
        f"आपकी शिकायत दर्ज की जा चुकी है। आप {hour} बजे {extraction.pickup_location} से "
        f"{extraction.platform} का ऑर्डर लेकर {extraction.drop_location} पर पहुँचे, "
        f"जिसके आपको {quoted} की जगह {paid} मिले।"
    )


def build_discard_feedback(missing_fields: list[str]) -> str:
    need = _join_missing_labels(missing_fields)
    return (
        f"आपकी शिकायत दर्ज नहीं की जा सकती। आपने {need} की जानकारी नहीं दी है। "
        "कृपया दोबारा से सभी जानकारी के साथ प्रयास करें।"
    )

import base64
import logging

from wagelens.logging_config import truncate
from wagelens.services.rime_tts import synthesize_speech

logger = logging.getLogger(__name__)


async def feedback_with_audio(feedback_text: str) -> tuple[str, str | None, str | None]:
    """Synthesize TTS and return inline base64 audio for the client."""
    tts_text = feedback_text.strip()
    logger.info(
        "Generating TTS feedback: text_len=%d preview=%r",
        len(tts_text),
        truncate(tts_text, 80),
    )
    audio_bytes, mime = await synthesize_speech(tts_text)

    if not audio_bytes:
        logger.warning("No TTS audio produced")
        return tts_text, None, None

    encoded = base64.b64encode(audio_bytes).decode("ascii")
    logger.info(
        "Feedback audio ready for client: size=%d bytes mime=%s",
        len(audio_bytes),
        mime,
    )
    return tts_text, encoded, mime

import base64
import json
import logging
from typing import Any

import httpx
import websockets

from wagelens.config import settings

logger = logging.getLogger(__name__)

_RIME_LANG = "hi"


async def synthesize_speech(text: str) -> tuple[bytes | None, str]:
    if not settings.rime_api_key:
        logger.warning("Rime TTS skipped: API key not configured")
        return None, "audio/mpeg"

    speaker = settings.rime_speaker
    logger.info(
        "Rime TTS starting: speaker=%s text_len=%d",
        speaker,
        len(text),
    )

    try:
        audio, mime = await _synthesize_ws(text, speaker=speaker)
        logger.info("Rime TTS succeeded via WebSocket: bytes=%d", len(audio or b""))
        return audio, mime
    except Exception as exc:
        logger.warning("Rime WebSocket TTS failed, falling back to HTTP: %s", exc)
        try:
            audio, mime = await _synthesize_http(text, speaker=speaker)
            logger.info("Rime TTS succeeded via HTTP: bytes=%d", len(audio or b""))
            return audio, mime
        except Exception as http_exc:
            logger.error("Rime TTS failed on both WebSocket and HTTP: %s", http_exc)
            return None, "audio/mpeg"


async def _synthesize_ws(text: str, *, speaker: str) -> tuple[bytes | None, str]:
    url = (
        f"wss://users-ws.rime.ai/ws3"
        f"?speaker={speaker}&modelId={settings.rime_model}"
        f"&audioFormat=mp3&segment=bySentence&lang={_RIME_LANG}"
    )
    headers = {"Authorization": f"Bearer {settings.rime_api_key}"}
    audio = b""

    logger.debug("Connecting to Rime WebSocket: speaker=%s", speaker)
    async with websockets.connect(url, additional_headers=headers) as ws:
        await ws.send(json.dumps({"text": text, "lang": _RIME_LANG}))
        await ws.send(json.dumps({"operation": "eos"}))
        async for raw in ws:
            event = json.loads(raw)
            if event.get("type") == "chunk":
                audio += base64.b64decode(event["data"])
            elif event.get("type") == "error":
                raise RuntimeError(event.get("message", "Rime synthesis failed"))

    if not audio:
        raise RuntimeError("Rime WebSocket returned empty audio")
    return audio, "audio/mpeg"


async def _synthesize_http(text: str, *, speaker: str) -> tuple[bytes | None, str]:
    if not settings.rime_api_key:
        return None, "audio/mpeg"

    payload: dict[str, Any] = {
        "speaker": speaker,
        "text": text,
        "modelId": settings.rime_model,
        "lang": _RIME_LANG,
    }
    logger.debug("Calling Rime HTTP TTS: speaker=%s", speaker)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://users.rime.ai/v1/rime-tts",
            headers={
                "Authorization": f"Bearer {settings.rime_api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json=payload,
        )
        if response.is_error:
            body_preview = response.text[:500] if response.text else "(empty body)"
            logger.error(
                "Rime HTTP TTS error: status=%s body=%s",
                response.status_code,
                body_preview,
            )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "audio/mpeg")
        return response.content, content_type

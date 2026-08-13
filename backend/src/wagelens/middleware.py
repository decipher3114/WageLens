"""HTTP middleware for request tracing and access logging."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log inbound requests with timing and a correlation id."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        client = request.client.host if request.client else "unknown"

        logger.info(
            "Request started: %s %s client=%s [request_id=%s]",
            request.method,
            request.url.path,
            client,
            request_id,
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "Request failed: %s %s duration=%.1fms [request_id=%s]",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Request completed: %s %s status=%s duration=%.1fms [request_id=%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response

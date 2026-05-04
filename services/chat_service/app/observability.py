"""Debug logging helpers for Chat Service."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

SENSITIVE_KEYS = {"authorization", "cookie", "set-cookie", "password", "token", "api_key", "apiKey", "secret"}
MAX_LOG_CHARS = 4000

logger = logging.getLogger("chat_service")


def configure_logging() -> None:
    """Configure Chat Service logging at DEBUG by default."""

    level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    logger.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("pymongo").setLevel(logging.WARNING)


def redact(value: Any) -> Any:
    """Return a log-safe copy of nested data."""

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_KEYS or any(secret in key_text.lower() for secret in ["password", "token", "secret", "key"]):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = redact(item)
        return sanitized
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def compact(value: Any) -> str:
    """Serialize a value for one-line debug logs."""

    try:
        text = json.dumps(redact(value), default=str, ensure_ascii=False)
    except TypeError:
        text = str(redact(value))
    return text if len(text) <= MAX_LOG_CHARS else f"{text[:MAX_LOG_CHARS]}... [truncated]"


def decode_body(body: bytes) -> Any:
    """Decode a request or response body for logs."""

    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body.decode("utf-8", errors="replace")


class DebugRequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log incoming Chat Service requests and outgoing responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        request_body = await request.body()
        if settings.log_request_bodies:
            logger.debug(
                "request.start method=%s path=%s query=%s headers=%s body=%s",
                request.method,
                request.url.path,
                str(request.url.query),
                compact(dict(request.headers)),
                compact(decode_body(request_body)),
            )
        else:
            logger.debug("request.start method=%s path=%s query=%s", request.method, request.url.path, str(request.url.query))
        response = await call_next(request)
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        if settings.log_response_bodies:
            logger.debug(
                "request.end method=%s path=%s status=%s durationMs=%s body=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                compact(decode_body(response_body)),
            )
        else:
            logger.debug("request.end method=%s path=%s status=%s durationMs=%s", request.method, request.url.path, response.status_code, duration_ms)
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
            background=response.background,
        )

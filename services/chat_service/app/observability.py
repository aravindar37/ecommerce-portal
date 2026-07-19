"""Debug logging helpers for Chat Service."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings

SENSITIVE_KEYS = {"authorization", "cookie", "set-cookie", "password", "token", "api_key", "apiKey", "secret"}
MAX_LOG_CHARS = 4000

logger = logging.getLogger("chat_service")


@dataclass
class VoiceMetrics:
    """In-process aggregate voice metrics without caller, transcript, or secret data."""

    calls_received: int = 0
    calls_verified: int = 0
    calls_verification_failed: int = 0
    calls_escalated: int = 0
    calls_ended: int = 0
    recording_upload_succeeded: int = 0
    recording_upload_failed: int = 0
    total_duration_seconds: int = 0
    turn_count: int = 0
    total_stt_latency_ms: int = 0
    total_agent_latency_ms: int = 0
    total_tts_latency_ms: int = 0
    total_turn_latency_ms: int = 0
    stt_connections_opened: int = 0
    stt_connections_failed: int = 0
    stt_partial_transcripts: int = 0
    stt_committed_transcripts: int = 0

    def record_stt_connection_opened(self) -> None:
        """Record a successfully established outbound realtime STT connection."""

        self.stt_connections_opened += 1
        logger.info("voice.metric event=stt_connection_opened count=%s", self.stt_connections_opened)

    def record_stt_connection_failed(self) -> None:
        """Record an upstream connection or receive failure without details."""

        self.stt_connections_failed += 1
        logger.info("voice.metric event=stt_connection_failed count=%s", self.stt_connections_failed)

    def record_stt_partial_transcript(self) -> None:
        """Count ephemeral partial packets without retaining their content."""

        self.stt_partial_transcripts += 1

    def record_stt_committed_transcript(self) -> None:
        """Count provider-committed transcript segments."""

        self.stt_committed_transcripts += 1

    def record_call_started(self) -> None:
        """Record a new accepted voice session."""

        self.calls_received += 1
        logger.info("voice.metric event=call_started callsReceived=%s", self.calls_received)

    def record_call_verified(self) -> None:
        """Record a successful hard caller verification."""

        self.calls_verified += 1
        logger.info("voice.metric event=call_verified callsVerified=%s", self.calls_verified)

    def record_turn(self, stt_ms: int, agent_ms: int, tts_ms: int, total_ms: int) -> None:
        """Record aggregate per-turn timing with no transcript content."""

        self.turn_count += 1
        self.total_stt_latency_ms += stt_ms
        self.total_agent_latency_ms += agent_ms
        self.total_tts_latency_ms += tts_ms
        self.total_turn_latency_ms += total_ms
        logger.info("voice.metric event=turn sttMs=%s agentMs=%s ttsMs=%s totalMs=%s", stt_ms, agent_ms, tts_ms, total_ms)

    def record_call_ended(self, duration_seconds: int, verified: bool, escalated: bool, recording_uploaded: bool) -> None:
        """Record final call outcome and recording result."""

        self.calls_ended += 1
        self.total_duration_seconds += duration_seconds
        if not verified:
            self.calls_verification_failed += 1
        if escalated:
            self.calls_escalated += 1
        if recording_uploaded:
            self.recording_upload_succeeded += 1
        else:
            self.recording_upload_failed += 1
        logger.info(
            "voice.metric event=call_ended durationSeconds=%s verified=%s escalated=%s recordingUploaded=%s",
            duration_seconds,
            verified,
            escalated,
            recording_uploaded,
        )

    def snapshot(self) -> dict[str, object]:
        """Return safe aggregate counters and averages for the health endpoint."""

        def average(total: int, count: int) -> float:
            return round(total / count, 2) if count else 0.0

        return {
            "callsReceived": self.calls_received,
            "callsVerified": self.calls_verified,
            "callsVerificationFailed": self.calls_verification_failed,
            "callsEscalated": self.calls_escalated,
            "callsEnded": self.calls_ended,
            "recordingUploadSucceeded": self.recording_upload_succeeded,
            "recordingUploadFailed": self.recording_upload_failed,
            "averageCallDurationSeconds": average(self.total_duration_seconds, self.calls_ended),
            "realtimeStt": {
                "connectionsOpened": self.stt_connections_opened,
                "connectionsFailed": self.stt_connections_failed,
                "partialTranscripts": self.stt_partial_transcripts,
                "committedTranscripts": self.stt_committed_transcripts,
            },
            "turnCount": self.turn_count,
            "averageTurnLatencyMs": {
                "stt": average(self.total_stt_latency_ms, self.turn_count),
                "agent": average(self.total_agent_latency_ms, self.turn_count),
                "tts": average(self.total_tts_latency_ms, self.turn_count),
                "total": average(self.total_turn_latency_ms, self.turn_count),
            },
        }


voice_metrics = VoiceMetrics()


def configure_logging() -> None:
    """Configure Chat Service logging at DEBUG by default."""

    level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    logger.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    # websockets DEBUG logs include HTTP headers, raw PCM previews, and raw
    # transcription packets. Voice diagnostics must use our safe aggregate
    # metrics and structured relay logs instead.
    logging.getLogger("websockets").setLevel(logging.WARNING)


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

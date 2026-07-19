"""Clients for ElevenLabs realtime STT and standalone TTS APIs."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import certifi
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.agentic.resilience import with_retry
from app.config import ChatServiceSettings, settings
from app.http import ServiceHttpError
from app.observability import compact, logger, redact

Json = dict[str, Any]


def _credential_fingerprint(value: str) -> str:
    """Return a non-reversible identifier for correlating configured credentials."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _http_error_summary(exc: urllib.error.HTTPError) -> Json:
    """Keep actionable provider error fields while omitting arbitrary response bodies."""

    body = exc.read()
    if not body:
        return {"bodyBytes": 0}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"bodyBytes": len(body), "bodyKind": "non_json"}
    if not isinstance(payload, dict):
        return {"bodyBytes": len(body), "bodyKind": type(payload).__name__}
    allowed_fields = {key: payload[key] for key in ("code", "detail", "message", "status") if key in payload}
    return {"bodyBytes": len(body), "provider": redact(allowed_fields)}


@dataclass(frozen=True)
class RealtimeTranscriptEvent:
    """A validated non-empty transcript packet from the realtime STT service."""

    message_type: str
    text: str
    committed_audio_end_seconds: float | None = None


class RealtimeSttNonRetryableError(ConnectionError):
    """An upstream auth or request error that must end the realtime STT session."""


class ElevenLabsRealtimeSttSession:
    """One persistent, outbound realtime transcription connection for one call."""

    def __init__(self, config: ChatServiceSettings, connection: ClientConnection) -> None:
        self.config = config
        self.connection = connection
        self._closed = False

    @classmethod
    async def connect(cls, config: ChatServiceSettings) -> "ElevenLabsRealtimeSttSession":
        """Open the authenticated upstream connection with the approved query parameters."""

        api_key = config.elevenlabs_api_key.strip()
        if not api_key:
            raise ServiceHttpError(503, "ElevenLabs API key is not configured")
        params = {
            "model_id": config.elevenlabs_stt_model,
            "audio_format": "pcm_16000",
            "commit_strategy": config.elevenlabs_stt_commit_strategy,
            "vad_silence_threshold_secs": str(config.elevenlabs_stt_vad_silence_threshold_secs),
            "no_verbatim": str(config.elevenlabs_stt_no_verbatim).lower(),
            "include_timestamps": str(config.elevenlabs_stt_include_timestamps).lower(),
        }
        url = f"{config.elevenlabs_stt_realtime_ws_url}?{urllib.parse.urlencode(params)}"
        timeout_seconds = max(config.voice_turn_max_latency_ms / 1000, 1)
        tls_context = ssl.create_default_context(cafile=certifi.where())
        try:
            connection = await connect(
                url,
                additional_headers={"xi-api-key": api_key},
                open_timeout=timeout_seconds,
                close_timeout=timeout_seconds,
                ssl=tls_context,
            )
        except InvalidStatus as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in {400, 401, 403, 422}:
                raise RealtimeSttNonRetryableError("ElevenLabs realtime speech request was rejected") from exc
            logger.warning("voice.elevenlabs.realtime_connect_failed status=%s", status_code)
            raise ConnectionError("ElevenLabs realtime speech service is unavailable") from exc
        except Exception as exc:
            logger.warning("voice.elevenlabs.realtime_connect_failed error=%s", exc.__class__.__name__)
            raise ConnectionError("ElevenLabs realtime speech service is unavailable") from exc
        return cls(config, connection)

    async def send_pcm16(self, audio: bytes) -> None:
        """Base64-encode and stream one PCM16 frame without buffering a caller turn."""

        if self._closed:
            raise ConnectionError("ElevenLabs realtime speech session is closed")
        if not audio:
            return
        message = {
            "message_type": "input_audio_chunk",
            "audio_base_64": base64.b64encode(audio).decode("ascii"),
            "commit": False,
            "sample_rate": 16000,
        }
        try:
            await self.connection.send(json.dumps(message, separators=(",", ":")))
        except ConnectionClosed as exc:
            self._closed = True
            if exc.code == 1008 and "invalid_request" in str(exc.reason).lower():
                raise RealtimeSttNonRetryableError("ElevenLabs rejected the realtime audio request") from exc
            raise ConnectionError("ElevenLabs realtime speech session closed") from exc

    async def receive(self) -> RealtimeTranscriptEvent | None:
        """Receive one partial or committed transcript event; ignore unknown packets."""

        if self._closed:
            return None
        try:
            raw_message = await self.connection.recv()
        except ConnectionClosed as exc:
            self._closed = True
            if exc.code == 1008 and "invalid_request" in str(exc.reason).lower():
                raise RealtimeSttNonRetryableError("ElevenLabs rejected the realtime audio request") from exc
            raise ConnectionError("ElevenLabs realtime speech session closed") from exc
        if isinstance(raw_message, bytes):
            logger.warning("voice.elevenlabs.realtime_invalid_packet kind=binary")
            return None
        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError:
            logger.warning("voice.elevenlabs.realtime_invalid_packet kind=json")
            return None
        if not isinstance(message, dict):
            return None
        message_type = message.get("message_type")
        if message_type in {"auth_error", "input_error", "unaccepted_terms"}:
            self._closed = True
            raise RealtimeSttNonRetryableError("ElevenLabs realtime speech request was rejected")
        text = message.get("text")
        accepted_types = {"partial_transcript", "committed_transcript", "committed_transcript_with_timestamps"}
        if message_type not in accepted_types or not isinstance(text, str) or not text.strip():
            return None
        if message_type == "committed_transcript" and self.config.elevenlabs_stt_include_timestamps:
            # With include_timestamps=true ElevenLabs emits this legacy event
            # immediately before committed_transcript_with_timestamps for the
            # same speech segment. Dispatch only the timestamped form so one
            # caller turn produces exactly one agent/TTS response.
            logger.debug("voice.elevenlabs.realtime_duplicate_commit_suppressed")
            return None
        committed_end = self._committed_audio_end_seconds(message) if message_type == "committed_transcript_with_timestamps" else None
        normalized_type = "committed_transcript" if message_type == "committed_transcript_with_timestamps" else message_type
        return RealtimeTranscriptEvent(message_type=normalized_type, text=text.strip(), committed_audio_end_seconds=committed_end)

    @staticmethod
    def _committed_audio_end_seconds(message: Json) -> float | None:
        """Map documented word-end timestamps to a session-relative PCM boundary."""

        words = message.get("words")
        if not isinstance(words, list):
            return None
        end_times = [word.get("end") for word in words if isinstance(word, dict) and isinstance(word.get("end"), (int, float))]
        return max(float(end) for end in end_times) if end_times else None

    async def close(self) -> None:
        """Close the upstream session exactly once during call finalization."""

        if self._closed:
            return
        self._closed = True
        await self.connection.close()


class ElevenLabsSpeechClient:
    """Call ElevenLabs STT and TTS without exposing credentials to callers."""

    def __init__(self, config: ChatServiceSettings = settings) -> None:
        self.config = config

    def readiness(self) -> Json:
        """Return non-sensitive dependency status for health checks."""

        api_key = self.config.elevenlabs_api_key.strip()
        return {
            "sttConfigured": bool(api_key and self.config.elevenlabs_stt_realtime_ws_url.strip()),
            "ttsConfigured": bool(api_key and self.config.elevenlabs_voice_id.strip() and self.config.elevenlabs_tts_api_url.strip()),
            "sttModel": self.config.elevenlabs_stt_model,
            "sttTransport": "websocket",
            "sttCommitStrategy": self.config.elevenlabs_stt_commit_strategy,
            "sttVadSilenceThresholdSecs": self.config.elevenlabs_stt_vad_silence_threshold_secs,
            "sttNoVerbatim": self.config.elevenlabs_stt_no_verbatim,
            "sttIncludeTimestamps": self.config.elevenlabs_stt_include_timestamps,
            "ttsModel": self.config.elevenlabs_tts_model,
            "ttsOutputFormat": self.config.elevenlabs_tts_output_format,
        }

    def _headers(self) -> dict[str, str]:
        api_key = self.config.elevenlabs_api_key.strip()
        if not api_key:
            raise ServiceHttpError(503, "ElevenLabs API key is not configured")
        return {"xi-api-key": api_key, "accept": "application/json"}

    async def open_realtime_stt_session(self) -> ElevenLabsRealtimeSttSession:
        """Create the one long-lived upstream STT session required for a voice call."""

        return await ElevenLabsRealtimeSttSession.connect(self.config)

    def synthesize_pcm16(self, text: str) -> bytes:
        """Synthesize short agent text as raw PCM16 in the configured format."""

        if not text.strip():
            raise ServiceHttpError(400, "Text is required for speech synthesis")
        return with_retry("elevenlabs_tts", lambda: self._synthesize_once(text), idempotent=True)

    def _synthesize_once(self, text: str) -> bytes:
        voice_id = self.config.elevenlabs_voice_id.strip()
        if not voice_id:
            raise ServiceHttpError(503, "ElevenLabs voice ID is not configured")
        endpoint = self.config.elevenlabs_tts_api_url.strip().rstrip("/")
        output_format = self.config.elevenlabs_tts_output_format.strip()
        base_url = f"{endpoint}/{urllib.parse.quote(voice_id)}/stream"
        url = f"{base_url}?{urllib.parse.urlencode({'output_format': output_format})}"
        payload = json.dumps({"text": text, "model_id": self.config.elevenlabs_tts_model.strip()}).encode("utf-8")
        logger.info(
            "voice.elevenlabs.tts_request model=%s outputFormat=%s voiceIdLength=%s textLength=%s apiKeyLength=%s apiKeyFingerprint=%s",
            self.config.elevenlabs_tts_model.strip(),
            output_format,
            len(voice_id),
            len(text),
            len(self.config.elevenlabs_api_key.strip()),
            _credential_fingerprint(self.config.elevenlabs_api_key.strip()),
        )
        audio = self._request(url, payload, {**self._headers(), "content-type": "application/json", "accept": "audio/pcm"})
        if not audio:
            raise ServiceHttpError(502, "ElevenLabs TTS returned no audio")
        logger.info("voice.elevenlabs.tts_response pcmBytes=%s", len(audio))
        return audio

    def _request(self, url: str, data: bytes, headers: dict[str, str]) -> bytes:
        request = urllib.request.Request(url, data=data, method="POST", headers=headers)
        tls_context = ssl.create_default_context(cafile=certifi.where())
        timeout_seconds = max(self.config.voice_turn_max_latency_ms / 1000, 1)
        api_key = str(headers.get("xi-api-key", ""))
        logger.info(
            "voice.elevenlabs.tts_http_request method=%s url=%s timeoutSeconds=%s headers=%s body=%s",
            request.method,
            request.full_url,
            timeout_seconds,
            {
                "accept": headers.get("accept"),
                "content-type": headers.get("content-type"),
                "xi-api-key": "[redacted]",
                "xiApiKeyLength": len(api_key),
                "xiApiKeyFingerprint": _credential_fingerprint(api_key),
            },
            {"byteLength": len(data), "jsonKeys": ["text", "model_id"]},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
                context=tls_context,
            ) as response:
                audio = response.read()
                logger.info(
                    "voice.elevenlabs.tts_http_response status=%s contentType=%s contentLength=%s requestId=%s pcmBytes=%s",
                    response.status,
                    response.headers.get("content-type"),
                    response.headers.get("content-length"),
                    response.headers.get("x-request-id") or response.headers.get("request-id"),
                    len(audio),
                )
                return audio
        except urllib.error.HTTPError as exc:
            logger.warning(
                "voice.elevenlabs.tts_http_error status=%s error=%s contentType=%s contentLength=%s requestId=%s response=%s",
                exc.code,
                redact(exc.reason),
                exc.headers.get("content-type"),
                exc.headers.get("content-length"),
                exc.headers.get("x-request-id") or exc.headers.get("request-id"),
                compact(_http_error_summary(exc)),
            )
            raise ServiceHttpError(exc.code, "ElevenLabs speech request failed") from exc
        except urllib.error.URLError as exc:
            logger.warning("voice.elevenlabs.tts_unavailable error=%s", redact(str(exc)))
            raise ConnectionError("ElevenLabs speech service is unavailable") from exc


elevenlabs_speech = ElevenLabsSpeechClient()

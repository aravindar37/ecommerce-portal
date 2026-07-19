"""Private, idempotent call-recording uploads for the voice channel."""

from __future__ import annotations

import io
import time
import wave
from typing import Any

from app.config import ChatServiceSettings, settings
from app.observability import logger

Json = dict[str, Any]


class CallRecordingStore:
    """Encode interleaved mono PCM call audio to WAV and upload it privately."""

    def __init__(self, config: ChatServiceSettings = settings) -> None:
        self.config = config

    def readiness(self) -> Json:
        """Return non-sensitive object-storage configuration state."""

        return {
            "configured": bool(self.config.aws_region.strip() and self.config.aws_s3_call_recordings_bucket.strip()),
            "bucket": self.config.aws_s3_call_recordings_bucket or None,
            "retentionDays": self.config.call_recording_retention_days,
        }

    def wav_bytes(self, pcm16: bytes, sample_rate: int = 16000) -> bytes:
        """Wrap mono little-endian PCM16 frames in a WAV container."""

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm16)
        return buffer.getvalue()

    def upload(self, call_id: str, pcm16: bytes, sample_rate: int = 16000) -> Json | None:
        """Upload a deterministic call object key; failures do not raise into call finalization."""

        if not self.readiness()["configured"]:
            logger.warning("voice.recording.skip callId=%s reason=storage_not_configured", call_id)
            return None
        try:
            import boto3
        except ImportError:
            logger.warning("voice.recording.skip callId=%s reason=boto3_not_installed", call_id)
            return None
        key = f"voice-call-recordings/{call_id}.wav"
        try:
            client: Any = boto3.client("s3", region_name=self.config.aws_region)
            payload = self.wav_bytes(pcm16, sample_rate)
            attempts = max(1, self.config.agent_retry_max_attempts)
            for attempt in range(1, attempts + 1):
                try:
                    client.put_object(
                        Bucket=self.config.aws_s3_call_recordings_bucket,
                        Key=key,
                        Body=payload,
                        ContentType="audio/wav",
                        Metadata={"call-id": call_id, "retention-days": str(self.config.call_recording_retention_days)},
                    )
                    break
                except Exception as exc:
                    if not self._is_transient_upload_error(exc) or attempt == attempts:
                        raise
                    logger.warning("voice.recording.retry callId=%s attempt=%s error=%s", call_id, attempt, exc.__class__.__name__)
                    delay_ms = min(self.config.agent_retry_base_delay_ms * (2 ** (attempt - 1)), self.config.agent_retry_max_delay_ms)
                    if delay_ms:
                        time.sleep(delay_ms / 1000)
            else:  # pragma: no cover - loop exits by success or raise
                return None
            return {"bucket": self.config.aws_s3_call_recordings_bucket, "key": key}
        except Exception as exc:
            logger.warning(
                "voice.recording.upload_failed callId=%s error=%s code=%s status=%s",
                call_id,
                exc.__class__.__name__,
                self._upload_error_code(exc),
                self._upload_error_status(exc),
            )
            return None

    @staticmethod
    def _upload_error_code(exc: Exception) -> str | None:
        """Extract the safe provider error code from an S3 client failure."""

        response = getattr(exc, "response", None)
        error = response.get("Error") if isinstance(response, dict) else None
        code = error.get("Code") if isinstance(error, dict) else None
        return str(code) if code else None

    @staticmethod
    def _upload_error_status(exc: Exception) -> int | None:
        """Extract the safe HTTP status from an S3 client failure."""

        response = getattr(exc, "response", None)
        metadata = response.get("ResponseMetadata") if isinstance(response, dict) else None
        status = metadata.get("HTTPStatusCode") if isinstance(metadata, dict) else None
        return int(status) if isinstance(status, int) else None

    @staticmethod
    def _is_transient_upload_error(exc: Exception) -> bool:
        """Retry only network/timeouts and S3's documented transient server responses."""

        if isinstance(exc, (TimeoutError, ConnectionError)):
            return True
        try:
            from botocore.exceptions import ClientError
        except ImportError:
            return False
        if not isinstance(exc, ClientError):
            return False
        response = exc.response or {}
        error = response.get("Error") or {}
        metadata = response.get("ResponseMetadata") or {}
        code = str(error.get("Code") or "")
        status = int(metadata.get("HTTPStatusCode") or 0)
        return status in {408, 429, 500, 502, 503, 504} or code in {"RequestTimeout", "SlowDown", "InternalError", "ServiceUnavailable"}


call_recordings = CallRecordingStore()

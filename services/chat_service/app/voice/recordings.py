"""Private, idempotent call-recording uploads for the voice channel."""

from __future__ import annotations

import io
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
            client.put_object(
                Bucket=self.config.aws_s3_call_recordings_bucket,
                Key=key,
                Body=self.wav_bytes(pcm16, sample_rate),
                ContentType="audio/wav",
                Metadata={"call-id": call_id, "retention-days": str(self.config.call_recording_retention_days)},
            )
            return {"bucket": self.config.aws_s3_call_recordings_bucket, "key": key}
        except Exception as exc:
            logger.warning("voice.recording.upload_failed callId=%s error=%s", call_id, exc.__class__.__name__)
            return None


call_recordings = CallRecordingStore()

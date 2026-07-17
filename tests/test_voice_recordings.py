"""Unit tests for private WAV call-recording storage."""

from __future__ import annotations

import io
import sys
import types
import wave
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.config import ChatServiceSettings  # noqa: E402
from app.voice.recordings import CallRecordingStore  # noqa: E402


def recording_store() -> CallRecordingStore:
    """Return an independently configured recording store for testing."""

    return CallRecordingStore(ChatServiceSettings(aws_region="us-east-1", aws_s3_call_recordings_bucket="private-recordings"))


def test_wav_encoding_preserves_pcm16_format() -> None:
    """Recorded audio is written as mono, 16-bit PCM WAV at the selected rate."""

    wav_bytes = recording_store().wav_bytes(b"\x01\x00" * 160, sample_rate=16000)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.getnframes() == 160


def test_upload_uses_private_deterministic_key_without_acl() -> None:
    """Uploads expose only the bucket/key and rely on the bucket's default encryption policy."""

    client = Mock()
    fake_boto3 = types.SimpleNamespace(client=Mock(return_value=client))
    with patch.dict(sys.modules, {"boto3": fake_boto3}):
        result = recording_store().upload("call-1", b"\x00\x00" * 16)

    assert result == {"bucket": "private-recordings", "key": "voice-call-recordings/call-1.wav"}
    kwargs = client.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "private-recordings"
    assert kwargs["Key"] == "voice-call-recordings/call-1.wav"
    assert kwargs["ContentType"] == "audio/wav"
    assert "ACL" not in kwargs


def test_upload_failure_does_not_escape_call_finalization() -> None:
    """Recording upload errors return no location so callers can persist the call anyway."""

    client = Mock()
    client.put_object.side_effect = RuntimeError("s3 unavailable")
    fake_boto3 = types.SimpleNamespace(client=Mock(return_value=client))
    with patch.dict(sys.modules, {"boto3": fake_boto3}):
        assert recording_store().upload("call-1", b"\x00\x00") is None

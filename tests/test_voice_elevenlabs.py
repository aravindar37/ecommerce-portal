"""Unit tests for the standalone ElevenLabs STT/TTS client."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.config import ChatServiceSettings  # noqa: E402
from app.voice.elevenlabs import ElevenLabsSpeechClient  # noqa: E402


def speech_client() -> ElevenLabsSpeechClient:
    """Build an isolated client with non-secret test configuration."""

    return ElevenLabsSpeechClient(
        ChatServiceSettings(
            elevenlabs_api_key="test-key",
            elevenlabs_voice_id="test-voice",
            elevenlabs_stt_model="scribe_v2",
            elevenlabs_stt_api_url="https://example.test/v1/speech-to-text",
            elevenlabs_tts_model="eleven_flash_v2_5",
            elevenlabs_tts_api_url="https://example.test/v1/text-to-speech",
            elevenlabs_tts_output_format="pcm_16000",
        )
    )


def test_transcribe_pcm16_parses_mocked_elevenlabs_response() -> None:
    """STT submits PCM audio and returns the mocked transcript text."""

    client = speech_client()
    with patch.object(client, "_request", return_value=b'{"text":"Where is my order?"}') as request:
        assert client.transcribe_pcm16(b"\x00\x00" * 1600) == "Where is my order?"

    url, payload, headers = request.call_args.args
    assert url == "https://example.test/v1/speech-to-text"
    assert b'name="model_id"' in payload
    assert b"scribe_v2" in payload
    assert headers["xi-api-key"] == "test-key"
    assert headers["content-type"].startswith("multipart/form-data; boundary=")


def test_synthesize_pcm16_returns_mocked_audio_with_configured_format() -> None:
    """TTS requests PCM16 output and returns the mocked raw audio bytes."""

    client = speech_client()
    expected_audio = b"\x01\x00\x02\x00"
    with patch.object(client, "_request", return_value=expected_audio) as request:
        assert client.synthesize_pcm16("Your order is on the way.") == expected_audio

    url, payload, headers = request.call_args.args
    assert url == "https://example.test/v1/text-to-speech/test-voice?output_format=pcm_16000"
    assert b'"model_id": "eleven_flash_v2_5"' in payload
    assert headers["accept"] == "audio/pcm"
    assert headers["xi-api-key"] == "test-key"

"""Unit tests for the ElevenLabs realtime STT and standalone TTS clients."""

from __future__ import annotations

import ssl
import sys
import asyncio
import base64
import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.config import ChatServiceSettings  # noqa: E402
from app.voice.elevenlabs import ElevenLabsRealtimeSttSession, ElevenLabsSpeechClient, _credential_fingerprint, _http_error_summary  # noqa: E402


def speech_client() -> ElevenLabsSpeechClient:
    """Build an isolated client with non-secret test configuration."""

    return ElevenLabsSpeechClient(
        ChatServiceSettings(
            elevenlabs_api_key="test-key",
            elevenlabs_voice_id="test-voice",
            elevenlabs_stt_model="scribe_v2_realtime",
            elevenlabs_stt_realtime_ws_url="wss://example.test/v1/speech-to-text/realtime",
            elevenlabs_stt_commit_strategy="vad",
            elevenlabs_stt_vad_silence_threshold_secs=1.5,
            elevenlabs_stt_no_verbatim=True,
            elevenlabs_stt_include_timestamps=True,
            elevenlabs_tts_model="eleven_flash_v2_5",
            elevenlabs_tts_api_url="https://example.test/v1/text-to-speech",
            elevenlabs_tts_output_format="pcm_16000",
        )
    )


class FakeRealtimeConnection:
    """Small async connection double for wire-contract unit tests."""

    def __init__(self, received: list[str]) -> None:
        self.received = iter(received)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        return next(self.received)

    async def close(self) -> None:
        self.closed = True


def test_realtime_stt_uses_required_handshake_query_and_api_key_header() -> None:
    """A per-call STT session uses the approved endpoint, settings, and header."""

    client = speech_client()
    connection = FakeRealtimeConnection([])

    async def connect_stub(*args: object, **kwargs: object) -> FakeRealtimeConnection:
        connect_stub.args = args
        connect_stub.kwargs = kwargs
        return connection

    with (
        patch("app.voice.elevenlabs.certifi.where", return_value="/tmp/certifi-ca.pem") as where,
        patch("app.voice.elevenlabs.ssl.create_default_context", return_value=ssl.create_default_context()) as create_context,
        patch("app.voice.elevenlabs.connect", side_effect=connect_stub),
    ):
        session = asyncio.run(client.open_realtime_stt_session())

    assert isinstance(session, ElevenLabsRealtimeSttSession)
    url = str(connect_stub.args[0])
    assert url.startswith("wss://example.test/v1/speech-to-text/realtime?")
    assert "model_id=scribe_v2_realtime" in url
    assert "audio_format=pcm_16000" in url
    assert "commit_strategy=vad" in url
    assert "vad_silence_threshold_secs=1.5" in url
    assert "no_verbatim=true" in url
    assert "include_timestamps=true" in url
    assert connect_stub.kwargs["additional_headers"] == {"xi-api-key": "test-key"}
    where.assert_called_once_with()
    create_context.assert_called_once_with(cafile="/tmp/certifi-ca.pem")
    assert connect_stub.kwargs["ssl"] is create_context.return_value


def test_realtime_stt_sends_base64_pcm_and_distinguishes_partial_from_committed() -> None:
    """Partial text remains ephemeral while committed text is identifiable by type."""

    connection = FakeRealtimeConnection(
        [
            '{"message_type":"partial_transcript","text":"where is"}',
            '{"message_type":"committed_transcript","text":"Where is my order?"}',
        ]
    )
    config = speech_client().config.model_copy(update={"elevenlabs_stt_include_timestamps": False})
    session = ElevenLabsRealtimeSttSession(config, connection)  # type: ignore[arg-type]

    async def scenario() -> tuple[object, object]:
        await session.send_pcm16(b"\x01\x00\x02\x00")
        return await session.receive(), await session.receive()

    partial, committed = asyncio.run(scenario())
    message = json.loads(connection.sent[0])
    assert message == {
        "message_type": "input_audio_chunk",
        "audio_base_64": base64.b64encode(b"\x01\x00\x02\x00").decode("ascii"),
        "commit": False,
        "sample_rate": 16000,
    }
    assert partial is not None and partial.message_type == "partial_transcript"
    assert committed is not None and committed.message_type == "committed_transcript"
    assert committed.text == "Where is my order?"


def test_timestamp_enabled_suppresses_legacy_duplicate_commit_event() -> None:
    """Only the timestamped committed event reaches the agent path for one provider segment."""

    connection = FakeRealtimeConnection(
        [
            '{"message_type":"committed_transcript","text":"Where is my order?"}',
            '{"message_type":"committed_transcript_with_timestamps","text":"Where is my order?",'
            '"words":[{"text":"order","start":0.0,"end":1.2}]}',
        ]
    )
    session = ElevenLabsRealtimeSttSession(speech_client().config, connection)  # type: ignore[arg-type]

    legacy, timestamped = asyncio.run(_two_events(session))

    assert legacy is None
    assert timestamped is not None
    assert timestamped.message_type == "committed_transcript"
    assert timestamped.committed_audio_end_seconds == 1.2


async def _two_events(session: ElevenLabsRealtimeSttSession) -> tuple[object, object]:
    """Receive a provider's legacy and timestamped committed event pair."""

    return await session.receive(), await session.receive()


def test_timestamped_committed_transcript_exposes_word_end_boundary() -> None:
    """The final word's session-relative end maps the committed PCM boundary."""

    connection = FakeRealtimeConnection(
        [
            '{"message_type":"committed_transcript_with_timestamps","text":"Where is my order?",'
            '"words":[{"text":"Where","start":0.0,"end":0.4},{"text":"order","start":0.5,"end":1.2}]}'
        ]
    )
    session = ElevenLabsRealtimeSttSession(speech_client().config, connection)  # type: ignore[arg-type]

    event = asyncio.run(session.receive())

    assert event is not None
    assert event.message_type == "committed_transcript"
    assert event.committed_audio_end_seconds == 1.2


def test_synthesize_pcm16_returns_mocked_audio_with_configured_format() -> None:
    """TTS requests PCM16 output and returns the mocked raw audio bytes."""

    client = speech_client()
    expected_audio = b"\x01\x00\x02\x00"
    with patch.object(client, "_request", return_value=expected_audio) as request:
        assert client.synthesize_pcm16("Your order is on the way.") == expected_audio

    url, payload, headers = request.call_args.args
    assert url == "https://example.test/v1/text-to-speech/test-voice/stream?output_format=pcm_16000"
    assert b'"model_id": "eleven_flash_v2_5"' in payload
    assert headers["accept"] == "audio/pcm"
    assert headers["xi-api-key"] == "test-key"


def test_speech_requests_strip_environment_style_whitespace() -> None:
    """Provider credentials and endpoint identifiers match the tester's trimmed browser values."""

    client = ElevenLabsSpeechClient(
        speech_client().config.model_copy(
            update={
                "elevenlabs_api_key": " test-key ",
                "elevenlabs_voice_id": " test-voice ",
                "elevenlabs_tts_api_url": " https://example.test/v1/text-to-speech/ ",
                "elevenlabs_tts_model": " eleven_flash_v2_5 ",
                "elevenlabs_tts_output_format": " pcm_16000 ",
            }
        )
    )
    with patch.object(client, "_request", return_value=b"pcm") as request:
        client.synthesize_pcm16("A brief response.")

    url, payload, headers = request.call_args.args
    assert url == "https://example.test/v1/text-to-speech/test-voice/stream?output_format=pcm_16000"
    assert b'"model_id": "eleven_flash_v2_5"' in payload
    assert headers["xi-api-key"] == "test-key"


def test_credential_fingerprint_is_stable_and_non_secret() -> None:
    """Safe diagnostics correlate a credential without writing its raw value to logs."""

    fingerprint = _credential_fingerprint("test-key")

    assert fingerprint == _credential_fingerprint("test-key")
    assert len(fingerprint) == 12
    assert "test-key" not in fingerprint


def test_http_error_summary_keeps_only_safe_provider_fields() -> None:
    """Provider error diagnostics omit unexpected fields and redact nested secrets."""

    body = b'{"detail":"Invalid key","token":"should-not-appear"}'
    error = urllib.error.HTTPError(
        "https://example.test",
        401,
        "Unauthorized",
        hdrs=None,
        fp=io.BytesIO(body),
    )

    assert _http_error_summary(error) == {
        "bodyBytes": len(body),
        "provider": {"detail": "Invalid key"},
    }


def test_requests_use_certifi_ca_bundle_for_tls_validation() -> None:
    """Live HTTPS requests retain certificate validation against the Certifi CA bundle."""

    client = speech_client()
    response = MagicMock()
    response.read.return_value = b"pcm"
    response.__enter__.return_value = response
    with (
        patch("app.voice.elevenlabs.certifi.where", return_value="/tmp/certifi-ca.pem") as where,
        patch("app.voice.elevenlabs.ssl.create_default_context", return_value=ssl.create_default_context()) as create_context,
        patch("app.voice.elevenlabs.urllib.request.urlopen", return_value=response) as urlopen,
    ):
        assert client._request("https://example.test/speech", b"payload", {"accept": "audio/pcm"}) == b"pcm"

    where.assert_called_once_with()
    create_context.assert_called_once_with(cafile="/tmp/certifi-ca.pem")
    assert urlopen.call_args.kwargs["context"] is create_context.return_value

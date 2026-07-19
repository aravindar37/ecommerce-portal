"""Protocol tests for the local authenticated voice WebSocket."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.voice.routes import router  # noqa: E402
from app.agentic.resilience import RetryExhaustedError  # noqa: E402


def voice_app() -> FastAPI:
    """Create an isolated test application with only the voice router."""

    app = FastAPI()
    app.include_router(router)
    return app


def test_voice_stream_rejects_missing_shared_token() -> None:
    """The development transport refuses connections without its shared token."""

    with patch("app.voice.routes.settings.voice_stream_ws_auth_token", "test-token"):
        with TestClient(voice_app()) as client:
            try:
                with client.websocket_connect("/api/voice/stream"):
                    pass
            except WebSocketDisconnect as exc:
                assert exc.code == 1008
            else:  # pragma: no cover - assertion guard
                raise AssertionError("Unauthenticated voice socket was accepted")


def test_voice_stream_requires_start_before_binary_audio() -> None:
    """The protocol returns a structured error for PCM sent before start."""

    with patch("app.voice.routes.settings.voice_stream_ws_auth_token", "test-token"):
        with TestClient(voice_app()) as client:
            with client.websocket_connect("/api/voice/stream?token=test-token") as websocket:
                websocket.send_bytes(b"\x00\x00")
                assert websocket.receive_json() == {"type": "error", "code": "SESSION_NOT_STARTED"}


def test_voice_stream_accepts_start_and_finalizes_call() -> None:
    """The JSON start/stop controls create and finalize exactly one call."""

    call = SimpleNamespace(call_id="call-1")
    with (
        patch("app.voice.routes.settings.voice_stream_ws_auth_token", "test-token"),
        patch("app.voice.routes.voice_pipeline.begin", return_value=call) as begin,
        patch("app.voice.routes.voice_pipeline.open_realtime_stt"),
        patch("app.voice.routes.voice_pipeline.close_realtime_stt"),
        patch("app.voice.routes.voice_pipeline.end") as end,
        TestClient(voice_app()) as client,
    ):
        with client.websocket_connect("/api/voice/stream?token=test-token") as websocket:
            websocket.send_json({"type": "start", "callerPhoneNumber": "+15555550100"})
            started = websocket.receive_json()
            websocket.send_json({"type": "stop"})

    assert started["type"] == "started"
    assert started["callId"] == "call-1"
    begin.assert_called_once_with("+15555550100")
    end.assert_called_once_with(call)


def test_voice_stream_finalizes_call_after_turn_failure() -> None:
    """A failed STT, tool, or TTS turn must not bypass recording/session finalization."""

    call = SimpleNamespace(call_id="call-1")
    with (
        patch("app.voice.routes.settings.voice_stream_ws_auth_token", "test-token"),
        patch("app.voice.routes.voice_pipeline.begin", return_value=call),
        patch("app.voice.routes.voice_pipeline.open_realtime_stt"),
        patch("app.voice.routes.voice_pipeline.next_transcript", side_effect=asyncio.CancelledError()),
        patch("app.voice.routes.voice_pipeline.push_audio", side_effect=RuntimeError("turn failed")),
        patch("app.voice.routes.voice_pipeline.close_realtime_stt"),
        patch("app.voice.routes.voice_pipeline.end") as end,
        TestClient(voice_app()) as client,
    ):
        with client.websocket_connect("/api/voice/stream?token=test-token") as websocket:
            websocket.send_json({"type": "start"})
            assert websocket.receive_json()["type"] == "started"
            websocket.send_bytes(b"\x00\x00")
            assert websocket.receive_json() == {"type": "error", "code": "VOICE_TURN_FAILED"}
            websocket.send_json({"type": "stop"})

    end.assert_called_once_with(call)


def test_voice_stream_forwards_continuous_audio_and_dispatches_only_committed_transcript() -> None:
    """Partial STT events are ignored; one committed event produces exactly one reply."""

    call = SimpleNamespace(call_id="call-1")
    events = iter([("partial_transcript", "where is"), ("committed_transcript", "Where is my order?")])

    async def next_event(_: object) -> tuple[str, str]:
        try:
            return next(events)
        except StopIteration:
            await asyncio.Future()
            raise AssertionError("unreachable")  # pragma: no cover

    with (
        patch("app.voice.routes.settings.voice_stream_ws_auth_token", "test-token"),
        patch("app.voice.routes.voice_pipeline.begin", return_value=call),
        patch("app.voice.routes.voice_pipeline.open_realtime_stt", new=AsyncMock()),
        patch("app.voice.routes.voice_pipeline.next_transcript", side_effect=next_event),
        patch("app.voice.routes.voice_pipeline.push_audio", new=AsyncMock()) as push_audio,
        patch("app.voice.routes.voice_pipeline.process_committed_transcript", return_value=b"agent-audio") as process,
        patch("app.voice.routes.voice_pipeline.close_realtime_stt", new=AsyncMock()),
        patch("app.voice.routes.voice_pipeline.end"),
        TestClient(voice_app()) as client,
    ):
        with client.websocket_connect("/api/voice/stream?token=test-token") as websocket:
            websocket.send_json({"type": "start"})
            assert websocket.receive_json()["type"] == "started"
            websocket.send_bytes(b"\x01\x00" * 3200)
            websocket.send_bytes(b"\x02\x00" * 3200)
            assert websocket.receive_bytes() == b"agent-audio"
            websocket.send_json({"type": "stop"})

    assert [entry.args[1] for entry in push_audio.await_args_list] == [b"\x01\x00" * 3200, b"\x02\x00" * 3200]
    process.assert_called_once_with(call, "Where is my order?")


def test_voice_stream_ignores_lifecycle_packet_before_committed_transcript() -> None:
    """A non-transcript provider packet must not stop the bidirectional consumer task."""

    call = SimpleNamespace(call_id="call-1")
    events = iter([None, ("committed_transcript", "Where is my order?")])

    async def next_event(_: object) -> tuple[str, str] | None:
        try:
            return next(events)
        except StopIteration:
            await asyncio.Future()
            raise AssertionError("unreachable")  # pragma: no cover

    with (
        patch("app.voice.routes.settings.voice_stream_ws_auth_token", "test-token"),
        patch("app.voice.routes.voice_pipeline.begin", return_value=call),
        patch("app.voice.routes.voice_pipeline.open_realtime_stt", new=AsyncMock()),
        patch("app.voice.routes.voice_pipeline.next_transcript", side_effect=next_event),
        patch("app.voice.routes.voice_pipeline.process_committed_transcript", return_value=b"agent-audio") as process,
        patch("app.voice.routes.voice_pipeline.close_realtime_stt", new=AsyncMock()),
        patch("app.voice.routes.voice_pipeline.end"),
        TestClient(voice_app()) as client,
    ):
        with client.websocket_connect("/api/voice/stream?token=test-token") as websocket:
            websocket.send_json({"type": "start"})
            assert websocket.receive_json()["type"] == "started"
            assert websocket.receive_bytes() == b"agent-audio"
            websocket.send_json({"type": "stop"})

    process.assert_called_once_with(call, "Where is my order?")


def test_voice_stream_reports_tts_failure_without_mislabeling_it_as_stt() -> None:
    """A committed transcript whose speech synthesis fails returns the TTS-specific code."""

    call = SimpleNamespace(call_id="call-1")

    async def committed_event(_: object) -> tuple[str, str]:
        return "committed_transcript", "Where is my order?"

    synthesis_failure = RetryExhaustedError("elevenlabs_tts", 1, RuntimeError("unauthorized"))
    with (
        patch("app.voice.routes.settings.voice_stream_ws_auth_token", "test-token"),
        patch("app.voice.routes.voice_pipeline.begin", return_value=call),
        patch("app.voice.routes.voice_pipeline.open_realtime_stt", new=AsyncMock()),
        patch("app.voice.routes.voice_pipeline.next_transcript", side_effect=committed_event),
        patch("app.voice.routes.voice_pipeline.process_committed_transcript", side_effect=synthesis_failure),
        patch("app.voice.routes.voice_pipeline.close_realtime_stt", new=AsyncMock()),
        patch("app.voice.routes.voice_pipeline.end"),
        TestClient(voice_app()) as client,
    ):
        with client.websocket_connect("/api/voice/stream?token=test-token") as websocket:
            websocket.send_json({"type": "start"})
            assert websocket.receive_json()["type"] == "started"
            assert websocket.receive_json() == {"type": "error", "code": "VOICE_TTS_UNAVAILABLE"}
            websocket.send_json({"type": "stop"})

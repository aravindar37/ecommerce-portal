"""Protocol tests for the local authenticated voice WebSocket."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.voice.routes import router  # noqa: E402


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

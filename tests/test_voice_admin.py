"""Restricted admin API tests for voice-call metadata and transcripts."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.voice.admin import router  # noqa: E402


def admin_app() -> FastAPI:
    """Create an isolated application for voice admin route tests."""

    app = FastAPI()
    app.include_router(router)
    return app


def test_voice_transcript_requires_admin_token() -> None:
    """Transcript content is unavailable without the restricted admin credential."""

    with patch("app.voice.admin.settings.test_admin_token", "admin-token"):
        with TestClient(admin_app()) as client:
            response = client.get("/api/admin/voice/call-sessions/call-1/transcript")

    assert response.status_code == 401


def test_voice_call_summary_exposes_artifact_status_without_storage_or_phone_data() -> None:
    """The local tester can verify artifacts without receiving the protected storage details."""

    call = {
        "callId": "call-1",
        "startedAt": "2026-07-19T00:00:00Z",
        "durationSeconds": 12,
        "verificationOutcome": "verified",
        "disposition": "escalated",
        "escalated": True,
        "supportTicketNumber": "SUP-1",
        "recordingS3Bucket": "private-recordings",
        "recordingS3Key": "voice-call-recordings/call-1.wav",
        "fromNumberMasked": "+1***00",
        "transcriptSummary": "Caller: help",
    }
    with (
        patch("app.voice.admin.settings.test_admin_token", "admin-token"),
        patch("app.voice.admin.store.list_voice_call_sessions", return_value=[call]),
        TestClient(admin_app()) as client,
    ):
        response = client.get("/api/admin/voice/call-sessions", headers={"authorization": "Bearer admin-token"})

    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["recordingStored"] is True
    assert item["supportTicketNumber"] == "SUP-1"
    assert "recordingS3Bucket" not in item
    assert "recordingS3Key" not in item
    assert "fromNumberMasked" not in item


def test_voice_transcript_exposes_messages_without_recording_or_phone_data() -> None:
    """The admin transcript endpoint returns persisted dialogue only, never storage/ANI metadata."""

    call = {
        "callId": "call-1",
        "chatSessionId": "session-1",
        "disposition": "resolved",
        "recordingS3Bucket": "private-recordings",
        "recordingS3Key": "voice-call-recordings/call-1.wav",
        "fromNumberMasked": "+1***00",
    }
    messages = [
        {"role": "user", "content": "Where is my order?", "createdAt": "2026-07-18T00:00:00Z"},
        {"role": "assistant", "content": "It is in transit.", "createdAt": "2026-07-18T00:00:01Z"},
    ]
    with (
        patch("app.voice.admin.settings.test_admin_token", "admin-token"),
        patch("app.voice.admin.store.find_voice_call_session", return_value=call),
        patch("app.voice.admin.store.list_messages", return_value=messages),
        TestClient(admin_app()) as client,
    ):
        response = client.get("/api/admin/voice/call-sessions/call-1/transcript", headers={"authorization": "Bearer admin-token"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {"callId": "call-1", "disposition": "resolved", "items": messages}
    assert "recordingS3Key" not in str(data)
    assert "fromNumberMasked" not in str(data)

"""Session-end behavior for voice recording and verified escalation."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.voice.identity import VoiceIdentity  # noqa: E402
from app.voice.pipeline import VoiceCall, voice_pipeline  # noqa: E402
from app.voice.vad import VoiceActivityDetector  # noqa: E402


def call_for_end(*, verified_user_id: str | None, escalated: bool) -> VoiceCall:
    """Build an isolated call state suitable for end-of-session tests."""

    return VoiceCall(
        call_id="call-end-1",
        chat_session={"_id": "session-end-1"},
        identity=VoiceIdentity(call_id="call-end-1", verified_user_id=verified_user_id),
        detector=VoiceActivityDetector(16000, -40, 600, 250),
        started_at=datetime.now(UTC),
        recording_frames=[b"\x00\x00" * 16],
        transcript_parts=["Caller: I need a human agent."],
        escalated=escalated,
    )


def test_verified_escalation_creates_ticket_and_links_recording() -> None:
    """A verified escalated session creates its ticket and persists only S3 location metadata."""

    call = call_for_end(verified_user_id="verified-user", escalated=True)
    session = {"callId": call.call_id}
    with (
        patch("app.voice.pipeline.call_recordings.upload", return_value={"bucket": "private-recordings", "key": "voice-call-recordings/call-end-1.wav"}),
        patch("app.voice.pipeline.core_tools.create_voice_support_ticket", return_value={"ticketNumber": "TKT-1"}) as ticket,
        patch("app.voice.pipeline.store.update_voice_call_session", return_value=session) as update,
        patch("app.voice.pipeline.voice_identity.end"),
        patch.object(voice_pipeline, "_voice_activity"),
    ):
        result = voice_pipeline.end(call)

    assert result == session
    ticket.assert_called_once()
    updates = update.call_args.args[1]
    assert updates["supportTicketNumber"] == "TKT-1"
    assert updates["recordingS3Bucket"] == "private-recordings"
    assert updates["recordingS3Key"] == "voice-call-recordings/call-end-1.wav"
    assert updates["disposition"] == "escalated"


def test_unverified_escalation_never_creates_ticket() -> None:
    """Identity lockout escalation never opens a ticket under an unverified customer account."""

    call = call_for_end(verified_user_id=None, escalated=True)
    with (
        patch("app.voice.pipeline.call_recordings.upload", return_value=None),
        patch("app.voice.pipeline.core_tools.create_voice_support_ticket") as ticket,
        patch("app.voice.pipeline.store.update_voice_call_session", return_value={"callId": call.call_id}) as update,
        patch("app.voice.pipeline.voice_identity.end"),
        patch.object(voice_pipeline, "_voice_activity"),
    ):
        voice_pipeline.end(call)

    ticket.assert_not_called()
    updates = update.call_args.args[1]
    assert updates["supportTicketNumber"] is None
    assert updates["disposition"] == "escalated"

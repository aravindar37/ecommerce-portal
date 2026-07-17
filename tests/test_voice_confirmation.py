"""Unit tests for explicit spoken confirmation in voice sessions."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.voice.identity import VoiceIdentity  # noqa: E402
from app.voice.pipeline import VoiceCall, voice_pipeline  # noqa: E402
from app.voice.vad import VoiceActivityDetector  # noqa: E402


def test_spoken_yes_executes_latest_unexpired_action_only() -> None:
    """An exact affirmative executes the one pending action associated with the call."""

    call = SimpleNamespace(chat_session={"_id": "session-1"})
    action = {"_id": "action-1", "type": "update_order", "payload": {}}
    with (
        patch("app.voice.pipeline.store.latest_pending_action", return_value=action) as latest,
        patch.object(voice_pipeline, "_execute_voice_action", return_value="Your order update is complete.") as execute,
    ):
        reply = voice_pipeline._confirm_spoken_yes(call, "Yes please.", "user-1")

    assert reply == "Your order update is complete."
    latest.assert_called_once_with("session-1", "user-1")
    execute.assert_called_once_with(action, "user-1")


def test_non_affirmative_reply_leaves_pending_action_unexecuted() -> None:
    """No, cancel, and arbitrary text must not inspect or execute pending actions."""

    call = SimpleNamespace(chat_session={"_id": "session-1"})
    with (
        patch("app.voice.pipeline.store.latest_pending_action") as latest,
        patch.object(voice_pipeline, "_execute_voice_action") as execute,
    ):
        assert voice_pipeline._confirm_spoken_yes(call, "no", "user-1") is None
        assert voice_pipeline._confirm_spoken_yes(call, "cancel", "user-1") is None
        assert voice_pipeline._confirm_spoken_yes(call, "yes, but tell me more", "user-1") is None
        assert voice_pipeline._confirm_spoken_yes(call, "tell me more", "user-1") is None

    latest.assert_not_called()
    execute.assert_not_called()


def test_spoken_yes_does_not_execute_when_no_unexpired_action_exists() -> None:
    """The store's expiry filter prevents a confirmation from reviving an old action."""

    call = SimpleNamespace(chat_session={"_id": "session-1"})
    with (
        patch("app.voice.pipeline.store.latest_pending_action", return_value=None) as latest,
        patch.object(voice_pipeline, "_execute_voice_action") as execute,
    ):
        assert voice_pipeline._confirm_spoken_yes(call, "yes", "user-1") is None

    latest.assert_called_once_with("session-1", "user-1")
    execute.assert_not_called()


def test_failed_execution_leaves_action_pending() -> None:
    """A transient Core failure must not mark the confirmed action complete."""

    action = {"_id": "action-1", "type": "update_order", "payload": {"orderId": "order-1", "action": "cancel"}}
    with (
        patch("app.voice.pipeline.core_tools.update_voice_order", side_effect=RuntimeError("unavailable")),
        patch("app.voice.pipeline.store.complete_action") as complete,
    ):
        try:
            voice_pipeline._execute_voice_action(action, "user-1")
        except RuntimeError:
            pass
        else:  # pragma: no cover - assertion guard
            raise AssertionError("Core execution failure must be propagated")

    complete.assert_not_called()


def test_confirmed_order_update_uses_verified_user_on_behalf() -> None:
    """A confirmed voice mutation is always attributed to the hard-verified Core user."""

    action = {"_id": "action-1", "type": "update_order", "payload": {"orderId": "order-1", "action": "cancel"}}
    with (
        patch("app.voice.pipeline.core_tools.update_voice_order", return_value={"_id": "order-1", "status": "cancelled"}) as update,
        patch("app.voice.pipeline.store.complete_action") as complete,
    ):
        reply = voice_pipeline._execute_voice_action(action, "verified-user")

    assert reply == "Your order update is complete."
    update.assert_called_once_with("verified-user", "order-1", "cancel", None)
    complete.assert_called_once()


def test_confirmation_reply_is_persisted_without_reinvoking_agent() -> None:
    """A deterministic confirmation turn remains visible in the transcript and history."""

    identity = VoiceIdentity(call_id="call-1", verified_user_id="verified-user")
    call = VoiceCall(
        call_id="call-1",
        chat_session={"_id": "session-1", "userId": "verified-user"},
        identity=identity,
        detector=VoiceActivityDetector(16000, -40, 600, 250),
        started_at=datetime.now(UTC),
    )
    with (
        patch("app.voice.pipeline.elevenlabs_speech.transcribe_pcm16", return_value="yes"),
        patch("app.voice.pipeline.voice_identity.get", return_value=identity),
        patch.object(voice_pipeline, "_confirm_spoken_yes", return_value="Your order update is complete."),
        patch("app.voice.pipeline.store.add_message") as add_message,
        patch.object(voice_pipeline, "_synthesize_reply", return_value=b"audio") as synthesize,
        patch("app.voice.pipeline.agent_service.try_answer") as try_answer,
    ):
        response = voice_pipeline.process_utterance(call, b"\x01\x00" * 160)

    assert response == b"audio"
    assert call.transcript_parts == ["Caller: yes", "Agent: Your order update is complete."]
    assert add_message.call_count == 2
    assert add_message.call_args_list[-1].args[2] == "Your order update is complete."
    assert add_message.call_args_list[-1].args[3]["confirmation"] is True
    synthesize.assert_called_once()
    try_answer.assert_not_called()

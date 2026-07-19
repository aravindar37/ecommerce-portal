"""Unit tests for explicit spoken confirmation in voice sessions."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.voice.identity import VoiceIdentity  # noqa: E402
from app.voice.pipeline import VoiceCall, voice_pipeline  # noqa: E402
from app.voice.elevenlabs import RealtimeTranscriptEvent  # noqa: E402
from app.voice.vad import VoiceActivityDetector  # noqa: E402
from app.agentic.models import AgentRunResult  # noqa: E402


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
        patch("app.voice.pipeline.voice_identity.get", return_value=identity),
        patch.object(voice_pipeline, "_confirm_spoken_yes", return_value="Your order update is complete."),
        patch("app.voice.pipeline.store.add_message") as add_message,
        patch.object(voice_pipeline, "_synthesize_reply", return_value=b"audio") as synthesize,
        patch("app.voice.pipeline.agent_service.try_answer") as try_answer,
    ):
        response = voice_pipeline.process_committed_transcript(call, "yes")

    assert response == b"audio"
    assert call.transcript_parts == ["Caller: yes", "Agent: Your order update is complete."]
    assert add_message.call_count == 2
    assert add_message.call_args_list[-1].args[2] == "Your order update is complete."
    assert add_message.call_args_list[-1].args[3]["confirmation"] is True
    synthesize.assert_called_once()
    try_answer.assert_not_called()


def test_scripted_utterance_runs_stt_agent_and_tts_with_persisted_turns() -> None:
    """A pre-recorded PCM fixture produces a transcript, agent reply, and PCM response."""

    identity = VoiceIdentity(call_id="call-1")
    call = VoiceCall(
        call_id="call-1",
        chat_session={"_id": "session-1", "userId": "voice:call-1"},
        identity=identity,
        detector=VoiceActivityDetector(16000, -40, 600, 250),
        started_at=datetime.now(UTC),
    )
    result = AgentRunResult(message="I need your order number and last name or postal code.", used_agentic_loop=True)
    with (
        patch("app.voice.pipeline.voice_identity.get", return_value=identity),
        patch("app.voice.pipeline.agent_service.try_answer", return_value=result) as answer,
        patch("app.voice.pipeline.elevenlabs_speech.synthesize_pcm16", return_value=b"agent-pcm") as tts,
        patch("app.voice.pipeline.store.add_message") as add_message,
        patch("app.voice.pipeline.store.update_voice_call_session") as update_session,
    ):
        response = voice_pipeline.process_committed_transcript(call, "Where is my order?")

    assert response == b"agent-pcm"
    answer.assert_called_once()
    tts.assert_called_once_with("I need your order number and last name or postal code.")
    assert [entry.args[1] for entry in add_message.call_args_list] == ["user", "assistant"]
    assert call.transcript_parts == [
        "Caller: Where is my order?",
        "Agent: I need your order number and last name or postal code.",
    ]
    assert call.stt_requests == 1
    assert call.tts_requests == 1
    update_session.assert_called_once()


def test_continuous_pcm_frames_are_forwarded_without_local_utterance_buffering() -> None:
    """Every caller frame reaches the persistent STT session immediately and in order."""

    upstream = AsyncMock()
    call = VoiceCall(
        call_id="call-1",
        chat_session={"_id": "session-1"},
        identity=VoiceIdentity(call_id="call-1"),
        started_at=datetime.now(UTC),
        realtime_stt=upstream,
    )
    frames = [b"\x01\x00" * 3200, b"\x02\x00" * 3200, b"\x03\x00" * 3200]

    async def stream_frames() -> None:
        for frame in frames:
            await voice_pipeline.push_audio(call, frame)

    asyncio.run(stream_frames())

    assert call.recording_frames == frames
    assert upstream.send_pcm16.await_args_list == [((frame,),) for frame in frames]
    assert call.stt_requests == 0
    assert not hasattr(call, "utterance_buffer")


def test_partial_transcript_is_ephemeral_and_committed_transcript_is_identified() -> None:
    """Provider partial packets cannot create a caller turn or invoke the agent."""

    upstream = AsyncMock()
    upstream.receive.side_effect = [
        RealtimeTranscriptEvent("partial_transcript", "where is"),
        RealtimeTranscriptEvent("committed_transcript", "Where is my order?"),
    ]
    call = VoiceCall(
        call_id="call-1",
        chat_session={"_id": "session-1"},
        identity=VoiceIdentity(call_id="call-1"),
        started_at=datetime.now(UTC),
        realtime_stt=upstream,
    )
    with (
        patch("app.voice.pipeline.voice_metrics.record_stt_partial_transcript") as partial_metric,
        patch("app.voice.pipeline.voice_metrics.record_stt_committed_transcript") as committed_metric,
        patch("app.voice.pipeline.store.add_message") as add_message,
        patch("app.voice.pipeline.agent_service.try_answer") as answer,
    ):
        partial, committed = asyncio.run(_read_two_transcript_events(call))

    assert partial == ("partial_transcript", "where is")
    assert committed == ("committed_transcript", "Where is my order?")
    partial_metric.assert_called_once_with()
    committed_metric.assert_called_once_with()
    add_message.assert_not_called()
    answer.assert_not_called()


def test_timestamped_committed_boundary_discards_only_already_committed_pcm() -> None:
    """Replay retains frames after the provider's documented final-word boundary."""

    upstream = AsyncMock()
    upstream.receive.return_value = RealtimeTranscriptEvent(
        "committed_transcript", "Where is my order?", committed_audio_end_seconds=0.4
    )
    call = VoiceCall(
        call_id="call-1",
        chat_session={"_id": "session-1"},
        identity=VoiceIdentity(call_id="call-1"),
        started_at=datetime.now(UTC),
        realtime_stt=upstream,
        replay_frames=[(0.2, b"committed"), (0.4, b"boundary"), (0.6, b"uncommitted")],
    )

    event = asyncio.run(voice_pipeline.next_transcript(call))

    assert event == ("committed_transcript", "Where is my order?")
    assert call.replay_frames == [(0.6, b"uncommitted")]


def test_reconnect_replays_only_uncommitted_pcm_after_two_fixed_delay_retries() -> None:
    """The approved policy retries transport failures twice, then resumes the same call."""

    reconnected = AsyncMock()
    call = VoiceCall(
        call_id="call-1",
        chat_session={"_id": "session-1"},
        identity=VoiceIdentity(call_id="call-1"),
        started_at=datetime.now(UTC),
        replay_frames=[(0.6, b"uncommitted")],
    )
    with (
        patch("app.voice.pipeline.elevenlabs_speech.open_realtime_stt_session", side_effect=[ConnectionError("down"), ConnectionError("down"), reconnected]) as open_session,
        patch("app.voice.pipeline.asyncio.sleep", new=AsyncMock()) as sleep,
        patch("app.voice.pipeline.voice_metrics.record_stt_connection_failed") as failed,
        patch("app.voice.pipeline.voice_metrics.record_stt_connection_opened") as opened,
    ):
        asyncio.run(voice_pipeline.reconnect_realtime_stt(call))

    assert call.realtime_stt is reconnected
    assert open_session.await_count == 3
    assert sleep.await_args_list == [((15,),), ((15,),)]
    assert reconnected.send_pcm16.await_args_list == [((b"uncommitted",),)]
    assert failed.call_count == 2
    opened.assert_called_once_with()


async def _read_two_transcript_events(call: VoiceCall) -> tuple[tuple[str, str] | None, tuple[str, str] | None]:
    """Read two upstream events without crossing the committed-turn boundary."""

    return await voice_pipeline.next_transcript(call), await voice_pipeline.next_transcript(call)

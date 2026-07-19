"""Per-call realtime STT → verified agent → TTS orchestration for local voice streams."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.agentic.service import agent_service
from app.config import ChatServiceSettings, settings
from app.dependencies import ChatContext
from app.observability import logger, voice_metrics
from app.store import Json, store
from app.tools.core import core_tools

from .elevenlabs import ElevenLabsRealtimeSttSession, RealtimeSttNonRetryableError, elevenlabs_speech
from .identity import VoiceIdentity, voice_identity
from .recordings import call_recordings


@dataclass
class VoiceCall:
    """In-memory state for one WebSocket voice call."""

    call_id: str
    chat_session: Json
    identity: VoiceIdentity
    started_at: datetime
    detector: Any | None = None
    realtime_stt: ElevenLabsRealtimeSttSession | None = None
    recording_frames: list[bytes] = field(default_factory=list)
    replay_frames: list[tuple[float, bytes]] = field(default_factory=list)
    replay_audio_end_seconds: float = 0.0
    realtime_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    transcript_parts: list[str] = field(default_factory=list)
    stt_requests: int = 0
    tts_requests: int = 0
    escalated: bool = False


class VoicePipeline:
    """Own the local audio session and reuse the existing agent harness."""

    def __init__(self, config: ChatServiceSettings = settings) -> None:
        self.config = config

    def begin(self, caller_phone_number: str | None = None) -> VoiceCall:
        """Open an unauthenticated call; account access remains blocked until verification."""

        call_id = f"call_{uuid.uuid4().hex}"
        identity = voice_identity.begin(call_id, caller_phone_number)
        masked_phone = self._mask_phone(caller_phone_number)
        chat_session = store.create_session(
            self.config.voice_agent_session_type,
            f"voice:{call_id}",
            {"entryPoint": "voice_call", "callId": call_id, "callerPhoneNumberMasked": masked_phone},
        )
        store.create_voice_call_session(call_id, masked_phone, {"entryPoint": "voice_call"})
        store.update_voice_call_session(call_id, {"chatSessionId": chat_session["_id"]})
        voice_metrics.record_call_started()
        self._voice_activity("voice_call_started", None, {"callId": call_id})
        return VoiceCall(
            call_id=call_id,
            chat_session=chat_session,
            identity=identity,
            started_at=datetime.now(UTC),
        )

    async def open_realtime_stt(self, call: VoiceCall) -> None:
        """Attach the one persistent upstream transcription session to a call."""

        call.realtime_stt = await elevenlabs_speech.open_realtime_stt_session()
        voice_metrics.record_stt_connection_opened()

    async def push_audio(self, call: VoiceCall, frame: bytes) -> None:
        """Forward one PCM frame immediately without local utterance buffering."""

        async with call.realtime_lock:
            call.recording_frames.append(frame)
            call.replay_audio_end_seconds += len(frame) / (16000 * 2)
            call.replay_frames.append((call.replay_audio_end_seconds, frame))
            if not call.realtime_stt:
                await self._reconnect_locked(call)
                return
            try:
                await call.realtime_stt.send_pcm16(frame)
            except RealtimeSttNonRetryableError:
                raise
            except ConnectionError:
                await self._reconnect_locked(call)

    async def next_transcript(self, call: VoiceCall) -> tuple[str, str] | None:
        """Read the next upstream event and return only a typed, safe transcript."""

        if not call.realtime_stt:
            return None
        try:
            event = await call.realtime_stt.receive()
        except RealtimeSttNonRetryableError:
            raise
        except ConnectionError:
            await self.reconnect_realtime_stt(call)
            return await self.next_transcript(call)
        if not event:
            return None
        if event.message_type == "partial_transcript":
            voice_metrics.record_stt_partial_transcript()
        else:
            voice_metrics.record_stt_committed_transcript()
            if event.committed_audio_end_seconds is not None:
                async with call.realtime_lock:
                    call.replay_frames = [
                        (frame_end, frame)
                        for frame_end, frame in call.replay_frames
                        if frame_end > event.committed_audio_end_seconds
                    ]
        return event.message_type, event.text

    async def reconnect_realtime_stt(self, call: VoiceCall) -> None:
        """Restore one call after a transport failure and replay only uncommitted PCM."""

        async with call.realtime_lock:
            await self._reconnect_locked(call)

    async def _reconnect_locked(self, call: VoiceCall) -> None:
        """Apply the approved two-retry, fixed-delay, forty-second reconnect policy."""

        started = time.monotonic()
        last_error: Exception | None = None
        for attempt in range(3):
            if attempt:
                remaining = 40 - (time.monotonic() - started)
                if remaining < 15:
                    break
                await asyncio.sleep(15)
            try:
                if call.realtime_stt:
                    await call.realtime_stt.close()
                call.realtime_stt = await elevenlabs_speech.open_realtime_stt_session()
                voice_metrics.record_stt_connection_opened()
                for _, frame in call.replay_frames:
                    await call.realtime_stt.send_pcm16(frame)
                return
            except RealtimeSttNonRetryableError:
                raise
            except Exception as exc:
                last_error = exc
                call.realtime_stt = None
                voice_metrics.record_stt_connection_failed()
        raise ConnectionError("ElevenLabs realtime speech reconnection budget exhausted") from last_error

    def process_committed_transcript(self, call: VoiceCall, transcript: str, stt_ms: int = 0) -> bytes:
        """Run only a provider-committed transcript through the agent harness and TTS."""

        started = time.perf_counter()
        call.stt_requests += 1
        logger.info("voice.turn.agent_started callId=%s sttRequestCount=%s", call.call_id, call.stt_requests)
        call.transcript_parts.append(f"Caller: {transcript}")
        store.add_message(call.chat_session["_id"], "user", transcript, {"voice": True, "sttLatencyMs": stt_ms})

        identity = voice_identity.get(call.call_id) or call.identity
        verified_user_id = identity.verified_user_id if identity.verified else None
        if verified_user_id and call.chat_session.get("userId") != verified_user_id:
            self._bind_verified_identity(call, verified_user_id)
        call.escalated = call.escalated or identity.locked

        confirmation_reply = self._confirm_spoken_yes(call, transcript, verified_user_id)
        if confirmation_reply is not None:
            store.add_message(call.chat_session["_id"], "assistant", confirmation_reply, {"voice": True, "confirmation": True})
            call.transcript_parts.append(f"Agent: {confirmation_reply}")
            return self._synthesize_reply(call, confirmation_reply, started, stt_ms, agent_ms=0)

        agent_started = time.perf_counter()
        context = ChatContext(
            user={"_id": verified_user_id or f"voice:{call.call_id}", "name": "Voice caller", "email": ""},
            cookie_header="",
        )
        result = agent_service.try_answer(
            context,
            call.chat_session,
            transcript,
            {"channel": "voice", "callId": call.call_id, "asrConfidence": None},
            on_behalf_user_id=verified_user_id,
        )
        agent_ms = round((time.perf_counter() - agent_started) * 1000)
        reply = result.message.strip() or self._verification_prompt(identity)
        logger.info(
            "voice.turn.agent_completed callId=%s agentMs=%s replyLength=%s",
            call.call_id,
            agent_ms,
            len(reply),
        )
        store.add_message(call.chat_session["_id"], "assistant", reply, {"voice": True, "agentLatencyMs": agent_ms, "usedAgenticLoop": result.used_agentic_loop})
        call.transcript_parts.append(f"Agent: {reply}")

        return self._synthesize_reply(call, reply, started, stt_ms, agent_ms)

    async def close_realtime_stt(self, call: VoiceCall) -> None:
        """Close the upstream WSS before persisting the final call disposition."""

        if call.realtime_stt:
            await call.realtime_stt.close()
            call.realtime_stt = None

    def _synthesize_reply(self, call: VoiceCall, reply: str, started: float, stt_ms: int, agent_ms: int) -> bytes:
        """Persist a reply and synthesize it consistently for agent and confirmation turns."""

        tts_started = time.perf_counter()
        logger.info("voice.turn.tts_started callId=%s replyLength=%s", call.call_id, len(reply))
        audio = elevenlabs_speech.synthesize_pcm16(reply)
        tts_ms = round((time.perf_counter() - tts_started) * 1000)
        call.tts_requests += 1
        call.recording_frames.append(audio)
        call.escalated = call.escalated or self._is_escalation(reply)
        total_ms = round((time.perf_counter() - started) * 1000)
        voice_metrics.record_turn(stt_ms, agent_ms, tts_ms, total_ms)
        logger.info("voice.turn.tts_completed callId=%s ttsMs=%s pcmBytes=%s", call.call_id, tts_ms, len(audio))
        store.update_voice_call_session(
            call.call_id,
            {
                "sttRequestCount": call.stt_requests,
                "ttsRequestCount": call.tts_requests,
                "transcriptSummary": " ".join(call.transcript_parts)[-2000:],
                "lastTurnLatencyMs": {"stt": stt_ms, "agent": agent_ms, "tts": tts_ms, "total": total_ms},
            },
        )
        return audio

    def _confirm_spoken_yes(self, call: VoiceCall, transcript: str, user_id: str | None) -> str | None:
        """Execute only the latest unexpired verified-caller action after an exact spoken confirmation."""

        if not user_id or not self._is_spoken_yes(transcript):
            return None
        action = store.latest_pending_action(str(call.chat_session["_id"]), user_id)
        if not action:
            return None
        try:
            result = self._execute_voice_action(action, user_id)
        except Exception:
            return "I could not complete that request. Please try again or ask for support."
        return str(result)

    def _execute_voice_action(self, action: Json, user_id: str) -> str:
        """Execute one confirmed action without relying on a browser session cookie."""

        payload = action["payload"]
        if action["type"] == "update_order":
            order = core_tools.update_voice_order(user_id, str(payload["orderId"]), str(payload["action"]), payload.get("shippingAddress"))
            store.complete_action(action, "completed", {"orderId": order.get("_id"), "status": order.get("status")})
            return "Your order update is complete."
        if action["type"] == "create_return_request":
            returned = core_tools.create_voice_return_request(
                user_id,
                str(payload["orderId"]),
                str(payload["orderItemId"]),
                str(payload["reason"]),
                str(payload["condition"]),
                str(payload["resolution"]),
            )
            store.complete_action(action, "completed", {"returnNumber": returned.get("returnNumber")})
            return "Your return request is complete."
        if action["type"] == "create_support_ticket":
            ticket = core_tools.create_voice_support_ticket(
                user_id,
                str(payload["category"]),
                str(payload["priority"]),
                str(payload["subject"]),
                str(payload["body"]),
                payload.get("orderId"),
            )
            store.complete_action(action, "completed", {"ticketNumber": ticket.get("ticketNumber")})
            return "Your support ticket is complete."
        raise ValueError("Unsupported pending voice action")

    def end(self, call: VoiceCall) -> Json | None:
        """Finalize the recording and call record even if recording upload fails."""

        duration = max(0, round((datetime.now(UTC) - call.started_at).total_seconds()))
        upload = call_recordings.upload(call.call_id, b"".join(call.recording_frames), sample_rate=16000)
        ticket_number = self._create_escalation_ticket(call) if call.escalated and call.identity.verified_user_id else None
        updates: Json = {
            "endedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "durationSeconds": duration,
            "verificationOutcome": "verified" if call.identity.verified else "failed" if call.identity.locked else "unverified",
            "disposition": "escalated" if call.escalated else "resolved" if call.identity.verified else "unresolved",
            "escalated": call.escalated,
            "supportTicketNumber": ticket_number,
            "transcriptSummary": " ".join(call.transcript_parts)[-2000:],
            "sttRequestCount": call.stt_requests,
            "ttsRequestCount": call.tts_requests,
        }
        if upload:
            updates["recordingS3Bucket"] = upload["bucket"]
            updates["recordingS3Key"] = upload["key"]
        record = store.update_voice_call_session(call.call_id, updates)
        voice_metrics.record_call_ended(duration, call.identity.verified, call.escalated, bool(upload))
        if call.escalated:
            self._voice_activity("voice_call_escalated", call.identity.verified_user_id, {"callId": call.call_id})
        self._voice_activity("voice_call_ended", call.identity.verified_user_id, {"callId": call.call_id, "durationSeconds": duration})
        voice_identity.end(call.call_id)
        return record

    def _create_escalation_ticket(self, call: VoiceCall) -> str | None:
        """Create a system-confirmed ticket because a phone call has no UI prompt."""

        try:
            ticket = core_tools.create_voice_support_ticket(
                str(call.identity.verified_user_id),
                "voice_escalation",
                "high",
                "Voice support escalation",
                "\n".join(call.transcript_parts)[-4000:] or "Voice caller requested escalation.",
                None,
            )
            return str(ticket.get("ticketNumber") or "") or None
        except Exception:
            return None

    def _bind_verified_identity(self, call: VoiceCall, user_id: str) -> None:
        call.chat_session = store.bind_session_to_user(call.chat_session["_id"], user_id) or call.chat_session
        call.chat_session["userId"] = user_id
        store.update_voice_call_session(call.call_id, {"userId": user_id, "chatSessionId": call.chat_session["_id"], "verificationOutcome": "verified"})
        voice_metrics.record_call_verified()
        self._voice_activity("voice_call_verified", user_id, {"callId": call.call_id})

    def _voice_activity(self, event_type: str, user_id: str | None, metadata: Json) -> None:
        if not user_id:
            return
        try:
            core_tools.write_voice_activity(event_type, user_id, metadata)
        except Exception:
            return

    @staticmethod
    def _mask_phone(phone_number: str | None) -> str | None:
        if not phone_number:
            return None
        return f"{phone_number[:2]}***{phone_number[-2:]}" if len(phone_number) > 4 else "***"

    @staticmethod
    def _is_escalation(reply: str) -> bool:
        lowered = reply.lower()
        return "support ticket" in lowered or "human agent" in lowered

    @staticmethod
    def _is_spoken_yes(transcript: str) -> bool:
        """Recognize only a compact, unambiguous affirmative confirmation."""

        return transcript.strip().lower().rstrip(".!?") in {"yes", "yes please", "please do", "confirm"}

    @staticmethod
    def _verification_prompt(identity: VoiceIdentity) -> str:
        if identity.locked:
            return "I could not verify the order. I can help create a support ticket instead."
        return "Please share your order number and either the last name or postal code on the shipping address."


voice_pipeline = VoicePipeline()

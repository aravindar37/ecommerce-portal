"""Authenticated local WebSocket transport for the direct voice pipeline."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.agentic.resilience import RetryExhaustedError
from app.config import settings
from app.observability import logger, voice_metrics

from .pipeline import VoiceCall, voice_pipeline

router = APIRouter(prefix="/api/voice", tags=["voice"])


def _upstream_error_code(exc: Exception) -> str:
    """Map known voice dependency failures to safe, actionable client codes."""

    if isinstance(exc, RetryExhaustedError) and exc.operation == "elevenlabs_tts":
        return "VOICE_TTS_UNAVAILABLE"
    return "VOICE_STT_UNAVAILABLE"


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket) -> None:
    """Process raw PCM16 frames from the development-only mock telephony tool."""

    if settings.voice_telephony_provider != "local" or settings.app_env != "development":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Voice local streaming is available only in development")
        return
    expected = settings.voice_stream_ws_auth_token.strip()
    provided = websocket.query_params.get("token", "")
    if not expected or provided != expected:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Voice stream authentication failed")
        return
    await websocket.accept()
    call: VoiceCall | None = None
    transcript_task: asyncio.Task[None] | None = None

    async def consume_transcripts(active_call: VoiceCall) -> None:
        """Deliver agent audio only for provider-committed transcript events."""

        try:
            while True:
                event = await voice_pipeline.next_transcript(active_call)
                if event is None:
                    # ElevenLabs emits non-transcript lifecycle packets such as
                    # session_started before its first transcript. They are
                    # intentionally ignored by the STT client, not terminal.
                    continue
                event_type, transcript = event
                if event_type != "committed_transcript":
                    continue
                logger.info(
                    "voice.turn.committed_transcript_received callId=%s transcriptLength=%s",
                    active_call.call_id,
                    len(transcript),
                )
                response_audio = await asyncio.to_thread(voice_pipeline.process_committed_transcript, active_call, transcript)
                if response_audio:
                    logger.info("voice.turn.agent_audio_ready callId=%s pcmBytes=%s", active_call.call_id, len(response_audio))
                    await websocket.send_bytes(response_audio)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error_code = _upstream_error_code(exc)
            logger.warning(
                "voice.stream.upstream_failed callId=%s component=%s error=%s",
                active_call.call_id,
                "tts" if error_code == "VOICE_TTS_UNAVAILABLE" else "stt",
                exc.__class__.__name__,
            )
            if error_code == "VOICE_STT_UNAVAILABLE":
                voice_metrics.record_stt_connection_failed()
            try:
                await websocket.send_json({"type": "error", "code": error_code})
            except Exception:
                pass
    try:
        while True:
            event: dict[str, Any] = await websocket.receive()
            if event.get("type") == "websocket.disconnect":
                break
            if event.get("text") is not None:
                try:
                    message = json.loads(event["text"])
                except (TypeError, json.JSONDecodeError):
                    await websocket.send_json({"type": "error", "code": "INVALID_CONTROL_MESSAGE"})
                    continue
                if not isinstance(message, dict):
                    await websocket.send_json({"type": "error", "code": "INVALID_CONTROL_MESSAGE"})
                    continue
                message_type = message.get("type")
                if message_type == "stop":
                    break
                if message_type == "start":
                    if call is not None:
                        await websocket.send_json({"type": "error", "code": "SESSION_ALREADY_STARTED"})
                        continue
                    caller_phone = message.get("callerPhoneNumber")
                    if caller_phone is not None and (not isinstance(caller_phone, str) or not caller_phone.strip()):
                        await websocket.send_json({"type": "error", "code": "INVALID_CALLER_PHONE_NUMBER"})
                        continue
                    call = voice_pipeline.begin(caller_phone)
                    try:
                        await voice_pipeline.open_realtime_stt(call)
                    except Exception as exc:
                        logger.warning("voice.stream.upstream_connect_failed callId=%s error=%s", call.call_id, exc.__class__.__name__)
                        voice_metrics.record_stt_connection_failed()
                        await asyncio.to_thread(voice_pipeline.end, call)
                        call = None
                        await websocket.send_json({"type": "error", "code": "VOICE_STT_UNAVAILABLE"})
                        continue
                    transcript_task = asyncio.create_task(consume_transcripts(call))
                    await websocket.send_json(
                        {
                            "type": "started",
                            "callId": call.call_id,
                            "audioFormat": "pcm16",
                            "sampleRate": 16000,
                            "channels": 1,
                        }
                    )
                    continue
                await websocket.send_json({"type": "error", "code": "INVALID_CONTROL_MESSAGE"})
                continue
            frame = event.get("bytes")
            if frame is None:
                continue
            if call is None:
                await websocket.send_json({"type": "error", "code": "SESSION_NOT_STARTED"})
                continue
            try:
                await voice_pipeline.push_audio(call, frame)
            except Exception as exc:
                logger.warning("voice.stream.turn_failed callId=%s error=%s", call.call_id, exc.__class__.__name__)
                await websocket.send_json({"type": "error", "code": "VOICE_TURN_FAILED"})
    except WebSocketDisconnect:
        pass
    finally:
        if transcript_task:
            transcript_task.cancel()
            try:
                await transcript_task
            except asyncio.CancelledError:
                pass
        if call:
            try:
                await voice_pipeline.close_realtime_stt(call)
            except Exception:
                pass
            await asyncio.to_thread(voice_pipeline.end, call)


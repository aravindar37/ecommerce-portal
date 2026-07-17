"""Authenticated local WebSocket transport for the direct voice pipeline."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import settings
from app.observability import logger

from .pipeline import VoiceCall, voice_pipeline

router = APIRouter(prefix="/api/voice", tags=["voice"])


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
                response_audio = await asyncio.to_thread(voice_pipeline.push_audio, call, frame)
                if response_audio:
                    await websocket.send_bytes(response_audio)
            except Exception as exc:
                logger.warning("voice.stream.turn_failed callId=%s error=%s", call.call_id, exc.__class__.__name__)
                await websocket.send_json({"type": "error", "code": "VOICE_TURN_FAILED"})
    except WebSocketDisconnect:
        pass
    finally:
        if call:
            try:
                trailing = await asyncio.to_thread(voice_pipeline.flush, call)
                if trailing:
                    await websocket.send_bytes(trailing)
            except Exception:
                pass
            await asyncio.to_thread(voice_pipeline.end, call)


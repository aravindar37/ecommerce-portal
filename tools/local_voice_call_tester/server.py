"""Development-only browser relay for testing a full local Chat Service voice call."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parent
STATIC_PAGE = ROOT / "static" / "index.html"
LOGGER = logging.getLogger("local_voice_call_tester")
SAMPLE_RATE = 16_000


def _masked_phone(phone_number: str | None) -> str | None:
    """Keep caller identity out of the detailed relay diagnostics."""

    if not phone_number:
        return None
    return f"{phone_number[:2]}***{phone_number[-2:]}" if len(phone_number) > 4 else "***"


def _redacted_url(raw_url: str) -> str:
    """Remove query data, including stream tokens, before emitting a request URL."""

    parsed = urllib.parse.urlsplit(raw_url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _response_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Log response shape and counts, never persisted transcript text or credentials."""

    data = result.get("data")
    summary: dict[str, Any] = {"topLevelKeys": sorted(result.keys())}
    if isinstance(data, dict):
        summary["dataKeys"] = sorted(data.keys())
        if isinstance(data.get("items"), list):
            summary["itemCount"] = len(data["items"])
    return summary


def _development_only() -> None:
    """Keep the microphone relay unavailable outside local development."""

    if os.getenv("APP_ENV", "development") != "development":
        raise HTTPException(403, "The local voice call tester is development-only.")


def _chat_http_url() -> str:
    return os.getenv("CHAT_SERVICE_BASE_URL", "http://127.0.0.1:4002").rstrip("/")


def _chat_stream_url() -> str:
    """Build the authenticated local Chat Service voice-stream URL."""

    parsed = urllib.parse.urlsplit(_chat_http_url())
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise HTTPException(400, "CHAT_SERVICE_BASE_URL must be a local HTTP URL.")
    token = os.getenv("VOICE_STREAM_WS_AUTH_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, "VOICE_STREAM_WS_AUTH_TOKEN is not configured.")
    return urllib.parse.urlunsplit(
        ("wss" if parsed.scheme == "https" else "ws", parsed.netloc, "/api/voice/stream", urllib.parse.urlencode({"token": token}), "")
    )


def _admin_headers() -> dict[str, str]:
    token = os.getenv("TEST_ADMIN_TOKEN", "").strip()
    if not token:
        raise HTTPException(503, "TEST_ADMIN_TOKEN is not configured.")
    return {"authorization": f"Bearer {token}", "accept": "application/json"}


def _request_json(url: str) -> dict[str, Any]:
    """Perform a detailed but redacted admin request/response trace."""

    request = urllib.request.Request(url, headers=_admin_headers(), method="GET")
    LOGGER.debug(
        "backend_http_request method=%s url=%s headers=%s",
        request.method,
        _redacted_url(url),
        {"authorization": "[redacted]", "accept": request.headers.get("Accept")},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            result = json.loads(body)
            LOGGER.debug(
                "backend_http_response method=%s url=%s status=%s bytes=%s summary=%s",
                request.method,
                _redacted_url(url),
                response.status,
                len(body),
                _response_summary(result) if isinstance(result, dict) else {"responseType": type(result).__name__},
            )
    except urllib.error.HTTPError as exc:
        LOGGER.warning("backend_http_response method=%s url=%s status=%s error=http_error", request.method, _redacted_url(url), exc.code)
        raise HTTPException(exc.code, "Unable to read the local Chat Service artifact.") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.warning("backend_http_response method=%s url=%s error_type=%s", request.method, _redacted_url(url), exc.__class__.__name__)
        raise HTTPException(502, "Local Chat Service artifact read failed.") from exc
    if not isinstance(result, dict):
        raise HTTPException(502, "Local Chat Service returned an invalid artifact response.")
    return result


async def _forward_from_chat(chat: Any, browser: WebSocket, trace: dict[str, Any]) -> None:
    """Relay agent PCM and Chat Service control messages to the browser."""

    async for message in chat:
        if isinstance(message, bytes):
            trace["backendResponseCount"] += 1
            trace["agentAudioFrameCount"] += 1
            trace["agentAudioBytes"] += len(message)
            LOGGER.debug(
                "backend_ws_response call_id=%s sequence=%s kind=agent_pcm bytes=%s total_audio_bytes=%s",
                trace.get("callId"),
                trace["backendResponseCount"],
                len(message),
                trace["agentAudioBytes"],
            )
            await browser.send_bytes(message)
            continue
        try:
            control = json.loads(message)
        except json.JSONDecodeError:
            LOGGER.warning("chat_invalid_control_json")
            continue
        if isinstance(control, dict):
            trace["backendResponseCount"] += 1
            if isinstance(control.get("callId"), str):
                trace["callId"] = control["callId"]
            safe = {key: control.get(key) for key in ("type", "callId", "audioFormat", "sampleRate", "channels", "code") if key in control}
            LOGGER.debug(
                "backend_ws_response call_id=%s sequence=%s kind=control payload=%s",
                trace.get("callId"),
                trace["backendResponseCount"],
                safe,
            )
            await browser.send_json({"type": "chat_control", "control": control})


app = FastAPI(title="Local Voice Call Tester", docs_url=None, redoc_url=None)


@app.get("/", include_in_schema=False)
async def page() -> FileResponse:
    _development_only()
    return FileResponse(STATIC_PAGE)


@app.get("/api/readiness")
async def readiness() -> dict[str, Any]:
    _development_only()
    return {"chatService": _chat_http_url(), "sampleRate": SAMPLE_RATE}


@app.get("/api/calls/{call_id}/artifacts")
async def artifacts(call_id: str) -> dict[str, Any]:
    """Return safe evidence of each artifact created when a call ended."""

    _development_only()
    if not call_id.startswith("call_") or len(call_id) > 100:
        raise HTTPException(400, "Invalid call ID.")
    LOGGER.info("artifact_check_requested call_id=%s", call_id)
    base_url = _chat_http_url()
    calls = await asyncio.to_thread(_request_json, f"{base_url}/api/admin/voice/call-sessions?limit=100")
    data = calls.get("data", {}) if isinstance(calls.get("data"), dict) else {}
    call = next((item for item in data.get("items", []) if isinstance(item, dict) and item.get("callId") == call_id), None)
    if not call:
        raise HTTPException(404, "Voice call has not finalized yet. Wait a moment and try again.")
    transcript_result = await asyncio.to_thread(
        _request_json, f"{base_url}/api/admin/voice/call-sessions/{urllib.parse.quote(call_id, safe='')}/transcript"
    )
    transcript_data = transcript_result.get("data", {}) if isinstance(transcript_result.get("data"), dict) else {}
    transcript = transcript_data.get("items", []) if isinstance(transcript_data.get("items"), list) else []
    response = {
        "call": call,
        "checks": {
            "voiceCallSessionPersisted": True,
            "chatSessionAndMessagesPersisted": bool(transcript),
            "recordingStored": bool(call.get("recordingStored")),
            "escalationTicketLinked": bool(call.get("supportTicketNumber")),
            "twilioCallSidIsNull": call.get("twilioCallSid") is None,
        },
        "transcript": transcript,
    }
    LOGGER.info(
        "artifact_check_response call_id=%s checks=%s transcript_message_count=%s",
        call_id,
        response["checks"],
        len(transcript),
    )
    return response


@app.websocket("/ws/call")
async def local_call(browser: WebSocket) -> None:
    """Relay browser microphone PCM16 frames to Chat Service's local voice route."""

    await browser.accept()
    chat = None
    receiver: asyncio.Task[None] | None = None
    trace: dict[str, Any] = {
        "callId": None,
        "backendRequestCount": 0,
        "backendResponseCount": 0,
        "callerAudioFrameCount": 0,
        "callerAudioBytes": 0,
        "agentAudioFrameCount": 0,
        "agentAudioBytes": 0,
    }
    try:
        _development_only()
        start = await asyncio.wait_for(browser.receive_json(), timeout=15)
        if not isinstance(start, dict) or start.get("type") != "start":
            raise HTTPException(400, "The first message must start a local call.")
        caller_phone = start.get("callerPhoneNumber")
        if caller_phone is not None and (not isinstance(caller_phone, str) or len(caller_phone) > 32):
            raise HTTPException(400, "Caller phone number is invalid.")
        stream_url = _chat_stream_url()
        LOGGER.info("backend_ws_connect_request url=%s headers=%s", _redacted_url(stream_url), {"token": "[redacted]"})
        chat = await connect(stream_url, open_timeout=10, close_timeout=10, max_size=None)
        LOGGER.info("backend_ws_connect_response url=%s connected=true", _redacted_url(stream_url))
        start_payload = {"type": "start", "callerPhoneNumber": caller_phone or None}
        trace["backendRequestCount"] += 1
        LOGGER.debug(
            "backend_ws_request sequence=%s kind=start payload=%s",
            trace["backendRequestCount"],
            {"type": "start", "callerPhoneNumber": _masked_phone(caller_phone)},
        )
        await chat.send(json.dumps(start_payload))
        receiver = asyncio.create_task(_forward_from_chat(chat, browser, trace))
        LOGGER.info("local_voice_call_connected caller_phone=%s", _masked_phone(caller_phone))
        while True:
            incoming = await browser.receive()
            if incoming["type"] == "websocket.disconnect":
                break
            if incoming.get("bytes") is not None:
                frame = incoming["bytes"]
                if frame:
                    await chat.send(frame)
                    trace["backendRequestCount"] += 1
                    trace["callerAudioFrameCount"] += 1
                    trace["callerAudioBytes"] += len(frame)
                    LOGGER.debug(
                        "backend_ws_request call_id=%s sequence=%s kind=caller_pcm bytes=%s frame_count=%s total_audio_bytes=%s",
                        trace.get("callId"),
                        trace["backendRequestCount"],
                        len(frame),
                        trace["callerAudioFrameCount"],
                        trace["callerAudioBytes"],
                    )
                continue
            if incoming.get("text"):
                control = json.loads(incoming["text"])
                if control.get("type") == "stop":
                    trace["backendRequestCount"] += 1
                    LOGGER.debug(
                        "backend_ws_request call_id=%s sequence=%s kind=stop payload=%s",
                        trace.get("callId"),
                        trace["backendRequestCount"],
                        {"type": "stop"},
                    )
                    await chat.send(json.dumps({"type": "stop"}))
                    break
    except (HTTPException, ValueError, json.JSONDecodeError) as exc:
        detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
        LOGGER.warning("local_voice_call_configuration_error detail=%s", detail)
        await browser.send_json({"type": "error", "message": str(detail)})
    except ConnectionClosed as exc:
        LOGGER.warning("chat_voice_stream_closed code=%s reason=%s", exc.code, exc.reason)
        await browser.send_json({"type": "error", "message": f"Chat voice stream closed ({exc.code})."})
    except WebSocketDisconnect:
        LOGGER.info("local_voice_browser_disconnected")
    except Exception as exc:
        LOGGER.exception("local_voice_call_failed type=%s", exc.__class__.__name__)
        await browser.send_json({"type": "error", "message": f"Local voice relay failed: {exc.__class__.__name__}. Inspect the server console."})
    finally:
        if receiver:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        if chat:
            await chat.close()
        LOGGER.info(
            "local_voice_call_closed call_id=%s backend_requests=%s backend_responses=%s caller_frames=%s caller_audio_bytes=%s agent_frames=%s agent_audio_bytes=%s",
            trace.get("callId"),
            trace["backendRequestCount"],
            trace["backendResponseCount"],
            trace["callerAudioFrameCount"],
            trace["callerAudioBytes"],
            trace["agentAudioFrameCount"],
            trace["agentAudioBytes"],
        )

"""Restricted admin read APIs for voice call metadata."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.api.envelope import fail, ok
from app.config import settings
from app.store import store

router = APIRouter(prefix="/api/admin/voice", tags=["voice-admin"])


def require_admin(authorization: Annotated[str | None, Header(alias="authorization")] = None) -> bool:
    """Reuse the demo admin bearer token without exposing it to clients."""

    if not settings.test_admin_token.strip() or authorization != f"Bearer {settings.test_admin_token}":
        fail(401, "UNAUTHENTICATED", "Admin credentials are required.")
    return True


@router.get("/call-sessions")
def list_call_sessions(
    _: Annotated[bool, Depends(require_admin)],
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, object]:
    """Return recent call metadata; recording locations remain server-only."""

    records = store.list_voice_call_sessions(limit)
    items = [
        {
            "callId": item.get("callId"),
            "startedAt": item.get("startedAt"),
            "durationSeconds": item.get("durationSeconds"),
            "verificationOutcome": item.get("verificationOutcome"),
            "disposition": item.get("disposition"),
            "escalated": item.get("escalated"),
            "supportTicketNumber": item.get("supportTicketNumber"),
            "recordingStored": bool(item.get("recordingS3Bucket") and item.get("recordingS3Key")),
            "transcriptSummary": item.get("transcriptSummary"),
        }
        for item in records
    ]
    return ok({"items": items})


@router.get("/call-sessions/{call_id}/transcript")
def get_call_transcript(call_id: str, _: Annotated[bool, Depends(require_admin)]) -> dict[str, object]:
    """Return the persisted text transcript for an admin without recording location or caller ANI."""

    call = store.find_voice_call_session(call_id)
    if not call:
        fail(404, "VOICE_CALL_NOT_FOUND", "Voice call session was not found.")
    session_id = call.get("chatSessionId")
    messages = store.list_messages(str(session_id), limit=200) if session_id else []
    items = [
        {"role": message.get("role"), "content": message.get("content"), "createdAt": message.get("createdAt")}
        for message in messages
        if message.get("role") in {"user", "assistant"}
    ]
    return ok({"callId": call_id, "disposition": call.get("disposition"), "items": items})
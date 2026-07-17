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
            "transcriptSummary": item.get("transcriptSummary"),
        }
        for item in records
    ]
    return ok({"items": items})
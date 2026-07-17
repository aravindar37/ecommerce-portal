"""Internal Core Service APIs for trusted service-to-service writes."""

from __future__ import annotations

from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.envelope import fail, ok
from app.dependencies import require_chat_service
from app.models import AgentToolAuditLogRequest, InternalActivityEventRequest, VerifyCallerRequest
from app.store import store

router = APIRouter(prefix="/api/internal", tags=["internal"])

_VERIFY_WINDOW_SECONDS = 900
_VERIFY_MAX_ATTEMPTS = 5
_verification_attempts: dict[str, tuple[float, int]] = {}


def enforce_verification_limit(key: str) -> None:
    """Apply a fixed-window limit without disclosing account existence."""

    now = monotonic()
    started_at, count = _verification_attempts.get(key, (now, 0))
    if now - started_at >= _VERIFY_WINDOW_SECONDS:
        started_at, count = now, 0
    if count >= _VERIFY_MAX_ATTEMPTS:
        fail(429, "TOO_MANY_ATTEMPTS", "Too many verification attempts. Please try again later.")
    _verification_attempts[key] = (started_at, count + 1)


@router.post("/agent-audit-logs", status_code=status.HTTP_201_CREATED)
def create_agent_audit_log(
    payload: AgentToolAuditLogRequest,
    _: Annotated[bool, Depends(require_chat_service)],
) -> dict[str, object]:
    """Persist one agent tool audit log from Chat Service."""

    return ok(store.add_audit_log(payload.model_dump()))


@router.get("/users/by-phone")
def user_by_phone(
    phone: Annotated[str, Query(pattern=r"^\+[1-9]\d{1,14}$")],
    _: Annotated[bool, Depends(require_chat_service)],
) -> dict[str, object]:
    """Return minimal ANI context for one verified phone-number owner."""

    user = store.find_verified_user_by_phone(phone)
    if not user:
        fail(404, "USER_NOT_FOUND", "Caller was not found.")
    return ok({"userId": user["_id"], "name": user.get("name"), "phoneVerified": True})


@router.post("/callers/verify")
def verify_caller(
    payload: VerifyCallerRequest,
    _: Annotated[bool, Depends(require_chat_service)],
) -> dict[str, object]:
    """Perform generic, rate-limited hard verification for a voice caller."""

    enforce_verification_limit(f"order:{payload.orderNumber.strip().lower()}")
    if payload.callerPhoneNumber:
        enforce_verification_limit(f"phone:{payload.callerPhoneNumber}")
    user_id = store.verify_caller_by_order(payload.orderNumber, payload.lastName, payload.postalCode)
    return ok({"verified": bool(user_id), "userId": user_id})


@router.post("/voice-activity-events", status_code=status.HTTP_201_CREATED)
def create_voice_activity_event(
    payload: InternalActivityEventRequest,
    _: Annotated[bool, Depends(require_chat_service)],
) -> dict[str, object]:
    """Record server-generated voice lifecycle events without browser cookies."""

    user = store.find_user_by_id(payload.userId) if payload.userId else None
    return ok(store.add_activity(payload.eventType, payload.metadata, user, None))

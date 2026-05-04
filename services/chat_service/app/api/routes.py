"""Chat Service health and assistant routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, status

from app.agents.shopping import shopping_agent
from app.agents.support import support_agent
from app.api.envelope import fail, ok
from app.config import settings
from app.database import mongo
from app.dependencies import require_user_context
from app.llm.client import llm_client
from app.mcp.client import mcp_client
from app.models import ConfirmActionRequest, ShoppingMessageRequest, ShoppingSessionRequest, SupportMessageRequest, SupportSessionRequest
from app.store import store

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health() -> dict[str, object]:
    """Return Chat Service readiness metadata."""

    mcp = mcp_client.readiness()
    return ok(
        {
            "service": "chat",
            "backend": {"runtime": "python", "framework": "fastapi"},
            "llm": llm_client.metadata(),
            "mcp": mcp,
            "database": mongo.health(),
            "ready": bool(mcp["enabled"] and mcp["ready"]),
        }
    )


@router.post("/assistant/shopping/sessions", status_code=status.HTTP_201_CREATED)
def create_shopping_session(payload: ShoppingSessionRequest, request: Request) -> dict[str, object]:
    """Create a shopping assistant session."""

    context = require_user_context(request)
    session = shopping_agent.create_session(context, payload.entryPoint, payload.productId)
    return ok(session)


@router.get("/assistant/shopping/sessions")
def latest_shopping_session(request: Request) -> dict[str, object]:
    """Return the latest active shopping assistant session for the signed-in user."""

    context = require_user_context(request)
    session = store.latest_session(context.user["_id"], "shopping")
    return ok({"session": session})


@router.get("/assistant/shopping/sessions/history")
def list_shopping_sessions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    before: str | None = None,
) -> dict[str, object]:
    """Return paginated shopping assistant session history."""

    context = require_user_context(request)
    return ok(store.list_sessions(context.user["_id"], "shopping", limit, before))


@router.get("/assistant/shopping/sessions/{session_id}/messages")
def list_shopping_messages(
    session_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, object]:
    """Return messages for an owned shopping assistant session."""

    context = require_user_context(request)
    session = store.find_session(session_id, context.user["_id"], "shopping")
    if not session:
        fail(404, "CHAT_SESSION_NOT_FOUND", "Shopping assistant session was not found.")
    return ok({"items": store.list_messages(session_id, limit)})


@router.post("/assistant/shopping/messages")
def shopping_message(payload: ShoppingMessageRequest, request: Request) -> dict[str, object]:
    """Handle a shopping assistant message."""

    context = require_user_context(request)
    try:
        reply = shopping_agent.answer(context, payload.sessionId, payload.message, payload.context)
    except ValueError as exc:
        if str(exc) == "CHAT_SESSION_NOT_FOUND":
            fail(404, "CHAT_SESSION_NOT_FOUND", "Shopping assistant session was not found.")
        raise
    return ok(reply)


@router.post("/assistant/support/sessions", status_code=status.HTTP_201_CREATED)
def create_support_session(payload: SupportSessionRequest, request: Request) -> dict[str, object]:
    """Create a support assistant session."""

    context = require_user_context(request)
    session = support_agent.create_session(context, payload.orderId)
    return ok(session)


@router.get("/assistant/support/sessions")
def latest_support_session(request: Request) -> dict[str, object]:
    """Return the latest active support assistant session for the signed-in user."""

    context = require_user_context(request)
    session = store.latest_session(context.user["_id"], "returns_support")
    return ok({"session": session})


@router.get("/assistant/support/sessions/history")
def list_support_sessions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    before: str | None = None,
) -> dict[str, object]:
    """Return paginated support assistant session history."""

    context = require_user_context(request)
    return ok(store.list_sessions(context.user["_id"], "returns_support", limit, before))


@router.get("/assistant/support/sessions/{session_id}/messages")
def list_support_messages(
    session_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, object]:
    """Return messages for an owned support assistant session."""

    context = require_user_context(request)
    session = store.find_session(session_id, context.user["_id"], "returns_support")
    if not session:
        fail(404, "CHAT_SESSION_NOT_FOUND", "Support assistant session was not found.")
    return ok({"items": store.list_messages(session_id, limit)})


@router.post("/assistant/support/messages")
def support_message(payload: SupportMessageRequest, request: Request) -> dict[str, object]:
    """Handle a support assistant message."""

    context = require_user_context(request)
    try:
        reply = support_agent.answer(context, payload.sessionId, payload.message, payload.context)
    except ValueError as exc:
        if str(exc) == "CHAT_SESSION_NOT_FOUND":
            fail(404, "CHAT_SESSION_NOT_FOUND", "Support assistant session was not found.")
        raise
    return ok(reply)


@router.post("/assistant/actions/confirm")
def confirm_action(payload: ConfirmActionRequest, request: Request) -> dict[str, object]:
    """Confirm or cancel a pending assistant action."""

    context = require_user_context(request)
    action = store.find_action(payload.actionId, context.user["_id"])
    if not action:
        fail(404, "ACTION_NOT_FOUND", "Pending action was not found.")
    if action["status"] != "pending":
        fail(409, "ACTION_ALREADY_RESOLVED", "Pending action has already been resolved.")
    if not payload.confirm:
        cancelled = store.complete_action(action, "cancelled", {"confirmed": False})
        return ok({"status": cancelled["status"], "actionId": cancelled["_id"]})
    if action["type"] == "create_return_request":
        if payload.reason:
            action["payload"]["reason"] = payload.reason
        if payload.condition:
            action["payload"]["condition"] = payload.condition
        if payload.resolution:
            action["payload"]["resolution"] = payload.resolution
        action["payload"]["requiresDetails"] = not all(
            [action["payload"].get("reason"), action["payload"].get("condition"), action["payload"].get("resolution")]
        )
        if action["payload"]["requiresDetails"]:
            fail(400, "RETURN_DETAILS_REQUIRED", "Reason, item condition, and preferred resolution are required.")
    if action["type"] == "add_to_cart":
        return ok(shopping_agent.confirm_action(context, action))
    if action["type"] == "create_return_request":
        return ok(support_agent.confirm_action(context, action))
    fail(400, "UNSUPPORTED_ACTION", "Assistant action type is not supported.")

"""Request dependencies for Chat Service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.api.envelope import fail
from app.config import settings
from app.http import ServiceHttpError, build_url, request_json, unwrap_envelope


@dataclass(frozen=True)
class ChatContext:
    """Authenticated request context passed to agents/tools."""

    user: dict[str, Any]
    cookie_header: str


def cookie_header_from_request(request: Request) -> str:
    """Serialize incoming cookies for forwarding to Core/Search."""

    return "; ".join(f"{key}={value}" for key, value in request.cookies.items())


def require_user_context(request: Request) -> ChatContext:
    """Validate Core-issued session and return user context."""

    cookie_header = cookie_header_from_request(request)
    if not cookie_header:
        fail(401, "UNAUTHENTICATED", "Authentication is required for assistant workflows.")
    try:
        envelope = request_json(
            "GET",
            build_url(settings.core_service_base_url, "/api/me"),
            headers={"cookie": cookie_header},
            timeout_seconds=10,
        )
        user = unwrap_envelope(envelope)
    except ServiceHttpError as exc:
        if exc.status_code in {401, 403}:
            fail(401, "UNAUTHENTICATED", "Core session is invalid.")
        fail(502, "CORE_SESSION_VALIDATION_FAILED", str(exc))
    if not isinstance(user, dict) or not user.get("_id"):
        fail(401, "UNAUTHENTICATED", "Core session is invalid.")
    return ChatContext(user=user, cookie_header=cookie_header)

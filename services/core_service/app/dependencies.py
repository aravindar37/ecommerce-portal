"""Shared FastAPI dependencies for Core Service routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import Cookie, Header, Request, Response

from app.api.envelope import fail
from app.config import settings
from app.security import is_configured_secret
from app.store import Json, store

SESSION_COOKIE_NAME = "core_session"
ANONYMOUS_COOKIE_NAME = "core_anonymous_id"


def issue_anonymous_id(response: Response, current_value: str | None) -> str:
    """Return an anonymous visitor ID, setting a cookie when needed."""

    if current_value:
        return current_value
    anonymous_id = uuid.uuid4().hex
    response.set_cookie(
        ANONYMOUS_COOKIE_NAME,
        anonymous_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return anonymous_id


def current_user_optional(
    core_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> Json | None:
    """Resolve the current user when a valid session cookie is present."""

    return store.user_for_session_token(core_session)


def current_user_required(
    core_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> Json:
    """Resolve the current user or return an authentication envelope."""

    user = store.user_for_session_token(core_session)
    if not user:
        fail(401, "UNAUTHENTICATED", "Authentication is required for this operation.")
    return user


def current_session_token(
    core_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str | None:
    """Return the raw session token from the request cookie."""

    return core_session


def anonymous_id_from_request(request: Request, response: Response) -> str:
    """Read or create the anonymous visitor cookie used for carts/activity."""

    return issue_anonymous_id(response, request.cookies.get(ANONYMOUS_COOKIE_NAME))


def require_admin(
    authorization: Annotated[str | None, Header(alias="authorization")] = None,
) -> bool:
    """Validate the restricted admin/test bearer credential."""

    expected = f"Bearer {settings.test_admin_token}"
    if not is_configured_secret(settings.test_admin_token) or authorization != expected:
        fail(401, "UNAUTHENTICATED", "Admin credentials are required.")
    return True


def require_chat_service(
    x_service_token: Annotated[str | None, Header(alias="x-service-token")] = None,
) -> bool:
    """Validate Chat Service internal API calls."""

    if not is_configured_secret(settings.chat_service_internal_token) or x_service_token != settings.chat_service_internal_token:
        fail(401, "UNAUTHENTICATED", "Chat Service credentials are required.")
    return True


def current_user_or_on_behalf(
    core_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    x_service_token: Annotated[str | None, Header(alias="x-service-token")] = None,
    x_on_behalf_of_user_id: Annotated[str | None, Header(alias="x-on-behalf-of-user-id")] = None,
) -> Json:
    """Resolve a cookie user or a Chat-Service-authenticated verified user.

    The internal mode is deliberately all-or-nothing: both headers must be
    present and the service token must be valid. The resolved user is then
    passed through the same ownership checks as browser-authenticated users.
    """

    user = store.user_for_session_token(core_session)
    if user:
        return user
    if x_service_token or x_on_behalf_of_user_id:
        if not (
            is_configured_secret(settings.chat_service_internal_token)
            and x_service_token == settings.chat_service_internal_token
            and x_on_behalf_of_user_id
        ):
            fail(401, "UNAUTHENTICATED", "Chat Service credentials are required.")
        user = store.find_user_by_id(x_on_behalf_of_user_id)
        if user:
            return user
    fail(401, "UNAUTHENTICATED", "Authentication is required for this operation.")


def redact_sensitive(value: Any) -> Any:
    """Recursively remove sensitive values from admin-facing payloads."""

    sensitive_fragments = ("api_key", "apikey", "secret", "password", "token", "authorization")
    if isinstance(value, dict):
        return {
            key: redact_sensitive(item)
            for key, item in value.items()
            if not any(fragment in key.lower() for fragment in sensitive_fragments)
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value

"""Authentication and identity routes."""

from __future__ import annotations

import secrets
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Query, Response, status
from starlette.responses import Response as StarletteResponse
from fastapi.responses import RedirectResponse

from app.api.envelope import fail, ok
from app.config import settings
from app.dependencies import SESSION_COOKIE_NAME, current_session_token, current_user_required
from app.models import LoginRequest, PasswordResetConfirmRequest, PasswordResetRequest, RegisterRequest, SavePreferenceRequest
from app.security import is_configured_secret
from app.store import Json, store

router = APIRouter(prefix="/api", tags=["auth"])


def google_redirect_uri() -> str:
    """Return the configured Google OAuth callback URL."""

    return settings.google_redirect_uri or f"{settings.app_base_url.rstrip('/')}/api/core/auth/google/callback"


def exchange_google_code(code: str) -> Json:
    """Exchange a Google OAuth code for user profile data."""

    token_payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    token_request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=token_payload,
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded", "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(token_request, timeout=15) as response:
            token_data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        fail(502, "GOOGLE_OAUTH_TOKEN_EXCHANGE_FAILED", f"Google OAuth token exchange failed: {exc}")
    access_token = token_data.get("access_token") if isinstance(token_data, dict) else None
    if not access_token:
        fail(502, "GOOGLE_OAUTH_TOKEN_EXCHANGE_FAILED", "Google OAuth token exchange did not return an access token.")
    user_request = urllib.request.Request(
        "https://openidconnect.googleapis.com/v1/userinfo",
        method="GET",
        headers={"authorization": f"Bearer {access_token}", "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(user_request, timeout=15) as response:
            user_data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        fail(502, "GOOGLE_OAUTH_PROFILE_FAILED", f"Google profile lookup failed: {exc}")
    if not isinstance(user_data, dict) or not user_data.get("email"):
        fail(502, "GOOGLE_OAUTH_PROFILE_FAILED", "Google profile did not include an email address.")
    return user_data


def set_session_cookie(response: Response, token: str) -> None:
    """Attach the session cookie to a login response."""

    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_cookie_max_age_seconds,
    )


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> dict[str, object]:
    """Create a password-backed customer identity."""

    try:
        user = store.register_user(payload.email, payload.password, payload.name)
    except ValueError as exc:
        if str(exc) == "EMAIL_ALREADY_EXISTS":
            fail(409, "EMAIL_ALREADY_EXISTS", "An account already exists for this email.")
        raise
    return ok(user)


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, object]:
    """Authenticate a password user and create a session."""

    try:
        user, token = store.login_user(payload.email, payload.password)
    except ValueError as exc:
        if str(exc) == "INVALID_CREDENTIALS":
            fail(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
        raise
    set_session_cookie(response, token)
    return ok({"user": user})


@router.get("/me")
def me(user: Annotated[Json, Depends(current_user_required)]) -> dict[str, object]:
    """Return the current authenticated user."""

    return ok(store.public_user(user))


@router.patch("/me/preferences")
def save_preference(
    payload: SavePreferenceRequest,
    user: Annotated[Json, Depends(current_user_required)],
) -> dict[str, object]:
    """Save one customer preference."""

    return ok(store.update_user_preference(user["_id"], payload.key, payload.value))


@router.post("/auth/logout")
def logout(
    response: Response,
    session_token: Annotated[str | None, Depends(current_session_token)],
) -> dict[str, object]:
    """Invalidate the current session."""

    store.logout(session_token)
    response.delete_cookie(SESSION_COOKIE_NAME, secure=settings.cookie_secure, samesite="lax")
    return ok({"loggedOut": True})


@router.get("/auth/google/start", response_model=None)
def google_start() -> StarletteResponse:
    """Start Google OAuth when enabled outside local development."""

    if (
        settings.app_env == "development"
        or not settings.auth_google_enabled
        or not is_configured_secret(settings.google_client_id)
        or not is_configured_secret(settings.google_client_secret)
    ):
        fail(404, "GOOGLE_OAUTH_DISABLED", "Google OAuth is disabled for this environment.")
    state = secrets.token_urlsafe(24)
    params = urllib.parse.urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": google_redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
    )
    redirect = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}", status_code=status.HTTP_302_FOUND)
    redirect.set_cookie("google_oauth_state", state, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=600)
    return redirect


@router.get("/auth/google/callback")
def google_callback(
    response: Response,
    state: Annotated[str, Query(min_length=1)],
    code: Annotated[str, Query(min_length=1)],
    google_oauth_state: Annotated[str | None, Cookie()] = None,
) -> dict[str, object]:
    """Complete Google OAuth callback for hosted demos."""

    if not code or not state:
        fail(400, "GOOGLE_OAUTH_INVALID_CALLBACK", "Google OAuth callback is missing required parameters.")
    if not google_oauth_state or not secrets.compare_digest(google_oauth_state, state):
        fail(400, "GOOGLE_OAUTH_STATE_MISMATCH", "Google OAuth state validation failed.")
    profile = exchange_google_code(code)
    public_user = store.upsert_google_user(str(profile["email"]), str(profile.get("name") or profile["email"]), profile.get("picture"))
    user = store.find_user_by_id(public_user["_id"])
    if not user:
        fail(500, "GOOGLE_OAUTH_USER_CREATE_FAILED", "Unable to create Google user.")
    token = store.create_session_for_user(user)
    set_session_cookie(response, token)
    response.delete_cookie("google_oauth_state", secure=settings.cookie_secure, samesite="lax")
    return ok({"user": public_user})


@router.post("/auth/password-reset/request")
def password_reset_request(payload: PasswordResetRequest) -> dict[str, object]:
    """Use safe response semantics for password reset requests."""

    normalized_email = payload.email.strip().lower()
    token = store.create_password_reset_token(normalized_email)
    data: dict[str, object] = {"accepted": True, "email": normalized_email}
    if settings.app_env == "development" and token:
        data["resetToken"] = token
    return ok(data)


@router.post("/auth/password-reset/confirm")
def password_reset_confirm(payload: PasswordResetConfirmRequest) -> dict[str, object]:
    """Consume a password reset token and update the password."""

    try:
        user = store.reset_password(payload.token, payload.password)
    except ValueError as exc:
        if str(exc) == "INVALID_RESET_TOKEN":
            fail(400, "INVALID_RESET_TOKEN", "Password reset token is invalid or expired.")
        raise
    return ok({"accepted": True, "user": user})

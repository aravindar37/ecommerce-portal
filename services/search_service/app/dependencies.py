"""Authentication and service-token helpers for Search Service."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Header, Request

from app.api.envelope import fail
from app.config import settings


@dataclass(frozen=True)
class SearchPrincipal:
    """Resolved request principal for Search Service."""

    user: dict[str, Any] | None
    service_authenticated: bool


def validate_service_token(x_service_token: Annotated[str | None, Header(alias="x-service-token")] = None) -> bool:
    """Validate service-to-service credential when configured."""

    if not settings.core_service_internal_token:
        return False
    return x_service_token == settings.core_service_internal_token


def resolve_core_session(request: Request) -> dict[str, Any] | None:
    """Validate a Core-issued session cookie and return the user if present."""

    session_cookie = request.cookies.get("core_session")
    if not session_cookie:
        return None
    url = f"{settings.core_service_base_url.rstrip('/')}/api/me"
    core_request = urllib.request.Request(url=url, method="GET", headers={"accept": "application/json", "cookie": f"core_session={session_cookie}"})
    try:
        with urllib.request.urlopen(core_request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            fail(401, "UNAUTHENTICATED", "Core session is invalid.")
        fail(502, "CORE_SESSION_VALIDATION_FAILED", f"Core session validation failed with HTTP {exc.code}.")
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        fail(502, "CORE_SESSION_VALIDATION_FAILED", f"Core session validation failed: {exc}")
    if not isinstance(payload, dict) or payload.get("error"):
        fail(401, "UNAUTHENTICATED", "Core session is invalid.")
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def resolve_principal(
    request: Request,
    x_service_token: Annotated[str | None, Header(alias="x-service-token")] = None,
) -> SearchPrincipal:
    """Resolve authenticated user or trusted service context."""

    return SearchPrincipal(user=resolve_core_session(request), service_authenticated=validate_service_token(x_service_token))

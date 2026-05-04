"""Core Service security helpers."""

from __future__ import annotations

from time import monotonic
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

PLACEHOLDER_PREFIXES = ("replace-with-", "<", "changeme", "example-")


def is_configured_secret(value: str) -> bool:
    """Return whether a configured secret is usable."""

    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    return not any(lowered.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def parse_cors_origins(value: str) -> list[str]:
    """Parse comma-separated CORS origins."""

    return [origin.strip() for origin in value.split(",") if origin.strip()]


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-client fixed-window rate limiter for local demo services."""

    def __init__(
        self,
        app: Callable[..., object],
        path_prefixes: tuple[str, ...],
        requests_per_minute: int,
        counted_status_codes: tuple[int, ...] | None = None,
    ) -> None:
        super().__init__(app)
        self.path_prefixes = path_prefixes
        self.requests_per_minute = requests_per_minute
        self.counted_status_codes = counted_status_codes
        self.window: dict[str, tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next: Callable[[Request], object]) -> Response:
        """Reject requests that exceed the configured fixed window."""

        if self.requests_per_minute <= 0 or not request.url.path.startswith(self.path_prefixes):
            response = await call_next(request)
            return response
        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{request.url.path}"
        now = monotonic()
        window_started, count = self.window.get(key, (now, 0))
        if now - window_started >= 60:
            window_started = now
            count = 0
        if count >= self.requests_per_minute:
            return Response(
                content='{"data":null,"error":{"code":"RATE_LIMITED","message":"Too many requests"},"meta":{}}',
                status_code=429,
                media_type="application/json",
            )
        response = await call_next(request)
        if self.counted_status_codes is not None and response.status_code not in self.counted_status_codes:
            return response
        count += 1
        self.window[key] = (window_started, count)
        return response

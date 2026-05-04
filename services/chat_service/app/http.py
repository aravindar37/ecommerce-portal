"""Small stdlib HTTP helper for service-to-service calls."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.observability import compact, logger, redact

Json = dict[str, Any]


class ServiceHttpError(Exception):
    """Raised when a service call fails."""

    def __init__(self, status_code: int, message: str, payload: Json | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def decode_body(body: bytes) -> Json:
    """Decode a JSON object response body."""

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ServiceHttpError(502, f"Service returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ServiceHttpError(502, "Service returned non-object JSON")
    return payload


def request_json(
    method: str,
    url: str,
    payload: Json | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 30,
) -> Json:
    """Make an HTTP request and decode the service envelope."""

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"accept": "application/json", **(headers or {})}
    if payload is not None:
        request_headers["content-type"] = "application/json"
    request = urllib.request.Request(url=url, data=data, method=method, headers=request_headers)
    logger.debug("service.request method=%s url=%s payload=%s headers=%s", method, url, compact(payload), compact(request_headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            decoded = decode_body(response.read())
            logger.debug("service.response method=%s url=%s status=%s body=%s", method, url, response.status, compact(decoded))
            return decoded
    except urllib.error.HTTPError as exc:
        body = exc.read()
        decoded = decode_body(body) if body else {}
        logger.debug("service.response method=%s url=%s status=%s body=%s", method, url, exc.code, compact(decoded))
        raise ServiceHttpError(exc.code, f"Service returned HTTP {exc.code}", decoded) from exc
    except urllib.error.URLError as exc:
        logger.debug("service.error method=%s url=%s error=%s", method, url, redact(str(exc)))
        raise ServiceHttpError(502, f"Service request failed: {exc}") from exc


def build_url(base_url: str, path: str, query: dict[str, Any] | None = None) -> str:
    """Build a service URL with optional query params."""

    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if not query:
        return url
    encoded = urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
    return f"{url}?{encoded}" if encoded else url


def unwrap_envelope(envelope: Json) -> Any:
    """Return envelope data or raise for an error envelope."""

    if envelope.get("error"):
        error = envelope["error"] if isinstance(envelope["error"], dict) else {}
        raise ServiceHttpError(502, str(error.get("message") or "Service returned an error"), envelope)
    return envelope.get("data")

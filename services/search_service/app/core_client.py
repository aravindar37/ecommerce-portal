"""Core Service client helpers used by Search Service."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.config import SearchServiceSettings, settings

Json = dict[str, Any]


class CoreClientError(Exception):
    """Raised when Core Service calls fail."""


class CoreClient:
    """Small stdlib HTTP client for Core Service activity writes."""

    def __init__(self, config: SearchServiceSettings) -> None:
        self.config = config

    def post_activity_event(self, event_type: str, metadata: Json) -> bool:
        """Write a user activity event to Core Service."""

        url = f"{self.config.core_service_base_url.rstrip('/')}/api/activity-events"
        encoded = json.dumps({"eventType": event_type, "metadata": metadata}).encode("utf-8")
        headers = {"content-type": "application/json", "accept": "application/json"}
        if self.config.core_service_internal_token:
            headers["x-service-token"] = self.config.core_service_internal_token
        request = urllib.request.Request(url=url, data=encoded, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            raise CoreClientError(f"Core activity event failed with HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise CoreClientError(f"Core activity event request failed: {exc}") from exc
        return 200 <= status < 300


core_client = CoreClient(settings)

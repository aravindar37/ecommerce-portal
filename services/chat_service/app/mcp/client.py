"""Mandatory local Codex MCP client facade."""

from __future__ import annotations

import shutil
import json
import urllib.error
import urllib.request
from typing import Any

from app.config import ChatServiceSettings, settings
from app.observability import compact, logger

Json = dict[str, Any]


class CodexMcpClient:
    """Local Codex MCP readiness and workflow facade.

    The demo exposes ecommerce-safe tool plans locally; live MCP transport can
    be wired behind this facade without changing agent route behavior.
    """

    def __init__(self, config: ChatServiceSettings) -> None:
        self.config = config

    def readiness(self) -> Json:
        """Return mandatory MCP readiness metadata."""

        if not self.config.codex_mcp_enabled:
            result = {
                "enabled": False,
                "ready": False,
                "transport": self.config.codex_mcp_transport,
                "command": None,
                "urlConfigured": False,
                "reason": "CODEX_MCP_ENABLED is false",
            }
            logger.debug("mcp.readiness result=%s", compact(result))
            return result
        if self.config.codex_mcp_transport == "stdio":
            command_path = shutil.which(self.config.codex_mcp_command)
            result = {
                "enabled": True,
                "ready": bool(command_path and self.config.codex_mcp_args.strip()),
                "transport": self.config.codex_mcp_transport,
                "command": self.config.codex_mcp_command,
                "commandPath": command_path,
                "urlConfigured": False,
            }
            logger.debug("mcp.readiness result=%s", compact(result))
            return result
        http_ready = self.http_ready()
        result = {
            "enabled": True,
            "ready": http_ready,
            "transport": self.config.codex_mcp_transport,
            "command": None,
            "urlConfigured": bool(self.config.codex_mcp_url),
        }
        logger.debug("mcp.readiness result=%s", compact(result))
        return result

    def http_ready(self) -> bool:
        """Check an HTTP MCP endpoint without exposing response contents."""

        if not self.config.codex_mcp_url.strip():
            return False
        request = urllib.request.Request(self.config.codex_mcp_url, method="GET", headers={"accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=max(self.config.codex_mcp_timeout_ms / 1000, 1)) as response:
                return 200 <= response.status < 500
        except (urllib.error.URLError, TimeoutError):
            return False

    def plan_support_return(self, order_id: str, order_item_id: str) -> Json:
        """Plan a support return workflow through ecommerce-safe tools."""

        if self.config.codex_mcp_enabled and self.config.codex_mcp_transport == "http" and self.http_ready():
            payload = {"tool": "planReturnWorkflow", "input": {"orderId": order_id, "orderItemId": order_item_id}}
            request = urllib.request.Request(
                self.config.codex_mcp_url.rstrip("/") + "/tools/execute",
                method="POST",
                headers={"accept": "application/json", "content-type": "application/json"},
                data=json.dumps(payload).encode("utf-8"),
            )
            try:
                with urllib.request.urlopen(request, timeout=max(self.config.codex_mcp_timeout_ms / 1000, 1)) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                    logger.debug("mcp.plan_support_return liveHttp orderId=%s response=%s", order_id, compact(parsed))
                    return parsed if isinstance(parsed, dict) else self._static_plan(order_id, order_item_id)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                logger.debug("mcp.plan_support_return liveHttpFallback orderId=%s error=%s", order_id, str(exc))
        plan = self._static_plan(order_id, order_item_id)
        logger.debug("mcp.plan_support_return orderId=%s orderItemId=%s plan=%s", order_id, order_item_id, compact(plan))
        return plan

    def _static_plan(self, order_id: str, order_item_id: str) -> Json:
        """Return the deterministic ecommerce-safe fallback plan."""

        plan = {
            "usedMcp": True,
            "workflow": "returns_support",
            "steps": [
                {"tool": "getOrder", "input": {"orderId": order_id}},
                {"tool": "checkReturnEligibility", "input": {"orderId": order_id, "orderItemId": order_item_id}},
                {"tool": "createReturnRequest", "requiresConfirmation": True},
            ],
        }
        return plan


mcp_client = CodexMcpClient(settings)

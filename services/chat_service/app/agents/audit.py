"""Agent audit helpers."""

from __future__ import annotations

from typing import Any

from app.tools.core import core_tools

Json = dict[str, Any]


def audit_tool_call(
    session_id: str,
    user_id: str,
    agent_type: str,
    tool_name: str,
    input_payload: Json,
    output_payload: Json,
    status: str = "success",
    requires_user_confirmation: bool = False,
) -> None:
    """Write an agent tool audit log through Core Service."""

    core_tools.write_audit_log(
        {
            "sessionId": session_id,
            "userId": user_id,
            "agentType": agent_type,
            "toolName": tool_name,
            "input": input_payload,
            "output": output_payload,
            "status": status,
            "requiresUserConfirmation": requires_user_confirmation,
        }
    )

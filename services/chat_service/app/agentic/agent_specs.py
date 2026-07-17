"""Agent and subagent specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .models import AgentRunContext
from .prompts import shopping_prompt, support_prompt


@dataclass(frozen=True)
class AgentSpec:
    """Declarative configuration for one domain agent."""

    agent_id: str
    display_name: str
    description: str
    session_type: str
    tool_names: tuple[str, ...]
    system_prompt_builder: Callable[[AgentRunContext], str]
    memory_scope: str
    requires_hitl_tools: tuple[str, ...] = ()
    handoff_targets: tuple[str, ...] = ()


SHOPPING_AGENT = AgentSpec(
    agent_id="shopping_assistant",
    display_name="Shopping Assistant",
    description="Product discovery, product questions, comparisons, outfit matching, and cart proposals.",
    session_type="shopping",
    tool_names=(
        "search_products",
        "get_product",
        "get_similar_products",
        "find_matching_products",
        "compare_products",
        "get_cart",
        "get_user_preferences",
        "request_add_to_cart_confirmation",
    ),
    system_prompt_builder=shopping_prompt,
    memory_scope="shopping",
    requires_hitl_tools=("request_add_to_cart_confirmation",),
)

SUPPORT_AGENT = AgentSpec(
    agent_id="returns_support",
    display_name="Returns Support",
    description="Order questions, return eligibility, return proposals, and support ticket proposals.",
    session_type="returns_support",
    tool_names=(
        "list_orders",
        "get_order",
        "check_return_eligibility",
        "get_return_policy",
        "request_create_return_confirmation",
        "request_create_support_ticket_confirmation",
    ),
    system_prompt_builder=support_prompt,
    memory_scope="support",
    requires_hitl_tools=("request_create_return_confirmation", "request_create_support_ticket_confirmation"),
)

AGENT_SPECS = {
    SHOPPING_AGENT.session_type: SHOPPING_AGENT,
    SUPPORT_AGENT.session_type: SUPPORT_AGENT,
}


def spec_for_session_type(session_type: str) -> AgentSpec:
    """Return the configured agent spec for a session type."""

    spec = AGENT_SPECS.get(session_type)
    if spec is None:
        raise ValueError(f"No agent spec configured for session type: {session_type!r}")
    return spec


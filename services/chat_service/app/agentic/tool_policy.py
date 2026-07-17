"""Agent tool classification and filtering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolPolicy:
    """Policy metadata for one tool."""

    name: str
    read_only: bool
    confirmation_required: bool = False
    admin_only: bool = False
    categories: tuple[str, ...] = ()


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "search_products": ToolPolicy("search_products", True, categories=("shopping",)),
    "get_product": ToolPolicy("get_product", True, categories=("shopping",)),
    "get_similar_products": ToolPolicy("get_similar_products", True, categories=("shopping",)),
    "find_matching_products": ToolPolicy("find_matching_products", True, categories=("shopping",)),
    "compare_products": ToolPolicy("compare_products", True, categories=("shopping",)),
    "get_cart": ToolPolicy("get_cart", True, categories=("shopping", "cart")),
    "get_user_preferences": ToolPolicy("get_user_preferences", True, categories=("shopping", "memory")),
    "list_orders": ToolPolicy("list_orders", True, categories=("support", "returns")),
    "get_order": ToolPolicy("get_order", True, categories=("support", "returns")),
    "check_return_eligibility": ToolPolicy("check_return_eligibility", True, categories=("support", "returns")),
    "get_return_policy": ToolPolicy("get_return_policy", True, categories=("support", "returns")),
    "request_add_to_cart_confirmation": ToolPolicy("request_add_to_cart_confirmation", False, True, categories=("shopping", "cart")),
    "request_create_return_confirmation": ToolPolicy("request_create_return_confirmation", False, True, categories=("support", "returns")),
    "request_create_support_ticket_confirmation": ToolPolicy(
        "request_create_support_ticket_confirmation",
        False,
        True,
        categories=("support",),
    ),
}


def policies_for_tools(tool_names: tuple[str, ...]) -> list[ToolPolicy]:
    """Return policies for a tool subset."""

    return [TOOL_POLICIES[name] for name in tool_names if name in TOOL_POLICIES]


def interrupt_on_for_tools(tool_names: tuple[str, ...]) -> list[str]:
    """Return names of tools that require human confirmation."""

    return [
        policy.name
        for policy in policies_for_tools(tool_names)
        if policy.confirmation_required
    ]


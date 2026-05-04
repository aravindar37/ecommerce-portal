"""OpenAI-compatible agent tool definitions."""

from __future__ import annotations

from typing import Any

Json = dict[str, Any]


FILTER_PROPERTIES: Json = {
    "gender": {"type": "string", "enum": ["Men", "Women", "Boys", "Girls", "Unisex"]},
    "usage": {"type": "array", "items": {"type": "string"}},
    "season": {"type": "string", "enum": ["Summer", "Winter", "Fall", "Spring"]},
    "baseColour": {"type": "string"},
    "masterCategory": {"type": "string"},
    "articleType": {"type": "string"},
    "priceMax": {"type": "number"},
}


def function_tool(name: str, description: str, properties: Json, required: list[str] | None = None) -> Json:
    """Return one OpenAI-compatible function tool definition."""

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


SHOPPING_TOOLS: list[Json] = [
    function_tool(
        "search_products",
        "Search for fashion products using a natural-language query and optional structured filters.",
        {
            "query": {"type": "string"},
            **FILTER_PROPERTIES,
            "limit": {"type": "integer", "default": 5},
        },
        ["query"],
    ),
    function_tool("get_product", "Fetch one product by ID or slug.", {"productId": {"type": "string"}}, ["productId"]),
    function_tool(
        "get_similar_products",
        "Fetch products similar to a reference product.",
        {"productId": {"type": "string"}, "limit": {"type": "integer", "default": 4}},
        ["productId"],
    ),
    function_tool(
        "find_matching_products",
        "Find products that complement a reference product, such as shoes for a shirt.",
        {
            "referenceProductId": {"type": "string"},
            "targetArticleType": {"type": "string"},
            "limit": {"type": "integer", "default": 5},
        },
        ["referenceProductId", "targetArticleType"],
    ),
    function_tool(
        "compare_products",
        "Fetch two or more products and return side-by-side attributes.",
        {"productIds": {"type": "array", "items": {"type": "string"}, "minItems": 2}},
        ["productIds"],
    ),
    function_tool("get_cart", "Return the current cart contents.", {}, []),
    function_tool(
        "add_to_cart",
        "Propose adding a product to the cart. This always requires user confirmation.",
        {"productId": {"type": "string"}, "quantity": {"type": "integer", "default": 1}, "size": {"type": "string"}},
        ["productId"],
    ),
    function_tool(
        "remove_from_cart",
        "Propose removing a cart item. This always requires user confirmation.",
        {"cartItemId": {"type": "string"}},
        ["cartItemId"],
    ),
    function_tool("get_user_preferences", "Return saved size, brand, and style preferences.", {}, []),
]


SUPPORT_TOOLS: list[Json] = [
    function_tool("list_orders", "List the user's orders with status and item summaries.", {}, []),
    function_tool("get_order", "Fetch a full order by order number or ID.", {"orderId": {"type": "string"}}, ["orderId"]),
    function_tool(
        "check_return_eligibility",
        "Check whether an order item is eligible for return.",
        {"orderId": {"type": "string"}, "orderItemId": {"type": "string"}},
        ["orderId", "orderItemId"],
    ),
    function_tool(
        "create_return_request",
        "Propose creating a return request. This always requires user confirmation.",
        {"orderId": {"type": "string"}, "orderItemId": {"type": "string"}},
        ["orderId", "orderItemId"],
    ),
    function_tool(
        "create_support_ticket",
        "Propose opening a support ticket. This always requires user confirmation.",
        {"category": {"type": "string"}, "priority": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
        ["category", "priority", "subject", "body"],
    ),
    function_tool("get_return_policy", "Return the current demo return window and resolution options.", {}, []),
]

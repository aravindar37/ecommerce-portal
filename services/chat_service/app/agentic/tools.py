"""Deep Agents-compatible ecommerce tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field as PydanticField

from app.agents.audit import audit_tool_call
from app.store import store
from app.tools.core import core_tools
from app.tools.search import search_tools

from .models import AgentRunContext
from .resilience import RetryState, with_retry

Json = dict[str, Any]


# ---------------------------------------------------------------------------
# Pydantic input schemas — one per tool that accepts arguments.
# Field names must match the inner function parameter names exactly.
# ---------------------------------------------------------------------------


class _SearchProductsInput(BaseModel):
    query: str = PydanticField(description="Natural-language search query")
    filters: dict[str, Any] = PydanticField(default_factory=dict, description="Optional catalogue filters")
    limit: int = PydanticField(default=5, ge=1, le=10, description="Max results to return")


class _GetProductInput(BaseModel):
    product_id: str = PydanticField(description="Product ID or slug")


class _GetSimilarProductsInput(BaseModel):
    product_id: str = PydanticField(description="Reference product ID")
    limit: int = PydanticField(default=4, ge=1, le=10)


class _FindMatchingProductsInput(BaseModel):
    reference_product_id: str = PydanticField(description="Reference product ID")
    target_article_type: str = PydanticField(description="Article type to find matches in, e.g. Shoes, Jeans, Watches")
    limit: int = PydanticField(default=5, ge=1, le=10)


class _CompareProductsInput(BaseModel):
    product_ids: list[str] = PydanticField(description="2–4 product IDs to compare side by side")


class _GetOrderInput(BaseModel):
    order_id: str = PydanticField(description="Order ID or order number")


class _CheckReturnEligibilityInput(BaseModel):
    order_id: str = PydanticField(description="Order ID")
    order_item_id: str = PydanticField(description="Order item ID")


class _RequestAddToCartInput(BaseModel):
    product_id: str = PydanticField(description="Product ID to add to cart")
    quantity: int = PydanticField(default=1, ge=1, description="Quantity to add")
    size: Optional[str] = PydanticField(default=None, description="Size if applicable; ask the user if unknown")


class _RequestReturnInput(BaseModel):
    order_id: str = PydanticField(description="Order ID")
    order_item_id: str = PydanticField(description="Order item ID")
    reason: str = PydanticField(default="", description="Return reason; ask if missing")
    condition: str = PydanticField(default="", description="Item condition; ask if missing")
    resolution: str = PydanticField(default="", description="Desired resolution (refund/exchange); ask if missing")


class _RequestTicketInput(BaseModel):
    category: str = PydanticField(description="Ticket category")
    priority: str = PydanticField(description="Ticket priority")
    subject: str = PydanticField(description="Short subject line")
    body: str = PydanticField(description="Full issue description")
    order_id: Optional[str] = PydanticField(default=None, description="Related order ID if applicable")


# ---------------------------------------------------------------------------
# BoundAgentTool — callable tool bound to one authenticated request context.
# ---------------------------------------------------------------------------


def compact_product(product: Json) -> Json:
    """Return a compact product for model context and API payloads."""

    return {
        "_id": product.get("_id"),
        "sourceProductId": product.get("sourceProductId"),
        "slug": product.get("slug"),
        "title": product.get("title"),
        "price": product.get("price"),
        "baseColour": product.get("baseColour"),
        "usage": product.get("usage"),
        "gender": product.get("gender"),
        "articleType": product.get("articleType"),
        "ratingAverage": product.get("ratingAverage"),
        "ratingCount": product.get("ratingCount"),
        "images": product.get("images") or [],
    }


@dataclass(frozen=True)
class BoundAgentTool:
    """Callable tool bound to one authenticated request context."""

    name: str
    description: str
    func: Callable[..., Any]
    schema: Optional[type[BaseModel]] = None

    def __call__(self, **kwargs: Any) -> Any:
        return self.func(**kwargs)

    def as_runtime_tool(self) -> Any:
        """Return a LangChain StructuredTool when available."""

        try:
            from langchain_core.tools import StructuredTool
        except Exception:
            return self
        return StructuredTool.from_function(
            func=self.func,
            name=self.name,
            description=self.description,
            args_schema=self.schema,
        )


def _audit(context: AgentRunContext, tool_name: str, input_payload: Json, output_payload: Json, status: str = "success") -> None:
    audit_tool_call(context.session_id, context.user_id, context.agent_id, tool_name, input_payload, output_payload, status=status)


def bind_tools(context: AgentRunContext, tool_names: tuple[str, ...]) -> list[Any]:
    """Return callable LangChain tools scoped to one agent run."""

    # --- inner functions (named defs for proper LangChain introspection) ---

    def _search(query: str, filters: dict[str, Any] = {}, limit: int = 5) -> list[Json]:
        return search_products(context, query, filters, int(limit))

    def _get_product(product_id: str) -> Json:
        return get_product(context, product_id)

    def _get_similar(product_id: str, limit: int = 4) -> list[Json]:
        return get_similar_products(context, product_id, int(limit))

    def _find_matching(reference_product_id: str, target_article_type: str, limit: int = 5) -> list[Json]:
        return find_matching_products(context, reference_product_id, target_article_type, int(limit))

    def _compare(product_ids: list[str]) -> Json:
        return compare_products(context, product_ids)

    def _get_cart() -> Json:
        return get_cart(context)

    def _get_prefs() -> Json:
        return get_user_preferences(context)

    def _list_orders() -> list[Json]:
        return list_orders(context)

    def _get_order(order_id: str) -> Json:
        return get_order(context, order_id)

    def _check_eligibility(order_id: str, order_item_id: str) -> Json:
        return check_return_eligibility(context, order_id, order_item_id)

    def _get_policy() -> Json:
        return get_return_policy(context)

    def _add_to_cart_confirm(product_id: str, quantity: int = 1, size: Optional[str] = None) -> Json:
        return request_add_to_cart_confirmation(context, product_id, int(quantity), size)

    def _return_confirm(
        order_id: str,
        order_item_id: str,
        reason: str = "",
        condition: str = "",
        resolution: str = "",
    ) -> Json:
        return request_create_return_confirmation(context, order_id, order_item_id, reason, condition, resolution)

    def _ticket_confirm(
        category: str,
        priority: str,
        subject: str,
        body: str,
        order_id: Optional[str] = None,
    ) -> Json:
        return request_create_support_ticket_confirmation(context, category, priority, subject, body, order_id)

    available: dict[str, BoundAgentTool] = {
        "search_products": BoundAgentTool(
            "search_products",
            "Search fashion products with a natural-language query and optional filters.",
            _search,
            _SearchProductsInput,
        ),
        "get_product": BoundAgentTool(
            "get_product",
            "Fetch one product by ID or slug.",
            _get_product,
            _GetProductInput,
        ),
        "get_similar_products": BoundAgentTool(
            "get_similar_products",
            "Fetch products similar to a reference product.",
            _get_similar,
            _GetSimilarProductsInput,
        ),
        "find_matching_products": BoundAgentTool(
            "find_matching_products",
            "Find products that complement a reference product, such as shoes for a shirt.",
            _find_matching,
            _FindMatchingProductsInput,
        ),
        "compare_products": BoundAgentTool(
            "compare_products",
            "Compare products side by side.",
            _compare,
            _CompareProductsInput,
        ),
        "get_cart": BoundAgentTool("get_cart", "Return the current cart contents.", _get_cart),
        "get_user_preferences": BoundAgentTool("get_user_preferences", "Return saved user preferences.", _get_prefs),
        "list_orders": BoundAgentTool("list_orders", "List the user's orders.", _list_orders),
        "get_order": BoundAgentTool(
            "get_order",
            "Fetch one owned order by ID.",
            _get_order,
            _GetOrderInput,
        ),
        "check_return_eligibility": BoundAgentTool(
            "check_return_eligibility",
            "Check whether an order item is eligible for return.",
            _check_eligibility,
            _CheckReturnEligibilityInput,
        ),
        "get_return_policy": BoundAgentTool("get_return_policy", "Return the current return policy.", _get_policy),
        "request_add_to_cart_confirmation": BoundAgentTool(
            "request_add_to_cart_confirmation",
            "Create a pending add-to-cart confirmation. Does not mutate the cart until the user confirms.",
            _add_to_cart_confirm,
            _RequestAddToCartInput,
        ),
        "request_create_return_confirmation": BoundAgentTool(
            "request_create_return_confirmation",
            "Create a pending return confirmation. Does not create a return until the user confirms.",
            _return_confirm,
            _RequestReturnInput,
        ),
        "request_create_support_ticket_confirmation": BoundAgentTool(
            "request_create_support_ticket_confirmation",
            "Create a pending support-ticket confirmation. Does not open a ticket until the user confirms.",
            _ticket_confirm,
            _RequestTicketInput,
        ),
    }
    return [available[name].as_runtime_tool() for name in tool_names if name in available]


# ---------------------------------------------------------------------------
# Tool implementations (module-level, called by the inner defs above)
# ---------------------------------------------------------------------------


def search_products(context: AgentRunContext, query: str, filters: Json, limit: int) -> list[Json]:
    state = RetryState()
    products = with_retry(
        "search_products",
        lambda: search_tools.search_products(context.cookie_header, query, filters=filters, limit=min(int(limit), 10)),
        policy=context.retry_policy,
        idempotent=True,
        state=state,
    )
    result = [compact_product(product) for product in products]
    _audit(context, "searchProducts", {"query": query, "filters": filters, "limit": limit}, {"count": len(result)})
    return result


def get_product(context: AgentRunContext, product_id: str) -> Json:
    product = with_retry(
        "get_product",
        lambda: search_tools.get_product(context.cookie_header, product_id),
        policy=context.retry_policy,
        idempotent=True,
    )
    result = compact_product(product)
    _audit(context, "getProduct", {"productId": product_id}, {"productId": result.get("_id")})
    return result


def get_similar_products(context: AgentRunContext, product_id: str, limit: int) -> list[Json]:
    products = with_retry(
        "get_similar_products",
        lambda: search_tools.get_similar_products(context.cookie_header, product_id, limit=min(int(limit), 10)),
        policy=context.retry_policy,
        idempotent=True,
    )
    result = [compact_product(product) for product in products]
    _audit(context, "getSimilarProducts", {"productId": product_id, "limit": limit}, {"count": len(result)})
    return result


def find_matching_products(context: AgentRunContext, product_id: str, target_article_type: str, limit: int) -> list[Json]:
    products = with_retry(
        "find_matching_products",
        lambda: search_tools.find_matching_products(context.cookie_header, product_id, target_article_type, limit=min(int(limit), 10)),
        policy=context.retry_policy,
        idempotent=True,
    )
    result = [compact_product(product) for product in products]
    _audit(context, "findMatchingProducts", {"referenceProductId": product_id, "targetArticleType": target_article_type}, {"count": len(result)})
    return result


def compare_products(context: AgentRunContext, product_ids: list[str]) -> Json:
    comparison = with_retry(
        "compare_products",
        lambda: search_tools.compare_products(context.cookie_header, [str(pid) for pid in product_ids[:4]]),
        policy=context.retry_policy,
        idempotent=True,
    )
    products = [compact_product(product) for product in comparison.get("products", [])]
    result = {"products": products, "attributes": comparison.get("attributes") or {}}
    _audit(context, "compareProducts", {"productIds": product_ids[:4]}, {"count": len(products)})
    return result


def get_cart(context: AgentRunContext) -> Json:
    cart = with_retry("get_cart", lambda: core_tools.get_cart(context.cookie_header), policy=context.retry_policy, idempotent=True)
    _audit(context, "getCart", {}, {"count": len(cart.get("items", []))})
    return cart


def get_user_preferences(context: AgentRunContext) -> Json:
    preferences = with_retry(
        "get_user_preferences",
        lambda: core_tools.get_user_preferences(context.cookie_header),
        policy=context.retry_policy,
        idempotent=True,
    )
    _audit(context, "getUserPreferences", {}, {"keys": sorted(preferences.keys())})
    return preferences


def list_orders(context: AgentRunContext) -> list[Json]:
    orders = with_retry("list_orders", lambda: core_tools.list_user_orders(context.cookie_header), policy=context.retry_policy, idempotent=True)
    _audit(context, "listOrders", {}, {"count": len(orders)})
    return orders


def get_order(context: AgentRunContext, order_id: str) -> Json:
    order = with_retry("get_order", lambda: core_tools.get_order(context.cookie_header, order_id), policy=context.retry_policy, idempotent=True)
    _audit(context, "getOrder", {"orderId": order_id}, {"orderNumber": order.get("orderNumber")})
    return order


def check_return_eligibility(context: AgentRunContext, order_id: str, order_item_id: str) -> Json:
    eligibility = with_retry(
        "check_return_eligibility",
        lambda: core_tools.check_return_eligibility(context.cookie_header, order_id, order_item_id),
        policy=context.retry_policy,
        idempotent=True,
    )
    _audit(context, "checkReturnEligibility", {"orderId": order_id, "orderItemId": order_item_id}, eligibility)
    return eligibility


def get_return_policy(context: AgentRunContext) -> Json:
    policy = core_tools.get_return_policy()
    _audit(context, "getReturnPolicy", {}, policy)
    return policy


def request_add_to_cart_confirmation(context: AgentRunContext, product_id: str, quantity: int = 1, size: Optional[str] = None) -> Json:
    action = store.create_action(
        context.session_id,
        context.user_id,
        "add_to_cart",
        {"productId": product_id, "quantity": max(1, int(quantity)), "size": size},
    )
    _audit(context, "addToCart", {"productId": product_id, "quantity": quantity}, {"pendingActionId": action["_id"]}, status="blocked")
    return {"pendingActionId": action["_id"], "type": action["type"], "expiresAt": action["expiresAt"]}


def request_create_return_confirmation(
    context: AgentRunContext,
    order_id: str,
    order_item_id: str,
    reason: str = "",
    condition: str = "",
    resolution: str = "",
) -> Json:
    action = store.create_action(
        context.session_id,
        context.user_id,
        "create_return_request",
        {
            "orderId": order_id,
            "orderItemId": order_item_id,
            "reason": reason,
            "condition": condition,
            "resolution": resolution,
            "requiresDetails": not all([reason, condition, resolution]),
        },
    )
    _audit(context, "createReturnRequest", {"orderId": order_id, "orderItemId": order_item_id}, {"pendingActionId": action["_id"]}, status="blocked")
    return {
        "pendingActionId": action["_id"],
        "type": action["type"],
        "expiresAt": action["expiresAt"],
        "requiresDetails": action["payload"]["requiresDetails"],
    }


def request_create_support_ticket_confirmation(
    context: AgentRunContext,
    category: str,
    priority: str,
    subject: str,
    body: str,
    order_id: Optional[str] = None,
) -> Json:
    action = store.create_action(
        context.session_id,
        context.user_id,
        "create_support_ticket",
        {"category": category, "priority": priority, "subject": subject, "body": body, "orderId": order_id},
    )
    _audit(context, "createSupportTicket", {"category": category, "priority": priority, "subject": subject}, {"pendingActionId": action["_id"]}, status="blocked")
    return {"pendingActionId": action["_id"], "type": action["type"], "expiresAt": action["expiresAt"]}

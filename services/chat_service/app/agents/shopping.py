"""Codex Shopping Assistant workflow."""

from __future__ import annotations

from typing import Any

from app.agents.audit import audit_tool_call
from app.agentic.service import agent_service
from app.dependencies import ChatContext
from app.http import ServiceHttpError
from app.llm.client import llm_client
from app.observability import compact, logger
from app.store import store
from app.tools.core import core_tools
from app.tools.registry import SHOPPING_TOOLS
from app.tools.search import search_tools

Json = dict[str, Any]


def compact_product(product: Json) -> Json:
    """Return user-facing product summary."""

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


class ShoppingAgent:
    """Tool-driven shopping assistant with deterministic local fallback."""

    system_prompt = (
        "You are a concise ecommerce shopping assistant. Catalogue filters include "
        "gender Men/Women/Boys/Girls/Unisex; usage Casual/Formal/Sports/Ethnic/Party/Travel/Smart Casual; "
        "season Summer/Winter/Fall/Spring; masterCategory Apparel/Footwear/Accessories/Personal Care; "
        "articleType Shirts/Jeans/Dresses/Shoes/Sneakers/Kurtas/Sarees/Watches and more; "
        "baseColour; and numeric INR priceMax. Wedding means Ethnic or Party, gym means Sports, "
        "summer or beach means Summer and Casual, office means Formal or Smart Casual. "
        "Never mutate cart state directly; create a pending action that the user must confirm."
    )

    def create_session(self, context: ChatContext, entry_point: str, product_id: str | None) -> Json:
        """Create a shopping assistant session."""

        logger.debug(
            "agent.task shopping.create_session userId=%s entryPoint=%s productId=%s",
            context.user.get("_id"),
            entry_point,
            product_id,
        )
        session = store.create_session(
            "shopping",
            context.user["_id"],
            {"entryPoint": entry_point, "productId": product_id},
        )
        logger.debug("agent.response shopping.create_session session=%s", compact({"_id": session.get("_id"), "context": session.get("context")}))
        return session

    def answer(self, context: ChatContext, session_id: str, message: str, request_context: Json) -> Json:
        """Handle one shopping assistant message."""

        session = store.find_session(session_id, context.user["_id"], "shopping")
        if not session:
            raise ValueError("CHAT_SESSION_NOT_FOUND")
        logger.debug(
            "agent.task shopping.answer userId=%s sessionId=%s message=%s context=%s",
            context.user.get("_id"),
            session_id,
            message,
            compact(request_context),
        )
        store.add_message(session_id, "user", message, {"context": request_context})
        agentic = agent_service.try_answer(context, session, message, request_context)
        if agentic.message and agentic.used_agentic_loop:
            metadata: Json = {
                "usedAgenticLoop": agentic.used_agentic_loop,
                "usedDeepAgents": agentic.used_deepagents,
                "runId": agentic.run_id,
                "contextWindow": agentic.context_window,
            }
            if agentic.pending_action:
                metadata["pendingActionId"] = agentic.pending_action.get("id")
                metadata["pendingActionType"] = agentic.pending_action.get("type")
                metadata["pendingActionExpiresAt"] = agentic.pending_action.get("expiresAt")
            if agentic.suggested_products:
                metadata["suggestedProducts"] = agentic.suggested_products
            store.add_message(session_id, "assistant", agentic.message, metadata)
            return agentic.to_public_dict()
        current_product_id = request_context.get("currentProductId") or session["context"].get("productId")
        lowered = message.lower()
        if "compare" in lowered:
            return self.compare_from_context(context, session_id, message, request_context)
        if current_product_id and any(term in lowered for term in ["match", "go with", "pair", "outfit"]):
            return self.matching_products(context, session_id, str(current_product_id), message)
        if current_product_id:
            return self.answer_product_question(context, session_id, str(current_product_id), message)
        return self.recommend_with_cart_action(context, session_id, message, request_context)

    def build_history(self, session_id: str, limit: int = 10) -> list[Json]:
        """Build OpenAI message history from stored session messages."""

        return [
            {"role": item["role"], "content": item["content"]}
            for item in store.list_messages(session_id, limit=limit)
            if item.get("role") in {"user", "assistant"} and str(item.get("content") or "").strip()
        ]

    def last_suggested_products(self, session_id: str) -> list[Json]:
        """Return the latest product snapshots from assistant message metadata."""

        for item in reversed(store.list_messages(session_id, limit=20)):
            products = ((item.get("metadata") or {}).get("suggestedProducts") or [])
            if products:
                return [product for product in products if isinstance(product, dict)]
        return []

    def filters_from_message(self, message: str) -> Json:
        """Extract common catalogue filters for the deterministic fallback path."""

        lowered = message.lower()
        filters: Json = {}
        if "casual" in lowered:
            filters["usage"] = ["Casual"]
        if "formal" in lowered or "office" in lowered:
            filters["usage"] = ["Formal", "Smart Casual"]
        if "gym" in lowered or "running" in lowered or "sports" in lowered:
            filters["usage"] = ["Sports"]
        if "wedding" in lowered or "party" in lowered:
            filters["usage"] = ["Ethnic", "Party"]
            filters["masterCategory"] = "Apparel"
        if "summer" in lowered or "beach" in lowered or "vacation" in lowered:
            filters["season"] = "Summer"
        if "under 3000" in lowered or "below 3000" in lowered:
            filters["priceMax"] = 3000
        if "cheaper" in lowered or "lower price" in lowered:
            filters["sort"] = "price_asc"
        for colour in ["Black", "White", "Blue", "Red", "Green", "Brown", "Grey", "Pink", "Yellow"]:
            if colour.lower() in lowered:
                filters["baseColour"] = colour
                break
        for article in ["Shirts", "Jeans", "Dresses", "Tshirts", "Kurtas", "Sarees", "Watches"]:
            if article.lower().rstrip("s") in lowered or article.lower() in lowered:
                filters["articleType"] = article
                break
        return filters

    def answer_product_question(self, context: ChatContext, session_id: str, product_id: str, message: str) -> Json:
        """Answer using product facts from Search Service."""

        product = search_tools.get_product(context.cookie_header, product_id)
        logger.debug(
            "agent.task shopping.get_product_facts sessionId=%s productId=%s title=%s",
            session_id,
            product.get("_id"),
            product.get("title"),
        )
        audit_tool_call(session_id, context.user["_id"], "shopping", "getProduct", {"productId": product_id}, {"productId": product["_id"]})
        fallback = (
            f"{product['title']} is {product['baseColour']} and is best positioned for "
            f"{product.get('usage') or 'general'} use. It sits in {product.get('articleType')} "
            f"and costs {product['price']['amount']} {product['price']['currency']}."
        )
        text = self.llm_text(
            [
                {"role": "system", "content": self.system_prompt + " Answer using only the supplied product facts."},
                *self.build_history(session_id),
                {"role": "user", "content": f"Question: {message}\nProduct facts: {product}"},
            ],
            fallback,
        )
        reply = {"message": text, "suggestedProducts": [compact_product(product)]}
        store.add_message(
            session_id,
            "assistant",
            text,
            {"productId": product["_id"], "suggestedProducts": reply["suggestedProducts"], "llmMetadataStored": True},
        )
        logger.debug("agent.response shopping.product_question sessionId=%s response=%s", session_id, compact(reply))
        return reply

    def recommend_with_cart_action(self, context: ChatContext, session_id: str, message: str, request_context: Json | None = None) -> Json:
        """Recommend products and prepare add-to-cart confirmation."""

        request_context = request_context or {}
        filters = self.filters_from_message(message)
        cart_product_ids: set[str] = set()
        if request_context.get("cartAware"):
            try:
                cart = core_tools.get_cart(context.cookie_header)
                cart_product_ids = {str(item.get("productId")) for item in cart.get("items", []) if item.get("productId")}
                logger.debug("agent.task shopping.get_cart sessionId=%s cartProductIds=%s", session_id, sorted(cart_product_ids))
            except ServiceHttpError as exc:
                logger.debug("agent.task shopping.get_cart.error sessionId=%s error=%s", session_id, str(exc))
        latest_products = self.last_suggested_products(session_id)
        if latest_products and any(term in message.lower() for term in ["cheaper", "similar", "another", "more option"]):
            reference = latest_products[0]
            filters.setdefault("articleType", reference.get("articleType"))
            if "cheaper" in message.lower() and isinstance(reference.get("price"), dict):
                filters["priceMax"] = reference["price"].get("amount")
        logger.debug("agent.task shopping.search_products sessionId=%s query=%s filters=%s", session_id, message, compact(filters))
        products = search_tools.search_products(context.cookie_header, message, filters=filters, limit=5)
        if not products and filters:
            relaxed_filters = {key: value for key, value in filters.items() if key not in {"articleType", "baseColour"}}
            products = search_tools.search_products(context.cookie_header, message, filters=relaxed_filters, limit=5)
            if products:
                filters = relaxed_filters
        if cart_product_ids:
            products = [product for product in products if str(product.get("_id")) not in cart_product_ids] or products
        audit_tool_call(session_id, context.user["_id"], "shopping", "searchProducts", {"query": message, "filters": filters}, {"count": len(products)})
        logger.debug("agent.task shopping.search_products.result sessionId=%s count=%s top=%s", session_id, len(products), compact(compact_product(products[0]) if products else {}))
        if not products:
            store.add_message(session_id, "assistant", "I could not find a matching product for that request.", {})
            reply = {"message": "I could not find a matching product for that request.", "suggestedProducts": []}
            logger.debug("agent.response shopping.recommendation sessionId=%s response=%s", session_id, compact(reply))
            return reply
        product = products[0]
        action = store.create_action(
            session_id,
            context.user["_id"],
            "add_to_cart",
            {"productId": product["_id"], "quantity": 1, "size": None},
        )
        core_tools.write_activity(
            "assistant_product_recommended",
            {"productId": product["_id"], "sourceProductId": product.get("sourceProductId"), "sessionId": session_id},
        )
        fallback = (
            f"I recommend {product['title']} for {product['price']['amount']} {product['price']['currency']}. "
            "I can add it to your cart after you confirm."
        )
        reply = self.llm_text(
            [
                {"role": "system", "content": self.system_prompt},
                *self.build_history(session_id),
                {"role": "user", "content": f"Customer request: {message}\nTop product: {compact_product(product)}"},
            ],
            fallback,
        )
        suggested_products = [compact_product(item) for item in products]
        store.add_message(
            session_id,
            "assistant",
            reply,
            {
                "pendingActionId": action["_id"],
                "pendingActionType": action["type"],
                "pendingActionExpiresAt": action["expiresAt"],
                "suggestedProducts": suggested_products,
                "llmMetadataStored": True,
            },
        )
        audit_tool_call(
            session_id,
            context.user["_id"],
            "shopping",
            "addToCart",
            {"productId": product["_id"], "quantity": 1},
            {"pendingActionId": action["_id"]},
            status="blocked",
            requires_user_confirmation=True,
        )
        reply_payload = {
            "message": reply,
            "suggestedProducts": suggested_products,
            "pendingAction": {"id": action["_id"], "type": "add_to_cart", "expiresAt": action["expiresAt"]},
        }
        logger.debug("agent.response shopping.recommendation sessionId=%s response=%s", session_id, compact(reply_payload))
        return reply_payload

    def matching_products(self, context: ChatContext, session_id: str, product_id: str, message: str) -> Json:
        """Find products that pair with the current product."""

        target = "Shoes"
        lowered = message.lower()
        if "pant" in lowered or "jean" in lowered:
            target = "Jeans"
        elif "watch" in lowered:
            target = "Watches"
        elif "shirt" in lowered:
            target = "Shirts"
        products = search_tools.find_matching_products(context.cookie_header, product_id, target, limit=5)
        audit_tool_call(
            session_id,
            context.user["_id"],
            "shopping",
            "findMatchingProducts",
            {"referenceProductId": product_id, "targetArticleType": target},
            {"count": len(products)},
        )
        suggested_products = [compact_product(product) for product in products]
        text = f"I found {len(suggested_products)} {target.lower()} options that can pair with this item."
        if suggested_products:
            text = f"{suggested_products[0]['title']} is a good {target.lower()} match. I found a few options to compare."
        store.add_message(session_id, "assistant", text, {"suggestedProducts": suggested_products, "llmMetadataStored": True})
        reply = {"message": text, "suggestedProducts": suggested_products}
        logger.debug("agent.response shopping.matching sessionId=%s response=%s", session_id, compact(reply))
        return reply

    def compare_from_context(self, context: ChatContext, session_id: str, message: str, request_context: Json) -> Json:
        """Compare products mentioned in context or recent recommendations."""

        product_ids = [str(item) for item in request_context.get("productIds", []) if item]
        if len(product_ids) < 2:
            product_ids = [str(product.get("_id")) for product in self.last_suggested_products(session_id)[:2] if product.get("_id")]
        if len(product_ids) < 2:
            return self.recommend_with_cart_action(context, session_id, message, request_context)
        comparison = search_tools.compare_products(context.cookie_header, product_ids[:4])
        audit_tool_call(
            session_id,
            context.user["_id"],
            "shopping",
            "compareProducts",
            {"productIds": product_ids[:4]},
            {"count": len(comparison.get("products") or [])},
        )
        products = [compact_product(product) for product in comparison.get("products", [])]
        names = [product.get("title") for product in products]
        text = f"Compared {', '.join(name for name in names if name)}. The better pick depends on price, usage, and colour preference."
        store.add_message(
            session_id,
            "assistant",
            text,
            {"suggestedProducts": products, "comparison": comparison.get("attributes"), "llmMetadataStored": True},
        )
        reply = {"message": text, "suggestedProducts": products, "comparison": comparison.get("attributes")}
        logger.debug("agent.response shopping.compare sessionId=%s response=%s", session_id, compact(reply))
        return reply

    def llm_text(self, messages: list[Json], fallback: str) -> str:
        """Call the configured LLM when available, with deterministic local fallback."""

        try:
            response = llm_client.chat_completion(messages, stream=False)
        except ServiceHttpError:
            logger.debug("agent.task shopping.llm fallbackUsed=true messages=%s", compact(messages))
            return fallback
        choices = response.get("choices") if isinstance(response, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else {}
        message = first.get("message") if isinstance(first, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        return str(content).strip() if content else fallback

    def confirm_action(self, context: ChatContext, action: Json) -> Json:
        """Execute a confirmed shopping action."""

        payload = action["payload"]
        try:
            item = core_tools.add_to_cart(context.cookie_header, payload["productId"], int(payload.get("quantity", 1)), payload.get("size"))
        except ServiceHttpError as exc:
            store.complete_action(action, "error", {"message": str(exc)})
            logger.debug("agent.task shopping.confirm_action.error actionId=%s error=%s", action.get("_id"), str(exc))
            raise
        audit_tool_call(
            action["sessionId"],
            context.user["_id"],
            "shopping",
            "addToCart",
            {"productId": payload["productId"], "quantity": payload.get("quantity", 1)},
            {"cartItemId": item.get("cartItemId")},
        )
        completed = store.complete_action(action, "completed", {"cartItemId": item.get("cartItemId")})
        reply = {"status": completed["status"], "actionId": completed["_id"], "result": item}
        logger.debug("agent.response shopping.confirm_action actionId=%s response=%s", action.get("_id"), compact(reply))
        return reply


shopping_agent = ShoppingAgent()

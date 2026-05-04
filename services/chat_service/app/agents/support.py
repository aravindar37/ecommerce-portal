"""Codex Returns and Support Agent workflow."""

from __future__ import annotations

from typing import Any

from app.agents.audit import audit_tool_call
from app.dependencies import ChatContext
from app.http import ServiceHttpError
from app.llm.client import llm_client
from app.mcp.client import mcp_client
from app.observability import compact, logger
from app.store import store
from app.tools.core import core_tools
from app.tools.registry import SUPPORT_TOOLS

Json = dict[str, Any]


class SupportAgent:
    """Tool-driven support agent backed by Core tools and MCP planning."""

    def create_session(self, context: ChatContext, order_id: str | None) -> Json:
        """Create an authenticated support session."""

        logger.debug("agent.task support.create_session userId=%s orderId=%s", context.user.get("_id"), order_id)
        session = store.create_session("returns_support", context.user["_id"], {"orderId": order_id})
        logger.debug("agent.response support.create_session session=%s", compact({"_id": session.get("_id"), "context": session.get("context")}))
        return session

    def answer(self, context: ChatContext, session_id: str, message: str, request_context: Json) -> Json:
        """Handle a support agent message."""

        session = store.find_session(session_id, context.user["_id"], "returns_support")
        if not session:
            raise ValueError("CHAT_SESSION_NOT_FOUND")
        logger.debug(
            "agent.task support.answer userId=%s sessionId=%s message=%s context=%s",
            context.user.get("_id"),
            session_id,
            message,
            compact(request_context),
        )
        store.add_message(session_id, "user", message, {"context": request_context})
        order_id = str(request_context.get("orderId") or session["context"].get("orderId") or "")
        order_item_id = str(request_context.get("orderItemId") or "")
        if not order_id or not order_item_id:
            inferred = self.infer_order_context(context, session_id, message, order_id)
            order_id = order_id or inferred.get("orderId", "")
            order_item_id = order_item_id or inferred.get("orderItemId", "")
        if not order_id or not order_item_id:
            text = "I can help with that. Please choose the order or item you want support for."
            store.add_message(session_id, "assistant", text, {"usedMcp": False})
            reply = {"message": text, "usedMcp": False}
            logger.debug("agent.response support.missing_details sessionId=%s response=%s", session_id, compact(reply))
            return reply
        plan = mcp_client.plan_support_return(order_id, order_item_id)
        logger.debug("agent.task support.mcp_plan sessionId=%s plan=%s", session_id, compact(plan))
        order = core_tools.get_order(context.cookie_header, order_id)
        logger.debug("agent.task support.get_order sessionId=%s orderId=%s orderNumber=%s", session_id, order_id, order.get("orderNumber"))
        audit_tool_call(session_id, context.user["_id"], "returns_support", "getOrder", {"orderId": order_id}, {"orderNumber": order["orderNumber"]})
        eligibility = core_tools.check_return_eligibility(context.cookie_header, order_id, order_item_id)
        logger.debug("agent.task support.check_return_eligibility sessionId=%s result=%s", session_id, compact(eligibility))
        audit_tool_call(
            session_id,
            context.user["_id"],
            "returns_support",
            "checkReturnEligibility",
            {"orderId": order_id, "orderItemId": order_item_id},
            eligibility,
        )
        policy = core_tools.get_return_policy()
        if not eligibility.get("eligible"):
            fallback_text = f"That item is not eligible for return under the {eligibility.get('policyCode', 'configured')} policy."
            text = self.llm_text(
                [
                    {"role": "system", "content": "Respond as a concise returns support assistant using the eligibility result only."},
                    *self.build_history(session_id),
                    {"role": "user", "content": f"Customer said: {message}\nEligibility: {eligibility}"},
                ],
                fallback_text,
            )
            store.add_message(session_id, "assistant", text, {"usedMcp": True, "mcpPlan": plan, "eligibility": eligibility})
            reply = {"message": text, "usedMcp": True, "eligibility": eligibility}
            logger.debug("agent.response support.ineligible sessionId=%s response=%s", session_id, compact(reply))
            return reply
        reason = str(request_context.get("reason") or "").strip()
        condition = str(request_context.get("condition") or "").strip()
        resolution = str(request_context.get("resolution") or "").strip()
        action = store.create_action(
            session_id,
            context.user["_id"],
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
        audit_tool_call(
            session_id,
            context.user["_id"],
            "returns_support",
            "createReturnRequest",
            {"orderId": order_id, "orderItemId": order_item_id},
            {"pendingActionId": action["_id"], "requiresDetails": action["payload"]["requiresDetails"]},
            status="blocked",
            requires_user_confirmation=True,
        )
        fallback_text = (
            f"Order {order['orderNumber']} item is eligible under the {eligibility['policyCode']} policy. "
            f"The demo return window is {policy['windowDays']} days, and I prepared a return request for confirmation."
        )
        text = self.llm_text(
            [
                {
                    "role": "system",
                    "content": "Respond as a returns support assistant. Do not promise refund timing. Mention user confirmation is required.",
                },
                *self.build_history(session_id),
                {"role": "user", "content": f"Customer said: {message}\nOrder: {order}\nEligibility: {eligibility}\nPolicy: {policy}"},
            ],
            fallback_text,
        )
        store.add_message(session_id, "assistant", text, {"usedMcp": True, "pendingActionId": action["_id"], "mcpPlan": plan})
        reply = {
            "message": text,
            "usedMcp": True,
            "eligibility": eligibility,
            "pendingAction": {
                "id": action["_id"],
                "type": "create_return_request",
                "expiresAt": action["expiresAt"],
                "requiresDetails": action["payload"]["requiresDetails"],
            },
        }
        logger.debug("agent.response support.eligible sessionId=%s response=%s", session_id, compact(reply))
        return reply

    def build_history(self, session_id: str, limit: int = 10) -> list[Json]:
        """Build OpenAI message history from stored session messages."""

        return [
            {"role": item["role"], "content": item["content"]}
            for item in store.list_messages(session_id, limit=limit)
            if item.get("role") in {"user", "assistant"} and str(item.get("content") or "").strip()
        ]

    def infer_order_context(self, context: ChatContext, session_id: str, message: str, existing_order_id: str = "") -> Json:
        """Infer order and item IDs from natural language or recent orders."""

        orders = core_tools.list_user_orders(context.cookie_header)
        audit_tool_call(session_id, context.user["_id"], "returns_support", "listOrders", {"message": message}, {"count": len(orders)})
        if not orders:
            return {}
        selected_order = None
        if existing_order_id:
            selected_order = next((order for order in orders if order.get("_id") == existing_order_id or order.get("orderNumber") == existing_order_id), None)
        if selected_order is None:
            lowered = message.lower()
            selected_order = next((order for order in orders if str(order.get("orderNumber", "")).lower() in lowered), None)
        if selected_order is None:
            selected_order = orders[0]
        selected_item = None
        lowered = message.lower()
        for item in selected_order.get("items", []):
            title = str(item.get("titleSnapshot") or "").lower()
            article = str(item.get("articleType") or "").lower()
            if ("first" in lowered and item == selected_order.get("items", [])[0]) or title and any(word in title for word in lowered.split()):
                selected_item = item
                break
            if article and article in lowered:
                selected_item = item
                break
        selected_item = selected_item or (selected_order.get("items") or [{}])[0]
        result = {"orderId": selected_order.get("_id") or selected_order.get("orderNumber"), "orderItemId": selected_item.get("orderItemId")}
        logger.debug("agent.task support.infer_order_context sessionId=%s result=%s", session_id, compact(result))
        return result

    def confirm_action(self, context: ChatContext, action: Json) -> Json:
        """Execute a confirmed support action."""

        payload = action["payload"]
        reason = str(payload["reason"]).strip()
        condition = str(payload["condition"]).strip()
        resolution = str(payload["resolution"]).strip()
        return_request = core_tools.create_return_request(
            context.cookie_header,
            payload["orderId"],
            payload["orderItemId"],
            reason,
            condition,
            resolution,
        )
        logger.debug("agent.task support.create_return_request actionId=%s result=%s", action.get("_id"), compact(return_request))
        audit_tool_call(
            action["sessionId"],
            context.user["_id"],
            "returns_support",
            "createReturnRequest",
            {"orderId": payload["orderId"], "orderItemId": payload["orderItemId"]},
            {"returnNumber": return_request.get("returnNumber")},
        )
        completed = store.complete_action(action, "completed", {"returnNumber": return_request.get("returnNumber")})
        reply = {"status": completed["status"], "actionId": completed["_id"], "result": return_request}
        logger.debug("agent.response support.confirm_action actionId=%s response=%s", action.get("_id"), compact(reply))
        return reply

    def llm_text(self, messages: list[Json], fallback: str) -> str:
        """Call the configured LLM when available, with deterministic local fallback."""

        try:
            response = llm_client.chat_completion(messages, stream=False)
        except ServiceHttpError:
            logger.debug("agent.task support.llm fallbackUsed=true messages=%s", compact(messages))
            return fallback
        choices = response.get("choices") if isinstance(response, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else {}
        message = first.get("message") if isinstance(first, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        return str(content).strip() if content else fallback


support_agent = SupportAgent()

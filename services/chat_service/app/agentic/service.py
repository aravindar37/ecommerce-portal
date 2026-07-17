"""Agentic service orchestration used by legacy agent facades."""

from __future__ import annotations

from app.dependencies import ChatContext
from app.observability import logger
from app.store import store

from .agent_specs import spec_for_session_type
from .context import build_run_context
from .deepagents_harness import deepagents_harness
from .memory import retrieve_episodes, retrieve_memories, session_summary
from .models import AgentRunInput, AgentRunResult, Json


class AgentService:
    """Coordinates Deep Agents runs while preserving route-compatible fallbacks."""

    def metadata(self) -> Json:
        """Return runtime metadata."""

        return deepagents_harness.metadata()

    def try_answer(
        self,
        chat_context: ChatContext,
        session: Json,
        message: str,
        request_context: Json,
        on_behalf_user_id: str | None = None,
    ) -> AgentRunResult:
        """Attempt an agentic answer. Caller may fallback when result has no message."""

        try:
            spec = spec_for_session_type(str(session["type"]))
        except ValueError:
            logger.debug("agentic.service.unknown_session_type type=%s", session.get("type"))
            return AgentRunResult(
                message="",
                agent_id="",
                thread_id=str(session.get("_id", "")),
                run_id="",
                used_agentic_loop=False,
                fallback_reason="unknown_session_type",
            )
        run_context = build_run_context(
            chat_context,
            str(session["_id"]),
            str(session["type"]),
            spec.agent_id,
            request_context,
            session.get("context") or {},
            on_behalf_user_id=on_behalf_user_id,
        )
        history = [
            {"role": item["role"], "content": item["content"], "metadata": item.get("metadata") or {}}
            for item in store.list_messages(str(session["_id"]), limit=200)
            if item.get("role") in {"user", "assistant"} and str(item.get("content") or "").strip()
        ]
        memories = retrieve_memories(run_context.user_id, spec.agent_id, message, run_context.context_budget.relevance_top_k)
        episodes = retrieve_episodes(run_context.user_id, spec.agent_id, message, run_context.context_budget.relevance_top_k)
        agent_input = AgentRunInput(
            message=message,
            history=history,
            summary=session_summary(session),
            relevant_memories=memories,
            relevant_episodes=episodes,
            context=run_context,
        )
        result = deepagents_harness.run_message_with_spec(agent_input, spec)
        logger.debug(
            "agentic.result sessionId=%s agentId=%s usedDeepAgents=%s fallback=%s context=%s",
            session.get("_id"),
            spec.agent_id,
            result.used_deepagents,
            result.fallback_reason,
            result.context_window,
        )
        return result


    def confirm_action(self, chat_context: ChatContext, action: Json) -> Json:
        """Delegate a confirmed pending action to the correct domain agent."""

        from app.agents.shopping import shopping_agent
        from app.agents.support import support_agent

        if action["type"] == "add_to_cart":
            return shopping_agent.confirm_action(chat_context, action)
        if action["type"] in {"create_return_request", "create_support_ticket"}:
            return support_agent.confirm_action(chat_context, action)
        if action["type"] == "update_order":
            from app.tools.core import core_tools

            payload = action["payload"]
            result = core_tools.update_voice_order(
                str(payload["voiceUserId"]),
                str(payload["orderId"]),
                str(payload["action"]),
                payload.get("shippingAddress"),
            )
            completed = store.complete_action(action, "completed", {"orderId": result.get("_id"), "status": result.get("status")})
            return {"status": completed["status"], "actionId": completed["_id"], "result": result}
        from app.api.envelope import fail
        fail(400, "UNSUPPORTED_ACTION", "Assistant action type is not supported.")


agent_service = AgentService()


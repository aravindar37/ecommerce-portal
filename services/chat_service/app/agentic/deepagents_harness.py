"""LangGraph-backed agent harness with safe fallback metadata."""

from __future__ import annotations

import inspect
import json as _json
import uuid
from typing import Any, Iterator

from app.config import ChatServiceSettings, settings
from app.llm.client import is_configured_secret
from app.observability import compact, logger
from app.store import store

from .agent_specs import AgentSpec
from .context_window import assemble_context
from .memory import memory_candidates_from_run
from .models import AgentRunInput, AgentRunResult, Json
from .tools import bind_tools


class DeepAgentsHarness:
    """Runs LangGraph create_react_agent when available; records normalised metadata."""

    def __init__(self, config: ChatServiceSettings = settings) -> None:
        self.config = config
        self._import_error: str | None = None

    def metadata(self) -> Json:
        """Return non-sensitive harness metadata."""

        return {
            "harness": self.config.agent_harness,
            "enabled": self.config.agentic_enabled,
            "langgraphAvailable": self.available(),
            "importError": self._import_error,
            "model": self.config.llm_model,
            "hitlEnabled": self.config.agent_hitl_enabled,
            "memoryEnabled": self.config.agent_memory_enabled,
            "episodicMemoryEnabled": self.config.agent_episodic_memory_enabled,
            "streamingEnabled": self.config.agent_streaming_enabled,
            "retry": {
                "maxAttempts": self.config.agent_retry_max_attempts,
                "baseDelayMs": self.config.agent_retry_base_delay_ms,
                "maxDelayMs": self.config.agent_retry_max_delay_ms,
            },
            "context": {
                "targetInputTokens": self.config.agent_context_target_input_tokens,
                "maxInputTokens": self.config.agent_context_max_input_tokens,
                "recentMessageLimit": self.config.agent_context_recent_message_limit,
                "relevanceTopK": self.config.agent_context_relevance_top_k,
            },
        }

    def available(self) -> bool:
        """Return whether the LangGraph runtime can be imported."""

        try:
            import langgraph  # noqa: F401
            import langchain_openai  # noqa: F401
            import langchain_core  # noqa: F401
        except Exception as exc:
            self._import_error = exc.__class__.__name__
            return False
        self._import_error = None
        return True

    def run_message_with_spec(self, agent_input: AgentRunInput, spec: AgentSpec) -> AgentRunResult:
        """Run one message against the selected agent spec."""

        run_id = uuid.uuid4().hex[:24]
        context_messages, context_meta = assemble_context(
            message=agent_input.message,
            history=agent_input.history,
            summary=agent_input.summary,
            memories=agent_input.relevant_memories,
            episodes=agent_input.relevant_episodes,
            request_context=agent_input.context.request_context,
            session_context=agent_input.context.session_context,
            budget=agent_input.context.context_budget,
        )
        store.create_agent_run(
            {
                "_id": run_id,
                "sessionId": agent_input.context.session_id,
                "userId": agent_input.context.user_id,
                "agentId": spec.agent_id,
                "threadId": agent_input.context.session_id,
                "status": "running",
                "model": self.config.llm_model,
                "harness": "langgraph",
                "contextWindow": context_meta,
                "startedAt": agent_input.context.started_at,
            }
        )
        if not self.config.agentic_enabled:
            return self._fallback_result(agent_input, spec, run_id, context_meta, "agentic_disabled")
        if not self.available():
            return self._fallback_result(agent_input, spec, run_id, context_meta, "langgraph_unavailable")
        if not is_configured_secret(self.config.llm_api_key):
            return self._fallback_result(agent_input, spec, run_id, context_meta, "llm_api_key_missing")

        try:
            result = self._invoke_deepagents(agent_input, spec, context_messages, run_id, context_meta)
            store.complete_agent_run(run_id, "completed", {"usage": result.usage, "contextWindow": context_meta})
            return result
        except Exception as exc:
            logger.debug("agent.langgraph.error runId=%s error=%s context=%s", run_id, str(exc), compact(context_meta))
            store.complete_agent_run(run_id, "failed", {"error": {"message": str(exc), "type": exc.__class__.__name__}})
            return self._fallback_result(agent_input, spec, run_id, context_meta, "langgraph_error")

    def run_message(self, agent_input: AgentRunInput) -> AgentRunResult:
        """Protocol placeholder. Call `run_message_with_spec` in service code."""

        raise NotImplementedError("AgentSpec is required")

    def stream_message(self, agent_input: AgentRunInput) -> Iterator[Json]:
        """Yield a non-streaming fallback event."""

        yield {"type": "error", "message": "Streaming is not wired for this harness wrapper yet."}

    def resume(self, agent_input: AgentRunInput) -> AgentRunResult:
        """Resume an interrupted run. Confirmation routes currently execute existing action handlers."""

        return AgentRunResult(
            message="The requested action has been handled.",
            agent_id=agent_input.context.agent_id,
            thread_id=agent_input.context.session_id,
            run_id=uuid.uuid4().hex[:24],
            used_agentic_loop=False,
            fallback_reason="resume_not_wired",
        )

    def _invoke_deepagents(
        self,
        agent_input: AgentRunInput,
        spec: AgentSpec,
        messages: list[Json],
        run_id: str,
        context_meta: Json,
    ) -> AgentRunResult:
        """Invoke LangGraph create_react_agent with ecommerce tools."""

        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent

        model = ChatOpenAI(
            model=self.config.llm_model,
            api_key=self.config.llm_api_key,
            base_url=self.config.llm_api_base_url,
            temperature=self.config.llm_temperature,
            timeout=self.config.llm_timeout_ms / 1000,
            max_tokens=self.config.llm_max_output_tokens,
        )

        # C5: merge any system-role messages from context into one combined prompt
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        combined_system = spec.system_prompt_builder(agent_input.context)
        if system_parts:
            combined_system += "\n\n" + "\n\n".join(system_parts)
        conversation_messages = [m for m in messages if m.get("role") != "system"]

        # bind_tools returns ready-to-use StructuredTool instances
        runtime_tools = bind_tools(agent_input.context, spec.tool_names)

        # state_modifier param name varies across LangGraph minor versions
        _sig = inspect.signature(create_react_agent)
        _modifier_kwarg = "state_modifier" if "state_modifier" in _sig.parameters else "prompt"
        graph = create_react_agent(model=model, tools=runtime_tools, **{_modifier_kwarg: combined_system})

        result = graph.invoke({"messages": conversation_messages})
        text = self._extract_text(result)

        # S5: extract real token counts from last AIMessage response_metadata
        result_messages = result.get("messages") if isinstance(result, dict) else []
        last_msg = result_messages[-1] if isinstance(result_messages, list) and result_messages else None
        token_usage: Json = {}
        if last_msg and hasattr(last_msg, "response_metadata"):
            raw = (
                last_msg.response_metadata.get("token_usage")
                or last_msg.response_metadata.get("usage")
                or {}
            )
            token_usage = {
                "promptTokens": raw.get("prompt_tokens") or raw.get("input_tokens"),
                "completionTokens": raw.get("completion_tokens") or raw.get("output_tokens"),
                "totalTokens": raw.get("total_tokens"),
            }

        # Scan ToolMessages to surface pending_action and suggested_products for the route response
        pending_action: Json | None = None
        suggested_products: list[Json] = []
        for msg in (result_messages or []):
            if not (hasattr(msg, "content") and hasattr(msg, "tool_call_id")):
                continue
            try:
                tool_result: Any = _json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except Exception:
                continue
            if isinstance(tool_result, dict) and "pendingActionId" in tool_result and pending_action is None:
                pending_action = {
                    "id": tool_result["pendingActionId"],
                    "type": tool_result.get("type", ""),
                    "expiresAt": tool_result.get("expiresAt", ""),
                }
            if (
                isinstance(tool_result, list)
                and tool_result
                and isinstance(tool_result[0], dict)
                and "_id" in tool_result[0]
                and "title" in tool_result[0]
            ):
                suggested_products = tool_result

        memory_updates = memory_candidates_from_run(agent_input.message, text, spec.agent_id)
        for candidate in memory_updates:
            store.add_memory(
                agent_input.context.user_id,
                spec.agent_id,
                str(candidate["type"]),
                str(candidate["content"]),
                agent_input.context.session_id,
                candidate,
            )

        return AgentRunResult(
            message=text,
            usage=token_usage,
            suggested_products=suggested_products,
            pending_action=pending_action,
            agent_id=spec.agent_id,
            thread_id=agent_input.context.session_id,
            run_id=run_id,
            context_window=context_meta,
            used_agentic_loop=True,
            used_deepagents=False,
            memory_updates=memory_updates,
        )

    def _fallback_result(
        self,
        agent_input: AgentRunInput,
        spec: AgentSpec,
        run_id: str,
        context_meta: Json,
        reason: str,
    ) -> AgentRunResult:
        """Return a controlled fallback result without pretending LangGraph ran."""

        store.complete_agent_run(run_id, "completed", {"contextWindow": context_meta, "error": {"fallbackReason": reason}})
        return AgentRunResult(
            message="",
            agent_id=spec.agent_id,
            thread_id=agent_input.context.session_id,
            run_id=run_id,
            context_window=context_meta,
            used_agentic_loop=False,
            used_deepagents=False,
            fallback_reason=reason,
        )

    def _extract_text(self, output: Any) -> str:
        """Extract final assistant text from a LangGraph output dict."""

        if isinstance(output, dict):
            messages = output.get("messages")
            if isinstance(messages, list) and messages:
                last = messages[-1]
                content = getattr(last, "content", None)
                if content:
                    return str(content).strip()
                if isinstance(last, dict) and last.get("content"):
                    return str(last["content"]).strip()
            if output.get("output"):
                return str(output["output"]).strip()
        return "I'm unable to respond at this moment. Please try again."


deepagents_harness = DeepAgentsHarness()

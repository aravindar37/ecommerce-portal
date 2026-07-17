"""Agent runtime context helpers."""

from __future__ import annotations

import uuid

from app.config import ChatServiceSettings, settings
from app.dependencies import ChatContext
from app.store import now_iso

from .models import AgentContextBudget, AgentRetryPolicy, AgentRunContext


def retryable_status_codes(config: ChatServiceSettings = settings) -> frozenset[int]:
    """Return configured HTTP status codes that may be retried."""

    codes: set[int] = set()
    for raw in config.agent_retryable_status_codes.split(","):
        try:
            codes.add(int(raw.strip()))
        except ValueError:
            continue
    return frozenset(codes)


def context_budget(config: ChatServiceSettings = settings) -> AgentContextBudget:
    """Return configured context-window budget."""

    return AgentContextBudget(
        max_input_tokens=config.agent_context_max_input_tokens,
        target_input_tokens=config.agent_context_target_input_tokens,
        recent_message_limit=config.agent_context_recent_message_limit,
        relevance_top_k=config.agent_context_relevance_top_k,
        summary_max_tokens=config.agent_context_summary_max_tokens,
        tool_result_max_tokens=config.agent_context_tool_result_max_tokens,
    )


def retry_policy(config: ChatServiceSettings = settings) -> AgentRetryPolicy:
    """Return configured retry policy."""

    return AgentRetryPolicy(
        max_attempts=max(1, config.agent_retry_max_attempts),
        base_delay_ms=max(0, config.agent_retry_base_delay_ms),
        max_delay_ms=max(0, config.agent_retry_max_delay_ms),
        jitter_enabled=config.agent_retry_jitter_enabled,
        retryable_status_codes=retryable_status_codes(config),
    )


def build_run_context(
    chat_context: ChatContext,
    session_id: str,
    session_type: str,
    agent_id: str,
    request_context: dict[str, object],
    session_context: dict[str, object],
) -> AgentRunContext:
    """Create an authenticated agent run context."""

    return AgentRunContext(
        user_id=str(chat_context.user["_id"]),
        user=chat_context.user,
        session_id=session_id,
        session_type=session_type,
        agent_id=agent_id,
        cookie_header=chat_context.cookie_header,
        request_context=dict(request_context),
        session_context=dict(session_context),
        context_budget=context_budget(),
        retry_policy=retry_policy(),
        trace_id=uuid.uuid4().hex,
        started_at=now_iso(),
    )


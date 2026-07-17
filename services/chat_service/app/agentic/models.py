"""Typed contracts for the agentic chat runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Json = dict[str, Any]


@dataclass(frozen=True)
class AgentContextBudget:
    """Token budget used when assembling model context."""

    max_input_tokens: int
    target_input_tokens: int
    recent_message_limit: int
    relevance_top_k: int
    summary_max_tokens: int
    tool_result_max_tokens: int


@dataclass(frozen=True)
class AgentRetryPolicy:
    """Bounded retry policy for transient model/tool failures."""

    max_attempts: int
    base_delay_ms: int
    max_delay_ms: int
    jitter_enabled: bool
    retryable_status_codes: frozenset[int]


@dataclass(frozen=True)
class AgentRunContext:
    """Authenticated run context passed to tools and harnesses."""

    user_id: str
    user: Json
    session_id: str
    session_type: str
    agent_id: str
    cookie_header: str
    request_context: Json
    session_context: Json
    context_budget: AgentContextBudget
    retry_policy: AgentRetryPolicy
    trace_id: str
    started_at: str


@dataclass
class AgentRunInput:
    """One agent request."""

    message: str
    history: list[Json]
    summary: str
    relevant_memories: list[Json]
    relevant_episodes: list[Json]
    context: AgentRunContext
    resume_action_id: str | None = None
    resume_decision: Json | None = None


@dataclass
class AgentToolCallRecord:
    """Auditable record for one tool call."""

    tool_call_id: str
    run_id: str
    agent_id: str
    tool_name: str
    input: Json
    output_summary: Json
    status: Literal["success", "error", "blocked"]
    latency_ms: int = 0
    attempts: int = 1
    retryable: bool = False
    error_code: str | None = None
    error_message: str | None = None
    requires_confirmation: bool = False


@dataclass
class AgentInterrupt:
    """Pending human-in-the-loop interruption."""

    pending_action_id: str
    tool_name: str
    proposed_args: Json
    allowed_decisions: list[str] = field(default_factory=lambda: ["accept", "edit", "reject"])


@dataclass
class AgentRunResult:
    """Normalized result returned to route handlers."""

    message: str
    suggested_products: list[Json] = field(default_factory=list)
    comparison: Json | None = None
    eligibility: Json | None = None
    pending_action: Json | None = None
    interrupt: AgentInterrupt | None = None
    tool_calls: list[AgentToolCallRecord] = field(default_factory=list)
    memory_updates: list[Json] = field(default_factory=list)
    usage: Json = field(default_factory=dict)
    agent_id: str = ""
    thread_id: str = ""
    run_id: str = ""
    retry_attempts: int = 0
    context_window: Json = field(default_factory=dict)
    used_agentic_loop: bool = True
    used_deepagents: bool = False
    fallback_reason: str | None = None

    def to_public_dict(self) -> Json:
        """Return the route-compatible assistant payload."""

        payload: Json = {
            "message": self.message,
            "usedAgenticLoop": self.used_agentic_loop,
            "usedDeepAgents": self.used_deepagents,
        }
        if self.suggested_products:
            payload["suggestedProducts"] = self.suggested_products
        if self.comparison is not None:
            payload["comparison"] = self.comparison
        if self.eligibility is not None:
            payload["eligibility"] = self.eligibility
        if self.pending_action is not None:
            payload["pendingAction"] = self.pending_action
        if self.fallback_reason:
            payload["agentFallbackReason"] = self.fallback_reason
        return payload


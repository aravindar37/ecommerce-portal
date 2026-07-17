"""Application-facing agent harness protocol."""

from __future__ import annotations

from typing import Iterator, Protocol

from .models import AgentRunInput, AgentRunResult, Json


class AgentHarness(Protocol):
    """Protocol implemented by Deep Agents wrapper."""

    def metadata(self) -> Json:
        """Return non-sensitive readiness metadata."""

    def run_message(self, agent_input: AgentRunInput) -> AgentRunResult:
        """Run one user message."""

    def stream_message(self, agent_input: AgentRunInput) -> Iterator[Json]:
        """Stream normalized agent events."""

    def resume(self, agent_input: AgentRunInput) -> AgentRunResult:
        """Resume an interrupted run."""


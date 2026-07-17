"""Token-aware context assembly for agent runs."""

from __future__ import annotations

import json
from typing import Any

from app.observability import compact

from .models import AgentContextBudget

Json = dict[str, Any]


def estimate_tokens(value: Any) -> int:
    """Estimate tokens conservatively without provider-specific tokenizers."""

    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, separators=(",", ":"), default=str)
    return max(1, (len(text) + 3) // 4)


def truncate_text(value: str, max_tokens: int) -> str:
    """Truncate text to an estimated token count."""

    max_chars = max_tokens * 4
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 3)].rstrip() + "..."


def compact_tool_result(value: Any, max_tokens: int) -> Any:
    """Return a compact version of a tool result for model context."""

    if estimate_tokens(value) <= max_tokens:
        return value
    compacted = compact(value)
    if isinstance(compacted, str):
        return truncate_text(compacted, max_tokens)
    return compacted


def score_message(message: Json, query: str, entity_ids: set[str]) -> int:
    """Score a historical message for context relevance."""

    content = str(message.get("content") or "").lower()
    query_terms = {term for term in query.lower().split() if len(term) > 2}
    overlap = sum(1 for term in query_terms if term in content)
    entity_score = sum(3 for entity_id in entity_ids if entity_id and entity_id.lower() in content)
    pending_score = 4 if (message.get("metadata") or {}).get("pendingActionId") else 0
    return overlap + entity_score + pending_score


def entity_ids_from_context(request_context: Json, session_context: Json) -> set[str]:
    """Extract product/order/ticket IDs from request and session context."""

    ids: set[str] = set()
    for context in (request_context, session_context):
        for key, value in context.items():
            if key.lower().endswith("id") and value:
                ids.add(str(value))
            if key.lower().endswith("ids") and isinstance(value, list):
                ids.update(str(item) for item in value if item)
    return ids


def assemble_context(
    *,
    message: str,
    history: list[Json],
    summary: str,
    memories: list[Json],
    episodes: list[Json],
    request_context: Json,
    session_context: Json,
    budget: AgentContextBudget,
) -> tuple[list[Json], Json]:
    """Assemble messages while staying inside the configured context budget."""

    entity_ids = entity_ids_from_context(request_context, session_context)
    recent = history[-budget.recent_message_limit :]
    older = history[: max(0, len(history) - len(recent))]
    ranked_older = sorted(
        older,
        key=lambda item: score_message(item, message, entity_ids),
        reverse=True,
    )[: budget.relevance_top_k]
    selected_memories = memories[: budget.relevance_top_k]
    selected_episodes = episodes[: budget.relevance_top_k]
    assembled: list[Json] = []
    if summary:
        assembled.append({"role": "system", "content": "Conversation summary: " + truncate_text(summary, budget.summary_max_tokens)})
    if selected_memories:
        assembled.append({"role": "system", "content": "Relevant user memories: " + json.dumps(selected_memories, default=str)})
    if selected_episodes:
        assembled.append({"role": "system", "content": "Relevant past episodes: " + json.dumps(selected_episodes, default=str)})
    assembled.extend(ranked_older)
    assembled.extend(recent)
    assembled.append({"role": "user", "content": message})

    dropped = 0
    while estimate_tokens(assembled) > budget.target_input_tokens and len(assembled) > 1:
        # Prefer removing the oldest complete user+assistant pair to preserve conversation coherence
        pair_index = None
        for i in range(len(assembled) - 1):
            if "Conversation summary:" in str(assembled[i].get("content") or ""):
                continue
            if assembled[i].get("role") == "user" and assembled[i + 1].get("role") == "assistant":
                pair_index = i
                break
        if pair_index is not None:
            assembled.pop(pair_index + 1)  # remove assistant first (higher index stays valid)
            assembled.pop(pair_index)       # then remove paired user message
            dropped += 2
            continue
        # Fallback: remove oldest standalone non-user, non-summary message
        removable_index = next(
            (
                index
                for index, item in enumerate(assembled)
                if item.get("role") != "user" and "Conversation summary:" not in str(item.get("content") or "")
            ),
            None,
        )
        if removable_index is None:
            break
        assembled.pop(removable_index)
        dropped += 1

    metadata = {
        "estimatedInputTokens": estimate_tokens(assembled),
        "targetInputTokens": budget.target_input_tokens,
        "maxInputTokens": budget.max_input_tokens,
        "messagesIncluded": len(assembled),
        "messagesDropped": dropped,
        "memoriesIncluded": len(selected_memories),
        "episodesIncluded": len(selected_episodes),
        "entityIds": sorted(entity_ids),
        "pruningStrategy": "summary_recent_relevance",
    }
    return assembled, metadata


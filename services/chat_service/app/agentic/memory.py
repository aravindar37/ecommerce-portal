"""Summary, episodic memory, and retrieval helpers."""

from __future__ import annotations

from typing import Any

from app.store import store

Json = dict[str, Any]


def session_summary(session: Json) -> str:
    """Return the best available compact conversation summary."""

    return str(session.get("summary") or "")


def retrieve_memories(user_id: str, agent_id: str, query: str, limit: int) -> list[Json]:
    """Return compact user memories relevant to a run."""

    memories = store.list_memories(user_id, agent_id, limit=max(1, limit * 2))
    terms = {term for term in query.lower().split() if len(term) > 2}
    ranked = sorted(
        memories,
        key=lambda item: (
            int(item.get("importance") or 0),
            sum(1 for term in terms if term in str(item.get("content") or "").lower()),
            str(item.get("updatedAt") or ""),
        ),
        reverse=True,
    )
    return ranked[:limit]


def retrieve_episodes(user_id: str, agent_id: str, query: str, limit: int) -> list[Json]:
    """Return compact episodic memories relevant to a run."""

    episodes = store.list_episodes(user_id, agent_id, limit=max(1, limit * 2))
    terms = {term for term in query.lower().split() if len(term) > 2}
    ranked = sorted(
        episodes,
        key=lambda item: (
            int(item.get("importance") or 0),
            sum(1 for term in terms if term in str(item.get("summary") or "").lower()),
            str(item.get("updatedAt") or ""),
        ),
        reverse=True,
    )
    return ranked[:limit]


_PREFERENCE_TRIGGERS = frozenset(["i prefer", "i like", "my size", "i'm a size", "favourite", "i always"])


def memory_candidates_from_run(message: str, response: str, agent_id: str) -> list[Json]:
    """Extract conservative memory candidates from a completed run."""

    candidates: list[Json] = []
    lowered_msg = message.lower()
    lowered_resp = response.lower()

    if any(t in lowered_msg for t in _PREFERENCE_TRIGGERS):
        candidates.append(
            {
                "agentId": agent_id,
                "type": "preference",
                "content": message.strip()[:500],
                "confidence": 0.6,
                "importance": 1,
            }
        )

    response_complete = "ticket number" in lowered_resp or (
        "return" in lowered_resp
        and any(kw in lowered_resp for kw in ["number", "created", "confirmed"])
    )
    if response_complete:
        candidates.append(
            {
                "agentId": agent_id,
                "type": "episodic",
                "content": f"User asked: {message.strip()[:300]} Assistant answered: {response.strip()[:300]}",
                "confidence": 0.5,
                "importance": 1,
            }
        )
    return candidates


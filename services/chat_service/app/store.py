"""Chat Service persistence with MongoDB Atlas and file-backed fallback."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import ChatServiceSettings, settings
from app.database import mongo

Json = dict[str, Any]


class ChatStoreError(Exception):
    """Raised when Chat Service state cannot be persisted."""


def now_iso() -> str:
    """Return the current UTC timestamp."""

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def new_id() -> str:
    """Return a demo object identifier."""

    return uuid.uuid4().hex[:24]


def clone(value: Any) -> Any:
    """Return a deep copy."""

    return copy.deepcopy(value)


def normalize(value: Any) -> Any:
    """Convert Mongo values into API-safe JSON structures."""

    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    return value


def title_from_content(content: str) -> str:
    """Create a compact session summary from the first user message."""

    cleaned = " ".join(content.strip().split())
    if not cleaned:
        return "New conversation"
    return cleaned[:77] + "..." if len(cleaned) > 80 else cleaned


def default_state() -> Json:
    """Return empty Chat Service state."""

    return {"chatSessions": [], "chatMessages": [], "pendingActions": []}


class ChatStore:
    """Repository for chat sessions/messages/actions."""

    def __init__(self, config: ChatServiceSettings) -> None:
        self.config = config
        self.path = config.chat_service_data_path
        self.state: Json = default_state()
        self.load()

    def load(self) -> None:
        """Load state from disk when available."""

        if not self.path.exists():
            self.state = default_state()
            return
        try:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ChatStoreError(f"Unable to load Chat Service state from {self.path}: {exc}") from exc

    def save(self) -> None:
        """Persist state to disk."""

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except OSError as exc:
            raise ChatStoreError(f"Unable to save Chat Service state to {self.path}: {exc}") from exc

    def create_session(self, session_type: str, user_id: str, context: Json) -> Json:
        """Create a chat session."""

        session = {
            "_id": new_id(),
            "type": session_type,
            "userId": user_id,
            "context": clone(context),
            "status": "active",
            "summary": "",
            "messageCount": 0,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        if mongo.configured:
            mongo.collection("chatSessions").insert_one(dict(session))
        else:
            self.state["chatSessions"].append(session)
            self.save()
        return clone(session)

    def find_session(self, session_id: str, user_id: str, session_type: str | None = None) -> Json | None:
        """Find an owned session."""

        if mongo.configured:
            query: Json = {"_id": session_id, "userId": user_id}
            if session_type:
                query["type"] = session_type
            doc = mongo.collection("chatSessions").find_one(query)
            return normalize(doc) if doc else None

        session = next(
            (
                item
                for item in self.state["chatSessions"]
                if item["_id"] == session_id and item["userId"] == user_id and (session_type is None or item["type"] == session_type)
            ),
            None,
        )
        return clone(session) if session else None

    def add_message(self, session_id: str, role: str, content: str, metadata: Json) -> Json:
        """Append a chat message."""

        message = {
            "_id": new_id(),
            "sessionId": session_id,
            "role": role,
            "content": content,
            "metadata": clone(metadata),
            "createdAt": now_iso(),
        }
        if mongo.configured:
            mongo.collection("chatMessages").insert_one(dict(message))
            update: Json = {
                "$set": {"updatedAt": message["createdAt"]},
                "$inc": {"messageCount": 1},
            }
            if role == "user":
                session = mongo.collection("chatSessions").find_one({"_id": session_id}, {"summary": 1})
                if not (session or {}).get("summary"):
                    update["$set"]["summary"] = title_from_content(content)
            mongo.collection("chatSessions").update_one({"_id": session_id}, update)
        else:
            self.state["chatMessages"].append(message)
            for session in self.state["chatSessions"]:
                if session["_id"] == session_id:
                    session["updatedAt"] = message["createdAt"]
                    session["messageCount"] = int(session.get("messageCount") or 0) + 1
                    if role == "user" and not session.get("summary"):
                        session["summary"] = title_from_content(content)
            self.save()
        return clone(message)

    def latest_session(self, user_id: str, session_type: str) -> Json | None:
        """Return the latest active owned session of a given type."""

        if mongo.configured:
            doc = mongo.collection("chatSessions").find_one(
                {"userId": user_id, "type": session_type, "status": "active"},
                sort=[("updatedAt", -1), ("createdAt", -1)],
            )
            return normalize(doc) if doc else None

        sessions = [
            item
            for item in self.state["chatSessions"]
            if item["userId"] == user_id and item["type"] == session_type and item.get("status") == "active"
        ]
        sessions.sort(key=lambda item: item.get("updatedAt") or item.get("createdAt") or "", reverse=True)
        return clone(sessions[0]) if sessions else None

    def list_messages(self, session_id: str, limit: int = 100) -> list[Json]:
        """Return session messages in chronological order."""

        bounded_limit = min(max(limit, 1), 200)
        if mongo.configured:
            docs = list(
                mongo.collection("chatMessages")
                .find({"sessionId": session_id})
                .sort("createdAt", 1)
                .limit(bounded_limit)
            )
            return [normalize(doc) for doc in docs]

        return clone(
            [
                item
                for item in self.state["chatMessages"]
                if item["sessionId"] == session_id
            ][:bounded_limit]
        )

    def list_sessions(self, user_id: str, session_type: str, limit: int = 20, before: str | None = None) -> Json:
        """Return paginated owned chat sessions."""

        bounded_limit = min(max(limit, 1), 50)
        if mongo.configured:
            query: Json = {"userId": user_id, "type": session_type}
            if before:
                before_doc = mongo.collection("chatSessions").find_one({"_id": before, "userId": user_id, "type": session_type})
                if before_doc:
                    query["updatedAt"] = {"$lt": before_doc.get("updatedAt")}
            docs = list(
                mongo.collection("chatSessions")
                .find(query)
                .sort([("updatedAt", -1), ("createdAt", -1)])
                .limit(bounded_limit + 1)
            )
            has_more = len(docs) > bounded_limit
            items = [normalize(doc) for doc in docs[:bounded_limit]]
            return {"items": items, "hasMore": has_more, "nextCursor": items[-1]["_id"] if has_more and items else None}

        sessions = [
            item
            for item in self.state["chatSessions"]
            if item["userId"] == user_id and item["type"] == session_type
        ]
        sessions.sort(key=lambda item: item.get("updatedAt") or item.get("createdAt") or "", reverse=True)
        if before:
            before_index = next((index for index, item in enumerate(sessions) if item["_id"] == before), None)
            if before_index is not None:
                sessions = sessions[before_index + 1 :]
        items = clone(sessions[:bounded_limit])
        has_more = len(sessions) > bounded_limit
        return {"items": items, "hasMore": has_more, "nextCursor": items[-1]["_id"] if has_more and items else None}

    def create_action(self, session_id: str, user_id: str, action_type: str, payload: Json) -> Json:
        """Create a pending mutating action."""

        expires_at = datetime.now(UTC) + timedelta(seconds=self.config.assistant_action_ttl_seconds)
        action = {
            "_id": new_id(),
            "sessionId": session_id,
            "userId": user_id,
            "type": action_type,
            "payload": clone(payload),
            "status": "pending",
            "expiresAt": expires_at,
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        if mongo.configured:
            mongo.collection("pendingActions").insert_one(dict(action))
        else:
            action["expiresAt"] = normalize(expires_at)
            self.state["pendingActions"].append(action)
            self.save()
        return normalize(action)

    def find_action(self, action_id: str, user_id: str) -> Json | None:
        """Find an owned pending action."""

        if mongo.configured:
            doc = mongo.collection("pendingActions").find_one({"_id": action_id, "userId": user_id})
            return normalize(doc) if doc else None
        action = next((item for item in self.state["pendingActions"] if item["_id"] == action_id and item["userId"] == user_id), None)
        return clone(action) if action else None

    def complete_action(self, action: Json, status: str, output: Json) -> Json:
        """Complete or cancel a pending action."""

        action["status"] = status
        action["output"] = clone(output)
        action["updatedAt"] = now_iso()
        if mongo.configured:
            mongo.collection("pendingActions").update_one(
                {"_id": action["_id"]},
                {"$set": {"status": status, "output": clone(output), "updatedAt": action["updatedAt"]}},
            )
        else:
            for index, item in enumerate(self.state["pendingActions"]):
                if item["_id"] == action["_id"]:
                    self.state["pendingActions"][index] = clone(action)
                    break
            self.save()
        return normalize(action)


store = ChatStore(settings)

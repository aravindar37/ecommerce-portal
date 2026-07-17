"""MongoDB Atlas connection helpers for Chat Service."""

from __future__ import annotations

from typing import Any

from app.config import ChatServiceSettings, settings


class MongoChatConnection:
    """Lazy MongoDB Atlas connection for chat-owned collections."""

    def __init__(self, config: ChatServiceSettings) -> None:
        self.config = config
        self._client: Any | None = None
        self._database: Any | None = None

    @property
    def configured(self) -> bool:
        """Return whether MongoDB Atlas persistence is configured."""

        return bool(self.config.mongodb_uri.strip())

    def client(self) -> Any:
        """Return a lazy pymongo client."""

        if not self.configured:
            raise RuntimeError("MONGODB_URI is not configured")
        if self._client is None:
            try:
                import certifi
                from pymongo import MongoClient
            except ImportError as exc:
                raise RuntimeError("pymongo and certifi required for MongoDB Atlas") from exc
            self._client = MongoClient(
                self.config.mongodb_uri,
                serverSelectionTimeoutMS=3000,
                tlsCAFile=certifi.where(),
            )
        return self._client

    def database(self) -> Any:
        """Return the configured MongoDB database handle."""

        if self._database is None:
            self._database = self.client()[self.config.mongodb_db]
        return self._database

    def collection(self, name: str) -> Any:
        """Return a named collection handle."""

        return self.database()[name]

    def ensure_indexes(self) -> None:
        """Create Chat Service indexes when MongoDB Atlas mode is configured."""

        if not self.configured:
            return
        self.collection("chatSessions").create_index([("userId", 1), ("type", 1), ("updatedAt", -1)])
        self.collection("chatSessions").create_index([("userId", 1), ("type", 1), ("status", 1), ("updatedAt", -1)])
        self.collection("chatMessages").create_index([("sessionId", 1), ("createdAt", 1)])
        self.collection("pendingActions").create_index([("userId", 1), ("status", 1), ("expiresAt", 1)])
        self.collection("pendingActions").create_index("expiresAt", expireAfterSeconds=0)
        self.collection("agentRuns").create_index([("sessionId", 1), ("startedAt", -1)])
        self.collection("agentRuns").create_index([("userId", 1), ("agentId", 1), ("startedAt", -1)])
        self.collection("agentToolCalls").create_index([("runId", 1), ("createdAt", 1)])
        self.collection("agentToolCalls").create_index([("sessionId", 1), ("createdAt", 1)])
        self.collection("agentInterrupts").create_index([("pendingActionId", 1), ("userId", 1)])
        self.collection("chatMemories").create_index([("userId", 1), ("agentId", 1), ("status", 1), ("updatedAt", -1)])
        self.collection("chatEpisodes").create_index([("userId", 1), ("agentId", 1), ("updatedAt", -1)])

    def health(self) -> dict[str, object]:
        """Return database readiness metadata without exposing connection details."""

        if not self.configured:
            return {"provider": "file_backed", "ready": True}
        try:
            self.client().admin.command("ping")
        except Exception:
            return {"provider": "mongodb_atlas", "ready": False}
        return {"provider": "mongodb_atlas", "ready": True}


mongo = MongoChatConnection(settings)

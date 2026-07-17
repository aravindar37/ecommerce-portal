"""MongoDB Atlas connection helpers for Core Service."""

from __future__ import annotations

from typing import Any

from app.config import CoreServiceSettings, settings


class MongoConnection:
    """Lazy MongoDB Atlas connection wrapper.

    The demo currently runs against the local file-backed repository unless
    `MONGODB_URI` is configured and the pymongo dependency is installed.
    """

    def __init__(self, config: CoreServiceSettings) -> None:
        self.config = config
        self._client: Any | None = None
        self._database: Any | None = None

    @property
    def configured(self) -> bool:
        """Return whether a MongoDB URI is available."""

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
                raise RuntimeError("pymongo and certifi must be installed for MongoDB Atlas mode") from exc
            self._client = MongoClient(self.config.mongodb_uri, serverSelectionTimeoutMS=3000, tlsCAFile=certifi.where())
        return self._client

    def database(self) -> Any:
        """Return the configured MongoDB database handle."""

        if self._database is None:
            self._database = self.client()[self.config.mongodb_db]
        return self._database

    def collection(self, name: str) -> Any:
        """Return a named collection handle."""

        return self.database()[name]

    def _drop_index_if_exists(self, collection_name: str, index_name: str) -> None:
        """Drop a named index if it exists, ignoring errors if it does not."""
        try:
            self.collection(collection_name).drop_index(index_name)
        except Exception:
            pass

    def ensure_indexes(self) -> None:
        """Create Core Service indexes when MongoDB Atlas mode is configured.

        Indexes that previously existed without uniqueness constraints are dropped
        and recreated with the correct options before any create_index call that
        changes those options, avoiding IndexKeySpecsConflict on startup.
        """
        if not self.configured:
            return

        # orders: old compound index was non-unique; drop it so we can add the
        # standalone unique orderNumber index alongside the updated compound one.
        self._drop_index_if_exists("orders", "userId_1_orderNumber_1")

        # carts: old index was a 3-field compound (userId, anonymousId, status);
        # drop it so the two focused indexes below can take its place cleanly.
        self._drop_index_if_exists("carts", "userId_1_anonymousId_1_status_1")

        self.collection("users").create_index("email", unique=True)
        self.collection("users").create_index("phoneNumber", unique=True, sparse=True)

        self.collection("sessions").create_index("sessionTokenHash", unique=True)
        self.collection("sessions").create_index("expiresAt", expireAfterSeconds=0)

        self.collection("passwordResetTokens").create_index("tokenHash", unique=True)
        self.collection("passwordResetTokens").create_index("expiresAt", expireAfterSeconds=0)

        self.collection("products").create_index([("source", 1), ("sourceProductId", 1)], unique=True)
        self.collection("products").create_index("slug", unique=True)
        self.collection("products").create_index([("gender", 1), ("masterCategory", 1), ("subCategory", 1)])

        self.collection("carts").create_index([("userId", 1), ("status", 1)])
        self.collection("carts").create_index([("anonymousId", 1), ("status", 1)])

        # orderNumber is globally unique (atomic counter) — enforce at DB level.
        # Keep the compound (userId, orderNumber) for efficient per-user lookups.
        self.collection("orders").create_index("orderNumber", unique=True)
        self.collection("orders").create_index([("userId", 1), ("orderNumber", 1)])
        self.collection("orders").create_index([("userId", 1), ("createdAt", -1)])

        self.collection("returnRequests").create_index([("userId", 1), ("createdAt", -1)])
        self.collection("returnRequests").create_index("orderId")

        self.collection("supportTickets").create_index("ticketNumber", unique=True)
        self.collection("supportTickets").create_index([("userId", 1), ("createdAt", -1)])

        self.collection("userActivityEvents").create_index([("eventType", 1), ("occurredAt", -1)])
        self.collection("userActivityEvents").create_index([("userId", 1), ("occurredAt", -1)])

        self.collection("agentToolAuditLogs").create_index([("agentType", 1), ("createdAt", -1)])

    def health(self) -> dict[str, object]:
        """Return database readiness metadata without exposing connection details."""

        if not self.configured:
            return {"provider": "mongodb_atlas", "ready": True, "mode": "local_file_backed"}
        try:
            self.client().admin.command("ping")
        except Exception:
            return {"provider": "mongodb_atlas", "ready": False, "mode": "atlas"}
        return {"provider": "mongodb_atlas", "ready": True, "mode": "atlas"}


mongo = MongoConnection(settings)

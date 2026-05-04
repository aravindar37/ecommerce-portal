"""MongoDB Atlas search/vector index helpers."""

from __future__ import annotations

from typing import Any

from app.config import SearchServiceSettings, settings


class AtlasIndexManager:
    """Lazy MongoDB Atlas helper for index validation metadata."""

    def __init__(self, config: SearchServiceSettings) -> None:
        self.config = config
        self._client: Any | None = None
        self._database: Any | None = None

    @property
    def configured(self) -> bool:
        """Return whether Atlas connection settings are present."""

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

    def health(self) -> dict[str, object]:
        """Return Atlas readiness metadata without sensitive details."""

        if not self.configured:
            return {"provider": "mongodb_atlas", "ready": True, "mode": "local_read_model"}
        try:
            self.client().admin.command("ping")
        except Exception:
            return {"provider": "mongodb_atlas", "ready": False, "mode": "atlas"}
        return {"provider": "mongodb_atlas", "ready": True, "mode": "atlas"}

    def metadata(self) -> dict[str, object]:
        """Return configured index metadata."""

        return {
            "keywordIndexName": self.config.mongodb_search_index_name,
            "vectorIndexName": self.config.mongodb_vector_index_name,
            "dimensions": self.config.embedding_dimensions,
            "filterFields": ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "season", "usage", "priceAmount"],
            "hybridSearch": {
                "enabled": True,
                "fullTextCollection": "products",
                "vectorCollection": "productEmbeddings",
                "filtersAppliedTo": ["fullText", "vector"],
                "fusion": {"vectorWeight": 0.6, "fullTextWeight": 0.4},
            },
            "ready": self.health()["ready"],
        }

    def product_search_index_definition(self) -> dict[str, object]:
        """Return the Atlas Search index definition for product full-text search."""

        return {
            "mappings": {
                "dynamic": False,
                "fields": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "brand": {"type": "string"},
                    "gender": [{"type": "string"}, {"type": "token"}],
                    "masterCategory": [{"type": "string"}, {"type": "token"}],
                    "subCategory": [{"type": "string"}, {"type": "token"}],
                    "articleType": [{"type": "string"}, {"type": "token"}],
                    "baseColour": [{"type": "string"}, {"type": "token"}],
                    "season": [{"type": "string"}, {"type": "token"}],
                    "usage": [{"type": "string"}, {"type": "token"}],
                    "tags": {"type": "string"},
                    "isActive": {"type": "boolean"},
                    "price": {"type": "document", "fields": {"amount": {"type": "number"}}},
                },
            }
        }

    def vector_index_definition(self) -> dict[str, object]:
        """Return the Atlas Vector Search index definition for product embeddings."""

        return {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": self.config.embedding_dimensions,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "productId"},
                {"type": "filter", "path": "provider"},
                {"type": "filter", "path": "model"},
                {"type": "filter", "path": "dimensions"},
                {"type": "filter", "path": "textTemplateVersion"},
                {"type": "filter", "path": "metadata.gender"},
                {"type": "filter", "path": "metadata.masterCategory"},
                {"type": "filter", "path": "metadata.subCategory"},
                {"type": "filter", "path": "metadata.articleType"},
                {"type": "filter", "path": "metadata.baseColour"},
                {"type": "filter", "path": "metadata.season"},
                {"type": "filter", "path": "metadata.usage"},
                {"type": "filter", "path": "metadata.priceAmount"},
                {"type": "filter", "path": "metadata.isActive"},
            ]
        }

    def definitions(self) -> dict[str, object]:
        """Return both required Atlas index definitions."""

        return {
            "products": {
                "collection": "products",
                "name": self.config.mongodb_search_index_name,
                "type": "search",
                "definition": self.product_search_index_definition(),
            },
            "productEmbeddings": {
                "collection": "productEmbeddings",
                "name": self.config.mongodb_vector_index_name,
                "type": "vectorSearch",
                "definition": self.vector_index_definition(),
            },
        }

    def upsert_search_index(self, collection_name: str, name: str, index_type: str, definition: dict[str, object]) -> str:
        """Create or update one Atlas Search index."""

        try:
            from pymongo.operations import SearchIndexModel
        except ImportError as exc:
            raise RuntimeError("pymongo must be installed for Atlas search index management") from exc
        collection = self.database()[collection_name]
        existing = {item.get("name") for item in collection.list_search_indexes()}
        if name in existing:
            collection.update_search_index(name=name, definition=definition)
            return "updated"
        collection.create_search_index(SearchIndexModel(definition=definition, name=name, type=index_type))
        return "created"

    def ensure_indexes(self) -> dict[str, object]:
        """Create or update required Atlas full-text and vector indexes."""

        if not self.configured:
            return {"configured": False, "actions": [], "message": "MONGODB_URI is not configured"}
        actions = []
        for index in self.definitions().values():
            assert isinstance(index, dict)
            action = self.upsert_search_index(
                str(index["collection"]),
                str(index["name"]),
                str(index["type"]),
                index["definition"],  # type: ignore[arg-type]
            )
            actions.append({"collection": index["collection"], "name": index["name"], "type": index["type"], "action": action})
        return {"configured": True, "actions": actions}


atlas_indexes = AtlasIndexManager(settings)

"""Runtime configuration for Search Service embedding generation."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def env_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable with a conservative default."""

    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class EmbeddingSettings(BaseModel):
    """Environment-backed settings for product embedding generation."""

    provider: str = Field(default="ollama")
    model: str = Field(default="nomic-embed-text:v1.5")
    dimensions: int = Field(default=768)
    text_template_version: str = Field(default="product-v1")
    text_max_chars: int = Field(default=4000)
    batch_size: int = Field(default=8)
    timeout_ms: int = Field(default=60000)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_embed_path: str = Field(default="/api/embed")
    voyage_api_base_url: str = Field(default="https://api.voyageai.com/v1")
    voyage_api_key: str = Field(default="")
    voyage_input_type_document: str = Field(default="document")
    input_products_path: Path = Field(default=Path("./artifacts/ingestion/products.jsonl"))
    output_embeddings_path: Path = Field(default=Path("./artifacts/embeddings/product_embeddings.jsonl"))
    checkpoint_enabled: bool = Field(default=False)
    checkpoint_path: Path | None = Field(default=None)
    mongodb_uri: str = Field(default="")
    mongodb_db: str = Field(default="ecommerce_demo")

    @classmethod
    def from_env(cls) -> "EmbeddingSettings":
        """Build settings from environment variables."""

        return cls(
            provider=os.getenv("EMBEDDING_PROVIDER", "ollama"),
            model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5"),
            dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
            text_template_version=os.getenv("EMBEDDING_TEXT_TEMPLATE_VERSION", "product-v1"),
            text_max_chars=int(os.getenv("EMBEDDING_TEXT_MAX_CHARS", "4000")),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "8")),
            timeout_ms=int(os.getenv("EMBEDDING_TIMEOUT_MS", "60000")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_embed_path=os.getenv("OLLAMA_EMBED_PATH", "/api/embed"),
            voyage_api_base_url=os.getenv("VOYAGE_API_BASE_URL", "https://api.voyageai.com/v1"),
            voyage_api_key=os.getenv("VOYAGE_API_KEY", ""),
            voyage_input_type_document=os.getenv("VOYAGE_INPUT_TYPE_DOCUMENT", "document"),
            input_products_path=Path(os.getenv("PRODUCTS_JSONL_PATH", "./artifacts/ingestion/products.jsonl")),
            output_embeddings_path=Path(os.getenv("PRODUCT_EMBEDDINGS_JSONL_PATH", "./artifacts/embeddings/product_embeddings.jsonl")),
            checkpoint_enabled=env_bool("EMBEDDING_CHECKPOINT_ENABLED", False),
            checkpoint_path=(
                Path(os.environ["EMBEDDING_CHECKPOINT_PATH"])
                if os.getenv("EMBEDDING_CHECKPOINT_PATH", "").strip()
                else None
            ),
            mongodb_uri=os.getenv("MONGODB_URI", ""),
            mongodb_db=os.getenv("MONGODB_DB", "ecommerce_demo"),
        )

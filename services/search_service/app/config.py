"""Search Service runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class SearchServiceSettings(BaseModel):
    """Typed environment-backed settings for Search Service."""

    app_env: str = Field(default="development")
    core_service_base_url: str = Field(default="http://localhost:4000")
    search_service_base_url: str = Field(default="http://localhost:4001")
    core_service_internal_token: str = Field(default="")
    dataset_name: str = Field(default="kaggle-fashion-product-images")
    dataset_path: Path = Field(default=Path("./dataset"))
    product_image_local_root: Path = Field(default=Path("./dataset/images"))
    core_service_data_path: Path = Field(default=Path("./artifacts/core_service/state.json"))
    products_jsonl_path: Path = Field(default=Path("./artifacts/ingestion/products.jsonl"))
    product_embeddings_jsonl_path: Path = Field(default=Path("./artifacts/embeddings/product_embeddings.jsonl"))
    mongodb_uri: str = Field(default="")
    mongodb_db: str = Field(default="ecommerce_demo")
    mongodb_vector_index_name: str = Field(default="product_embeddings_voyage")
    mongodb_search_index_name: str = Field(default="products_keyword")
    embedding_provider: str = Field(default="mongodb_atlas_autoembed")
    embedding_model: str = Field(default="voyage-4")
    embedding_dimensions: int = Field(default=1024)
    embedding_text_template_version: str = Field(default="product-v1")
    embedding_text_max_chars: int = Field(default=4000)
    embedding_batch_size: int = Field(default=8)
    embedding_timeout_ms: int = Field(default=60000)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_embed_path: str = Field(default="/api/embed")
    voyage_api_base_url: str = Field(default="https://api.voyageai.com/v1")
    voyage_api_key: str = Field(default="")
    voyage_input_type_query: str = Field(default="query")
    demo_currency: str = Field(default="INR")
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    rate_limit_search_per_minute: int = Field(default=0)

    @classmethod
    def from_env(cls) -> "SearchServiceSettings":
        """Build settings from process environment variables."""

        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            core_service_base_url=os.getenv("CORE_SERVICE_BASE_URL", "http://localhost:4000"),
            search_service_base_url=os.getenv("SEARCH_SERVICE_BASE_URL", "http://localhost:4001"),
            core_service_internal_token=os.getenv("CORE_SERVICE_INTERNAL_TOKEN", ""),
            dataset_name=os.getenv("DATASET_NAME", "kaggle-fashion-product-images"),
            dataset_path=Path(os.getenv("DATASET_PATH", "./dataset")),
            product_image_local_root=Path(os.getenv("PRODUCT_IMAGE_LOCAL_ROOT", "./dataset/images")),
            core_service_data_path=Path(os.getenv("CORE_SERVICE_DATA_PATH", "./artifacts/core_service/state.json")),
            products_jsonl_path=Path(os.getenv("PRODUCTS_JSONL_PATH", "./artifacts/ingestion/products.jsonl")),
            product_embeddings_jsonl_path=Path(
                os.getenv("PRODUCT_EMBEDDINGS_JSONL_PATH", "./artifacts/embeddings/product_embeddings.jsonl")
            ),
            mongodb_uri=os.getenv("MONGODB_URI", ""),
            mongodb_db=os.getenv("MONGODB_DB", "ecommerce_demo"),
            mongodb_vector_index_name=os.getenv("MONGODB_VECTOR_INDEX_NAME", "product_embeddings_voyage"),
            mongodb_search_index_name=os.getenv("MONGODB_SEARCH_INDEX_NAME", "products_keyword"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "mongodb_atlas_autoembed"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "voyage-4"),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1024")),
            embedding_text_template_version=os.getenv("EMBEDDING_TEXT_TEMPLATE_VERSION", "product-v1"),
            embedding_text_max_chars=int(os.getenv("EMBEDDING_TEXT_MAX_CHARS", "4000")),
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "8")),
            embedding_timeout_ms=int(os.getenv("EMBEDDING_TIMEOUT_MS", "60000")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_embed_path=os.getenv("OLLAMA_EMBED_PATH", "/api/embed"),
            voyage_api_base_url=os.getenv("VOYAGE_API_BASE_URL", "https://api.voyageai.com/v1"),
            voyage_api_key=os.getenv("VOYAGE_API_KEY", ""),
            voyage_input_type_query=os.getenv("VOYAGE_INPUT_TYPE_QUERY", "query"),
            demo_currency=os.getenv("DEMO_CURRENCY", "INR"),
            cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
            rate_limit_search_per_minute=int(os.getenv("RATE_LIMIT_SEARCH_PER_MINUTE", "0")),
        )


settings = SearchServiceSettings.from_env()

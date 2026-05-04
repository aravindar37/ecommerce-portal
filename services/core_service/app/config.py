"""Core Service runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class CoreServiceSettings(BaseModel):
    """Typed environment configuration for Core Service."""

    app_env: str = Field(default="development")
    app_base_url: str = Field(default="http://localhost:3000")
    dataset_name: str = Field(default="kaggle-fashion-product-images")
    dataset_path: Path = Field(default=Path("./dataset"))
    ingestion_output_dir: Path = Field(default=Path("./artifacts/ingestion"))
    product_image_local_root: Path = Field(default=Path("./dataset/images"))
    product_image_public_base_url: str = Field(default="/product-images")
    demo_currency: str = Field(default="INR")
    demo_tax_percent: float = Field(default=18.0)
    demo_free_shipping_threshold: float = Field(default=3000.0)
    demo_shipping_fee: float = Field(default=99.0)
    auth_google_enabled: bool = Field(default=False)
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(default="")
    password_hash_algorithm: str = Field(default="argon2id")
    cookie_secure: bool = Field(default=False)
    session_cookie_max_age_seconds: int = Field(default=604800)
    admin_seed_email: str = Field(default="admin@example.test")
    admin_seed_password: str = Field(default="")
    test_admin_token: str = Field(default="")
    chat_service_internal_token: str = Field(default="")
    core_data_path: Path = Field(default=Path("./artifacts/core_service/state.json"))
    mongodb_uri: str = Field(default="")
    mongodb_db: str = Field(default="ecommerce_demo")
    embedding_provider: str = Field(default="ollama")
    embedding_model: str = Field(default="nomic-embed-text:v1.5")
    embedding_dimensions: int = Field(default=768)
    embedding_text_template_version: str = Field(default="product-v1")
    mongodb_vector_index_name: str = Field(default="product_embeddings_ollama_768")
    llm_provider: str = Field(default="openai")
    llm_model: str = Field(default="gpt-5.4")
    codex_mcp_enabled: bool = Field(default=True)
    codex_mcp_transport: str = Field(default="stdio")
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    rate_limit_auth_per_minute: int = Field(default=0)

    @classmethod
    def from_env(cls) -> "CoreServiceSettings":
        """Build settings from environment variables."""

        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_base_url=os.getenv("APP_BASE_URL", "http://localhost:3000"),
            dataset_name=os.getenv("DATASET_NAME", "kaggle-fashion-product-images"),
            dataset_path=Path(os.getenv("DATASET_PATH", "./dataset")),
            ingestion_output_dir=Path(os.getenv("INGESTION_OUTPUT_DIR", "./artifacts/ingestion")),
            product_image_local_root=Path(os.getenv("PRODUCT_IMAGE_LOCAL_ROOT", "./dataset/images")),
            product_image_public_base_url=os.getenv("PRODUCT_IMAGE_PUBLIC_BASE_URL", "/product-images"),
            demo_currency=os.getenv("DEMO_CURRENCY", "INR"),
            demo_tax_percent=float(os.getenv("DEMO_TAX_PERCENT", "18")),
            demo_free_shipping_threshold=float(os.getenv("DEMO_FREE_SHIPPING_THRESHOLD", "3000")),
            demo_shipping_fee=float(os.getenv("DEMO_SHIPPING_FEE", "99")),
            auth_google_enabled=os.getenv("AUTH_GOOGLE_ENABLED", "false").lower() == "true",
            google_client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            google_redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", ""),
            password_hash_algorithm=os.getenv("PASSWORD_HASH_ALGORITHM", "argon2id"),
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
            session_cookie_max_age_seconds=int(os.getenv("SESSION_COOKIE_MAX_AGE_SECONDS", "604800")),
            admin_seed_email=os.getenv("ADMIN_SEED_EMAIL", "admin@example.test"),
            admin_seed_password=os.getenv("ADMIN_SEED_PASSWORD", ""),
            test_admin_token=os.getenv("TEST_ADMIN_TOKEN", ""),
            chat_service_internal_token=os.getenv("CHAT_SERVICE_INTERNAL_TOKEN", ""),
            core_data_path=Path(os.getenv("CORE_SERVICE_DATA_PATH", "./artifacts/core_service/state.json")),
            mongodb_uri=os.getenv("MONGODB_URI", ""),
            mongodb_db=os.getenv("MONGODB_DB", "ecommerce_demo"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "ollama"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text:v1.5"),
            embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "768")),
            embedding_text_template_version=os.getenv("EMBEDDING_TEXT_TEMPLATE_VERSION", "product-v1"),
            mongodb_vector_index_name=os.getenv("MONGODB_VECTOR_INDEX_NAME", "product_embeddings_ollama_768"),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            llm_model=os.getenv("LLM_MODEL", "gpt-5.4"),
            codex_mcp_enabled=os.getenv("CODEX_MCP_ENABLED", "true").lower() == "true",
            codex_mcp_transport=os.getenv("CODEX_MCP_TRANSPORT", "stdio"),
            cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
            rate_limit_auth_per_minute=int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "0")),
        )


settings = CoreServiceSettings.from_env()

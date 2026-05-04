"""Chat Service runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class ChatServiceSettings(BaseModel):
    """Typed environment-backed settings for Chat Service."""

    app_env: str = Field(default="development")
    core_service_base_url: str = Field(default="http://localhost:4000")
    search_service_base_url: str = Field(default="http://localhost:4001")
    chat_service_base_url: str = Field(default="http://localhost:4002")
    core_service_internal_token: str = Field(default="")
    search_service_internal_token: str = Field(default="")
    chat_service_internal_token: str = Field(default="")
    mongodb_uri: str = Field(default="")
    mongodb_db: str = Field(default="ecommerce_demo")
    chat_service_data_path: Path = Field(default=Path("./artifacts/chat_service/state.json"))
    llm_provider: str = Field(default="openai")
    llm_model: str = Field(default="gpt-5.4")
    llm_api_base_url: str = Field(default="https://api.openai.com/v1")
    llm_chat_completions_path: str = Field(default="/chat/completions")
    llm_api_key: str = Field(default="")
    llm_timeout_ms: int = Field(default=60000)
    llm_max_output_tokens: int = Field(default=1200)
    llm_temperature: float = Field(default=0.3)
    llm_streaming_enabled: bool = Field(default=True)
    codex_mcp_enabled: bool = Field(default=True)
    codex_mcp_transport: str = Field(default="stdio")
    codex_mcp_command: str = Field(default="codex")
    codex_mcp_args: str = Field(default="mcp,serve")
    codex_mcp_url: str = Field(default="http://localhost:9000/mcp")
    codex_mcp_timeout_ms: int = Field(default=120000)
    assistant_action_ttl_seconds: int = Field(default=900)
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    rate_limit_chat_per_minute: int = Field(default=0)
    log_level: str = Field(default="DEBUG")
    log_request_bodies: bool = Field(default=True)
    log_response_bodies: bool = Field(default=True)

    @classmethod
    def from_env(cls) -> "ChatServiceSettings":
        """Build settings from process environment variables."""

        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            core_service_base_url=os.getenv("CORE_SERVICE_BASE_URL", "http://localhost:4000"),
            search_service_base_url=os.getenv("SEARCH_SERVICE_BASE_URL", "http://localhost:4001"),
            chat_service_base_url=os.getenv("CHAT_SERVICE_BASE_URL", "http://localhost:4002"),
            core_service_internal_token=os.getenv("CORE_SERVICE_INTERNAL_TOKEN", ""),
            search_service_internal_token=os.getenv("SEARCH_SERVICE_INTERNAL_TOKEN", ""),
            chat_service_internal_token=os.getenv("CHAT_SERVICE_INTERNAL_TOKEN", ""),
            mongodb_uri=os.getenv("MONGODB_URI", ""),
            mongodb_db=os.getenv("MONGODB_DB", "ecommerce_demo"),
            chat_service_data_path=Path(os.getenv("CHAT_SERVICE_DATA_PATH", "./artifacts/chat_service/state.json")),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            llm_model=os.getenv("LLM_MODEL", "gpt-5.4"),
            llm_api_base_url=os.getenv("LLM_API_BASE_URL", "https://api.openai.com/v1"),
            llm_chat_completions_path=os.getenv("LLM_CHAT_COMPLETIONS_PATH", "/chat/completions"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_timeout_ms=int(os.getenv("LLM_TIMEOUT_MS", "60000")),
            llm_max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1200")),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            llm_streaming_enabled=os.getenv("LLM_STREAMING_ENABLED", "true").lower() == "true",
            codex_mcp_enabled=os.getenv("CODEX_MCP_ENABLED", "true").lower() == "true",
            codex_mcp_transport=os.getenv("CODEX_MCP_TRANSPORT", "stdio"),
            codex_mcp_command=os.getenv("CODEX_MCP_COMMAND", "codex"),
            codex_mcp_args=os.getenv("CODEX_MCP_ARGS", "mcp,serve"),
            codex_mcp_url=os.getenv("CODEX_MCP_URL", "http://localhost:9000/mcp"),
            codex_mcp_timeout_ms=int(os.getenv("CODEX_MCP_TIMEOUT_MS", "120000")),
            assistant_action_ttl_seconds=int(os.getenv("ASSISTANT_ACTION_TTL_SECONDS", "900")),
            cors_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
            rate_limit_chat_per_minute=int(os.getenv("RATE_LIMIT_CHAT_PER_MINUTE", "0")),
            log_level=os.getenv("CHAT_LOG_LEVEL", "DEBUG"),
            log_request_bodies=os.getenv("CHAT_LOG_REQUEST_BODIES", "true").lower() == "true",
            log_response_bodies=os.getenv("CHAT_LOG_RESPONSE_BODIES", "true").lower() == "true",
        )


settings = ChatServiceSettings.from_env()

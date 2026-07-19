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
    test_admin_token: str = Field(default="")
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
    agent_harness: str = Field(default="langgraph")
    agentic_enabled: bool = Field(default=True)
    agent_max_model_calls_per_run: int = Field(default=8)
    agent_max_tool_calls_per_run: int = Field(default=12)
    agent_tool_timeout_ms: int = Field(default=15000)
    agent_streaming_enabled: bool = Field(default=True)
    agent_summary_trigger_messages: int = Field(default=6)
    agent_memory_enabled: bool = Field(default=True)
    agent_episodic_memory_enabled: bool = Field(default=True)
    agent_hitl_enabled: bool = Field(default=True)
    agent_deepagents_enable_subagents: bool = Field(default=True)
    agent_deepagents_memory_paths: str = Field(default="/memories/preferences.md,/memories/episodes.md")
    agent_deepagents_filesystem_policy: str = Field(default="deny")
    agent_retry_max_attempts: int = Field(default=3)
    agent_retry_base_delay_ms: int = Field(default=250)
    agent_retry_max_delay_ms: int = Field(default=3000)
    agent_retry_jitter_enabled: bool = Field(default=True)
    agent_retryable_status_codes: str = Field(default="408,409,425,429,500,502,503,504")
    agent_context_max_input_tokens: int = Field(default=24000)
    agent_context_target_input_tokens: int = Field(default=18000)
    agent_context_recent_message_limit: int = Field(default=12)
    agent_context_relevance_top_k: int = Field(default=8)
    agent_context_summary_max_tokens: int = Field(default=1200)
    agent_context_tool_result_max_tokens: int = Field(default=1600)
    agent_trace_verbose: bool = Field(default=False)
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
    elevenlabs_api_key: str = Field(default="")
    elevenlabs_voice_id: str = Field(default="")
    elevenlabs_stt_model: str = Field(default="scribe_v2_realtime")
    elevenlabs_stt_realtime_ws_url: str = Field(default="wss://api.elevenlabs.io/v1/speech-to-text/realtime")
    elevenlabs_stt_commit_strategy: str = Field(default="vad")
    elevenlabs_stt_vad_silence_threshold_secs: float = Field(default=1.5, gt=0)
    elevenlabs_stt_no_verbatim: bool = Field(default=True)
    elevenlabs_stt_include_timestamps: bool = Field(default=True)
    elevenlabs_tts_model: str = Field(default="eleven_flash_v2_5")
    elevenlabs_tts_api_url: str = Field(default="https://api.elevenlabs.io/v1/text-to-speech")
    elevenlabs_tts_output_format: str = Field(default="pcm_16000")
    voice_telephony_provider: str = Field(default="local")
    voice_stream_ws_auth_token: str = Field(default="")
    voice_agent_session_type: str = Field(default="voice_support")
    voice_caller_verification_max_attempts: int = Field(default=2)
    voice_turn_max_latency_ms: int = Field(default=8000)
    aws_region: str = Field(default="")
    aws_s3_call_recordings_bucket: str = Field(default="")
    call_recording_retention_days: int = Field(default=1)

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
            test_admin_token=os.getenv("TEST_ADMIN_TOKEN", ""),
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
            agent_harness=os.getenv("AGENT_HARNESS", "langgraph"),
            agentic_enabled=os.getenv("AGENTIC_ENABLED", "true").lower() == "true",
            agent_max_model_calls_per_run=int(os.getenv("AGENT_MAX_MODEL_CALLS_PER_RUN", "8")),
            agent_max_tool_calls_per_run=int(os.getenv("AGENT_MAX_TOOL_CALLS_PER_RUN", "12")),
            agent_tool_timeout_ms=int(os.getenv("AGENT_TOOL_TIMEOUT_MS", "15000")),
            agent_streaming_enabled=os.getenv("AGENT_STREAMING_ENABLED", "true").lower() == "true",
            agent_summary_trigger_messages=int(os.getenv("AGENT_SUMMARY_TRIGGER_MESSAGES", "6")),
            agent_memory_enabled=os.getenv("AGENT_MEMORY_ENABLED", "true").lower() == "true",
            agent_episodic_memory_enabled=os.getenv("AGENT_EPISODIC_MEMORY_ENABLED", "true").lower() == "true",
            agent_hitl_enabled=os.getenv("AGENT_HITL_ENABLED", "true").lower() == "true",
            agent_deepagents_enable_subagents=os.getenv("AGENT_DEEPAGENTS_ENABLE_SUBAGENTS", "true").lower() == "true",
            agent_deepagents_memory_paths=os.getenv("AGENT_DEEPAGENTS_MEMORY_PATHS", "/memories/preferences.md,/memories/episodes.md"),
            agent_deepagents_filesystem_policy=os.getenv("AGENT_DEEPAGENTS_FILESYSTEM_POLICY", "deny"),
            agent_retry_max_attempts=int(os.getenv("AGENT_RETRY_MAX_ATTEMPTS", "3")),
            agent_retry_base_delay_ms=int(os.getenv("AGENT_RETRY_BASE_DELAY_MS", "250")),
            agent_retry_max_delay_ms=int(os.getenv("AGENT_RETRY_MAX_DELAY_MS", "3000")),
            agent_retry_jitter_enabled=os.getenv("AGENT_RETRY_JITTER_ENABLED", "true").lower() == "true",
            agent_retryable_status_codes=os.getenv("AGENT_RETRYABLE_STATUS_CODES", "408,409,425,429,500,502,503,504"),
            agent_context_max_input_tokens=int(os.getenv("AGENT_CONTEXT_MAX_INPUT_TOKENS", "24000")),
            agent_context_target_input_tokens=int(os.getenv("AGENT_CONTEXT_TARGET_INPUT_TOKENS", "18000")),
            agent_context_recent_message_limit=int(os.getenv("AGENT_CONTEXT_RECENT_MESSAGE_LIMIT", "12")),
            agent_context_relevance_top_k=int(os.getenv("AGENT_CONTEXT_RELEVANCE_TOP_K", "8")),
            agent_context_summary_max_tokens=int(os.getenv("AGENT_CONTEXT_SUMMARY_MAX_TOKENS", "1200")),
            agent_context_tool_result_max_tokens=int(os.getenv("AGENT_CONTEXT_TOOL_RESULT_MAX_TOKENS", "1600")),
            agent_trace_verbose=os.getenv("AGENT_TRACE_VERBOSE", "false").lower() == "true",
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
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", ""),
            elevenlabs_stt_model=os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2_realtime"),
            elevenlabs_stt_realtime_ws_url=os.getenv("ELEVENLABS_STT_REALTIME_WS_URL", "wss://api.elevenlabs.io/v1/speech-to-text/realtime"),
            elevenlabs_stt_commit_strategy=os.getenv("ELEVENLABS_STT_COMMIT_STRATEGY", "vad"),
            elevenlabs_stt_vad_silence_threshold_secs=float(os.getenv("ELEVENLABS_STT_VAD_SILENCE_THRESHOLD_SECS", "1.5")),
            elevenlabs_stt_no_verbatim=os.getenv("ELEVENLABS_STT_NO_VERBATIM", "true").lower() == "true",
            elevenlabs_stt_include_timestamps=os.getenv("ELEVENLABS_STT_INCLUDE_TIMESTAMPS", "true").lower() == "true",
            elevenlabs_tts_model=os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"),
            elevenlabs_tts_api_url=os.getenv("ELEVENLABS_TTS_API_URL", "https://api.elevenlabs.io/v1/text-to-speech"),
            elevenlabs_tts_output_format=os.getenv("ELEVENLABS_TTS_OUTPUT_FORMAT", "pcm_16000"),
            voice_telephony_provider=os.getenv("VOICE_TELEPHONY_PROVIDER", "local"),
            voice_stream_ws_auth_token=os.getenv("VOICE_STREAM_WS_AUTH_TOKEN", ""),
            voice_agent_session_type=os.getenv("VOICE_AGENT_SESSION_TYPE", "voice_support"),
            voice_caller_verification_max_attempts=int(os.getenv("VOICE_CALLER_VERIFICATION_MAX_ATTEMPTS", "2")),
            voice_turn_max_latency_ms=int(os.getenv("VOICE_TURN_MAX_LATENCY_MS", "8000")),
            aws_region=os.getenv("AWS_REGION", ""),
            aws_s3_call_recordings_bucket=os.getenv("AWS_S3_CALL_RECORDINGS_BUCKET", ""),
            call_recording_retention_days=int(os.getenv("CALL_RECORDING_RETENTION_DAYS", "1")),
        )


settings = ChatServiceSettings.from_env()

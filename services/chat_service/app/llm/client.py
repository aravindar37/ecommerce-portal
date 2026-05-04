"""OpenAI-compatible Chat Completions adapter."""

from __future__ import annotations

from typing import Any

from app.config import ChatServiceSettings, settings
from app.http import ServiceHttpError, build_url, request_json
from app.observability import compact, logger

Json = dict[str, Any]


def is_configured_secret(value: str) -> bool:
    """Return whether a configured secret looks usable."""

    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    return not (lowered.startswith("replace-with-") or lowered.startswith("example-") or lowered in {"changeme", "placeholder"})


class LlmClient:
    """OpenAI-compatible LLM client for OpenAI or Grove/Azure gateway routing."""

    def __init__(self, config: ChatServiceSettings) -> None:
        self.config = config

    def metadata(self) -> Json:
        """Return non-sensitive provider metadata."""

        return {
            "provider": self.config.llm_provider,
            "model": self.config.llm_model,
            "streamingEnabled": self.config.llm_streaming_enabled,
            "timeoutMs": self.config.llm_timeout_ms,
        }

    def chat_completion(self, messages: list[Json], stream: bool | None = None) -> Json:
        """Call an OpenAI-compatible chat completions endpoint."""

        if not is_configured_secret(self.config.llm_api_key):
            raise ServiceHttpError(503, "LLM_API_KEY is required for live LLM calls")
        headers = {"authorization": f"Bearer {self.config.llm_api_key}"}
        payload = {
            "model": self.config.llm_model,
            "messages": messages,
            "max_tokens": self.config.llm_max_output_tokens,
            "temperature": self.config.llm_temperature,
            "stream": self.config.llm_streaming_enabled if stream is None else stream,
        }
        logger.debug(
            "llm.request provider=%s model=%s stream=%s messages=%s",
            self.config.llm_provider,
            self.config.llm_model,
            payload["stream"],
            compact(messages),
        )
        response = request_json(
            "POST",
            build_url(self.config.llm_api_base_url, self.config.llm_chat_completions_path),
            payload=payload,
            headers=headers,
            timeout_seconds=self.config.llm_timeout_ms / 1000,
        )
        logger.debug("llm.response provider=%s model=%s response=%s", self.config.llm_provider, self.config.llm_model, compact(response))
        return response


llm_client = LlmClient(settings)

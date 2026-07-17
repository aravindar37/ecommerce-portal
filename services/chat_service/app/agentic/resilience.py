"""Retry and transient-error handling for agentic execution."""

from __future__ import annotations

import random
import time
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from app.http import ServiceHttpError
from app.observability import logger, redact

from .context import retry_policy
from .models import AgentRetryPolicy

T = TypeVar("T")


class RetryExhaustedError(Exception):
    """Raised when a retriable operation exhausts attempts."""

    def __init__(self, operation: str, attempts: int, last_error: Exception) -> None:
        super().__init__(f"{operation} failed after {attempts} attempts: {last_error}")
        self.operation = operation
        self.attempts = attempts
        self.last_error = last_error


@dataclass
class RetryState:
    """Retry metadata for logging and persistence."""

    attempts: int = 0
    retryable: bool = False
    first_error_code: str | None = None
    last_error_code: str | None = None
    total_delay_ms: int = 0


def error_code(exc: Exception) -> str:
    """Return a compact error code."""

    if isinstance(exc, ServiceHttpError):
        return str(exc.status_code)
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        return "url_error"
    return exc.__class__.__name__


def is_retryable_error(exc: Exception, policy: AgentRetryPolicy | None = None) -> bool:
    """Return whether an exception is probably transient."""

    policy = policy or retry_policy()
    if isinstance(exc, ServiceHttpError):
        return exc.status_code in policy.retryable_status_codes
    return isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError))


def retry_delay_ms(attempt_index: int, policy: AgentRetryPolicy) -> int:
    """Return bounded exponential backoff with optional jitter."""

    base = policy.base_delay_ms * (2 ** max(attempt_index - 1, 0))
    bounded = min(base, policy.max_delay_ms)
    if policy.jitter_enabled and bounded > 0:
        bounded = int(random.uniform(bounded * 0.5, bounded))
    return max(0, bounded)


def with_retry(
    operation: str,
    fn: Callable[[], T],
    *,
    policy: AgentRetryPolicy | None = None,
    idempotent: bool = True,
    state: RetryState | None = None,
) -> T:
    """Run a callable with bounded transient retries."""

    policy = policy or retry_policy()
    state = state or RetryState()
    max_attempts = policy.max_attempts if idempotent else 1
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        state.attempts = attempt
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            code = error_code(exc)
            state.first_error_code = state.first_error_code or code
            state.last_error_code = code
            state.retryable = is_retryable_error(exc, policy)
            if not state.retryable or attempt >= max_attempts:
                break
            delay = retry_delay_ms(attempt, policy)
            state.total_delay_ms += delay
            logger.debug(
                "agent.retry_scheduled operation=%s attempt=%s delayMs=%s error=%s",
                operation,
                attempt,
                delay,
                redact(str(exc)),
            )
            if delay:
                time.sleep(delay / 1000)
    assert last_error is not None
    raise RetryExhaustedError(operation, state.attempts, last_error)


def safe_error_message(exc: Exception) -> str:
    """Return a user-safe error explanation."""

    if isinstance(exc, RetryExhaustedError):
        return "The assistant could not complete that step because a dependency is temporarily unavailable."
    if isinstance(exc, ServiceHttpError) and exc.status_code in {401, 403, 404}:
        return "I could not access that information for this account."
    return "The assistant hit a temporary problem. Please try again."


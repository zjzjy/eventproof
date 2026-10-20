"""Small, deterministic guards for external data and model responses."""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import requests


T = TypeVar("T")
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ResilienceError(RuntimeError):
    """Base class for external-data failures that are visible to callers."""


class ExternalRequestError(ResilienceError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class RetryExhausted(ExternalRequestError):
    pass


class InvalidSourceContent(ValueError):
    pass


class InvalidLLMResponse(ValueError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 2.0
    retryable_status: frozenset[int] = frozenset(RETRYABLE_STATUS)

    def delay(self, attempt: int) -> float:
        return min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))


def call_with_retry(
    operation: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry timeouts, connection failures and transient HTTP statuses."""
    policy = policy or RetryPolicy()
    last_error: Exception | None = None
    for attempt in range(1, policy.attempts + 1):
        try:
            response = operation()
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt >= policy.attempts:
                raise RetryExhausted(
                    f"request did not recover after {policy.attempts} attempts"
                ) from exc
            sleep(policy.delay(attempt))
            continue

        status = int(getattr(response, "status_code", 200))
        if status in policy.retryable_status:
            last_error = ExternalRequestError(
                f"transient HTTP status {status}",
                status_code=status,
            )
            if attempt >= policy.attempts:
                raise RetryExhausted(
                    f"transient HTTP {status} persisted after {policy.attempts} attempts",
                    status_code=status,
                ) from last_error
            sleep(policy.delay(attempt))
            continue
        if status >= 400:
            raise ExternalRequestError(
                f"non-retryable HTTP status {status}",
                status_code=status,
            )
        return response

    raise RetryExhausted("request failed without a response") from last_error


def extract_json_object(content: str | bytes | dict[str, Any] | list[Any]) -> dict[str, Any]:
    """Parse a JSON object and reject model wrappers or malformed output."""
    if isinstance(content, dict):
        return content
    if isinstance(content, bytes):
        content = content.decode("utf-8")
    if not isinstance(content, str):
        raise InvalidLLMResponse("LLM response must be a JSON object")

    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise InvalidLLMResponse("LLM response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise InvalidLLMResponse("LLM response must be a JSON object")
    return parsed


def validate_source_text(
    source_id: str,
    content: str,
    *,
    content_type: str = "text/plain",
) -> str:
    """Reject empty, binary PDF, HTML shell and challenge-page content."""
    normalized = content.lstrip("\ufeff").strip()
    lowered = normalized.lower()
    if "pdf" in content_type.lower() or normalized.startswith("%PDF"):
        raise InvalidSourceContent(f"{source_id}: binary PDF requires OCR or snippets")
    if len(normalized) < 20:
        raise InvalidSourceContent(f"{source_id}: source text is empty or too short")
    if "html" in content_type.lower() or lowered.startswith(
        ("<!doctype html", "<html", "<head", "<body")
    ):
        raise InvalidSourceContent(f"{source_id}: raw HTML is not accepted as source text")
    if any(
        marker in lowered
        for marker in ("access denied", "captcha", "verify you are human", "cf-chl-")
    ):
        raise InvalidSourceContent(f"{source_id}: challenge page returned instead of content")
    return normalized


class RateLimiter:
    """In-process rate limiter suitable for a single-instance demo."""

    def __init__(self, *, limit: int, window_seconds: float):
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(current)
            return True

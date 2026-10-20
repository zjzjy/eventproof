import json

import pytest
import requests

from app.resilience import (
    InvalidLLMResponse,
    InvalidSourceContent,
    RateLimiter,
    RetryExhausted,
    RetryPolicy,
    call_with_retry,
    extract_json_object,
    validate_source_text,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


def test_429_is_retried_then_succeeds():
    responses = [FakeResponse(429), FakeResponse(200, {"ok": True})]
    delays: list[float] = []

    result = call_with_retry(
        lambda: responses.pop(0),
        policy=RetryPolicy(attempts=3, base_delay=0.01),
        sleep=delays.append,
    )

    assert result.json() == {"ok": True}
    assert delays == [0.01]


def test_timeout_is_retried_and_reports_exhaustion():
    delays: list[float] = []

    def always_timeout():
        raise requests.Timeout("upstream timeout")

    with pytest.raises(RetryExhausted, match="3 attempts"):
        call_with_retry(
            always_timeout,
            policy=RetryPolicy(attempts=3, base_delay=0.01),
            sleep=delays.append,
        )

    assert delays == [0.01, 0.02]


def test_bad_html_and_pdf_are_rejected():
    with pytest.raises(InvalidSourceContent, match="raw HTML"):
        validate_source_text("doc_html", "<html><body>公告</body></html>")
    with pytest.raises(InvalidSourceContent, match="binary PDF"):
        validate_source_text("doc_pdf", "%PDF-1.7 invalid", content_type="application/pdf")
    with pytest.raises(InvalidSourceContent, match="challenge page"):
        validate_source_text("doc_blocked", "Please verify you are human before continuing")


def test_invalid_llm_json_is_rejected():
    with pytest.raises(InvalidLLMResponse, match="not valid JSON"):
        extract_json_object('{"claims": [}')
    with pytest.raises(InvalidLLMResponse, match="JSON object"):
        extract_json_object(json.dumps(["not", "an", "object"]))


def test_llm_json_fence_is_accepted():
    parsed = extract_json_object('```json\n{"claims": []}\n```')
    assert parsed == {"claims": []}


def test_sliding_window_rate_limiter_blocks_excess_requests():
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("client-a", now=10)
    assert limiter.allow("client-a", now=20)
    assert not limiter.allow("client-a", now=30)
    assert limiter.allow("client-b", now=30)
    assert limiter.allow("client-a", now=71)

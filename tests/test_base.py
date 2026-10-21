import requests
from conftest import KEY, FakeResponse, FakeSession, ok

from indiasearchbench.providers.base import NOT_OFFERED, redact
from indiasearchbench.providers.exa import ExaProvider
from indiasearchbench.providers.serpapi import SerpApiProvider


def test_redact_removes_known_secret_and_query_fragments():
    text = f"GET https://x/search?api_key={KEY}&q=a failed, token=abc123 {KEY}"
    cleaned = redact(text, [KEY])
    assert KEY not in cleaned and "abc123" not in cleaned
    assert "q=a" in cleaned


def test_intent_not_offered_makes_no_call(q_local):
    session = FakeSession(FakeResponse({}))
    result = ExaProvider(KEY, session).search(q_local)
    assert (result.ok, result.error) == (False, NOT_OFFERED)
    assert session.calls == []
    assert result.latency_ms is None


def test_retry_on_5xx_is_counted_once(q_shop):
    session = FakeSession(FakeResponse(status=503, text="busy"), ok("serpapi_shopping"))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert result.ok and result.retries == 1
    assert len(session.calls) == 2


def test_second_5xx_fails_after_exactly_one_retry(q_shop):
    session = FakeSession(FakeResponse(status=500, text="boom"))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert not result.ok and result.http_status == 500
    assert result.retries == 1 and len(session.calls) == 2


def test_timeout_is_retried_then_reported(q_shop):
    session = FakeSession(requests.Timeout("slow"))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert (result.ok, result.error, result.retries) == (False, "timeout", 1)


def test_timeout_then_success(q_shop):
    session = FakeSession(requests.Timeout("slow"), ok("serpapi_shopping"))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert result.ok and result.retries == 1


def test_4xx_is_not_retried_and_error_is_redacted(q_shop):
    session = FakeSession(FakeResponse(status=401, text=f"bad key {KEY}"))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert result.http_status == 401 and result.retries == 0 and len(session.calls) == 1
    assert KEY not in result.error


def test_connection_error_text_never_contains_the_key(q_shop):
    exc = requests.ConnectionError(f"https://serpapi.com/search?api_key={KEY}")
    result = SerpApiProvider(KEY, FakeSession(exc)).search(q_shop)
    assert not result.ok and KEY not in result.error


def test_invalid_json_is_reported(q_shop):
    session = FakeSession(FakeResponse(bad_json=True))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert (result.ok, result.error) == (False, "invalid_json")


def test_raw_payload_is_saved_and_redacted(tmp_path, q_shop):
    payload = {"shopping_results": [], "echo": KEY}
    session = FakeSession(FakeResponse(payload))
    result = SerpApiProvider(KEY, session, raw_dir=tmp_path / "raw").search(q_shop)
    saved = (tmp_path / "raw" / "serpapi__shop-01.json").read_text(encoding="utf-8")
    assert result.raw_ref and KEY not in saved and "REDACTED" in saved

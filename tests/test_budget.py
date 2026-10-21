import pytest
import requests
from conftest import KEY, FakeResponse, FakeSession, fixture, redacted

from indiasearchbench.providers.serpapi import (
    DEFAULT_MAX_SEARCHES,
    BudgetError,
    check_budget,
    fetch_account,
    parse_account,
)


def test_parse_account_fixture():
    info = parse_account(fixture("serpapi_account"))
    assert info.total_searches_left == 240
    assert info.account_rate_limit_per_hour == 50
    assert info.this_hour_searches == 3


def test_parse_account_rejects_missing_field():
    with pytest.raises(BudgetError, match="malformed"):
        parse_account({"plan_searches_left": 1})


def test_fetch_account_request_shape():
    session = FakeSession(FakeResponse(fixture("serpapi_account")))
    info = fetch_account(KEY, session)
    call = redacted(session.calls[0])
    assert call["url"] == "https://serpapi.com/account.json"
    assert call["params"] == {"api_key": "<KEY>"}
    assert info.searches_per_month == 250


def test_fetch_account_failures_are_budget_errors_without_key():
    with pytest.raises(BudgetError, match="HTTP 401"):
        fetch_account(KEY, FakeSession(FakeResponse({}, status=401)))
    with pytest.raises(BudgetError) as err:
        fetch_account(KEY, FakeSession(requests.ConnectionError(f"x api_key={KEY}")))
    assert KEY not in str(err.value)
    with pytest.raises(BudgetError):
        fetch_account(KEY, FakeSession(FakeResponse(bad_json=True)))


def test_budget_guard_default_is_160():
    assert DEFAULT_MAX_SEARCHES == 160


def test_budget_guard_refuses_over_cap_and_over_balance():
    info = parse_account(fixture("serpapi_account"))
    check_budget(160, info.__class__(**{**info.__dict__, "total_searches_left": 500}))
    with pytest.raises(BudgetError, match="budget guard of 160"):
        check_budget(161, info.__class__(**{**info.__dict__, "total_searches_left": 500}))
    with pytest.raises(BudgetError, match="240 left"):
        check_budget(241, info, max_searches=1000)
    check_budget(67, info)

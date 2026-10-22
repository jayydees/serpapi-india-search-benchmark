"""SerpApi adapter plus the free Account API budget guard.

Parameter names come from docs/facts fetched 2026-10-21 (see METHODOLOGY.md).
Cache detection: the docs name no cache flag, so a response whose `processed_at` is older than
`CACHE_AGE_SECONDS` counts as cached (see `_is_cached`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

from indiasearchbench.providers.base import (
    Parsed,
    Provider,
    ProviderError,
    RequestSpec,
    local_item,
    news_item,
    redact,
    shopping_item,
    web_item,
)
from indiasearchbench.queries import Query

SEARCH_URL = "https://serpapi.com/search"
ACCOUNT_URL = "https://serpapi.com/account.json"
DEFAULT_MAX_SEARCHES = 160

# Intent to engine calls. "news" issues two searches: engine=google (web results, which are
# the overlap baseline) and engine=google_news (dated items with source). Every call is one
# billable search unless the response reports a cache hit.
_CALLS: dict[str, tuple[str, ...]] = {
    "news": ("google", "google_news"),
    "local": ("google_maps",),
    "shopping": ("google_shopping",),
}


def _params(engine: str, query: Query) -> dict[str, Any]:
    """Per-engine parameters. google_maps takes `ll` (not `location`) per the docs."""
    common: dict[str, Any] = {"engine": engine, "q": query.text, "hl": "en", "gl": "in"}
    if engine in ("google", "google_shopping"):
        common["google_domain"] = "google.co.in"
    if engine == "google_maps":
        city = query.city_info
        assert city is not None
        common.update({"type": "search", "ll": f"@{city.lat},{city.lon},12z"})
    return common


def _parse_web(payload: dict[str, Any], out: Parsed) -> None:
    for i, r in enumerate(payload.get("organic_results", []), 1):
        out.results.append(
            web_item(
                r.get("title", ""), r.get("link", ""), r.get("snippet", ""), r.get("position", i)
            )
        )


def _parse_news(payload: dict[str, Any], out: Parsed) -> None:
    for r in payload.get("news_results", []):
        source = r.get("source")
        name = source.get("name") if isinstance(source, dict) else source
        out.news_items.append(news_item(r.get("title"), r.get("iso_date") or r.get("date"), name))


def _parse_maps(payload: dict[str, Any], out: Parsed) -> None:
    for i, r in enumerate(payload.get("local_results", []), 1):
        out.results.append(
            web_item(
                r.get("title", ""), r.get("website", ""), r.get("type", ""), r.get("position", i)
            )
        )
        out.local_results.append(
            local_item(
                r.get("title"),
                r.get("address"),
                r.get("phone"),
                r.get("rating"),
                (r.get("gps_coordinates") or {}).get("latitude"),
                (r.get("gps_coordinates") or {}).get("longitude"),
            )
        )


def _parse_shopping(payload: dict[str, Any], out: Parsed) -> None:
    for i, r in enumerate(payload.get("shopping_results", []), 1):
        out.results.append(
            web_item(r.get("title", ""), r.get("product_link", ""), r.get("source", ""), i)
        )
        out.shopping_results.append(
            shopping_item(r.get("title"), r.get("price"), r.get("source"), r.get("rating"))
        )


_PARSERS: dict[str, Callable[[dict[str, Any], Parsed], None]] = {
    "google": _parse_web,
    "google_news": _parse_news,
    "google_maps": _parse_maps,
    "google_shopping": _parse_shopping,
}


CACHE_AGE_SECONDS = 30


def _is_cached(metadata: dict[str, Any], now: datetime | None = None) -> bool:
    """A cached response carries the original `processed_at`, so it is older than a live one.

    The docs name no cache flag. Observed live on 2026-10-21: a repeated query returned the same
    search id and the first search's timestamps in about 60-100 ms. `cache_hit` is kept in case a
    flag is added later. Without a parsable timestamp the response counts as live.
    """
    if metadata.get("cache_hit"):
        return True
    stamp = str(metadata.get("processed_at") or "").removesuffix(" UTC")
    try:
        processed = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return False
    return ((now or datetime.now(UTC)) - processed).total_seconds() > CACHE_AGE_SECONDS


class SerpApiProvider(Provider):
    name = "serpapi"
    env_var = "SERPAPI_API_KEY"
    intents = frozenset({"news", "local", "shopping"})
    structured = frozenset({"news", "local", "shopping"})
    no_cache = False  # set by the CLI: every search is then billed and timed live

    def calls_for(self, intent: str) -> int:
        return len(_CALLS[intent])

    def build_requests(self, query: Query) -> list[RequestSpec]:
        no_cache = "true" if self.no_cache else "false"
        return [
            RequestSpec(
                "GET",
                SEARCH_URL,
                params={**_params(engine, query), "no_cache": no_cache, "api_key": self.api_key},
            )
            for engine in _CALLS[query.intent]
        ]

    def parse(self, query: Query, payloads: list[Any]) -> Parsed:
        out = Parsed()
        for engine, payload in zip(_CALLS[query.intent], payloads, strict=True):
            if payload.get("error"):
                raise ProviderError(self._clean(str(payload["error"])))
            _PARSERS[engine](payload, out)
            cached = _is_cached(payload.get("search_metadata") or {})
            out.cache_hit = out.cache_hit or cached
            out.credits_used += 0 if cached else 1
        return out


@dataclass(frozen=True)
class AccountInfo:
    plan_searches_left: int
    total_searches_left: int
    searches_per_month: int
    this_hour_searches: int
    account_rate_limit_per_hour: int


class BudgetError(RuntimeError):
    """Raised when a live SerpApi run would exceed the budget guard."""


def parse_account(payload: dict[str, Any]) -> AccountInfo:
    try:
        return AccountInfo(
            plan_searches_left=int(payload["plan_searches_left"]),
            total_searches_left=int(payload["total_searches_left"]),
            searches_per_month=int(payload["searches_per_month"]),
            this_hour_searches=int(payload["this_hour_searches"]),
            account_rate_limit_per_hour=int(payload["account_rate_limit_per_hour"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise BudgetError(f"account.json missing or malformed field: {exc}") from None


def fetch_account(api_key: str, session: Any = None, timeout: float = 30) -> AccountInfo:
    """Read the free Account API (not counted against the quota)."""
    session = session or requests.Session()
    try:
        response = session.request("GET", ACCOUNT_URL, params={"api_key": api_key}, timeout=timeout)
        if response.status_code != 200:
            raise BudgetError(f"account.json returned HTTP {response.status_code}")
        return parse_account(response.json())
    except (requests.RequestException, ValueError) as exc:
        raise BudgetError(redact(f"could not read account.json: {exc}", [api_key])) from None


def check_budget(
    planned: int, account: AccountInfo, max_searches: int = DEFAULT_MAX_SEARCHES
) -> None:
    """Refuse a run that exceeds the configured cap or the searches left on the account."""
    if planned > max_searches:
        raise BudgetError(
            f"planned {planned} SerpApi searches exceeds the budget guard of {max_searches}"
        )
    if planned > account.total_searches_left:
        raise BudgetError(
            f"planned {planned} SerpApi searches exceeds the {account.total_searches_left} left"
        )

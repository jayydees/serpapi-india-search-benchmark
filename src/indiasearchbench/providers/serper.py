"""Serper.dev adapter.

UNVERIFIED: Serper's first-party docs could not be read (JavaScript-rendered). Every endpoint
name, body field and response key in SERPER_MAP comes from third-party guides or the
homepage navigation, so it is kept in this single dict. See the verify-live note in
METHODOLOGY.md before trusting any Serper number.
"""

from __future__ import annotations

from typing import Any

from indiasearchbench.providers.base import (
    Parsed,
    Provider,
    RequestSpec,
    local_item,
    news_item,
    shopping_item,
    web_item,
)
from indiasearchbench.queries import Query

BASE_URL = "https://google.serper.dev"

# kind -> (endpoint path, response list key). All UNVERIFIED, see module docstring.
SERPER_MAP: dict[str, tuple[str, str]] = {
    "web": ("search", "organic"),
    "news": ("news", "news"),
    "local": ("places", "places"),
    "shopping": ("shopping", "shopping"),
}

# Intent to the kinds of call made. "news" asks /search (web, overlap baseline) and /news.
_KINDS: dict[str, tuple[str, ...]] = {
    "news": ("web", "news"),
    "local": ("local",),
    "shopping": ("shopping",),
}


def _body(kind: str, query: Query) -> dict[str, Any]:
    body: dict[str, Any] = {"q": query.text, "gl": "in", "hl": "en", "num": 10}
    city = query.city_info
    if kind == "local" and city is not None:
        body["location"] = city.location  # format UNVERIFIED
    return body


class SerperProvider(Provider):
    name = "serper"
    env_var = "SERPER_API_KEY"
    intents = frozenset({"news", "local", "shopping"})
    structured = frozenset({"news", "local", "shopping"})

    def is_overhead_call(self, intent: str, index: int) -> bool:
        """The first call of a news query is the web baseline used for the overlap metric."""
        return intent == "news" and index == 0

    def calls_for(self, intent: str) -> int:
        return len(_KINDS[intent])

    def build_requests(self, query: Query) -> list[RequestSpec]:
        headers = {"X-API-KEY": self.api_key, "Content-Type": "application/json"}
        return [
            RequestSpec(
                "POST",
                f"{BASE_URL}/{SERPER_MAP[kind][0]}",
                headers=headers,
                json=_body(kind, query),
            )
            for kind in _KINDS[query.intent]
        ]

    def parse(self, query: Query, payloads: list[Any]) -> Parsed:
        out = Parsed()
        for kind, payload in zip(_KINDS[query.intent], payloads, strict=True):
            items = payload.get(SERPER_MAP[kind][1], [])
            _PARSERS[kind](items, out)
            credits = payload.get("credits", 1)
            out.credits_used += credits
            if kind == "web":  # web baseline for the overlap metric, not part of the news cost
                out.overhead_credits += credits
        return out


def _parse_web(items: list[dict[str, Any]], out: Parsed) -> None:
    for i, r in enumerate(items, 1):
        out.results.append(
            web_item(
                r.get("title", ""), r.get("link", ""), r.get("snippet", ""), r.get("position", i)
            )
        )


def _parse_news(items: list[dict[str, Any]], out: Parsed) -> None:
    for r in items:
        out.news_items.append(news_item(r.get("title"), r.get("date"), r.get("source")))


def _parse_local(items: list[dict[str, Any]], out: Parsed) -> None:
    for i, r in enumerate(items, 1):
        out.results.append(web_item(r.get("title", ""), r.get("website", ""), "", i))
        out.local_results.append(
            local_item(
                r.get("title"),
                r.get("address"),
                r.get("phoneNumber") or r.get("phone"),
                r.get("rating"),
                r.get("latitude"),
                r.get("longitude"),
            )
        )


def _parse_shopping(items: list[dict[str, Any]], out: Parsed) -> None:
    for i, r in enumerate(items, 1):
        out.results.append(web_item(r.get("title", ""), r.get("link", ""), r.get("source", ""), i))
        out.shopping_results.append(
            shopping_item(r.get("title"), r.get("price"), r.get("source"), r.get("rating"))
        )


_PARSERS = {
    "web": _parse_web,
    "news": _parse_news,
    "local": _parse_local,
    "shopping": _parse_shopping,
}

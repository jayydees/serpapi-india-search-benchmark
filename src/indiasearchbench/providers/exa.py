"""Exa adapter. Exa is its own neural index, not a Google SERP, and offers no local or shopping."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from indiasearchbench.providers.base import (
    Parsed,
    Provider,
    RequestSpec,
    news_item,
    web_item,
)
from indiasearchbench.queries import Query

SEARCH_URL = "https://api.exa.ai/search"


class ExaProvider(Provider):
    name = "exa"
    env_var = "EXA_API_KEY"
    intents = frozenset({"news"})
    structured = frozenset({"news"})

    def build_requests(self, query: Query) -> list[RequestSpec]:
        body = {
            "query": query.text,
            "type": "auto",
            "numResults": 10,
            "userLocation": "IN",
            "category": "news",
            "contents": {"highlights": True},
        }
        headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}
        return [RequestSpec("POST", SEARCH_URL, headers=headers, json=body)]

    def parse(self, query: Query, payloads: list[Any]) -> Parsed:
        payload = payloads[0]
        out = Parsed(credits_used=1)
        for i, r in enumerate(payload.get("results", []), 1):
            url = r.get("url", "")
            highlights = r.get("highlights") or []
            snippet = highlights[0] if highlights else (r.get("text") or "")[:300]
            out.results.append(web_item(r.get("title", ""), url, snippet, i))
            out.news_items.append(
                news_item(r.get("title"), r.get("publishedDate"), urlparse(url).netloc or None)
            )
        out.cost_usd = (payload.get("costDollars") or {}).get("total")
        return out

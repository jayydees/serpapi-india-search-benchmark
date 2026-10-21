"""SearchApi.io adapter (optional: skipped unless SEARCHAPI_API_KEY is set).

UNVERIFIED: the India `location` string format is an inference from the docs example
("New York,United States"). It is not used for news or shopping, only noted here.
The free trial is 100 requests, so a full 50-query run needs a paid plan or a smaller --limit.
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

SEARCH_URL = "https://www.searchapi.io/api/v1/search"

# Intent to engine. News reads organic_results, whose documented fields include date and source.
_ENGINES = {"news": "google", "local": "google_maps", "shopping": "google_shopping"}


class SearchApiProvider(Provider):
    name = "searchapi"
    env_var = "SEARCHAPI_API_KEY"
    intents = frozenset({"news", "local", "shopping"})
    structured = frozenset({"news", "local", "shopping"})

    def build_requests(self, query: Query) -> list[RequestSpec]:
        params: dict[str, Any] = {
            "engine": _ENGINES[query.intent],
            "q": query.text,
            "gl": "in",
            "hl": "en",
        }
        city = query.city_info
        if query.intent == "local" and city is not None:
            params["ll"] = f"@{city.lat},{city.lon},12z"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        return [RequestSpec("GET", SEARCH_URL, params=params, headers=headers)]

    def parse(self, query: Query, payloads: list[Any]) -> Parsed:
        payload = payloads[0]
        out = Parsed(credits_used=1)
        if query.intent == "news":
            for i, r in enumerate(payload.get("organic_results", []), 1):
                out.results.append(
                    web_item(
                        r.get("title", ""),
                        r.get("link", ""),
                        r.get("snippet", ""),
                        r.get("position", i),
                    )
                )
                out.news_items.append(news_item(r.get("title"), r.get("date"), r.get("source")))
        elif query.intent == "local":
            for i, r in enumerate(payload.get("local_results", []), 1):
                out.results.append(
                    web_item(
                        r.get("title", ""),
                        r.get("website", ""),
                        r.get("type", ""),
                        r.get("position", i),
                    )
                )
                out.local_results.append(
                    local_item(r.get("title"), r.get("address"), r.get("phone"), r.get("rating"))
                )
        else:
            for i, r in enumerate(payload.get("shopping_results", []), 1):
                out.results.append(
                    web_item(
                        r.get("title", ""),
                        r.get("product_link", ""),
                        r.get("seller", ""),
                        r.get("position", i),
                    )
                )
                out.shopping_results.append(
                    shopping_item(r.get("title"), r.get("price"), r.get("seller"), r.get("rating"))
                )
        return out

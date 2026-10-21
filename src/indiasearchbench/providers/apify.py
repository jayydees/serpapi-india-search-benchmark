"""Apify adapter: google-search-scraper for web, crawler-google-places for local.

UNVERIFIED: the auth mechanism (Authorization: Bearer here, instead of a token query
parameter, so the secret never lands in a URL) was not shown in the docs portion read.
Latency includes actor start-up, so it is not comparable with a direct API.
"""

from __future__ import annotations

from typing import Any

from indiasearchbench.providers.base import (
    Parsed,
    Provider,
    RequestSpec,
    local_item,
    web_item,
)
from indiasearchbench.queries import Query

BASE_URL = "https://api.apify.com/v2/acts"
SYNC_PATH = "run-sync-get-dataset-items"
PLACES_PER_SEARCH = 10

# Intent to actor. Shopping is not offered by either actor.
ACTORS = {
    "news": "apify~google-search-scraper",
    "local": "compass~crawler-google-places",
}


class ApifyProvider(Provider):
    name = "apify"
    env_var = "APIFY_TOKEN"
    intents = frozenset({"news", "local"})
    structured = frozenset({"local"})
    timeout = 310  # the sync endpoint answers HTTP 408 after 300 seconds

    def est_credits(self, intent: str) -> int:
        return PLACES_PER_SEARCH if intent == "local" else 1

    def pricing_key(self, intent: str) -> str:
        return "apify_places" if intent == "local" else "apify"

    def build_requests(self, query: Query) -> list[RequestSpec]:
        if query.intent == "local":
            city = query.city_info
            assert city is not None
            body: dict[str, Any] = {
                "searchStringsArray": [query.text],
                "locationQuery": city.location,
                "countryCode": "in",
                "language": "en",
                "maxCrawledPlacesPerSearch": PLACES_PER_SEARCH,
            }
        else:
            body = {
                "queries": query.text,
                "countryCode": "in",
                "languageCode": "en",
                "maxPagesPerQuery": 1,
            }
        url = f"{BASE_URL}/{ACTORS[query.intent]}/{SYNC_PATH}"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        return [RequestSpec("POST", url, headers=headers, json=body)]

    def parse(self, query: Query, payloads: list[Any]) -> Parsed:
        records: list[dict[str, Any]] = payloads[0]
        out = Parsed(credits_used=len(records))
        if query.intent == "local":
            for i, r in enumerate(records, 1):
                out.results.append(web_item(r.get("title", ""), r.get("website") or "", "", i))
                out.local_results.append(
                    local_item(
                        r.get("title"), r.get("address"), r.get("phone"), r.get("totalScore")
                    )
                )
            return out
        for record in records:
            for r in record.get("organicResults", []):
                out.results.append(
                    web_item(
                        r.get("title", ""),
                        r.get("url", ""),
                        r.get("description", ""),
                        r.get("position", len(out.results) + 1),
                    )
                )
        return out

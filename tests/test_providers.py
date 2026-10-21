from conftest import KEY, FakeResponse, FakeSession, ok, redacted

from indiasearchbench.providers import PROVIDERS
from indiasearchbench.providers.apify import ApifyProvider
from indiasearchbench.providers.exa import ExaProvider
from indiasearchbench.providers.searchapi import SearchApiProvider
from indiasearchbench.providers.serpapi import SerpApiProvider
from indiasearchbench.providers.serper import SerperProvider


def test_registry_has_all_five_adapters():
    assert set(PROVIDERS) == {"serpapi", "serper", "exa", "apify", "searchapi"}
    assert {p.env_var for p in PROVIDERS.values()} == {
        "SERPAPI_API_KEY",
        "SERPER_API_KEY",
        "EXA_API_KEY",
        "APIFY_TOKEN",
        "SEARCHAPI_API_KEY",
    }


# ---- SerpApi ----------------------------------------------------------------


def test_serpapi_news_requests_and_normalisation(q_news):
    session = FakeSession(ok("serpapi_web"), ok("serpapi_news"))
    result = SerpApiProvider(KEY, session).search(q_news)
    web, news = (redacted(c) for c in session.calls)
    assert web["method"] == "GET" and web["url"] == "https://serpapi.com/search"
    assert web["params"] == {
        "engine": "google",
        "q": "RBI repo rate decision latest",
        "hl": "en",
        "gl": "in",
        "google_domain": "google.co.in",
        "no_cache": "false",
        "api_key": "<KEY>",
    }
    assert news["params"] == {
        "engine": "google_news",
        "q": "RBI repo rate decision latest",
        "hl": "en",
        "gl": "in",
        "no_cache": "false",
        "api_key": "<KEY>",
    }
    assert result.ok and result.credits_used == 2 and not result.cache_hit
    assert result.results[0]["url"] == "https://www.example.in/a"
    assert result.news_items[0] == {
        "title": "Synthetic headline one",
        "date": "2026-10-21T08:00:00Z",
        "source": "Example Times",
    }
    assert result.news_items[1]["date"] == "1 day ago"
    assert result.pricing_key == "serpapi" and result.structured_offered


def test_serpapi_local_uses_ll_not_location(q_local):
    session = FakeSession(ok("serpapi_maps"))
    result = SerpApiProvider(KEY, session).search(q_local)
    params = redacted(session.calls[0])["params"]
    assert params == {
        "engine": "google_maps",
        "q": "vegan cafe in Indiranagar",
        "hl": "en",
        "gl": "in",
        "type": "search",
        "ll": "@12.9716,77.5946,12z",
        "no_cache": "false",
        "api_key": "<KEY>",
    }
    assert "location" not in params
    assert result.local_results[0]["address"].startswith("12 Sample Road")
    assert result.local_results[2]["rating"] is None


def test_serpapi_shopping_normalisation(q_shop):
    session = FakeSession(ok("serpapi_shopping"))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert redacted(session.calls[0])["params"]["engine"] == "google_shopping"
    assert result.shopping_results[0] == {
        "title": "Sample Whey Protein 1kg",
        "price": "Rs. 2,499",
        "merchant": "Example Store",
        "rating": 4.4,
    }
    assert result.results[0]["url"] == "https://shop.example.in/p/1"


def test_serpapi_cache_hit_is_recorded_and_not_billed(q_shop):
    response = ok("serpapi_shopping")
    response._payload["search_metadata"]["cache_hit"] = True
    result = SerpApiProvider(KEY, FakeSession(response)).search(q_shop)
    assert result.cache_hit and result.credits_used == 0


def test_serpapi_error_payload_is_a_failure(q_shop):
    session = FakeSession(FakeResponse({"error": f"Invalid API key {KEY}"}))
    result = SerpApiProvider(KEY, session).search(q_shop)
    assert not result.ok and KEY not in result.error


# ---- Serper -----------------------------------------------------------------


def test_serper_news_makes_two_calls_with_headers(q_news):
    session = FakeSession(ok("serper_search"), ok("serper_news"))
    result = SerperProvider(KEY, session).search(q_news)
    first, second = (redacted(c) for c in session.calls)
    assert first["url"] == "https://google.serper.dev/search" and first["method"] == "POST"
    assert second["url"] == "https://google.serper.dev/news"
    assert first["headers"] == {"X-API-KEY": "<KEY>", "Content-Type": "application/json"}
    assert first["json"] == {
        "q": "RBI repo rate decision latest",
        "gl": "in",
        "hl": "en",
        "num": 10,
    }
    assert result.credits_used == 2
    assert result.news_items[1] == {
        "title": "Synthetic headline two",
        "date": None,
        "source": "Example Daily",
    }


def test_serper_local_sends_location_and_parses_places(q_local):
    session = FakeSession(ok("serper_places"))
    result = SerperProvider(KEY, session).search(q_local)
    call = redacted(session.calls[0])
    assert call["url"] == "https://google.serper.dev/places"
    assert call["json"]["location"] == "Bengaluru, Karnataka, India"
    assert result.local_results[0] == {
        "name": "Sample Pharmacy",
        "address": "1 Sample Road, Koramangala, Bengaluru",
        "phone": "+91 80 0000 0002",
        "rating": 4.2,
    }


def test_serper_shopping(q_shop):
    session = FakeSession(ok("serper_shopping"))
    result = SerperProvider(KEY, session).search(q_shop)
    assert redacted(session.calls[0])["url"] == "https://google.serper.dev/shopping"
    assert result.shopping_results[1] == {
        "title": "Demo Earbuds",
        "price": "Rs. 999",
        "merchant": "Demo Mart",
        "rating": None,
    }


# ---- Exa --------------------------------------------------------------------


def test_exa_request_and_normalisation(q_news):
    session = FakeSession(ok("exa_search"))
    result = ExaProvider(KEY, session).search(q_news)
    call = redacted(session.calls[0])
    assert call["url"] == "https://api.exa.ai/search" and call["method"] == "POST"
    assert call["headers"] == {"x-api-key": "<KEY>", "Content-Type": "application/json"}
    assert call["json"] == {
        "query": "RBI repo rate decision latest",
        "type": "auto",
        "numResults": 10,
        "userLocation": "IN",
        "category": "news",
        "contents": {"highlights": True},
    }
    assert result.results[0]["snippet"] == "A synthetic highlight."
    assert result.results[1]["snippet"].startswith("Synthetic body text")
    assert result.news_items[0] == {
        "title": "Synthetic headline one",
        "date": "2026-10-20T10:00:00.000Z",
        "source": "news.example.in",
    }
    assert result.cost_usd == 0.008 and result.credits_used == 1


def test_exa_does_not_offer_local_or_shopping(q_local, q_shop):
    for query in (q_local, q_shop):
        result = ExaProvider(KEY, FakeSession(ok("exa_search"))).search(query)
        assert result.error == "intent_not_offered"


# ---- Apify ------------------------------------------------------------------


def test_apify_web_request_uses_bearer_header_not_url(q_news):
    session = FakeSession(ok("apify_web"))
    result = ApifyProvider(KEY, session).search(q_news)
    call = redacted(session.calls[0])
    assert call["url"] == (
        "https://api.apify.com/v2/acts/apify~google-search-scraper/run-sync-get-dataset-items"
    )
    assert call["headers"]["Authorization"] == "Bearer <KEY>"
    assert call["json"] == {
        "queries": "RBI repo rate decision latest",
        "countryCode": "in",
        "languageCode": "en",
        "maxPagesPerQuery": 1,
    }
    assert result.results[1]["url"] == "https://six.example.net/6"
    assert result.credits_used == 1 and result.pricing_key == "apify"
    assert not result.structured_offered


def test_apify_local_uses_places_actor_and_bills_per_place(q_local):
    session = FakeSession(ok("apify_places"))
    result = ApifyProvider(KEY, session).search(q_local)
    call = redacted(session.calls[0])
    assert "compass~crawler-google-places" in call["url"]
    assert call["json"] == {
        "searchStringsArray": ["vegan cafe in Indiranagar"],
        "locationQuery": "Bengaluru, Karnataka, India",
        "countryCode": "in",
        "language": "en",
        "maxCrawledPlacesPerSearch": 10,
    }
    assert result.credits_used == 2 and result.pricing_key == "apify_places"
    assert result.local_results[1]["phone"] is None
    assert ApifyProvider(KEY).est_credits("local") == 10
    assert ApifyProvider(KEY).est_credits("news") == 1


def test_apify_shopping_is_not_offered(q_shop):
    result = ApifyProvider(KEY, FakeSession(ok("apify_web"))).search(q_shop)
    assert result.error == "intent_not_offered"


# ---- SearchApi --------------------------------------------------------------


def test_searchapi_news_request_and_date_source(q_news):
    session = FakeSession(ok("searchapi_web"))
    result = SearchApiProvider(KEY, session).search(q_news)
    call = redacted(session.calls[0])
    assert call["url"] == "https://www.searchapi.io/api/v1/search" and call["method"] == "GET"
    assert call["headers"] == {"Authorization": "Bearer <KEY>"}
    assert call["params"] == {
        "engine": "google",
        "q": "RBI repo rate decision latest",
        "gl": "in",
        "hl": "en",
    }
    assert result.news_items[0] == {
        "title": "Sample result one",
        "date": "Oct 20, 2026",
        "source": "Example Times",
    }


def test_searchapi_local_and_shopping(q_local, q_shop):
    local_session = FakeSession(ok("searchapi_maps"))
    local = SearchApiProvider(KEY, local_session).search(q_local)
    assert local.local_results[0]["rating"] == 4.5
    assert redacted(local_session.calls[0])["params"]["ll"] == "@12.9716,77.5946,12z"
    session = FakeSession(ok("searchapi_shopping"))
    shop = SearchApiProvider(KEY, session).search(q_shop)
    assert redacted(session.calls[0])["params"]["engine"] == "google_shopping"
    assert shop.shopping_results[0]["merchant"] == "Example Store"

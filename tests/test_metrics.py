import pytest

from indiasearchbench import metrics
from indiasearchbench.metrics import PriceRow, load_pricing, summarize


def rec(provider="serper", intent="news", qid="q1", ok=True, **kw):
    base = {
        "provider": provider,
        "intent": intent,
        "query_id": qid,
        "ok": ok,
        "error": None if ok else "http_500",
        "latency_ms": 100.0,
        "results": [],
        "local_results": [],
        "shopping_results": [],
        "news_items": [],
        "structured_offered": True,
        "credits_used": 1,
        "cost_usd": None,
        "cache_hit": False,
        "pricing_key": provider,
        "city": None,
    }
    base.update(kw)
    return base


def test_percentile_nearest_rank():
    values = [15, 20, 35, 40, 50]
    assert metrics.percentile(values, 50) == 35
    assert metrics.percentile(values, 95) == 50
    assert metrics.percentile(values, 20) == 15
    assert metrics.percentile([7], 95) == 7
    assert metrics.percentile([], 50) is None
    assert metrics.percentile(list(range(1, 101)), 95) == 95


def test_success_rate_ignores_not_offered():
    rows = [rec(), rec(ok=False), rec(ok=False, error="intent_not_offered")]
    assert metrics.success_rate(rows) == pytest.approx(0.5)
    assert metrics.success_rate([rec(ok=False, error="intent_not_offered")]) is None
    assert metrics.success_rate([]) is None


def test_latencies_skip_failures_and_cache_hits():
    rows = [
        rec(latency_ms=100.0),
        rec(latency_ms=900.0, cache_hit=True),
        rec(ok=False, latency_ms=None),
    ]
    assert metrics.latencies(rows) == [100.0]


def test_completeness_per_intent():
    local = rec(
        intent="local",
        local_results=[
            {"name": "a", "address": "x", "rating": 4.0},
            {"name": "b", "address": "x", "rating": None},
        ],
    )
    assert metrics.completeness(local) == 0.5
    shop = rec(
        intent="shopping",
        shopping_results=[{"title": "t", "price": "Rs 5", "merchant": "m"}],
    )
    assert metrics.completeness(shop) == 1.0
    news = rec(news_items=[{"date": "d", "source": ""}, {"date": "d", "source": "s"}])
    assert metrics.completeness(news) == 0.5


def test_completeness_not_applicable_vs_zero():
    assert metrics.completeness(rec(ok=False)) is None
    assert metrics.completeness(rec(structured_offered=False)) is None
    assert metrics.completeness(rec(intent="local")) == 0.0


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.example.in/a", "example.in"),
        ("https://news.example.co.in/b", "example.co.in"),
        ("https://sub.deep.example.com/x", "example.com"),
        ("https://example.org", "example.org"),
        ("not a url", ""),
        ("", ""),
    ],
)
def test_registrable_domain(url, expected):
    assert metrics.registrable_domain(url) == expected


def test_jaccard_overlap_on_domains():
    a = [{"url": "https://a.example.in/1"}, {"url": "https://b.example.com/2"}]
    b = [{"url": "https://www.example.in/3"}, {"url": "https://c.example.org/4"}]
    assert metrics.jaccard_overlap(a, b) == pytest.approx(1 / 3)
    assert metrics.jaccard_overlap(a, a) == 1.0
    assert metrics.jaccard_overlap([], []) is None


def test_jaccard_uses_only_top_ten():
    a = [{"url": f"https://site{i}.com"} for i in range(12)]
    b = [{"url": f"https://site{i}.com"} for i in range(10)]
    assert metrics.jaccard_overlap(a, b) == 1.0


def test_india_relevance_local_matches_city_aliases():
    record = rec(
        intent="local",
        city="Bangalore",
        local_results=[{"address": "1 Road, Bengaluru"}, {"address": "2 Lane, Pune"}],
    )
    assert metrics.india_relevance(record) == 0.5
    assert metrics.india_relevance(rec(intent="local", city="Bangalore")) is None


def test_india_relevance_web_counts_in_domains():
    record = rec(results=[{"url": "https://a.example.in/x"}, {"url": "https://b.com"}])
    assert metrics.india_relevance(record) == 0.5
    assert metrics.india_relevance(rec()) is None
    assert metrics.india_relevance(rec(ok=False)) is None


def test_cost_prefers_reported_then_table():
    pricing = {"serper": PriceRow(1.0, "credit", "UNVERIFIED", "u", "2026-10-21")}
    assert metrics.cost_per_1000([rec(credits_used=2), rec(credits_used=2)], pricing) == 2.0
    assert metrics.cost_per_1000([rec(cost_usd=0.008)], pricing) == pytest.approx(8.0)
    assert metrics.cost_per_1000([rec(provider="exa", pricing_key="exa")], pricing) is None
    assert metrics.cost_per_1000([rec(ok=False)], pricing) is None


def test_judge_mean_skips_errors():
    rows = [rec(judge={"score": 3, "reason": "r"}), rec(judge={"error": "x"}), rec()]
    assert metrics.judge_mean(rows) == 3
    assert metrics.judge_mean([rec()]) is None


def test_summarize_overlap_and_not_offered_handling():
    serp = rec(provider="serpapi", results=[{"url": "https://a.example.in"}])
    other = rec(provider="serper", results=[{"url": "https://a.example.in"}])
    exa_local = rec(provider="exa", intent="local", ok=False)
    exa_local["error"] = "intent_not_offered"
    summary = summarize([serp, other, exa_local], {})
    assert summary["news"]["serper"]["overlap_with_serpapi"] == 1.0
    assert summary["news"]["serpapi"]["overlap_with_serpapi"] is None
    assert "local" not in summary


def test_load_pricing_reads_shipped_table():
    pricing = load_pricing()
    assert pricing["serpapi"].usd_per_1000 == 25.0
    assert pricing["serpapi"].status == "VERIFIED"
    assert pricing["serper"].status == "UNVERIFIED"
    assert {"exa", "apify", "apify_places", "searchapi"} <= set(pricing)


def test_load_pricing_missing_file(tmp_path):
    assert load_pricing(tmp_path / "none.md") == {}

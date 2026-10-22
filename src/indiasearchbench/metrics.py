"""Pure metric functions plus the per-provider, per-intent summary.

Records are plain dicts shaped like NormalizedResult.to_dict() plus an optional
"city" and "judge" key. A metric that cannot be computed is None (shown as n/a), never 0.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlparse

from indiasearchbench.providers.base import NOT_OFFERED
from indiasearchbench.queries import CITIES

TOP_K = 10
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu", "nic", "res"}
DEFAULT_PRICING_PATH = Path(__file__).resolve().parents[2] / "docs" / "PRICING.md"


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def applicable(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Records where the provider offers the intent. intent_not_offered is N/A, never a failure."""
    return [r for r in records if r.get("error") != NOT_OFFERED]


def success_rate(records: Sequence[dict[str, Any]]) -> float | None:
    rows = applicable(records)
    return sum(1 for r in rows if r["ok"]) / len(rows) if rows else None


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile: the ceil(p/100 * n)-th smallest value. None when empty."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def latencies(records: Iterable[dict[str, Any]]) -> list[float]:
    """Latency of successful, non-cached responses only."""
    return [
        r["latency_ms"]
        for r in records
        if r["ok"] and not r.get("cache_hit") and r.get("latency_ms") is not None
    ]


_COMPLETENESS_FIELDS = {
    "local": ("local_results", ("name", "address", "rating")),
    "shopping": ("shopping_results", ("title", "price", "merchant")),
    "news": ("news_items", ("date", "source")),
}


def completeness(record: dict[str, Any]) -> float | None:
    """Share of structured items that have every required field.

    None when the query failed or the provider has no structured block for the intent.
    A provider that offers the block but returned no items scores 0.0.
    """
    if not record["ok"] or not record.get("structured_offered"):
        return None
    key, fields = _COMPLETENESS_FIELDS[record["intent"]]
    items = record.get(key, [])[:TOP_K]
    if not items:
        return 0.0
    return sum(all(_present(i.get(f)) for f in fields) for i in items) / len(items)


def registrable_domain(url: str) -> str:
    """Heuristic registrable domain without a public-suffix list (handles co.in style suffixes)."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _domains(results: Sequence[dict[str, Any]]) -> set[str]:
    return {d for r in results[:TOP_K] if (d := registrable_domain(r.get("url", "")))}


def jaccard_overlap(
    results: Sequence[dict[str, Any]], baseline: Sequence[dict[str, Any]]
) -> float | None:
    """Jaccard index of top-10 registrable domains. An agreement measure, not accuracy."""
    a, b = _domains(results), _domains(baseline)
    return len(a & b) / len(a | b) if a | b else None


_INR_MARKERS = ("₹", "inr", "rs.", "rs ")


def _is_indian_host(url: str) -> bool:
    """A .in host that is not a Google domain (google.co.in is a request artifact, not signal)."""
    host = urlparse(url).hostname or ""
    return host.endswith(".in") and not host.startswith(("google.", "www.google."))


LOCAL_RADIUS_KM = 30.0


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 12742 * math.asin(math.sqrt(a))


def _in_city(item: dict[str, Any], city: Any) -> bool:
    """Within LOCAL_RADIUS_KM of the city centre by coordinates, else by address alias.

    Coordinates come first because some providers leave the city out of the address.
    """
    lat, lon = item.get("lat"), item.get("lon")
    if lat is not None and lon is not None:
        return _distance_km(float(lat), float(lon), city.lat, city.lon) <= LOCAL_RADIUS_KM
    return any(a in str(item.get("address") or "").lower() for a in city.aliases)


def india_relevance(record: dict[str, Any]) -> float | None:
    """Local: top-10 places inside the query city. Shopping: items priced in rupees.
    News: share of non-Google .in domains."""
    if not record["ok"]:
        return None
    if record["intent"] == "local":
        city = CITIES.get(record.get("city") or "")
        items = record.get("local_results", [])[:TOP_K]
        if city is None or not items:
            return None
        return sum(_in_city(i, city) for i in items) / len(items)
    if record["intent"] == "shopping":
        items = record.get("shopping_results", [])[:TOP_K]
        if not items:
            return None
        return sum(
            any(m in str(i.get("price") or "").lower() for m in _INR_MARKERS) for i in items
        ) / len(items)
    results = record.get("results", [])[:TOP_K]
    if not results:
        return None
    return sum(_is_indian_host(r.get("url", "")) for r in results) / len(results)


@dataclass(frozen=True)
class PriceRow:
    usd_per_1000: float
    unit: str
    status: str
    source: str
    fetched: str


def load_pricing(path: Path = DEFAULT_PRICING_PATH) -> dict[str, PriceRow]:
    """Parse rows of docs/PRICING.md whose first cell is a backticked provider key."""
    rows: dict[str, PriceRow] = {}
    if not Path(path).exists():
        return rows
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7 or not (cells[0].startswith("`") and cells[0].endswith("`")):
            continue
        rows[cells[0].strip("`")] = PriceRow(
            usd_per_1000=float(cells[2].lstrip("$")),
            unit=cells[3],
            status=cells[4],
            source=cells[5],
            fetched=cells[6],
        )
    return rows


_TWO_CALL_NEWS = ("serpapi", "serper")


def _billable(record: dict[str, Any]) -> float:
    """Credits for the calls that answer the query, without the benchmark's baseline web call.

    Records saved before `overhead_credits` existed used one web call plus one news call for
    SerpApi and Serper, so half of the credits are overhead for those.
    """
    credits = record["credits_used"]
    if "overhead_credits" in record:
        return credits - record["overhead_credits"]
    if record["intent"] == "news" and record.get("provider") in _TWO_CALL_NEWS:
        return credits / 2
    return credits


def cost_per_1000(records: Sequence[dict[str, Any]], pricing: dict[str, PriceRow]) -> float | None:
    """USD per 1,000 queries: the provider-reported cost, else table price x mean credits."""
    rows = [r for r in applicable(records) if r["ok"]]
    if not rows:
        return None
    reported = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    if reported:
        return mean(reported) * 1000
    price = pricing.get(rows[0].get("pricing_key", ""))
    if price is None:
        return None
    return mean(_billable(r) for r in rows) * price.usd_per_1000


def judge_mean(records: Iterable[dict[str, Any]]) -> float | None:
    scores = [r["judge"]["score"] for r in records if r.get("judge") and "score" in r["judge"]]
    return mean(scores) if scores else None


def _mean(values: Iterable[float | None]) -> float | None:
    kept = [v for v in values if v is not None]
    return mean(kept) if kept else None


def summarize(
    records: Sequence[dict[str, Any]], pricing: dict[str, PriceRow]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Metrics keyed by intent, then provider. Providers with no applicable record are omitted."""
    baseline = {
        r["query_id"]: r["results"]
        for r in records
        if r["provider"] == "serpapi" and r["intent"] == "news" and r["ok"]
    }
    summary: dict[str, dict[str, dict[str, Any]]] = {}
    for intent in sorted({r["intent"] for r in records}):
        for provider in sorted({r["provider"] for r in records if r["intent"] == intent}):
            rows = [r for r in records if r["intent"] == intent and r["provider"] == provider]
            if not applicable(rows):
                continue
            lat = latencies(rows)
            overlaps = [
                jaccard_overlap(r["results"], baseline[r["query_id"]])
                for r in rows
                if r["ok"]
                and provider != "serpapi"
                and r["query_id"] in baseline
                and intent == "news"
            ]
            summary.setdefault(intent, {})[provider] = {
                "n": len(applicable(rows)),
                "success_rate": success_rate(rows),
                "latency_p50_ms": percentile(lat, 50),
                "latency_p95_ms": percentile(lat, 95),
                "completeness": _mean(completeness(r) for r in rows),
                "overlap_with_serpapi": _mean(overlaps),
                "india_relevance": _mean(india_relevance(r) for r in rows),
                "judge_mean": judge_mean(rows),
                "cost_per_1000_usd": cost_per_1000(rows, pricing),
            }
    return summary

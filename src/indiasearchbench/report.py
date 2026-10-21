"""Render results.md from results.json. Every number comes from the data, none is invented."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from indiasearchbench.metrics import DEFAULT_PRICING_PATH, PriceRow, load_pricing, summarize
from indiasearchbench.runner import RESULTS_FILE, load_state

REPORT_FILE = "results.md"

# (key, column label, value kind, higher is better, include in wins and losses)
COLUMNS: list[tuple[str, str, str, bool, bool]] = [
    ("success_rate", "Success", "pct", True, True),
    ("latency_p50_ms", "p50 latency", "ms", False, True),
    ("latency_p95_ms", "p95 latency", "ms", False, True),
    ("completeness", "Structured completeness", "pct", True, True),
    ("overlap_with_serpapi", "Domain overlap with SerpApi", "pct", True, False),
    ("india_relevance", "India relevance", "pct", True, True),
    ("judge_mean", "Judge (0-3)", "num", True, True),
    ("cost_per_1000_usd", "USD per 1,000 queries", "usd", False, True),
]


def fmt(value: float | None, kind: str) -> str:
    if value is None:
        return "n/a"
    return {
        "pct": f"{value * 100:.0f}%",
        "ms": f"{value:,.0f} ms",
        "usd": f"${value:,.2f}",
        "num": f"{value:.2f}",
    }[kind]


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _intent_table(providers: dict[str, dict[str, Any]]) -> str:
    headers = ["Provider", "Queries"] + [c[1] for c in COLUMNS]
    rows = [
        [name, str(m["n"])] + [fmt(m[key], kind) for key, _, kind, _, _ in COLUMNS]
        for name, m in providers.items()
    ]
    return _table(headers, rows)


def _cost_table(summary: dict[str, dict[str, dict[str, Any]]], pricing: dict[str, PriceRow]) -> str:
    rows = [
        [intent, name, fmt(m["cost_per_1000_usd"], "usd")]
        for intent, providers in summary.items()
        for name, m in providers.items()
    ]
    stale = sorted({p.fetched for p in pricing.values()})
    note = (
        f"\nPrices come from docs/PRICING.md (fetched {', '.join(stale) or 'unknown'}). "
        "Re-verify before publishing."
    )
    return _table(["Intent", "Provider", "USD per 1,000 queries"], rows) + note


def standings(summary: dict[str, dict[str, dict[str, Any]]]) -> dict[str, list[str]]:
    """Per provider, the metrics where it is best or worst among providers with a value."""
    lines: dict[str, list[str]] = {}
    for intent, providers in summary.items():
        for key, label, kind, higher, include in COLUMNS:
            if not include:
                continue
            values = {n: m[key] for n, m in providers.items() if m[key] is not None}
            if len(values) < 2:
                continue
            best = max(values.values()) if higher else min(values.values())
            worst = min(values.values()) if higher else max(values.values())
            if best == worst:
                continue
            for name, value in values.items():
                if value == best:
                    lines.setdefault(name, []).append(
                        f"best on {intent} {label.lower()} ({fmt(value, kind)})"
                    )
                elif value == worst:
                    lines.setdefault(name, []).append(
                        f"worst on {intent} {label.lower()} ({fmt(value, kind)})"
                    )
    return lines


def _wins_losses(summary: dict[str, dict[str, dict[str, Any]]]) -> str:
    found = standings(summary)
    names = sorted({n for providers in summary.values() for n in providers})
    out = [
        "Generated from the tables above. A provider is listed as best or worst only when at "
        "least two providers have a value for that intent and metric and the values differ. "
        "Domain overlap is excluded because it measures agreement, not quality."
    ]
    for name in names:
        out.append(
            f"- {name}: " + ("; ".join(found[name]) if name in found else "no extreme values")
        )
    return "\n".join(out)


def _judge_versions(records: list[dict[str, Any]]) -> str:
    """Exact model versions the judge API reported, since an alias can move between runs."""
    versions = sorted(
        {r["judge"]["model_version"] for r in records if r.get("judge", {}).get("model_version")}
    )
    return f" (resolved to: {', '.join(versions)})" if versions else ""


def _methods(meta: dict[str, Any], state: dict[str, Any]) -> str:
    account = meta.get("serpapi_account")
    lines = [
        f"- Run started: {meta.get('started_at', 'unknown')}",
        f"- Tool version {meta.get('tool_version', 'unknown')}, "
        f"Python {meta.get('python', 'unknown')}, requests {meta.get('requests', 'unknown')}",
        f"- Providers: {', '.join(meta.get('providers', []))}; intents: "
        f"{', '.join(meta.get('intents', []))}; queries per intent limit: {meta.get('limit')}",
        f"- Judge: {meta.get('judge_model') or 'off'}{_judge_versions(state['records'])}",
        f"- Records: {len(state['records'])}",
        "- Latency is measured client-side from the runner's network location, successful "
        "non-cached responses only, p50 and p95 by nearest rank. Apify latency includes actor "
        "start-up.",
        "- Domain overlap is an agreement measure against SerpApi's web top 10, not accuracy.",
        "- Small samples: differences between providers can be noise. See METHODOLOGY.md.",
    ]
    if account:
        lines.append(
            f"- SerpApi searches left before: {account.get('before')}, "
            f"after: {account.get('after')}"
        )
    return "\n".join(lines)


def render_report(state: dict[str, Any], pricing: dict[str, PriceRow]) -> str:
    summary = summarize(state["records"], pricing)
    parts = ["# India search benchmark results", ""]
    for intent, providers in summary.items():
        parts += [f"## {intent}", "", _intent_table(providers), ""]
    parts += ["## Cost", "", _cost_table(summary, pricing), ""]
    parts += ["## Where each provider wins and loses", "", _wins_losses(summary), ""]
    parts += ["## Methods and caveats", "", _methods(state["meta"], state), ""]
    return "\n".join(parts)


def write_report(run_dir: Path, pricing_path: Path = DEFAULT_PRICING_PATH) -> Path:
    if not (run_dir / RESULTS_FILE).exists():
        raise FileNotFoundError(f"{run_dir / RESULTS_FILE} not found")
    state = load_state(run_dir)
    out = run_dir / REPORT_FILE
    out.write_text(render_report(state, load_pricing(pricing_path)), encoding="utf-8")
    return out

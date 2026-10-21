"""Run planning and execution with per-record persistence so a run can resume."""

from __future__ import annotations

import json
import platform
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from indiasearchbench import __version__
from indiasearchbench.judge import Judge
from indiasearchbench.metrics import PriceRow
from indiasearchbench.providers import PROVIDERS, Provider
from indiasearchbench.queries import Query

RESULTS_FILE = "results.json"


@dataclass(frozen=True)
class ProviderPlan:
    name: str
    env_var: str
    key_present: bool
    queries: int
    calls: int
    credits: int
    est_usd: float | None


def plan_run(
    names: list[str],
    queries: list[Query],
    env: Mapping[str, str],
    pricing: dict[str, PriceRow],
) -> list[ProviderPlan]:
    """Count calls and estimated billable credits per provider without touching the network."""
    plans = []
    for name in names:
        provider = PROVIDERS[name]("")
        offered = [q for q in queries if q.intent in provider.intents]
        credits = sum(provider.est_credits(q.intent) for q in offered)
        usd = [
            provider.est_credits(q.intent) * pricing[provider.pricing_key(q.intent)].usd_per_1000
            for q in offered
            if provider.pricing_key(q.intent) in pricing
        ]
        complete = len(usd) == len(offered)
        plans.append(
            ProviderPlan(
                name=name,
                env_var=provider.env_var,
                key_present=bool(env.get(provider.env_var)),
                queries=len(offered),
                calls=sum(provider.calls_for(q.intent) for q in offered),
                credits=credits,
                est_usd=sum(usd) / 1000 if complete else None,
            )
        )
    return plans


def load_state(run_dir: Path) -> dict[str, Any]:
    path = run_dir / RESULTS_FILE
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"meta": {}, "records": []}


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / RESULTS_FILE).write_text(json.dumps(state, indent=2, ensure_ascii=False), "utf-8")


def new_meta(
    providers: list[str], intents: list[str], limit: int | None, judge_model: str | None
) -> dict[str, Any]:
    return {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool_version": __version__,
        "python": platform.python_version(),
        "requests": requests.__version__,
        "providers": providers,
        "intents": intents,
        "limit": limit,
        "judge_model": judge_model,
    }


def execute_run(
    run_dir: Path,
    providers: Mapping[str, Provider],
    queries: list[Query],
    meta: dict[str, Any],
    judge: Judge | None = None,
    progress: Callable[[str], None] = lambda line: None,
) -> dict[str, Any]:
    """Call every (query, provider) pair not already recorded; save after each one."""
    state = load_state(run_dir)
    state["meta"] = {**meta, **state["meta"]}
    done = {(r["query_id"], r["provider"]) for r in state["records"]}
    for query in queries:
        for name, provider in providers.items():
            if (query.id, name) in done:
                continue
            result = provider.search(query).to_dict()
            result["city"] = query.city
            if judge is not None and result["ok"]:
                result["judge"] = judge.score(query, result)
            state["records"].append(result)
            save_state(run_dir, state)
            progress(f"{query.id} {name}: {'ok' if result['ok'] else result['error']}")
    return state

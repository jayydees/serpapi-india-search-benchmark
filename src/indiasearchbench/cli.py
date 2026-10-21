"""Command line: `indiasearchbench run ...` and `indiasearchbench report <run dir>`."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from indiasearchbench.judge import Judge, JudgeError, judge_model
from indiasearchbench.metrics import DEFAULT_PRICING_PATH, load_pricing
from indiasearchbench.providers import PROVIDERS
from indiasearchbench.providers.serpapi import (
    DEFAULT_MAX_SEARCHES,
    BudgetError,
    check_budget,
    fetch_account,
)
from indiasearchbench.queries import DEFAULT_QUERIES_PATH, INTENTS, load_queries, select_queries
from indiasearchbench.report import write_report
from indiasearchbench.runner import execute_run, new_meta, plan_run, save_state

DEFAULT_PROVIDERS = "serpapi,serper,exa,apify"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="indiasearchbench", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="plan or execute a benchmark run (dry run by default)")
    run.add_argument("--providers", default=DEFAULT_PROVIDERS)
    run.add_argument("--intents", default=",".join(INTENTS))
    run.add_argument("--limit", type=int, default=None, help="queries per intent")
    run.add_argument("--live", action="store_true", help="call the APIs (spends credits)")
    run.add_argument("--judge", action="store_true", help="score results with the Gemini judge")
    run.add_argument("--max-serpapi-searches", type=int, default=DEFAULT_MAX_SEARCHES)
    run.add_argument("--queries", type=Path, default=DEFAULT_QUERIES_PATH)
    run.add_argument("--pricing", type=Path, default=DEFAULT_PRICING_PATH)
    run.add_argument("--out", type=Path, default=Path("runs"))
    run.add_argument("--resume", type=Path, default=None, help="existing run dir to continue")
    report = sub.add_parser("report", help="regenerate results.md from a run directory")
    report.add_argument("run_dir", type=Path)
    report.add_argument("--pricing", type=Path, default=DEFAULT_PRICING_PATH)
    return parser


def _csv(value: str, allowed: Sequence[str], label: str) -> list[str]:
    items = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in items if v not in allowed]
    if unknown:
        raise SystemExit(f"unknown {label}: {', '.join(unknown)}")
    return items


def _print_plan(plans: list[Any], queries: list[Any]) -> None:
    print(f"Queries selected: {len(queries)}")
    print("provider    key         queries  calls  est. credits  est. USD")
    for p in plans:
        key = f"{p.env_var} set" if p.key_present else f"{p.env_var} MISSING"
        usd = "n/a" if p.est_usd is None else f"{p.est_usd:.2f}"
        print(f"{p.name:<11} {key:<22} {p.queries:>5} {p.calls:>6} {p.credits:>12}  {usd:>8}")


def _run(args: argparse.Namespace, env: Mapping[str, str], session: Any) -> int:
    names = _csv(args.providers, list(PROVIDERS), "provider")
    intents = _csv(args.intents, INTENTS, "intent")
    queries = select_queries(load_queries(args.queries), intents, args.limit)
    pricing = load_pricing(args.pricing)
    plans = plan_run(names, queries, env, pricing)
    _print_plan(plans, queries)
    if not args.live:
        print("Dry run: no API calls made. Add --live to execute.")
        return 0
    active = [p.name for p in plans if p.key_present]
    for p in plans:
        if not p.key_present:
            print(f"Skipping {p.name}: environment variable {p.env_var} is not set")
    if not active:
        print("No provider has a key set; nothing to run.")
        return 2
    judge, model = None, None
    if args.judge:
        try:
            model = judge_model(env)
        except JudgeError as exc:
            print(exc)
            return 2
        if not env.get("GEMINI_API_KEY"):
            print("Cannot judge: environment variable GEMINI_API_KEY is not set")
            return 2
        judge = Judge(env["GEMINI_API_KEY"], model, session)
    account_before = None
    if "serpapi" in active:
        planned = next(p.credits for p in plans if p.name == "serpapi")
        try:
            account_before = fetch_account(env[PROVIDERS["serpapi"].env_var], session)
            check_budget(planned, account_before, args.max_serpapi_searches)
        except BudgetError as exc:
            print(f"Refusing to start: {exc}")
            return 2
        if planned > account_before.account_rate_limit_per_hour:
            print(
                f"Warning: {planned} planned searches exceed the hourly limit of "
                f"{account_before.account_rate_limit_per_hour}; use --limit or --resume later."
            )
    run_dir = args.resume or args.out / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    providers = {
        n: PROVIDERS[n](env[PROVIDERS[n].env_var], session, run_dir / "raw") for n in active
    }
    meta = new_meta(active, intents, args.limit, model)
    state = execute_run(run_dir, providers, queries, meta, judge, print)
    if account_before is not None:
        try:
            after = fetch_account(env[PROVIDERS["serpapi"].env_var], session).total_searches_left
        except BudgetError:
            after = None
        state["meta"]["serpapi_account"] = {
            "before": account_before.total_searches_left,
            "after": after,
        }
        save_state(run_dir, state)
    print(f"Report: {write_report(run_dir, args.pricing)}")
    return 0


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    session: Any = None,
) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "report":
        print(f"Report: {write_report(args.run_dir, args.pricing)}")
        return 0
    return _run(args, os.environ if env is None else env, session)


if __name__ == "__main__":
    sys.exit(main())

import json

import pytest
from conftest import KEY, FakeResponse, FakeSession, fixture, ok

from indiasearchbench.cli import main
from indiasearchbench.metrics import load_pricing
from indiasearchbench.report import fmt, render_report, standings, write_report

ENV_ALL = {"SERPAPI_API_KEY": KEY, "SERPER_API_KEY": KEY}


def test_dry_run_prints_plan_and_makes_no_call(capsys):
    session = FakeSession(FakeResponse({}))
    code = main(
        ["run", "--providers", "serpapi,exa", "--limit", "2"],
        env={"EXA_API_KEY": KEY},
        session=session,
    )
    out = capsys.readouterr().out
    assert code == 0 and session.calls == []
    assert "Dry run: no API calls made" in out
    assert "SERPAPI_API_KEY MISSING" in out and "EXA_API_KEY set" in out
    assert KEY not in out
    rows = {line.split()[0]: line.split() for line in out.splitlines() if line.split()}
    # serpapi: 2 news x 2 searches + 2 local + 2 shopping; exa: 2 news
    assert rows["serpapi"][3:6] == ["6", "8", "8"]
    assert rows["exa"][3:6] == ["2", "2", "2"]


def test_unknown_provider_exits():
    with pytest.raises(SystemExit):
        main(["run", "--providers", "nope"], env={})


def test_live_without_keys_does_nothing(capsys):
    assert (
        main(["run", "--live", "--limit", "1"], env={}, session=FakeSession(FakeResponse({}))) == 2
    )
    assert "Skipping serpapi" in capsys.readouterr().out


def test_live_refuses_over_budget_before_any_search(capsys, tmp_path):
    account = fixture("serpapi_account")
    session = FakeSession(FakeResponse(account))
    code = main(
        [
            "run",
            "--live",
            "--providers",
            "serpapi",
            "--max-serpapi-searches",
            "3",
            "--limit",
            "2",
            "--out",
            str(tmp_path),
        ],
        env=ENV_ALL,
        session=session,
    )
    assert code == 2
    assert "Refusing to start" in capsys.readouterr().out
    assert [c["url"] for c in session.calls] == ["https://serpapi.com/account.json"]


def test_judge_needs_model_and_key(capsys):
    args = ["run", "--live", "--judge", "--providers", "serper", "--limit", "1"]
    assert main(args, env={"SERPER_API_KEY": KEY}, session=FakeSession(FakeResponse({}))) == 2
    assert "JUDGE_MODEL" in capsys.readouterr().out
    env = {"SERPER_API_KEY": KEY, "JUDGE_MODEL": "m"}
    assert main(args, env=env, session=FakeSession(FakeResponse({}))) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().out


class RouterSession:
    """Routes by URL so one run can touch several providers and the account endpoint."""

    def __init__(self):
        self.calls = []
        self.account_reads = 0

    def request(self, method, url, **kwargs):
        self.calls.append(url)
        if url.endswith("account.json"):
            self.account_reads += 1
            payload = dict(fixture("serpapi_account"))
            payload["total_searches_left"] -= 3 * (self.account_reads - 1)
            return FakeResponse(payload)
        if "generativelanguage" in url:
            return ok("gemini_response")
        if "google_news" in str(kwargs.get("params")):
            return ok("serpapi_news")
        if "serpapi.com" in url:
            return ok("serpapi_web")
        if url.endswith("/news"):
            return ok("serper_news")
        return ok("serper_search")


def test_live_run_end_to_end_with_resume(tmp_path, capsys):
    session = RouterSession()
    env = {**ENV_ALL, "GEMINI_API_KEY": KEY, "JUDGE_MODEL": "m"}
    base = [
        "run",
        "--live",
        "--judge",
        "--providers",
        "serpapi,serper",
        "--intents",
        "news",
        "--limit",
        "2",
        "--out",
        str(tmp_path),
    ]
    assert main(base, env=env, session=session) == 0
    run_dir = next(tmp_path.iterdir())
    state = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    assert len(state["records"]) == 4
    assert state["meta"]["serpapi_account"] == {"before": 240, "after": 237}
    assert state["records"][0]["judge"]["score"] == 2
    assert (run_dir / "results.md").exists() and (run_dir / "raw").exists()
    calls_before = len(session.calls)
    assert main(base + ["--resume", str(run_dir)], env=env, session=session) == 0
    new_search_calls = [c for c in session.calls[calls_before:] if "account" not in c]
    assert new_search_calls == []
    assert KEY not in (run_dir / "results.json").read_text(encoding="utf-8")


def test_report_command_regenerates_markdown(tmp_path, capsys):
    (tmp_path / "results.json").write_text(json.dumps(STATE), encoding="utf-8")
    assert main(["report", str(tmp_path)]) == 0
    text = (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "# India search benchmark results" in text


def _rec(provider, intent, latency, ok_=True, **kw):
    row = {
        "provider": provider,
        "intent": intent,
        "query_id": f"{intent}-1",
        "ok": ok_,
        "error": None if ok_ else "http_500",
        "latency_ms": latency,
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
    row.update(kw)
    return row


STATE = {
    "meta": {
        "started_at": "2026-10-21T00:00:00+00:00",
        "providers": ["serpapi", "serper"],
        "intents": ["news"],
        "limit": 1,
        "judge_model": None,
        "serpapi_account": {"before": 10, "after": 8},
    },
    "records": [
        _rec(
            "serpapi",
            "news",
            800.0,
            results=[{"url": "https://a.in"}],
            news_items=[{"date": "d", "source": "s"}],
        ),
        _rec(
            "serper",
            "news",
            400.0,
            results=[{"url": "https://a.in"}],
            news_items=[{"date": "d", "source": ""}],
        ),
        _rec("exa", "local", None, ok_=False, error="intent_not_offered"),
    ],
}


def test_render_report_sections_and_numbers():
    text = render_report(STATE, load_pricing())
    for heading in (
        "## news",
        "## Cost",
        "## Where each provider wins and loses",
        "## Methods and caveats",
    ):
        assert heading in text
    assert "| serpapi | 1 | 100% | 800 ms |" in text
    assert "serper: best on news p50 latency (400 ms)" in text
    assert "serpapi: worst on news p50 latency (800 ms)" in text
    assert "SerpApi searches left before: 10, after: 8" in text
    assert "## local" not in text


def test_standings_requires_two_providers_and_a_difference():
    one = {
        "news": {
            "a": {
                "success_rate": 1.0,
                **{
                    k: None
                    for k in (
                        "latency_p50_ms",
                        "latency_p95_ms",
                        "completeness",
                        "overlap_with_serpapi",
                        "india_relevance",
                        "judge_mean",
                        "cost_per_1000_usd",
                    )
                },
            }
        }
    }
    assert standings(one) == {}


def test_fmt():
    assert fmt(None, "pct") == "n/a"
    assert fmt(0.456, "pct") == "46%"
    assert fmt(1234.4, "ms") == "1,234 ms"
    assert fmt(2.5, "usd") == "$2.50"
    assert fmt(2.0, "num") == "2.00"


def test_write_report_missing_results(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_report(tmp_path)

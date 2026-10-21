import json

import pytest
import requests
from conftest import KEY, FakeResponse, FakeSession, fixture, redacted

from indiasearchbench import judge
from indiasearchbench.queries import Query

QUERY = Query("news-01", "news", "RBI repo rate decision latest", "Must name the rate.")


def result(provider="serper"):
    return {
        "provider": provider,
        "results": [
            {"title": f"t{i}", "url": f"https://s{i}.example.in", "snippet": "s", "position": i}
            for i in range(1, 8)
        ],
    }


def test_judge_model_comes_from_env_and_is_never_defaulted():
    assert judge.judge_model({"JUDGE_MODEL": " some-model "}) == "some-model"
    with pytest.raises(judge.JudgeError, match="JUDGE_MODEL"):
        judge.judge_model({})


def test_shuffle_is_deterministic_and_seeded():
    first = judge.blind_items(result(), QUERY, seed=1)
    again = judge.blind_items(result(), QUERY, seed=1)
    other = judge.blind_items(result(), QUERY, seed=2)
    assert first == again
    assert first != other
    assert sorted(i["title"] for i in first) == sorted(i["title"] for i in other)
    assert first != result()["results"]


def test_prompt_is_blind_and_carries_rubric():
    prompt = judge.build_prompt(QUERY, judge.blind_items(result("serper"), QUERY))
    assert "serper" not in prompt.lower()
    assert "Must name the rate." in prompt and QUERY.text in prompt
    assert '"position"' not in prompt


def test_local_intent_uses_structured_items():
    local = Query("local-01", "local", "cafe", "r", "Pune")
    record = {"provider": "x", "local_results": [{"name": "A"}], "results": [{"title": "z"}]}
    assert judge.blind_items(record, local) == [{"name": "A"}]


def test_request_building_has_temperature_zero_and_header_key():
    spec = judge.build_request("model-x", KEY, "prompt")
    call = redacted({"url": spec.url, "headers": spec.headers, "json": spec.json})
    assert call["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/model-x:generateContent"
    )
    assert call["headers"]["x-goog-api-key"] == "<KEY>"
    assert call["json"]["generationConfig"]["temperature"] == 0
    assert call["json"]["contents"][0]["parts"][0]["text"] == "prompt"


def test_score_parses_synthetic_gemini_reply():
    session = FakeSession(FakeResponse(fixture("gemini_response")))
    out = judge.Judge(KEY, "model-x", session).score(QUERY, result())
    assert out == {"score": 2, "reason": "Most results match the rubric."}
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    "reply",
    [
        FakeResponse({}, status=500),
        FakeResponse({"candidates": []}),
        FakeResponse(bad_json=True),
        FakeResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps({"score": 9, "reason": "r"})}]}}
                ]
            }
        ),
    ],
)
def test_score_failures_return_error_not_exception(reply):
    out = judge.Judge(KEY, "model-x", FakeSession(reply)).score(QUERY, result())
    assert "error" in out and KEY not in out["error"]


def test_score_network_error_is_redacted():
    session = FakeSession(requests.ConnectionError(f"boom api_key={KEY}"))
    out = judge.Judge(KEY, "model-x", session).score(QUERY, result())
    assert "error" in out and KEY not in out["error"]

"""Optional blind LLM judge using the Gemini REST API.

The judge sees the query, the rubric and a shuffled list of result items. It never sees the
provider name. Temperature is 0. The model id comes from the JUDGE_MODEL environment
variable, so no model name is hard-coded. Limits: LLM judges are biased and noisy, so treat the
score as one signal; agreement with a human-labelled subset is still a TODO for the author.
"""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from typing import Any

import requests

from indiasearchbench.providers.base import RequestSpec, redact
from indiasearchbench.queries import Query

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_ITEMS = 10
DEFAULT_SEED = 20261021


class JudgeError(RuntimeError):
    pass


def judge_model(env: Mapping[str, str]) -> str:
    model = env.get("JUDGE_MODEL", "").strip()
    if not model:
        raise JudgeError("JUDGE_MODEL is not set; export the Gemini model id to use --judge")
    return model


def blind_items(
    result: dict[str, Any], query: Query, seed: int = DEFAULT_SEED
) -> list[dict[str, Any]]:
    """Top items for the intent, provider-agnostic, in a seeded shuffled order."""
    source = (
        {
            "local": result.get("local_results"),
            "shopping": result.get("shopping_results"),
        }.get(query.intent)
        or result.get("results")
        or []
    )
    items = [dict(i) for i in source[:MAX_ITEMS]]
    random.Random(f"{seed}:{query.id}:{result['provider']}").shuffle(items)
    return items


def build_prompt(query: Query, items: list[dict[str, Any]]) -> str:
    listing = "\n".join(
        f"{n}. {json.dumps({k: v for k, v in item.items() if k != 'position'}, ensure_ascii=False)}"
        for n, item in enumerate(items, 1)
    )
    return (
        "You grade search results for a user in India. Score how well the result list answers "
        "the query, using only the rubric.\n"
        f"Query: {query.text}\n"
        f"Rubric: {query.rubric}\n"
        "Scale: 0 = unusable, 1 = weak, 2 = good, 3 = excellent.\n"
        f"Results (unordered):\n{listing or '(no results)'}\n"
        'Reply with JSON only: {"score": <0-3 integer>, "reason": "<one sentence>"}'
    )


def build_request(model: str, api_key: str, prompt: str) -> RequestSpec:
    return RequestSpec(
        "POST",
        GEMINI_URL.format(model=model),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        },
    )


def parse_judgement(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        score = int(data["score"])
        reason = str(data["reason"])
    except (KeyError, IndexError, TypeError, ValueError):
        raise JudgeError("judge reply was not the expected JSON") from None
    if not 0 <= score <= 3:
        raise JudgeError(f"judge score {score} is outside 0-3")
    return {"score": score, "reason": reason, "model_version": payload.get("modelVersion")}


class Judge:
    def __init__(self, api_key: str, model: str, session: Any = None, seed: int = DEFAULT_SEED):
        self.api_key = api_key
        self.model = model
        self.seed = seed
        self.session = session or requests.Session()

    def score(self, query: Query, result: dict[str, Any]) -> dict[str, Any]:
        """Return {"score", "reason"} or {"error"}; a judge failure never aborts a run."""
        spec = build_request(
            self.model, self.api_key, build_prompt(query, blind_items(result, query, self.seed))
        )
        try:
            response = self.session.request(
                spec.method, spec.url, headers=spec.headers, json=spec.json, timeout=60
            )
            if response.status_code != 200:
                raise JudgeError(f"judge HTTP {response.status_code}")
            return parse_judgement(response.json())
        except (JudgeError, requests.RequestException, ValueError) as exc:
            return {"error": redact(str(exc), [self.api_key])}

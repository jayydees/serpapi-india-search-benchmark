"""Shared offline test helpers: a fake HTTP session and synthetic fixture loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from indiasearchbench.queries import Query

FIXTURES = Path(__file__).parent / "fixtures"
KEY = "test-key-123"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"synthetic_{name}.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(
        self, payload: Any = None, status: int = 200, text: str = "", bad_json: bool = False
    ):
        self.status_code = status
        self._payload = payload
        self._bad_json = bad_json
        self.text = text or json.dumps(payload)

    def json(self) -> Any:
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Replays queued responses (or raises queued exceptions); the last item repeats."""

    def __init__(self, *queue: Any):
        self.queue = list(queue)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        item = self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]
        if isinstance(item, Exception):
            raise item
        return item


def redacted(call: dict[str, Any]) -> dict[str, Any]:
    """Copy of a recorded call with the test key replaced, so assertions never hold a key."""
    return json.loads(json.dumps(call, default=str).replace(KEY, "<KEY>"))


def ok(name: str) -> FakeResponse:
    return FakeResponse(fixture(name))


@pytest.fixture
def q_news() -> Query:
    return Query("news-01", "news", "RBI repo rate decision latest", "rubric news")


@pytest.fixture
def q_local() -> Query:
    return Query("local-01", "local", "vegan cafe in Indiranagar", "rubric local", "Bangalore")


@pytest.fixture
def q_shop() -> Query:
    return Query("shop-01", "shopping", "whey protein 1kg", "rubric shop")

"""Shared types and the HTTP template used by every provider adapter."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

from indiasearchbench.queries import Query

NOT_OFFERED = "intent_not_offered"
REDACTED = "***REDACTED***"
DEFAULT_TIMEOUT = 30
_SECRET_PARAM = re.compile(r"(api_key|token)=[^&\s'\"]+", re.IGNORECASE)


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove known secrets and any api_key=/token= query fragments from text."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return _SECRET_PARAM.sub(lambda m: f"{m.group(1)}={REDACTED}", text)


def web_item(title: str, url: str, snippet: str, position: int) -> dict[str, Any]:
    return {"title": title, "url": url, "snippet": snippet, "position": position}


def local_item(
    name: Any,
    address: Any,
    phone: Any,
    rating: Any,
    lat: Any = None,
    lon: Any = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "address": address,
        "phone": phone,
        "rating": rating,
        "lat": lat,
        "lon": lon,
    }


def shopping_item(title: Any, price: Any, merchant: Any, rating: Any) -> dict[str, Any]:
    return {"title": title, "price": price, "merchant": merchant, "rating": rating}


def news_item(title: Any, date: Any, source: Any) -> dict[str, Any]:
    return {"title": title, "date": date, "source": source}


@dataclass
class RequestSpec:
    method: str
    url: str
    params: dict[str, Any] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    json: dict[str, Any] | None = None


@dataclass
class Parsed:
    """What an adapter extracts from the raw payloads of one query."""

    results: list[dict[str, Any]] = field(default_factory=list)
    local_results: list[dict[str, Any]] = field(default_factory=list)
    shopping_results: list[dict[str, Any]] = field(default_factory=list)
    news_items: list[dict[str, Any]] = field(default_factory=list)
    credits_used: float = 0.0
    overhead_credits: float = 0.0
    overhead_credits: float = 0.0  # benchmark-only calls, excluded from the cost table
    cost_usd: float | None = None
    cache_hit: bool = False


@dataclass
class NormalizedResult:
    provider: str
    intent: str
    query_id: str
    ok: bool
    error: str | None = None
    http_status: int | None = None
    latency_ms: float | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    local_results: list[dict[str, Any]] = field(default_factory=list)
    shopping_results: list[dict[str, Any]] = field(default_factory=list)
    news_items: list[dict[str, Any]] = field(default_factory=list)
    structured_offered: bool = False
    credits_used: float = 0.0
    cost_usd: float | None = None
    cache_hit: bool = False
    retries: int = 0
    pricing_key: str = ""
    raw_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderError(Exception):
    def __init__(self, message: str, http_status: int | None = None, retries: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.http_status = http_status
        self.retries = retries


class Provider:
    """Template: subclasses build requests and parse payloads, this class does the I/O."""

    name = ""
    env_var = ""
    intents: frozenset[str] = frozenset()
    structured: frozenset[str] = frozenset()
    timeout: float = DEFAULT_TIMEOUT

    def __init__(
        self,
        api_key: str,
        session: Any = None,
        raw_dir: Path | None = None,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.raw_dir = raw_dir

    def calls_for(self, intent: str) -> int:
        return 1

    def est_credits(self, intent: str) -> int:
        """Estimated billable units for one query (calls unless a provider overrides)."""
        return self.calls_for(intent)

    def pricing_key(self, intent: str) -> str:
        return self.name

    def is_overhead_call(self, intent: str, index: int) -> bool:
        """True for a call made only for the benchmark (not timed, not costed)."""
        return False

    def build_requests(self, query: Query) -> list[RequestSpec]:
        raise NotImplementedError

    def parse(self, query: Query, payloads: list[Any]) -> Parsed:
        raise NotImplementedError

    def search(self, query: Query) -> NormalizedResult:
        base = NormalizedResult(
            provider=self.name,
            intent=query.intent,
            query_id=query.id,
            ok=False,
            structured_offered=query.intent in self.structured,
            pricing_key=self.pricing_key(query.intent),
        )
        if query.intent not in self.intents:
            base.error = NOT_OFFERED
            return base
        payloads: list[Any] = []
        latency, retries, status = 0.0, 0, None
        try:
            for index, spec in enumerate(self.build_requests(query)):
                payload, elapsed, status, spent = self._send(spec)
                payloads.append(payload)
                if not self.is_overhead_call(query.intent, index):
                    latency += elapsed
                retries += spent
            parsed = self.parse(query, payloads)
        except ProviderError as exc:
            base.error = exc.message
            base.http_status = exc.http_status or status
            base.retries = retries + exc.retries
            base.raw_ref = self._save_raw(query, payloads)
            return base
        base.ok = True
        base.http_status = status
        base.retries = retries
        base.latency_ms = round(latency, 1)
        base.results = parsed.results
        base.local_results = parsed.local_results
        base.shopping_results = parsed.shopping_results
        base.news_items = parsed.news_items
        base.credits_used = parsed.credits_used
        base.overhead_credits = parsed.overhead_credits
        base.cost_usd = parsed.cost_usd
        base.cache_hit = parsed.cache_hit
        base.raw_ref = self._save_raw(query, payloads)
        return base

    def _clean(self, text: str) -> str:
        return redact(text, [self.api_key])

    def _send(self, spec: RequestSpec) -> tuple[Any, float, int, int]:
        """Send one request, retrying once on a 5xx or timeout.

        Returns the decoded payload, elapsed milliseconds, HTTP status and retries spent.
        """
        retries = 0
        while True:
            started = time.perf_counter()
            response = None
            try:
                response = self.session.request(
                    spec.method,
                    spec.url,
                    params=spec.params,
                    headers=spec.headers,
                    json=spec.json,
                    timeout=self.timeout,
                )
                failure = self._check_status(response)
            except requests.Timeout:
                failure = ProviderError("timeout")
            except requests.RequestException as exc:
                raise ProviderError(self._clean(f"request_error: {exc}"), retries=retries) from None
            elapsed = (time.perf_counter() - started) * 1000
            if failure is None:
                return self._decode(response, retries), elapsed, response.status_code, retries
            failure.retries = retries
            if retries >= 1 or (failure.http_status or 0) in range(400, 500):
                raise failure
            retries += 1

    def _check_status(self, response: Any) -> ProviderError | None:
        status = response.status_code
        if status < 400:
            return None
        body = self._clean(str(response.text)[:200])
        return ProviderError(f"http_{status}: {body}", status)

    def _decode(self, response: Any, retries: int) -> Any:
        try:
            return response.json()
        except ValueError:
            raise ProviderError("invalid_json", response.status_code, retries) from None

    def _save_raw(self, query: Query, payloads: list[Any]) -> str | None:
        if self.raw_dir is None or not payloads:
            return None
        path = Path(self.raw_dir) / f"{self.name}__{query.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._clean(json.dumps(payloads, ensure_ascii=False)), encoding="utf-8")
        return str(path)

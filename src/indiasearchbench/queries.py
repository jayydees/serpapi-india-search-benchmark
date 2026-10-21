"""Query model, city table and loader for queries/queries.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

INTENTS = ("news", "local", "shopping")
DEFAULT_QUERIES_PATH = Path(__file__).resolve().parents[2] / "queries" / "queries.yaml"


@dataclass(frozen=True)
class City:
    """A benchmark city: provider location string, map centre and address aliases."""

    location: str
    lat: float
    lon: float
    aliases: tuple[str, ...]


CITIES: dict[str, City] = {
    "Bangalore": City("Bengaluru, Karnataka, India", 12.9716, 77.5946, ("bangalore", "bengaluru")),
    "Mumbai": City("Mumbai, Maharashtra, India", 19.0760, 72.8777, ("mumbai", "bombay")),
    "Delhi NCR": City(
        "Delhi, India",
        28.6139,
        77.2090,
        ("delhi", "gurgaon", "gurugram", "noida", "ghaziabad", "faridabad"),
    ),
    "Chennai": City("Chennai, Tamil Nadu, India", 13.0827, 80.2707, ("chennai", "madras")),
    "Hyderabad": City(
        "Hyderabad, Telangana, India", 17.3850, 78.4867, ("hyderabad", "secunderabad")
    ),
    "Pune": City("Pune, Maharashtra, India", 18.5204, 73.8567, ("pune",)),
}


@dataclass(frozen=True)
class Query:
    id: str
    intent: str
    text: str
    rubric: str
    city: str | None = None

    @property
    def city_info(self) -> City | None:
        return CITIES[self.city] if self.city else None


def load_queries(path: Path = DEFAULT_QUERIES_PATH) -> list[Query]:
    """Load and validate queries. Raises ValueError on any schema problem."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    queries = [
        Query(
            id=str(item["id"]),
            intent=item["intent"],
            text=item["text"],
            rubric=item["rubric"],
            city=item.get("city"),
        )
        for item in raw["queries"]
    ]
    _validate(queries)
    return queries


def _validate(queries: list[Query]) -> None:
    ids = [q.id for q in queries]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate query ids")
    for q in queries:
        if q.intent not in INTENTS:
            raise ValueError(f"{q.id}: unknown intent {q.intent!r}")
        if q.intent == "local" and q.city not in CITIES:
            raise ValueError(f"{q.id}: local query needs a known city, got {q.city!r}")
        if not q.rubric.strip():
            raise ValueError(f"{q.id}: empty rubric")


def select_queries(queries: list[Query], intents: list[str], limit: int | None) -> list[Query]:
    """Keep the first `limit` queries of each requested intent, in file order."""
    chosen: list[Query] = []
    for intent in intents:
        group = [q for q in queries if q.intent == intent]
        chosen.extend(group if limit is None else group[:limit])
    return chosen

import pytest
import yaml

from indiasearchbench.queries import Query, load_queries, select_queries


def test_shipped_query_file_has_the_agreed_mix():
    queries = load_queries()
    counts = {i: sum(q.intent == i for q in queries) for i in ("news", "local", "shopping")}
    assert counts == {"news": 17, "local": 17, "shopping": 16}
    assert all(q.rubric for q in queries)
    assert {q.city for q in queries if q.intent == "local"} == {
        "Bangalore",
        "Mumbai",
        "Delhi NCR",
        "Chennai",
        "Hyderabad",
        "Pune",
    }


def test_select_queries_limits_per_intent():
    queries = load_queries()
    chosen = select_queries(queries, ["news", "shopping"], 2)
    assert [q.intent for q in chosen] == ["news", "news", "shopping", "shopping"]
    assert len(select_queries(queries, ["local"], None)) == 17


@pytest.mark.parametrize(
    "item",
    [
        {"id": "a", "intent": "video", "text": "t", "rubric": "r"},
        {"id": "a", "intent": "local", "text": "t", "rubric": "r"},
        {"id": "a", "intent": "news", "text": "t", "rubric": " "},
    ],
)
def test_invalid_queries_are_rejected(tmp_path, item):
    path = tmp_path / "q.yaml"
    path.write_text(yaml.safe_dump({"queries": [item]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_queries(path)


def test_duplicate_ids_are_rejected(tmp_path):
    item = {"id": "a", "intent": "news", "text": "t", "rubric": "r"}
    path = tmp_path / "q.yaml"
    path.write_text(yaml.safe_dump({"queries": [item, item]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_queries(path)


def test_city_info_is_none_without_city():
    assert Query("a", "news", "t", "r").city_info is None

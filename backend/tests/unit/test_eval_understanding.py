import json

from vio.eval.queries import QueryRecord
from vio.eval.understanding import metrics, run, similarity
from vio.llm.client import ChatResult, LLMClient, Message, RateLimitedError
from vio.llm.query_understanding import QueryUnderstanding
from vio.models import Filters, Product

ANSWERS = {
    "headphones under 50": {
        "search_text": "headphones",
        "category": "Electronics",
        "price_max": 50,
    },
    "quiet keyboard": {"search_text": "quiet keyboard", "category": "Toys"},  # wrong category
    "quiet keybaord": {"search_text": "quiet keyboard"},
    "gift for dad": {"search_text": "gift for dad"},
    "cheap pens": {"search_text": "pens", "price_intent": "cheap"},
}


class Fake:
    def __call__(
        self, model: str, messages: list[Message], temperature: float, json_mode: bool
    ) -> ChatResult:
        req = messages[-1]["content"].split("<request>")[1].split("</request>")[0].strip()
        if req == "explode":
            raise RateLimitedError(9999.0, "TPD")
        return ChatResult(json.dumps(ANSWERS[req]))


def _qu() -> QueryUnderstanding:
    return QueryUnderstanding(
        LLMClient(Fake(), max_attempts=1, sleep=lambda s: None),
        "m",
        lambda: ["Electronics", "Toys"],
    )


QUERIES = [
    QueryRecord(
        qid="q1",
        bucket="constrained",
        query="headphones under 50",
        seed_product_id="1",
        filters=Filters(price_max=50),
    ),
    QueryRecord(qid="q2", bucket="descriptive", query="quiet keyboard", seed_product_id="2"),
    QueryRecord(qid="q3", bucket="noisy", query="quiet keybaord", seed_product_id="2"),
    QueryRecord(qid="q4", bucket="vague", query="gift for dad"),
    QueryRecord(qid="q5", bucket="specific", query="cheap pens", seed_product_id="3"),
    QueryRecord(qid="q6", bucket="image", image_file="x.jpg", seed_product_id="1"),
]
PRODUCTS = {
    "1": Product(product_id="1", name="h", category="Electronics"),
    "2": Product(product_id="2", name="k", category="Electronics"),
    "3": Product(product_id="3", name="p", category="Office"),
}


def test_metrics_against_built_in_ground_truth() -> None:
    results, stopped = run(QUERIES, _qu())
    assert stopped is None and len(results) == 5  # image query skipped
    m = metrics(results, PRODUCTS)
    assert m["budget extracted exactly (constrained)"] == "1/1 = 100.0%"
    assert m["invented price filter (no budget stated)"] == "0/4 = 0.0%"
    assert m["invented price intent (no budget stated)"] == "1/4 = 25.0%"  # 'cheap pens'
    assert m["category committed (seeded queries)"] == "2/4 = 50.0%"
    assert m["category correct when committed"] == "1/2 = 50.0%"
    assert m["category abstained on vague goals"] == "1/1 = 100.0%"
    assert "1.000" in m["typo queries: similarity to clean query (before -> after)"]


def test_quota_stops_with_partial_results() -> None:
    qs = [QUERIES[0], QueryRecord(qid="x", bucket="descriptive", query="explode"), QUERIES[1]]
    results, stopped = run(qs, _qu())
    assert len(results) == 1 and stopped and "TPD" in stopped


def test_similarity() -> None:
    assert similarity("Quiet Keyboard", "quiet keyboard") == 1.0
    assert similarity("quiet keybaord", "quiet keyboard") < 1.0

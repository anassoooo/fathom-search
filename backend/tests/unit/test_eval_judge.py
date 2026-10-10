import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from vio.config import Settings
from vio.embeddings.fake import fake_encoders
from vio.eval.judge import build_pool, describe_request, judge_all, load_qrels, save_qrels
from vio.eval.queries import QueryRecord
from vio.llm.client import ChatResult, LLMClient, Message
from vio.models import Filters
from vio.search.pipeline import SearchService
from vio.search.rerank import FakeReranker
from vio.store.qdrant import ProductStore


@pytest.fixture
def service(memory_store: ProductStore) -> SearchService:
    return SearchService(
        memory_store, fake_encoders(), FakeReranker(), Settings(_env_file=None, rerank_top_n=10)
    )


class FakeJudge:
    """Grades 2 when a candidate title shares a word with the request; skips c1 the first time."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self, model: str, messages: list[Message], temperature: float, json_mode: bool
    ) -> ChatResult:
        self.calls += 1
        first = messages[0]["content"]
        request = first.split("Shopper's request:")[1].split("Candidates:")[0].lower()
        words = set(re.findall(r"[a-z]+", request)) - {"the", "for", "a", "up", "to", "budget"}
        cands = [json.loads(line) for line in first.split("Candidates:")[1].strip().splitlines()]
        if len(messages) > 1:  # follow-up for skipped ids
            wanted = re.findall(r"'(c\d+)'", messages[-1]["content"])
            cands = [c for c in cands if c["id"] in wanted]
        else:
            cands = [c for c in cands if c["id"] != "c1"]
        grades = [
            {
                "id": c["id"],
                "grade": 2 if words & set(re.findall(r"[a-z]+", c["title"].lower())) else 0,
            }
            for c in cands
        ]
        return ChatResult(json.dumps({"grades": grades}))


def test_pool_unions_variants_and_includes_seed(service: SearchService, tmp_path: Path) -> None:
    q = QueryRecord(qid="q1", bucket="descriptive", query="coffee maker", seed_product_id="23")
    pool = build_pool(q, service, tmp_path, depth=3)
    ids = {p.product_id for p in pool}
    assert "23" in ids  # seed added even though it's a board game
    assert ids & {"16", "17", "18"}
    assert len(ids) == len(pool)


def test_describe_request_adds_budget_and_image_context() -> None:
    q = QueryRecord(
        qid="q", bucket="constrained", query="headphones", filters=Filters(price_max=50)
    )
    assert describe_request(q, None) == "headphones (budget: up to $50)"
    img = QueryRecord(qid="q", bucket="image", image_file="x.jpg")
    assert "uploaded a photo" in describe_request(img, None)


def test_judge_all_grades_every_pooled_product(service: SearchService, tmp_path: Path) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "blue").save(buf, format="JPEG")
    (tmp_path / "q.jpg").write_bytes(buf.getvalue())
    queries = [
        QueryRecord(qid="q1", bucket="specific", query="running shoes", seed_product_id="13"),
        QueryRecord(qid="q2", bucket="image", image_file="q.jpg", seed_product_id="22"),
    ]
    fake = FakeJudge()
    run = judge_all(queries, service, LLMClient(fake, sleep=lambda s: None), "m", tmp_path, depth=5)
    judgments = run.judgments
    assert run.judged_queries == 2 and run.skipped_queries == 0
    by_q: dict[str, dict[str, int]] = {}
    for j in judgments:
        by_q.setdefault(j.qid, {})[j.product_id] = j.grade
    assert by_q["q1"]["13"] == 2  # seed graded relevant
    assert set(by_q) == {"q1", "q2"}
    assert fake.calls == 4  # each query: one call + one follow-up for the skipped c1

    path = tmp_path / "qrels.jsonl"
    save_qrels(judgments, path)
    assert load_qrels(path) == by_q


def test_balanced_order_interleaves_buckets() -> None:
    from vio.eval.judge import balanced_order

    qs = [QueryRecord(qid=f"d{i}", bucket="descriptive", query="x") for i in range(6)]
    qs += [QueryRecord(qid=f"v{i}", bucket="vague", query="x") for i in range(2)]
    order = balanced_order(qs)
    assert {q.bucket for q in order[:2]} == {"descriptive", "vague"}  # any prefix is mixed
    assert sorted(q.qid for q in order) == sorted(q.qid for q in qs)
    assert balanced_order(qs) == order


def test_quota_mid_run_keeps_cached_queries(service: SearchService, tmp_path: Path) -> None:
    from vio.eval.judge import balanced_order
    from vio.llm.client import RateLimitedError

    queries = [
        QueryRecord(qid=f"q{i}", bucket="specific", query=t)
        for i, t in enumerate(["running shoes", "coffee maker", "yoga mat"])
    ]
    cache = tmp_path / "c.sqlite"
    # warm the cache for the query that will come last in balanced order
    last = balanced_order(queries)[-1]
    judge_all(
        [last],
        service,
        LLMClient(FakeJudge(), cache_path=cache, sleep=lambda s: None),
        "m",
        tmp_path,
        depth=3,
    )

    class QuotaGone:
        def __call__(self, *args: object) -> ChatResult:
            raise RateLimitedError(3600.0, "tokens per day (TPD)")

    run = judge_all(
        queries,
        service,
        LLMClient(QuotaGone(), cache_path=cache, sleep=lambda s: None),
        "m",
        tmp_path,
        depth=3,
    )
    assert run.judged_queries == 1 and run.skipped_queries == 2
    assert {j.qid for j in run.judgments} == {last.qid}
    assert run.quota_message and "TPD" in run.quota_message

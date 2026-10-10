from pathlib import Path

import pytest

from vio.config import Settings
from vio.embeddings.fake import fake_encoders
from vio.eval.queries import QueryRecord
from vio.eval.retrieval import ORACLE, run, score, summarize, write_report
from vio.models import Filters
from vio.search.pipeline import SearchService
from vio.search.rerank import FakeReranker
from vio.store.qdrant import ProductStore


@pytest.fixture
def service(memory_store: ProductStore) -> SearchService:
    return SearchService(
        memory_store, fake_encoders(), FakeReranker(), Settings(_env_file=None, rerank_top_n=10)
    )


QUERIES = [
    QueryRecord(qid="q1", bucket="specific", query="coffee maker", seed_product_id="17"),
    QueryRecord(qid="q2", bucket="descriptive", query="noise cancelling headphones"),
    QueryRecord(qid="q3", bucket="constrained", query="headphones", filters=Filters(price_max=60)),
    QueryRecord(qid="q4", bucket="vague", query="nothing judged relevant"),
]
QRELS = {
    "q1": {"16": 2, "17": 2, "18": 2},
    "q2": {"3": 2, "4": 2, "5": 1},
    "q3": {"4": 2, "5": 2, "3": 1},
    "q4": {"0": 0},
}


def test_score_perfect_ranking() -> None:
    s = score(["a", "b"], {"a": 2, "b": 2})
    assert s["ndcg@10"] == pytest.approx(1.0) and s["recall@10"] == 1.0 and s["mrr@10"] == 1.0


def test_run_scores_variants_and_oracle(service: SearchService, tmp_path: Path) -> None:
    results = run(QUERIES, QRELS, service, ["bm25", "hybrid_rerank"], tmp_path)
    assert {r.qid for r in results} == {"q1", "q2", "q3"}  # q4 has no relevant product
    assert {r.variant for r in results} == {"bm25", "hybrid_rerank", ORACLE}
    oracle = next(r for r in results if r.variant == ORACLE)
    plain = next(r for r in results if r.variant == "hybrid_rerank" and r.qid == "q3")
    assert oracle.metrics["ndcg@10"] >= plain.metrics["ndcg@10"]  # budget filter can only help here

    summaries = {s.variant: s for s in summarize(results)}
    assert summaries["bm25"].n == 3 and not summaries["bm25"].p_vs_baseline
    assert set(summaries["hybrid_rerank"].p_vs_baseline) == {
        "ndcg@10",
        "recall@10",
        "recall@50",
        "mrr@10",
    }
    lo, hi = summaries["hybrid_rerank"].ci95["ndcg@10"]
    assert lo <= summaries["hybrid_rerank"].means["ndcg@10"] <= hi

    md = write_report(results, QUERIES, QRELS, tmp_path, {"sha": "test", "queries": "q.jsonl"})
    text = md.read_text(encoding="utf-8")
    assert "| `hybrid_rerank` |" in text and "### constrained" in text
    assert md.with_suffix(".json").exists()


def test_budget_queries_count_only_exact_matches() -> None:
    from vio.eval.retrieval import min_grade_for

    qrels = {"in_budget": 2, "over_budget": 1}
    assert score(["in_budget"], qrels, min_grade_for("constrained"))["recall@10"] == 1.0
    assert score(["in_budget"], qrels, min_grade_for("descriptive"))["recall@10"] == 0.5

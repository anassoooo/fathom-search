import math

import pytest

from vio.eval.metrics import (
    bootstrap_ci,
    mrr_at_k,
    ndcg_at_k,
    paired_bootstrap_p,
    percentile,
    precision_at_k,
    precision_recall_f1,
    recall_at_k,
)

QRELS = {"a": 2, "b": 1, "c": 0, "d": 2}


def test_ndcg_hand_computed() -> None:
    # ranked a(2), c(0), b(1): DCG = 3/1 + 0 + 1/log2(4) = 3.5
    # ideal 2,2,1: IDCG = 3 + 3/log2(3) + 1/2
    ideal = 3 + 3 / math.log2(3) + 0.5
    assert ndcg_at_k(["a", "c", "b"], QRELS, k=3) == pytest.approx(3.5 / ideal)


def test_ndcg_perfect_and_empty() -> None:
    assert ndcg_at_k(["a", "d", "b"], QRELS, k=3) == pytest.approx(1.0)
    assert ndcg_at_k(["x"], {}, k=10) == 0.0
    assert ndcg_at_k(["c", "x"], QRELS, k=2) == 0.0


def test_recall_precision_mrr() -> None:
    ranked = ["c", "b", "x", "a"]
    assert recall_at_k(ranked, QRELS, k=2) == pytest.approx(1 / 3)
    assert recall_at_k(ranked, QRELS, k=10, min_grade=2) == pytest.approx(1 / 2)
    assert precision_at_k(ranked, QRELS, k=4) == pytest.approx(2 / 4)
    assert mrr_at_k(ranked, QRELS) == pytest.approx(1 / 2)
    assert mrr_at_k(["x", "y"], QRELS) == 0.0


def test_percentile() -> None:
    assert percentile([1, 2, 3, 4], 50) == pytest.approx(2.5)
    assert percentile([10.0], 95) == 10.0
    assert math.isnan(percentile([], 50))


def test_precision_recall_f1() -> None:
    p, r, f1 = precision_recall_f1([True, True, False, False], [True, False, True, False])
    assert (p, r, f1) == (0.5, 0.5, 0.5)


def test_bootstrap_ci_brackets_mean() -> None:
    xs = [0.1, 0.4, 0.5, 0.9, 0.3, 0.7] * 10
    lo, hi = bootstrap_ci(xs, n_boot=500)
    assert lo < sum(xs) / len(xs) < hi


def test_paired_bootstrap_detects_real_improvement() -> None:
    a = [0.2, 0.3, 0.4, 0.5] * 25
    better = [x + 0.1 for x in a]
    assert paired_bootstrap_p(a, better) < 0.01
    assert paired_bootstrap_p(a, a) > 0.4

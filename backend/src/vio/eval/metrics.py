"""Ranking and classification metrics. Pure Python, no dependencies.

Relevance is graded: 0 = irrelevant, 1 = partially relevant, 2 = exact match.
Binary metrics (recall, MRR, precision) count grade >= `min_grade` as relevant.
"""

import math
from collections.abc import Mapping, Sequence

Qrels = Mapping[str, int]  # product_id -> relevance grade for one query


def dcg_at_k(grades: Sequence[int], k: int) -> float:
    """Exponential-gain DCG: sum (2^g - 1) / log2(rank + 1)."""
    return float(sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(grades[:k])))


def ndcg_at_k(ranked: Sequence[str], qrels: Qrels, k: int = 10) -> float:
    ideal = dcg_at_k(sorted(qrels.values(), reverse=True), k)
    if ideal == 0:
        return 0.0
    return dcg_at_k([qrels.get(pid, 0) for pid in ranked], k) / ideal


def recall_at_k(ranked: Sequence[str], qrels: Qrels, k: int = 10, min_grade: int = 1) -> float:
    relevant = {pid for pid, g in qrels.items() if g >= min_grade}
    if not relevant:
        return 0.0
    return len(relevant & set(ranked[:k])) / len(relevant)


def precision_at_k(ranked: Sequence[str], qrels: Qrels, k: int = 10, min_grade: int = 1) -> float:
    if k == 0:
        return 0.0
    return sum(qrels.get(pid, 0) >= min_grade for pid in ranked[:k]) / k


def mrr_at_k(ranked: Sequence[str], qrels: Qrels, k: int = 10, min_grade: int = 1) -> float:
    for i, pid in enumerate(ranked[:k]):
        if qrels.get(pid, 0) >= min_grade:
            return 1.0 / (i + 1)
    return 0.0


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]."""
    if not values:
        return float("nan")
    xs = sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def precision_recall_f1(
    predicted: Sequence[bool], actual: Sequence[bool]
) -> tuple[float, float, float]:
    tp = sum(p and a for p, a in zip(predicted, actual, strict=True))
    fp = sum(p and not a for p, a in zip(predicted, actual, strict=True))
    fn = sum(a and not p for p, a in zip(predicted, actual, strict=True))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f1


def bootstrap_ci(
    per_query: Sequence[float], n_boot: int = 1000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean over queries."""
    import random

    if not per_query:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(per_query)
    means = sorted(sum(rng.choices(per_query, k=n)) / n for _ in range(n_boot))
    return means[int(alpha / 2 * n_boot)], means[int((1 - alpha / 2) * n_boot) - 1]


def paired_bootstrap_p(
    a: Sequence[float], b: Sequence[float], n_boot: int = 2000, seed: int = 0
) -> float:
    """One-sided p-value that mean(b) > mean(a) is due to chance (paired by query)."""
    import random

    diffs = [y - x for x, y in zip(a, b, strict=True)]
    if not diffs:
        return float("nan")
    rng = random.Random(seed)
    n = len(diffs)
    observed = sum(diffs) / n
    centered = [d - observed for d in diffs]
    hits = sum(sum(rng.choices(centered, k=n)) / n >= observed for _ in range(n_boot))
    return (hits + 1) / (n_boot + 1)

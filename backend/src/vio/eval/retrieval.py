"""Run every retrieval variant over the judged query set and report (T034).

For each (variant, query): NDCG@10, Recall@10, Recall@50, MRR@10, and latency. Aggregates
come with 95% bootstrap CIs; each variant is compared with the BM25 baseline by a paired
bootstrap test over the same queries. Unjudged results count as irrelevant, the standard
pooled-evaluation assumption: all variants were pooled, so this is fair between them.

An extra "oracle filters" run re-scores constrained queries with their ground-truth budget
applied: an upper bound on what LLM query understanding (M3) could add.
"""

import json
import subprocess
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from vio.eval.judge import query_request
from vio.eval.metrics import (
    bootstrap_ci,
    mrr_at_k,
    ndcg_at_k,
    paired_bootstrap_p,
    percentile,
    recall_at_k,
)
from vio.eval.queries import QueryRecord
from vio.models import Variant
from vio.search.pipeline import SearchService

METRICS = ("ndcg@10", "recall@10", "recall@50", "mrr@10")
ORACLE = "hybrid_rerank+oracle_filters"


@dataclass
class QueryResult:
    qid: str
    bucket: str
    variant: str
    metrics: dict[str, float]
    latency_ms: float


@dataclass
class VariantSummary:
    variant: str
    n: int
    means: dict[str, float]
    ci95: dict[str, tuple[float, float]]
    p_vs_baseline: dict[str, float] = field(default_factory=dict)
    latency_p50: float = 0.0
    latency_p95: float = 0.0


def min_grade_for(bucket: str) -> int:
    """Budget queries count only exact, within-budget matches (grade 2) as relevant for
    recall/MRR: the rubric lets over-budget items earn a 1, and counting those would
    penalize exactly the variants that respect the budget. NDCG stays graded."""
    return 2 if bucket == "constrained" else 1


def score(ranked: Sequence[str], qrels: dict[str, int], min_grade: int = 1) -> dict[str, float]:
    return {
        "ndcg@10": ndcg_at_k(ranked, qrels, 10),
        "recall@10": recall_at_k(ranked, qrels, 10, min_grade),
        "recall@50": recall_at_k(ranked, qrels, 50, min_grade),
        "mrr@10": mrr_at_k(ranked, qrels, 10, min_grade),
    }


def run(
    queries: Sequence[QueryRecord],
    qrels: dict[str, dict[str, int]],
    service: SearchService,
    variants: Sequence[Variant],
    eval_dir: Path,
    on_step: Callable[[], None] | None = None,
) -> list[QueryResult]:
    results: list[QueryResult] = []
    judged = [q for q in queries if q.qid in qrels and any(g > 0 for g in qrels[q.qid].values())]
    for q in judged:
        image = q.bucket == "image"
        for v in variants:
            if image and v != variants[0]:
                continue  # image search is variant-independent; score it once
            resp = service.search(query_request(q, eval_dir, 50, v))
            ranked = [h.product.product_id for h in resp.results]
            name = "image" if image else v
            results.append(
                QueryResult(
                    q.qid,
                    q.bucket,
                    name,
                    score(ranked, qrels[q.qid], min_grade_for(q.bucket)),
                    resp.timings_ms["total_ms"],
                )
            )
            if on_step:
                on_step()
        if q.bucket == "constrained" and q.filters.price_max is not None:
            req = query_request(q, eval_dir, 50, "hybrid_rerank")
            req = req.model_copy(update={"filters": q.filters})
            resp = service.search(req)
            ranked = [h.product.product_id for h in resp.results]
            results.append(
                QueryResult(
                    q.qid,
                    q.bucket,
                    ORACLE,
                    score(ranked, qrels[q.qid], min_grade_for(q.bucket)),
                    resp.timings_ms["total_ms"],
                )
            )
    return results


def summarize(
    results: Sequence[QueryResult], baseline: str = "bm25", buckets: set[str] | None = None
) -> list[VariantSummary]:
    rows = [r for r in results if buckets is None or r.bucket in buckets]
    by_variant: dict[str, list[QueryResult]] = defaultdict(list)
    for r in rows:
        by_variant[r.variant].append(r)
    base = {r.qid: r for r in by_variant.get(baseline, [])}
    out = []
    for v, rs in by_variant.items():
        means = {m: sum(r.metrics[m] for r in rs) / len(rs) for m in METRICS}
        ci = {m: bootstrap_ci([r.metrics[m] for r in rs]) for m in METRICS}
        p: dict[str, float] = {}
        paired = [(base[r.qid], r) for r in rs if r.qid in base]
        if v != baseline and paired:
            for m in METRICS:
                p[m] = paired_bootstrap_p(
                    [b.metrics[m] for b, _ in paired], [r.metrics[m] for _, r in paired]
                )
        lat = [r.latency_ms for r in rs]
        out.append(
            VariantSummary(v, len(rs), means, ci, p, percentile(lat, 50), percentile(lat, 95))
        )
    return out


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _table(summaries: Sequence[VariantSummary], order: Sequence[str]) -> str:
    rank = {v: i for i, v in enumerate(order)}
    lines = [
        "| Variant | n | NDCG@10 | Recall@10 | Recall@50 | MRR@10 | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in sorted(summaries, key=lambda s: rank.get(s.variant, 99)):
        cells = []
        for m in METRICS:
            lo, hi = s.ci95[m]
            sig = ""
            if m in s.p_vs_baseline:
                sig = " ▲" if s.p_vs_baseline[m] < 0.05 else ""
            cells.append(f"{s.means[m]:.3f} [{lo:.3f}, {hi:.3f}]{sig}")
        lines.append(
            f"| `{s.variant}` | {s.n} | "
            + " | ".join(cells)
            + f" | {s.latency_p50:.0f} | {s.latency_p95:.0f} |"
        )
    return "\n".join(lines)


def write_report(
    results: Sequence[QueryResult],
    queries: Sequence[QueryRecord],
    qrels: dict[str, dict[str, int]],
    out_dir: Path,
    meta: dict[str, str],
) -> Path:
    order = ["bm25", "dense", "hybrid", "hybrid_rerank", ORACLE, "image"]
    text_buckets = {"specific", "descriptive", "constrained", "noisy", "vague"}
    overall = summarize(results, buckets=text_buckets)
    bucket_names = sorted({r.bucket for r in results})
    n_judged = sum(len(v) for v in qrels.values())
    overlap: dict[str, list[float]] = defaultdict(list)
    for q in queries:
        if q.title_overlap is not None:
            overlap[q.bucket].append(q.title_overlap)

    sections = [
        f"# Retrieval evaluation, {date.today().isoformat()} ({meta.get('sha', _git_sha())})",
        "",
        f"- **Queries:** {len({r.qid for r in results})} judged queries "
        f"from `{meta.get('queries')}`",
        f"- **Judgments:** {n_judged:,} graded (query, product) pairs; "
        f"judge `{meta.get('judge_model')}`",
        f"- **Collection:** `{meta.get('collection')}` ({meta.get('n_points')} products)",
        "- Values are means with 95% bootstrap CIs. "
        "▲ = better than `bm25` (paired bootstrap, p < 0.05).",
        "- Unjudged results count as irrelevant (pooled evaluation; every variant was pooled).",
        "",
        "## Text queries (all buckets except image)",
        "",
        _table(overall, order),
        "",
        "## By query type",
        "",
    ]
    for b in bucket_names:
        if b == "image":
            continue
        avg = sum(overlap[b]) / len(overlap[b]) if overlap[b] else float("nan")
        sections += [
            f"### {b}  (mean title-word overlap {avg:.2f})",
            "",
            _table(summarize(results, buckets={b}), order),
            "",
        ]
    if "image" in bucket_names:
        sections += [
            "## Image queries (augmented product photos)",
            "",
            _table(summarize(results, buckets={"image"}), order),
            "",
        ]

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date.today().isoformat()}-{meta.get('sha', _git_sha())}"
    md = out_dir / f"{stem}.md"
    md.write_text("\n".join(sections), encoding="utf-8")
    (out_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                "meta": meta,
                "summary": [asdict(s) for s in overall],
                "results": [asdict(r) for r in results],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return md

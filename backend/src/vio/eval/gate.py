"""Fit and evaluate the relevance gate (ADR-0008).

1. Replay every judged text query through `hybrid_rerank` (gate off) and keep the reranked
   top-N: cross-encoder scores and pre-rerank (fused) positions.
2. Fit a logistic regression on `vio.search.gate.features` with judge grades as labels
   (grade >= 1 = relevant; unjudged pairs are left out of training).
3. Report, with out-of-fold probabilities (5 folds grouped by query):
   - separation (ROC-AUC, Brier, calibration error);
   - what users see: precision and recall of the shown set vs today's fixed top-12, with
     paired bootstrap CIs (unjudged shown products count as irrelevant: conservative);
   - abstention: on no-answer queries (things the catalog cannot sell), how often the
     best-P floor says "no close match", against how often it wrongly says so on
     answerable queries.

No-answer queries are evaluation only. Training the item gate on them was tried and
cost recall on real queries (see ADR-0008).
"""

import json
import random
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from vio.eval.queries import QueryRecord
from vio.models import SearchRequest
from vio.search.gate import FEATURES, RelevanceGate, features
from vio.search.pipeline import SearchService

FIXED_K = 12  # what the web app showed before the gate
FLOORS = (0.6, 0.65, 0.7, 0.75, 0.8)
TAUS = (0.4, 0.5, 0.6, 0.7)


@dataclass
class Candidate:
    pid: str
    ce: float
    fused_rank: int
    grade: int | None  # None = unjudged


@dataclass
class QueryCandidates:
    qid: str
    bucket: str  # QueryRecord bucket, or "noanswer"
    query: str
    candidates: list[Candidate]  # reranked order


def collect(
    queries: Sequence[tuple[str, str, str]],
    qrels: dict[str, dict[str, int]],
    service: SearchService,
    top_n: int,
    on_step: Callable[[], None] | None = None,
) -> list[QueryCandidates]:
    """`queries` = (qid, bucket, text). Raises if the reranker degrades: its scores are the
    features, and a fused-order fallback would silently poison the training data."""
    out = []
    for qid, bucket, text in queries:
        res = service.search(SearchRequest(query=text, k=top_n, variant="hybrid_rerank"))
        if "reranker" in res.degraded:
            raise RuntimeError(f"reranker degraded on {qid}; raise RERANK_TIMEOUT_S and re-run")
        judged = qrels.get(qid, {})
        cands = [
            Candidate(
                h.product.product_id,
                h.score,
                h.fused_rank or h.rank,
                judged.get(h.product.product_id),
            )
            for h in res.results
        ]
        out.append(QueryCandidates(qid, bucket, text, cands))
        if on_step:
            on_step()
    return out


def text_queries(queries: Sequence[QueryRecord]) -> list[tuple[str, str, str]]:
    return [(q.qid, q.bucket, q.query) for q in queries if q.bucket != "image" and q.query]


def load_noanswer(path: Path) -> list[tuple[str, str, str]]:
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    return [(r["qid"], "noanswer", r["query"]) for r in rows]


def _rows(qs: Sequence[QueryCandidates]) -> list[list[float]]:
    return [
        row
        for q in qs
        for row in features([c.ce for c in q.candidates], [c.fused_rank for c in q.candidates])
    ]


# --- fitting -----------------------------------------------------------------------------------


@dataclass
class Fit:
    gate: RelevanceGate
    oof: dict[tuple[str, str], float]  # (qid, pid) -> out-of-fold P(relevant), answerable only
    auc: float
    auc_raw_ce: float
    brier: float
    ece: float
    weights: dict[str, float]


def fit(
    answerable: Sequence[QueryCandidates],
    tau: float,
    floor: float,
    rerank_model: str,
    top_n: int,
    version: str,
) -> Fit:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    keys, groups, labels = [], [], []
    for q in answerable:
        for c in q.candidates:
            keys.append((q.qid, c.pid))
            groups.append(q.qid)
            labels.append(-1 if c.grade is None else int(c.grade >= 1))
    feats_all = np.array(_rows(answerable))
    y_all = np.array(labels)
    judged = y_all >= 0
    feats, y, g = feats_all[judged], y_all[judged], np.array(groups)[judged]

    def model() -> Any:
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))

    # Out-of-fold P for every candidate (judged or not), folds grouped by query.
    p_all = np.zeros(len(y_all))
    all_groups = np.array(groups)
    for tr, te in GroupKFold(n_splits=5).split(feats, y, g):
        m = model().fit(feats[tr], y[tr])
        held_out = np.isin(all_groups, np.unique(g[te]))
        p_all[held_out] = m.predict_proba(feats_all[held_out])[:, 1]
    p = p_all[judged]

    final = model().fit(feats, y)
    scaler, lr = final[0], final[-1]
    gate = RelevanceGate(
        version=version,
        mean=[float(v) for v in scaler.mean_],
        scale=[float(v) for v in scaler.scale_],
        coef=[float(v) for v in lr.coef_[0]],
        intercept=float(lr.intercept_[0]),
        tau=tau,
        floor=floor,
        rerank_model=rerank_model,
        rerank_top_n=top_n,
    )
    bins = np.clip((p * 10).astype(int), 0, 9)
    ece = sum(
        abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean()
        for b in range(10)
        if (bins == b).any()
    )
    return Fit(
        gate=gate,
        oof={k: float(v) for k, v in zip(keys, p_all, strict=True)},
        auc=float(roc_auc_score(y, p)),
        auc_raw_ce=float(roc_auc_score(y, feats[:, FEATURES.index("ce")])),
        brier=float(np.mean((p - y) ** 2)),
        ece=float(ece),
        weights=dict(zip(FEATURES, (float(c) for c in lr.coef_[0]), strict=True)),
    )


# --- what users would see ------------------------------------------------------------------


Shown = Callable[[list[float]], list[bool]]  # per-candidate P -> shown?


def fixed(_: list[float]) -> list[bool]:
    return [i < FIXED_K for i in range(len(_))]


def gated(tau: float, floor: float = 0.0) -> Shown:
    def shown(p: list[float]) -> list[bool]:
        if not p or max(p) < floor:
            return [False] * len(p)
        return [x >= tau for x in p]

    return shown


def _counts(q: QueryCandidates, p: list[float], policy: Shown) -> tuple[int, int, int]:
    keep = policy(p)
    rel = [int((c.grade or 0) >= 1) for c in q.candidates]
    return sum(r for r, k in zip(rel, keep, strict=True) if k), sum(keep), sum(rel)


def precision_recall(
    qs: Sequence[QueryCandidates], probs: dict[str, list[float]], policy: Shown
) -> tuple[float, float, float]:
    tp = shown = rel = 0
    for q in qs:
        a, b, c = _counts(q, probs[q.qid], policy)
        tp, shown, rel = tp + a, shown + b, rel + c
    return tp / max(shown, 1), tp / max(rel, 1), shown / max(len(qs), 1)


def paired_ci(
    qs: Sequence[QueryCandidates],
    probs: dict[str, list[float]],
    a: Shown,
    b: Shown,
    n: int = 2000,
    seed: int = 0,
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """95% bootstrap CIs (over queries) of b - a in precision and recall, and the share of
    resamples where b wins on both."""
    rng = random.Random(seed)
    dp, dr, both = [], [], 0
    for _ in range(n):
        sample = [rng.choice(qs) for _ in qs]
        pa, ra, _ = precision_recall(sample, probs, a)
        pb, rb, _ = precision_recall(sample, probs, b)
        dp.append(pb - pa)
        dr.append(rb - ra)
        both += pb > pa and rb > ra
    dp.sort()
    dr.sort()
    lo, hi = int(0.025 * n), int(0.975 * n) - 1
    return (dp[lo], dp[hi]), (dr[lo], dr[hi]), both / n


# --- report --------------------------------------------------------------------------------------


def write_report(
    answerable: Sequence[QueryCandidates],
    noanswer: Sequence[QueryCandidates],
    result: Fit,
    out_dir: Path,
    meta: dict[str, str],
) -> Path:
    gate = result.gate
    probs = {q.qid: [result.oof[(q.qid, c.pid)] for c in q.candidates] for q in answerable}
    probs |= {
        q.qid: gate.predict([c.ce for c in q.candidates], [c.fused_rank for c in q.candidates])
        for q in noanswer
    }
    n_pairs = sum(len(q.candidates) for q in answerable)
    n_judged = sum(c.grade is not None for q in answerable for c in q.candidates)
    chosen = gated(gate.tau)
    pf, rf, sf = precision_recall(answerable, probs, fixed)
    pg, rg, _ = precision_recall(answerable, probs, chosen)
    (plo, phi), (rlo, rhi), both = paired_ci(answerable, probs, fixed, chosen)

    lines = [
        f"# Relevance gate, {date.today().isoformat()} ({meta.get('sha')})",
        "",
        f"- **Gate:** `{gate.version}`: logistic regression on {len(FEATURES)} features of the "
        f"reranked top-{gate.rerank_top_n} (`{gate.rerank_model}`), variant `hybrid_rerank`",
        f"- **Answerable queries:** {len(answerable)} text queries from `{meta.get('queries')}`; "
        f"{n_pairs:,} candidates, {n_judged:,} judged ({n_judged / n_pairs:.0%}); "
        f"judge `{meta.get('judge_model')}`",
        f"- **No-answer queries:** {len(noanswer)} from `{meta.get('noanswer')}` "
        "(hand-written: services, bookings, live animals, perishables, gibberish, ...)",
        "- All probabilities on answerable queries are out-of-fold (5 folds grouped by query).",
        "- Unjudged candidates count as irrelevant when shown (conservative).",
        "",
        "## Separation",
        "",
        "| score | global ROC-AUC |",
        "|---|---|",
        f"| raw cross-encoder score | {result.auc_raw_ce:.3f} |",
        f"| gate P(relevant) | {result.auc:.3f} |",
        "",
        f"Gate calibration: Brier {result.brier:.3f}, ECE {result.ece:.3f}.",
        "",
        "Weights (standardized features; + = more likely relevant): "
        + ", ".join(
            f"`{f}` {w:+.2f}" for f, w in sorted(result.weights.items(), key=lambda t: -abs(t[1]))
        ),
        "",
        "## What users see (answerable queries)",
        "",
        "| policy | precision | recall (of relevant in top-30) | avg shown |",
        "|---|---|---|---|",
        f"| fixed top-{FIXED_K} (before the gate) | {pf:.3f} | {rf:.3f} | {sf:.1f} |",
    ]
    for tau in TAUS:
        p_, r_, s_ = precision_recall(answerable, probs, gated(tau))
        mark = " **(chosen)**" if tau == gate.tau else ""
        lines.append(f"| P ≥ {tau}{mark} | {p_:.3f} | {r_:.3f} | {s_:.1f} |")
    lines += [
        "",
        f"Chosen gate vs fixed top-{FIXED_K} (paired bootstrap over queries, 95% CI): "
        f"precision {pg - pf:+.3f} [{plo:+.3f}, {phi:+.3f}], "
        f"recall {rg - rf:+.3f} [{rlo:+.3f}, {rhi:+.3f}]; "
        f"the gate wins on both in {both:.1%} of resamples.",
        "",
        "### By query type (precision / recall)",
        "",
        f"| bucket | n | fixed top-{FIXED_K} | gate P ≥ {gate.tau} |",
        "|---|---|---|---|",
    ]
    for b in sorted({q.bucket for q in answerable}):
        sub = [q for q in answerable if q.bucket == b]
        p1, r1, _ = precision_recall(sub, probs, fixed)
        p2, r2, _ = precision_recall(sub, probs, chosen)
        lines.append(f"| {b} | {len(sub)} | {p1:.3f} / {r1:.3f} | {p2:.3f} / {r2:.3f} |")

    best = {q.qid: max(probs[q.qid], default=0.0) for q in [*answerable, *noanswer]}
    has_rel = [q for q in answerable if any((c.grade or 0) >= 1 for c in q.candidates)]
    lines += [
        "",
        '## Abstention: "no close match" when the best P is below a floor',
        "",
        "Below the floor the app still shows the nearest products, under a "
        '"no close matches" heading, so a wrong flag costs a label, not the results.',
        "",
        "| floor | no-answer queries flagged | answerable queries wrongly flagged "
        "| matches precision | matches recall |",
        "|---|---|---|---|---|",
    ]
    for floor in FLOORS:
        p_, r_, _ = precision_recall(answerable, probs, gated(gate.tau, floor))
        na = sum(best[q.qid] < floor for q in noanswer) / max(len(noanswer), 1)
        wrong = sum(best[q.qid] < floor for q in has_rel) / max(len(has_rel), 1)
        mark = " **(chosen)**" if floor == gate.floor else ""
        lines.append(f"| {floor}{mark} | {na:.0%} | {wrong:.0%} | {p_:.3f} | {r_:.3f} |")
    lines += [
        "",
        f"Without a floor, no-answer queries show {sum(sum(x >= gate.tau for x in probs[q.qid]) for q in noanswer) / max(len(noanswer), 1):.1f} "  # noqa: E501
        f"products on average (fixed top-{FIXED_K} showed {FIXED_K}).",
        "",
        f"### No-answer queries that pass the floor ({gate.floor})",
        "",
    ]
    passing = sorted((q for q in noanswer if best[q.qid] >= gate.floor), key=lambda q: -best[q.qid])
    lines += [f"- {best[q.qid]:.2f}  {q.query}" for q in passing] or ["- none"]

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date.today().isoformat()}-{meta.get('sha')}-gate"
    md = out_dir / f"{stem}.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                "meta": meta,
                "gate": asdict(gate),
                "separation": {
                    "auc": result.auc,
                    "auc_raw_ce": result.auc_raw_ce,
                    "brier": result.brier,
                    "ece": result.ece,
                },
                "queries": [asdict(q) for q in [*answerable, *noanswer]],
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return md

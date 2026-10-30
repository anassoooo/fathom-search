"""Relevance gate: which reranked candidates are good enough to show (ADR-0008).

The cross-encoder orders candidates well within a query but its raw score does not mean
the same thing across queries. The gate is a logistic regression on query-relative
features of the reranked list (score minus the query's best, rank, spread, ...), trained
by `vio eval gate` on judged pairs. It gives each candidate P(relevant):

- P >= tau          -> "match"
- otherwise         -> "related" (shown behind "Show more")
- best P < floor    -> the query has no close match; everything is "related"

`features` is the single definition used for both training and serving, so the two
cannot drift apart. Weights live in a JSON file; serving needs no scikit-learn.
"""

import json
import logging
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

FEATURES = (
    "ce",  # cross-encoder score
    "ce_rank",  # 1-based position after reranking
    "ce_gap",  # score minus the query's best score
    "ce_z",  # score standardized within the query
    "ce_max",  # the query's best score
    "ce_top_margin",  # best minus second-best score
    "ce_std",  # spread of the query's scores
    "log_fused_rank",  # log(1 + position before reranking, i.e. hybrid RRF order)
)
DEFAULT_PATH = Path(__file__).with_name("gate_v1.json")

Answer = Literal["matches", "no_close_match"]
Tier = Literal["match", "related"]


def features(scores: Sequence[float], fused_ranks: Sequence[int]) -> list[list[float]]:
    """One feature row per candidate, in reranked order (`scores` sorted descending)."""
    n = len(scores)
    if n == 0:
        return []
    top = max(scores)
    second = sorted(scores, reverse=True)[1] if n > 1 else top
    mean = sum(scores) / n
    std = math.sqrt(sum((s - mean) ** 2 for s in scores) / n) + 1e-6
    return [
        [s, float(i), s - top, (s - mean) / std, top, top - second, std, math.log1p(fr)]
        for i, (s, fr) in enumerate(zip(scores, fused_ranks, strict=True), start=1)
    ]


@dataclass(frozen=True)
class GateDecision:
    answer: Answer
    p: list[float]
    tiers: list[Tier]


@dataclass(frozen=True)
class RelevanceGate:
    version: str
    mean: list[float]
    scale: list[float]
    coef: list[float]
    intercept: float
    tau: float  # P(relevant) needed to be a match
    floor: float  # below this best P, the query has no close match
    # The features only mean something for the reranker and list size they were fit on.
    rerank_model: str
    rerank_top_n: int

    def predict(self, scores: Sequence[float], fused_ranks: Sequence[int]) -> list[float]:
        out = []
        for row in features(scores, fused_ranks):
            z = self.intercept + sum(
                c * (x - m) / s
                for c, x, m, s in zip(self.coef, row, self.mean, self.scale, strict=True)
            )
            out.append(1.0 / (1.0 + math.exp(-z)))
        return out

    def decide(self, scores: Sequence[float], fused_ranks: Sequence[int]) -> GateDecision:
        p = self.predict(scores, fused_ranks)
        if not p or max(p) < self.floor:
            return GateDecision("no_close_match", p, ["related"] * len(p))
        return GateDecision("matches", p, ["match" if x >= self.tau else "related" for x in p])

    def fits(self, rerank_model: str, rerank_top_n: int) -> bool:
        return self.rerank_model == rerank_model and self.rerank_top_n == rerank_top_n

    def save(self, path: Path) -> None:
        body = {"features": list(FEATURES), **asdict(self)}
        path.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "RelevanceGate":
        body = json.loads(path.read_text("utf-8"))
        if tuple(body.pop("features")) != FEATURES:
            raise ValueError(f"{path.name} was fit on different features; re-run `vio eval gate`")
        return cls(**body)


def load_for(
    rerank_model: str, rerank_top_n: int, path: Path = DEFAULT_PATH
) -> RelevanceGate | None:
    """The packaged gate, or None (search still works, ungated) if it is missing or stale."""
    if not path.exists():
        log.warning("relevance gate %s not found; results are not gated", path.name)
        return None
    gate = RelevanceGate.load(path)
    if not gate.fits(rerank_model, rerank_top_n):
        log.warning(
            "relevance gate %s was fit for %s top-%d, not %s top-%d; results are not gated",
            gate.version,
            gate.rerank_model,
            gate.rerank_top_n,
            rerank_model,
            rerank_top_n,
        )
        return None
    return gate

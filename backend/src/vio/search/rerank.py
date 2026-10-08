"""Second-stage reranking with a cross-encoder, bounded by a timeout (Constitution Art. VI)."""

import logging
import re
from collections.abc import Sequence
from concurrent.futures import Executor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, replace
from typing import Protocol

from fastembed.rerank.cross_encoder import TextCrossEncoder

from vio.lazy import Lazy
from vio.search.retrieve import Candidate

log = logging.getLogger(__name__)


class Reranker(Protocol):
    def score(self, query: str, documents: Sequence[str]) -> list[float]: ...


class FastEmbedReranker:
    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self._model = Lazy(lambda: TextCrossEncoder(model_name, cache_dir=cache_dir))

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        return [float(s) for s in self._model.get().rerank(query, list(documents))]


class FakeReranker:
    """Scores by query-term overlap. Deterministic and instant, for tests."""

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        return [float(len(terms & set(re.findall(r"[a-z0-9]+", d.lower())))) for d in documents]


@dataclass(frozen=True)
class RerankOutcome:
    candidates: list[Candidate]
    degraded: bool = False


def rerank(
    reranker: Reranker,
    query: str,
    candidates: list[Candidate],
    *,
    top_n: int,
    timeout_s: float,
    executor: Executor,
) -> RerankOutcome:
    """Rerank the first `top_n` candidates; the tail keeps its fused order.

    On timeout or model error the fused order is returned unchanged with degraded=True.
    """
    head, tail = candidates[:top_n], candidates[top_n:]
    if len(head) < 2:
        return RerankOutcome(candidates)

    docs = [c.product.doc_text() for c in head]
    future = executor.submit(reranker.score, query, docs)
    try:
        scores = future.result(timeout=timeout_s)
    except FutureTimeout:
        log.warning("rerank timed out after %.2fs; using fused order", timeout_s)
        return RerankOutcome(candidates, degraded=True)
    except Exception:
        log.exception("rerank failed; using fused order")
        return RerankOutcome(candidates, degraded=True)

    order = sorted(range(len(head)), key=lambda i: scores[i], reverse=True)
    reranked = [replace(head[i], score=scores[i]) for i in order]
    return RerankOutcome(reranked + tail)

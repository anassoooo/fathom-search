import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor

import pytest

from vio.models import Product
from vio.search.rerank import FakeReranker, Reranker, rerank
from vio.search.retrieve import Candidate


@pytest.fixture
def pool() -> Iterator[ThreadPoolExecutor]:
    with ThreadPoolExecutor(2) as ex:
        yield ex


def _cands(products: list[Product], ids: list[int]) -> list[Candidate]:
    return [Candidate(products[i], score=1.0 / (r + 1)) for r, i in enumerate(ids)]


def test_reranks_head_and_keeps_tail(products: list[Product], pool: ThreadPoolExecutor) -> None:
    # fused order puts the skillet first; the query is about coffee makers
    cands = _cands(products, [19, 16, 17, 18, 0])
    out = rerank(FakeReranker(), "coffee maker", cands, top_n=4, timeout_s=1, executor=pool)
    ids = [c.product.product_id for c in out.candidates]
    assert not out.degraded
    assert ids[0] in {"17", "18"}  # both titles contain "coffee maker"
    assert ids[-1] == "0"  # outside top_n: untouched
    assert len(ids) == 5


class _Slow:
    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        time.sleep(0.5)
        return [0.0] * len(documents)


class _Broken:
    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        raise RuntimeError("model crashed")


@pytest.mark.parametrize("reranker", [_Slow(), _Broken()])
def test_timeout_or_error_falls_back_to_fused_order(
    products: list[Product], pool: ThreadPoolExecutor, reranker: Reranker
) -> None:
    cands = _cands(products, [19, 16, 17])
    out = rerank(reranker, "coffee", cands, top_n=3, timeout_s=0.05, executor=pool)
    assert out.degraded
    assert out.candidates == cands


def test_single_candidate_is_returned_as_is(
    products: list[Product], pool: ThreadPoolExecutor
) -> None:
    cands = _cands(products, [3])
    out = rerank(FakeReranker(), "x", cands, top_n=10, timeout_s=1, executor=pool)
    assert out.candidates == cands and not out.degraded

import base64
import math
from pathlib import Path
from typing import Any

import pytest

from tests.store_helpers import fake_image_bytes
from vio.config import Settings
from vio.embeddings.fake import fake_encoders
from vio.models import Product, SearchRequest
from vio.search.gate import FEATURES, RelevanceGate, features, load_for
from vio.search.pipeline import SearchService
from vio.search.rerank import FakeReranker
from vio.store.qdrant import ProductStore

SETTINGS = Settings(_env_file=None, rerank_top_n=10, rerank_timeout_s=0.5)


def gap_gate(tau: float = 0.45, floor: float = 0.4, **kw: object) -> RelevanceGate:
    """P = sigmoid(score - best score): the best candidate gets 0.5, the rest less."""
    coef = [1.0 if f == "ce_gap" else 0.0 for f in FEATURES]
    args: dict[str, Any] = dict(
        version="test",
        mean=[0.0] * len(FEATURES),
        scale=[1.0] * len(FEATURES),
        coef=coef,
        intercept=0.0,
        tau=tau,
        floor=floor,
        rerank_model=SETTINGS.rerank_model,
        rerank_top_n=SETTINGS.rerank_top_n,
    )
    return RelevanceGate(**(args | kw))


def test_features_are_relative_to_the_query() -> None:
    rows = features([3.0, 1.0, 0.0], [2, 1, 3])
    assert len(rows) == 3 and all(len(r) == len(FEATURES) for r in rows)
    col = {f: [r[i] for r in rows] for i, f in enumerate(FEATURES)}
    assert col["ce_gap"] == [0.0, -2.0, -3.0]
    assert col["ce_rank"] == [1.0, 2.0, 3.0]
    assert col["ce_max"] == [3.0] * 3
    assert col["ce_top_margin"] == [2.0] * 3
    assert col["log_fused_rank"] == [math.log1p(2), math.log1p(1), math.log1p(3)]
    assert features([], []) == []


def test_decide_labels_matches_and_abstains() -> None:
    gate = gap_gate()
    d = gate.decide([5.0, 4.9, 1.0], [1, 2, 3])
    assert d.answer == "matches"
    assert d.p[0] == pytest.approx(0.5)
    assert d.tiers == ["match", "match", "related"]

    shy = gap_gate(floor=0.6)  # the best P (0.5) is below the floor
    d = shy.decide([5.0, 4.9, 1.0], [1, 2, 3])
    assert d.answer == "no_close_match"
    assert d.tiers == ["related"] * 3


def test_round_trip_and_staleness(tmp_path: Path) -> None:
    gate = gap_gate()
    path = tmp_path / "gate.json"
    gate.save(path)
    assert RelevanceGate.load(path) == gate
    assert load_for(SETTINGS.rerank_model, SETTINGS.rerank_top_n, path) == gate
    assert load_for("another/reranker", SETTINGS.rerank_top_n, path) is None
    assert load_for(SETTINGS.rerank_model, 50, path) is None
    assert load_for(SETTINGS.rerank_model, 10, tmp_path / "missing.json") is None

    path.write_text(path.read_text().replace('"ce_gap"', '"something_else"'))
    with pytest.raises(ValueError, match="different features"):
        RelevanceGate.load(path)


def test_packaged_gate_loads() -> None:
    gate = RelevanceGate.load()
    assert len(gate.coef) == len(FEATURES)
    assert 0 < gate.floor <= 1 and 0 < gate.tau <= 1


@pytest.fixture
def service(memory_store: ProductStore) -> SearchService:
    return SearchService(memory_store, fake_encoders(), FakeReranker(), SETTINGS, gate=gap_gate())


def test_gated_search_lists_matches_first(service: SearchService) -> None:
    resp = service.search(SearchRequest(query="espresso coffee machine", k=10, gate=True))
    assert resp.answer == "matches"
    tiers = [h.tier for h in resp.results]
    assert tiers[0] == "match"
    assert tiers == sorted(tiers, key=lambda t: t != "match")  # matches, then related
    assert [h.rank for h in resp.results] == list(range(1, len(resp.results) + 1))
    assert all(h.p_relevant is not None and h.fused_rank is not None for h in resp.results)
    assert resp.results[0].product.subcategory == "Coffee Makers"


def test_gate_is_opt_in(service: SearchService) -> None:
    resp = service.search(SearchRequest(query="espresso coffee machine", k=5))
    assert resp.answer is None
    assert all(h.tier is None and h.p_relevant is None for h in resp.results)
    assert all(h.fused_rank is not None for h in resp.results)  # still reranked


def test_gate_skips_unreranked_searches(service: SearchService, products: list[Product]) -> None:
    resp = service.search(SearchRequest(query="espresso", k=5, variant="hybrid", gate=True))
    assert resp.answer is None and resp.results[0].fused_rank is None

    img = base64.b64encode(fake_image_bytes(products[12])).decode()
    resp = service.search(SearchRequest(image_b64=img, k=3, gate=True))
    assert resp.answer is None  # nothing textual to rerank, so nothing to gate

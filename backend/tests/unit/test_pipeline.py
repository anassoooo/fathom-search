import base64
import time
from collections.abc import Sequence

import pytest

from tests.store_helpers import fake_image_bytes
from vio.config import Settings
from vio.embeddings import Encoders
from vio.embeddings.fake import fake_encoders
from vio.models import Filters, Product, SearchRequest, Variant
from vio.search.pipeline import SearchInputError, SearchService, decode_image
from vio.search.rerank import FakeReranker
from vio.store.qdrant import ProductStore

SETTINGS = Settings(_env_file=None, rerank_top_n=10, rerank_timeout_s=0.5)


@pytest.fixture
def service(memory_store: ProductStore) -> SearchService:
    return SearchService(memory_store, fake_encoders(), FakeReranker(), SETTINGS)


@pytest.mark.parametrize("variant", ["bm25", "dense", "hybrid", "hybrid_rerank", "full"])
def test_every_variant_returns_ranked_results(service: SearchService, variant: Variant) -> None:
    resp = service.search(SearchRequest(query="espresso coffee machine", k=3, variant=variant))
    assert resp.variant == variant
    assert [h.rank for h in resp.results] == [1, 2, 3]
    assert resp.results[0].product.subcategory == "Coffee Makers"
    assert {"total_ms", "encode_ms", "retrieve_ms"} <= set(resp.timings_ms)
    assert ("rerank_ms" in resp.timings_ms) == (variant in {"hybrid_rerank", "full"})


def test_filters_are_sanitized_and_reported(service: SearchService) -> None:
    resp = service.search(
        SearchRequest(
            query="headphones", filters=Filters(category="electronics", subcategory="Jetpacks")
        )
    )
    assert resp.applied_filters.category == "Electronics"
    assert resp.applied_filters.subcategory is None
    assert resp.dropped_filters == ["unknown subcategory 'Jetpacks'"]
    assert {h.product.category for h in resp.results} == {"Electronics"}


def test_image_only_search(service: SearchService, products: list[Product]) -> None:
    img = base64.b64encode(fake_image_bytes(products[12])).decode()
    resp = service.search(SearchRequest(image_b64=f"data:image/jpeg;base64,{img}", k=1))
    assert resp.results[0].product.product_id == "12"
    assert "rerank_ms" not in resp.timings_ms  # nothing textual to rerank against


class _BrokenImage:
    dim = 32

    def embed_images(self, images: Sequence[bytes]) -> list[list[float]]:
        raise OSError("cannot identify image file")

    def embed_text(self, text: str) -> list[float]:
        return [1.0] + [0.0] * 31


def _broken_image_service(store: ProductStore) -> SearchService:
    enc = fake_encoders()
    return SearchService(
        store, Encoders(enc.dense, enc.sparse, _BrokenImage()), FakeReranker(), SETTINGS
    )


def test_bad_image_with_text_degrades_to_text(memory_store: ProductStore) -> None:
    svc = _broken_image_service(memory_store)
    resp = svc.search(
        SearchRequest(
            query="yoga mat", image_b64=base64.b64encode(b"junk").decode(), variant="dense"
        )
    )
    assert "image_encoder" in resp.degraded
    assert resp.results[0].product.product_id == "15"


def test_bad_image_alone_is_a_client_error(memory_store: ProductStore) -> None:
    svc = _broken_image_service(memory_store)
    with pytest.raises(SearchInputError):
        svc.search(SearchRequest(image_b64=base64.b64encode(b"junk").decode()))


def test_slow_reranker_degrades(memory_store: ProductStore) -> None:
    class Slow:
        def score(self, query: str, documents: Sequence[str]) -> list[float]:
            time.sleep(1)
            return [0.0] * len(documents)

    settings = Settings(_env_file=None, rerank_top_n=10, rerank_timeout_s=0.05)
    svc = SearchService(memory_store, fake_encoders(), Slow(), settings)
    resp = svc.search(SearchRequest(query="laptop", k=3))
    assert resp.degraded == ["reranker"]
    assert len(resp.results) == 3


@pytest.mark.parametrize("payload", ["!!!not-base64!!!", base64.b64encode(b"x" * 2048).decode()])
def test_decode_image_rejects_bad_or_large(payload: str) -> None:
    with pytest.raises(SearchInputError):
        decode_image(payload, max_bytes=1024)


def test_similar_and_browse(service: SearchService) -> None:
    hits = service.similar("17", Filters(), k=3)
    assert len(hits) == 3 and "17" not in [h.product.product_id for h in hits]
    page, cursor = service.browse(Filters(category="computers"), limit=10, cursor=None)
    assert len(page) == 6 and cursor is None

import pytest

from tests.store_helpers import fake_image_bytes
from vio.embeddings.fake import fake_encoders
from vio.models import Filters, Product
from vio.search.filters import to_qdrant
from vio.search.retrieve import QueryVectors, retrieve, similar
from vio.store.qdrant import ProductStore

ENC = fake_encoders()


def _vectors(
    text: str, *, dense: bool = True, sparse: bool = True, clip: bool = True
) -> QueryVectors:
    return QueryVectors(
        dense=ENC.dense.embed_query(text) if dense else None,
        sparse=ENC.sparse.embed_query(text) if sparse else None,
        clip_text=ENC.image.embed_text(text) if clip else None,
    )


def _ids(store: ProductStore, qv: QueryVectors, f: Filters | None = None, k: int = 5) -> list[str]:
    hits = retrieve(store.client, store.collection, qv, to_qdrant(f or Filters()), k)
    return [h.product.product_id for h in hits]


@pytest.mark.parametrize(
    "toggles",
    [
        {"dense": True, "sparse": False, "clip": False},
        {"dense": False, "sparse": True, "clip": False},
        {"dense": True, "sparse": True, "clip": False},
        {"dense": True, "sparse": True, "clip": True},
    ],
)
def test_each_source_combination_finds_headphones(
    memory_store: ProductStore, toggles: dict[str, bool]
) -> None:
    ids = _ids(memory_store, _vectors("noise cancelling headphones", **toggles), k=3)
    assert set(ids[:2]) <= {"3", "4", "5"}


def test_filters_apply_inside_retrieval(
    memory_store: ProductStore, products: list[Product]
) -> None:
    by_id = {p.product_id: p for p in products}
    ids = _ids(memory_store, _vectors("headphones"), Filters(price_max=60), k=10)
    assert ids, "filtered query should still return results"
    assert all((by_id[i].price or 0) <= 60 for i in ids)
    assert "3" not in ids  # the $329 Sony is excluded, not just ranked lower


def test_category_filter_returns_only_that_category(
    memory_store: ProductStore, products: list[Product]
) -> None:
    by_id = {p.product_id: p for p in products}
    ids = _ids(memory_store, _vectors("black"), Filters(category="Home & Kitchen"), k=10)
    assert ids and {by_id[i].category for i in ids} == {"Home & Kitchen"}


def test_image_query_finds_the_same_product(
    memory_store: ProductStore, products: list[Product]
) -> None:
    img = ENC.image.embed_images([fake_image_bytes(products[16])])[0]
    assert _ids(memory_store, QueryVectors(image=img), k=1) == ["16"]


def test_no_vectors_is_an_error(memory_store: ProductStore) -> None:
    with pytest.raises(ValueError):
        _ids(memory_store, QueryVectors())


def test_similar_excludes_itself_and_respects_filters(memory_store: ProductStore) -> None:
    hits = similar(memory_store.client, memory_store.collection, "17", None, 5)
    ids = [h.product.product_id for h in hits]
    assert "17" not in ids and len(ids) == 5
    assert set(ids[:2]) & {"16", "18"}  # other coffee makers

    cheap = similar(
        memory_store.client, memory_store.collection, "17", to_qdrant(Filters(price_max=20)), 5
    )
    assert all((h.product.price or 0) <= 20 for h in cheap)


def test_similar_works_without_image_vector(memory_store: ProductStore) -> None:
    hits = similar(memory_store.client, memory_store.collection, "11", None, 3)  # no image
    assert hits and "11" not in [h.product.product_id for h in hits]


def test_similar_unknown_product_is_empty(memory_store: ProductStore) -> None:
    assert similar(memory_store.client, memory_store.collection, "nope", None, 3) == []


def test_exclusion_keeps_existing_must_not() -> None:
    from qdrant_client import models as qm

    from vio.search.retrieve import _with_exclusion

    single = qm.FieldCondition(key="category", match=qm.MatchValue(value="Toys"))
    f = _with_exclusion(qm.Filter(must_not=single), "abc")
    assert isinstance(f.must_not, list) and len(f.must_not) == 2

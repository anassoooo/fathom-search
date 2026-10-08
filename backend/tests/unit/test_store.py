from vio.embeddings.fake import fake_encoders
from vio.models import Filters, Product
from vio.search.filters import to_qdrant
from vio.store.qdrant import IMAGE, ProductPoint, ProductStore


def test_count_and_get(memory_store: ProductStore, products: list[Product]) -> None:
    assert memory_store.count() == len(products)
    got = memory_store.get("3")
    assert got is not None and got == products[3]
    assert memory_store.get("does-not-exist") is None


def test_ensure_collection_is_idempotent(memory_store: ProductStore) -> None:
    assert memory_store.ensure_collection(64, 32) is False
    assert memory_store.count() == 24


def test_existing_ids(memory_store: ProductStore) -> None:
    assert memory_store.existing_ids(["0", "5", "999"]) == {"0", "5"}
    assert memory_store.existing_ids([]) == set()


def test_products_without_images_have_no_image_vector(memory_store: ProductStore) -> None:
    rec = memory_store.client.retrieve(
        memory_store.collection,
        ids=[Product(product_id="11", name="x", category="c").point_id],
        with_vectors=True,
    )[0]
    assert isinstance(rec.vector, dict) and IMAGE not in rec.vector


def test_browse_paginates_with_filters(memory_store: ProductStore) -> None:
    f = to_qdrant(Filters(category="Electronics"))
    page1, cursor = memory_store.browse(f, limit=4)
    page2, cursor2 = memory_store.browse(f, limit=4, cursor=cursor)
    assert len(page1) == 4 and len(page2) == 2 and cursor2 is None
    assert {p.category for p in page1 + page2} == {"Electronics"}
    assert len({p.product_id for p in page1 + page2}) == 6


def test_taxonomy(memory_store: ProductStore) -> None:
    tax = memory_store.taxonomy()
    assert "Home & Kitchen" in tax.categories and len(tax.categories) == 6
    assert "Coffee Makers" in tax.subcategories
    assert tax.max_price == 1299.0


def test_upsert_is_idempotent(memory_store: ProductStore, products: list[Product]) -> None:
    enc = fake_encoders()
    subset = products[:5]
    texts = [p.doc_text() for p in subset]
    points = [
        ProductPoint(p, d, s)
        for p, d, s in zip(
            subset, enc.dense.embed_documents(texts), enc.sparse.embed_documents(texts), strict=True
        )
    ]
    memory_store.upsert(points)
    memory_store.upsert(points)
    assert memory_store.count() == len(products)

import uuid
from collections.abc import Iterator

import pytest

from tests.store_helpers import populate
from vio.config import Settings
from vio.embeddings.fake import fake_encoders
from vio.models import Filters, Product
from vio.search.filters import to_qdrant
from vio.search.retrieve import QueryVectors, retrieve, similar
from vio.store.qdrant import ProductStore, create_client

pytestmark = pytest.mark.integration
ENC = fake_encoders()


@pytest.fixture(scope="module")
def store(products: list[Product]) -> Iterator[ProductStore]:
    s = ProductStore(create_client(Settings()), f"test_{uuid.uuid4().hex[:8]}")
    populate(s, products, ENC)
    yield s
    s.client.delete_collection(s.collection)


def test_hybrid_rrf_with_filters_on_server(store: ProductStore) -> None:
    q = "wireless headphones"
    qv = QueryVectors(
        dense=ENC.dense.embed_query(q),
        sparse=ENC.sparse.embed_query(q),
        clip_text=ENC.image.embed_text(q),
    )
    hits = retrieve(store.client, store.collection, qv, to_qdrant(Filters(price_max=60)), 5)
    assert hits and all((h.product.price or 0) <= 60 for h in hits)
    assert hits[0].product.subcategory == "Headphones"


def test_similar_on_server(store: ProductStore) -> None:
    hits = similar(store.client, store.collection, "17", None, 3)
    assert hits and "17" not in [h.product.product_id for h in hits]

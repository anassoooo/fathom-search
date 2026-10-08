import uuid
from collections.abc import Iterator

import pytest

from tests.store_helpers import populate
from vio.config import Settings
from vio.embeddings.fake import fake_encoders
from vio.models import Filters, Product
from vio.search.filters import to_qdrant
from vio.store.qdrant import ProductStore, create_client

pytestmark = pytest.mark.integration


@pytest.fixture
def server_store(products: list[Product]) -> Iterator[ProductStore]:
    store = ProductStore(create_client(Settings()), f"test_{uuid.uuid4().hex[:8]}")
    populate(store, products, fake_encoders())
    yield store
    store.client.delete_collection(store.collection)


def test_schema_has_indexes_and_vectors(server_store: ProductStore) -> None:
    info = server_store.client.get_collection(server_store.collection)
    assert {"category", "subcategory", "price_bucket", "price", "rating"} <= set(
        info.payload_schema
    )
    assert server_store.ensure_collection(64, 32) is False  # idempotent


def test_filtered_count_and_taxonomy(server_store: ProductStore) -> None:
    assert server_store.count() == 24
    assert server_store.count(to_qdrant(Filters(price_max=20))) == 7
    tax = server_store.taxonomy()
    assert len(tax.categories) == 6 and tax.max_price == 1299.0

import csv
from pathlib import Path

import pytest

from vio.models import Product
from vio.store.qdrant import ProductStore

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_csv() -> Path:
    return FIXTURES / "products.csv"


@pytest.fixture(scope="session")
def products(fixture_csv: Path) -> list[Product]:
    with fixture_csv.open(encoding="utf-8", newline="") as f:
        return [Product.from_csv_row(row) for row in csv.DictReader(f)]


@pytest.fixture
def memory_store(products: list[Product]) -> ProductStore:
    from qdrant_client import QdrantClient

    from tests.store_helpers import populate
    from vio.embeddings.fake import fake_encoders

    store = ProductStore(QdrantClient(location=":memory:"), "test_products")
    populate(store, products, fake_encoders())
    return store

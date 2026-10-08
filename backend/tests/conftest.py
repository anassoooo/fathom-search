import csv
from pathlib import Path

import pytest

from vio.models import Product

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_csv() -> Path:
    return FIXTURES / "products.csv"


@pytest.fixture(scope="session")
def products(fixture_csv: Path) -> list[Product]:
    with fixture_csv.open(encoding="utf-8", newline="") as f:
        return [Product.from_csv_row(row) for row in csv.DictReader(f)]

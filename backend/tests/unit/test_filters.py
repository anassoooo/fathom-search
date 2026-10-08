import pytest
from qdrant_client import models as qm

from vio.models import Filters
from vio.search.filters import Taxonomy, sanitize, to_qdrant

TAX = Taxonomy(
    categories=frozenset({"Electronics", "Home & Kitchen"}),
    subcategories=frozenset({"Headphones", "Coffee Makers"}),
    max_price=5000,
)


@pytest.mark.parametrize(
    ("given", "expected", "n_dropped"),
    [
        (Filters(category="electronics"), Filters(category="Electronics"), 0),
        (Filters(category="  home   &  KITCHEN "), Filters(category="Home & Kitchen"), 0),
        (Filters(category="Spaceships"), Filters(), 1),
        (Filters(subcategory="coffee makers"), Filters(subcategory="Coffee Makers"), 0),
        (Filters(price_min=100, price_max=20), Filters(price_min=20, price_max=100), 1),
        (Filters(price_max=10_000_000), Filters(), 1),
        (Filters(price_min=0, price_max=50), Filters(price_max=50), 0),
        (
            Filters(price_bucket="cheap", min_rating=4),
            Filters(price_bucket="cheap", min_rating=4),
            0,
        ),
    ],
)
def test_sanitize(given: Filters, expected: Filters, n_dropped: int) -> None:
    cleaned, dropped = sanitize(given, TAX)
    assert cleaned == expected
    assert len(dropped) == n_dropped


def test_empty_filters_build_nothing() -> None:
    assert to_qdrant(Filters()) is None


def test_to_qdrant_builds_all_conditions() -> None:
    f = to_qdrant(
        Filters(
            category="Electronics", price_min=10, price_max=50, price_bucket="mid", min_rating=4
        )
    )
    assert f is not None and isinstance(f.must, list)
    by_key = {c.key: c for c in f.must if isinstance(c, qm.FieldCondition)}
    assert set(by_key) == {"category", "price", "price_bucket", "rating"}
    assert by_key["price"].range == qm.Range(gte=10, lte=50)
    assert by_key["category"].match == qm.MatchValue(value="Electronics")

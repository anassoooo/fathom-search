from typing import Any

from vio.ingest.normalize import apply_quality_flags, normalize
from vio.models import Product


def _p(pid: str, name: str, category: str, price: float = 10.0) -> Product:
    return Product(product_id=pid, name=name, category=category, subcategory="x", price=price)


def test_flags_union_over_merged_listings_and_suggestion_is_added() -> None:
    merged, _ = normalize(
        [_p("1", "Pulse 3D Headset", "Groceries"), _p("2", "Pulse 3D Headset", "Groceries")]
    )
    findings: dict[str, dict[str, Any]] = {
        "1": {"flags": ["category_disagreement"], "suggested_category": "Gaming & Accessories"},
        "2": {"flags": ["price_outlier"]},
    }
    [p] = apply_quality_flags(merged, findings)
    assert p.quality_flags == ["category_disagreement", "price_outlier"]
    assert p.categories == ["Groceries", "Gaming & Accessories"]  # listed category kept
    assert p.category == "Groceries"


def test_suggestion_uses_canonical_name_and_is_not_duplicated() -> None:
    [p] = apply_quality_flags(
        [_p("1", "Brush", "Arts & Crafts")],
        {"1": {"flags": ["category_disagreement"], "suggested_category": "Art Supplies"}},
    )
    assert p.categories == ["Arts & Crafts"]


def test_unflagged_products_are_untouched() -> None:
    items = [_p("1", "Mouse", "Computers")]
    assert apply_quality_flags(items, {}) == items

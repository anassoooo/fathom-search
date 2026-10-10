from vio.ingest.normalize import normalize
from vio.models import Product


def _p(
    pid: str, name: str, category: str, sub: str, price: float = 10.0, img: str = "A1"
) -> Product:
    return Product(
        product_id=pid,
        name=name,
        category=category,
        subcategory=sub,
        price=price,
        image_url=f"https://m.media-amazon.com/images/I/{img}._AC_UY218_.jpg",
    )


def test_same_title_and_price_merge_across_categories() -> None:
    rows = [
        _p("32819", "Acer Aspire 3 Laptop", "Gaming & Accessories", "Gaming laptops", 299.99),
        _p("41", "Acer Aspire 3 Laptop", "Electronics", "Laptops", 299.99),
        _p("7", "Lodge Skillet", "Kitchenware", "Cookware", 19.9),
    ]
    out, report = normalize(rows)
    assert (report.input_rows, report.output_products, report.merged_rows) == (3, 2, 1)
    acer = next(p for p in out if p.name.startswith("Acer"))
    assert acer.product_id == "41"  # lowest numeric ID wins, not lexicographic
    assert acer.category == "Electronics"
    assert acer.categories == ["Electronics", "Gaming & Accessories"]
    assert acer.subcategories == ["Laptops", "Gaming laptops"]
    assert acer.merged_ids == ["41", "32819"]
    assert [p.product_id for p in out] == ["7", "41"]  # stable, ID-ordered output


def test_same_title_different_price_stays_separate() -> None:
    out, _ = normalize(
        [
            _p("1", "Rolex", "Jewelry", "Watches", 10995),
            _p("2", "Rolex", "Jewelry", "Watches", 5000),
        ]
    )
    assert len(out) == 2


def test_title_match_ignores_case_and_whitespace() -> None:
    out, _ = normalize(
        [
            _p("1", "LEGO  Classic Box", "Toys", "Bricks"),
            _p("2", "lego classic box", "Toys", "Bricks"),
        ]
    )
    assert len(out) == 1 and out[0].subcategories == ["Bricks"]


def test_category_aliases_and_raw_values_are_kept() -> None:
    out, report = normalize(
        [
            _p("1", "Oil paint set", "Art Supplies", "Oil paints"),
            _p("2", "Oil paint set", "Art & Craft", "Oil Paints"),
            _p("3", "Lipstick", "Beauty & Personal", "Lipstick"),
        ]
    )
    paint, lipstick = out
    assert paint.category == "Arts & Crafts" and paint.categories == ["Arts & Crafts"]
    assert paint.raw_categories == ["Art Supplies", "Art & Craft"]
    assert paint.subcategories == ["Oil paints"]  # spelling variants collapse to one
    assert lipstick.category == "Beauty & Personal Care"
    assert (report.categories_before, report.categories_after) == (3, 2)


def test_unmerged_product_gets_default_lists() -> None:
    p = _p("5", "Mouse", "Computers", "Mice")
    assert p.categories == ["Computers"] and p.subcategories == ["Mice"] and p.merged_ids == ["5"]


def test_brand_only_titles_with_different_images_stay_separate() -> None:
    out, _ = normalize(
        [
            _p("1", "PAVOI", "Jewelry", "Earrings", 14.95, img="X1"),
            _p("2", "PAVOI", "Jewelry", "Rings", 14.95, img="X2"),
        ]
    )
    assert len(out) == 2


def test_thumbnail_size_variants_count_as_the_same_image() -> None:
    a = _p("1", "Echo Show 15", "Electronics", "Smart TVs", 299.99, img="719v0Sii3JL")
    b = a.model_copy(
        update={
            "product_id": "2",
            "image_url": "https://m.media-amazon.com/images/I/719v0Sii3JL._AC_UL320_.jpg",
        }
    )
    assert len(normalize([a, b])[0]) == 1


def test_image_key() -> None:
    from vio.ingest.normalize import image_key

    assert (
        image_key("https://m.media-amazon.com/images/I/61n0lmxP5-L._AC_UY218_.jpg") == "61n0lmxP5-L"
    )
    assert image_key(None) is None

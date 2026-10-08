import pytest
from pydantic import ValidationError

from vio.models import Filters, Product, SearchRequest, point_id_for


def test_fixture_rows_parse(products: list[Product]) -> None:
    assert len(products) == 24
    s25 = products[0]
    assert s25.product_id == "0"
    assert s25.category == "Electronics"
    assert s25.price == pytest.approx(1219.99)
    assert s25.price_bucket == "premium"
    assert s25.total_ratings == 1520


def test_blank_and_nan_become_none(products: list[Product]) -> None:
    assert products[11].image_url is None  # empty cell
    assert products[23].image_url is None  # literal "nan" written by pandas


def test_point_id_matches_legacy_notebooks() -> None:
    # uuid5(NAMESPACE_URL, "vio:42") as computed in notebooks/03_embedding.ipynb
    assert point_id_for("42") == "da79addd-1fab-584f-93ab-6387a0298668"
    assert point_id_for("42") != point_id_for("43")


def test_float_formatted_ids_are_normalized() -> None:
    row = {"Product ID": "12.0", "Product Name": "x", "Product Category": "c"}
    assert Product.from_csv_row(row).product_id == "12"


def test_doc_text_excludes_price(products: list[Product]) -> None:
    text = products[3].doc_text()
    assert (
        text
        == "Sony WH-1000XM5 Wireless Noise Canceling Over-Ear Headphones | Electronics | Headphones"
    )
    assert "329" not in text


@pytest.mark.parametrize(
    "row",
    [
        {"Product ID": "1", "Product Name": "", "Product Category": "c"},
        {"Product ID": "1", "Product Name": "x", "Product Category": "c", "Product Rating": "7"},
        {"Product ID": "1", "Product Name": "x", "Product Category": "c", "price_bucket": "luxury"},
    ],
)
def test_invalid_rows_raise(row: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        Product.from_csv_row(row)


def test_search_request_needs_query_or_image() -> None:
    with pytest.raises(ValidationError):
        SearchRequest(query="   ")
    assert SearchRequest(query="laptop").k == 12
    assert SearchRequest(image_b64="abc").query is None


def test_filters_is_empty() -> None:
    assert Filters().is_empty()
    assert not Filters(price_max=50).is_empty()

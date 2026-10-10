import base64
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import ResponseHandlingException

from tests.store_helpers import fake_image_bytes
from vio.api.app import create_app
from vio.config import Settings
from vio.embeddings.fake import fake_encoders
from vio.models import Product
from vio.search.pipeline import SearchService
from vio.search.rerank import FakeReranker
from vio.store.qdrant import ProductStore

SETTINGS = Settings(_env_file=None, rerank_top_n=10, max_image_bytes=64 * 1024)


@pytest.fixture
def client(memory_store: ProductStore) -> Iterator[TestClient]:
    service = SearchService(memory_store, fake_encoders(), FakeReranker(), SETTINGS)
    with TestClient(create_app(service, SETTINGS)) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["points"] == 24 and r.json()["qdrant"] is True


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    assert client.get("/health", headers={"X-Request-ID": "abc"}).headers["X-Request-ID"] == "abc"
    assert len(client.get("/health").headers["X-Request-ID"]) == 32


def test_taxonomy(client: TestClient) -> None:
    body = client.get("/v1/taxonomy").json()
    assert body["categories"][0] == "Computers"  # sorted
    assert body["price_buckets"] == ["cheap", "mid", "premium"]


def test_search_returns_trace_and_timings(client: TestClient) -> None:
    r = client.post(
        "/v1/search",
        json={"query": "running shoes", "k": 3, "filters": {"price_max": 100}},
        headers={"X-Request-ID": "req-1"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trace_id"] == "req-1"
    assert body["variant"] == "hybrid_rerank"
    assert len(body["results"]) == 3
    assert all(h["product"]["price"] <= 100 for h in body["results"])
    assert body["results"][0]["product"]["subcategory"] == "Running Shoes"
    assert "total_ms" in body["timings_ms"]


def test_search_with_image(client: TestClient, products: list[Product]) -> None:
    img = base64.b64encode(fake_image_bytes(products[22])).decode()
    r = client.post("/v1/search", json={"image_b64": img, "k": 1})
    assert r.status_code == 200
    assert r.json()["results"][0]["product"]["product_id"] == "22"


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({}, 422),
        ({"query": "x", "k": 1000}, 422),
        ({"query": "x", "variant": "magic"}, 422),
        ({"image_b64": "@@@"}, 400),
    ],
)
def test_search_rejects_bad_input(
    client: TestClient, payload: dict[str, object], status: int
) -> None:
    r = client.post("/v1/search", json=payload)
    assert r.status_code == status
    assert "error" in r.json()


def test_oversized_body_is_413(client: TestClient) -> None:
    big = "A" * (200 * 1024)
    r = client.post("/v1/search", json={"image_b64": big})
    assert r.status_code == 413 and r.headers["X-Request-ID"]


def test_browse_and_pagination(client: TestClient) -> None:
    body = client.get("/v1/products", params={"category": "electronics", "limit": 4}).json()
    assert len(body["items"]) == 4 and body["total"] == 6 and body["has_more"] is True
    body2 = client.get(
        "/v1/products", params={"category": "electronics", "limit": 4, "page": 2}
    ).json()
    assert len(body2["items"]) == 2 and body2["has_more"] is False


def test_get_product_and_404(client: TestClient) -> None:
    assert client.get("/v1/products/3").json()["name"].startswith("Sony")
    r = client.get("/v1/products/nope")
    assert r.status_code == 404 and r.json()["error"] == "product nope not found"


def test_similar(client: TestClient) -> None:
    body = client.get("/v1/products/17/similar", params={"k": 3}).json()
    assert len(body["results"]) == 3
    assert "17" not in [h["product"]["product_id"] for h in body["results"]]
    assert client.get("/v1/products/nope/similar").status_code == 404


def test_store_outage_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service: SearchService = client.app.state.service  # type: ignore[attr-defined]

    def boom(*args: object, **kwargs: object) -> None:
        raise ResponseHandlingException(ConnectionError("qdrant down"))

    monkeypatch.setattr(service.store, "get", boom)
    monkeypatch.setattr(service.store, "count", boom)
    r = client.get("/v1/products/3")
    assert r.status_code == 503 and "unavailable" in r.json()["error"]
    assert client.get("/health").status_code == 503

"""Response models that exist only at the HTTP boundary."""

from pydantic import BaseModel

from vio.models import Product, SearchHit


class HealthOut(BaseModel):
    status: str
    version: str
    qdrant: bool
    points: int | None = None


class TaxonomyOut(BaseModel):
    categories: list[str]
    subcategories: list[str]
    price_buckets: list[str]
    max_price: float


class ProductPage(BaseModel):
    items: list[Product]
    page: int
    limit: int
    total: int
    has_more: bool


class SimilarOut(BaseModel):
    product_id: str
    results: list[SearchHit]


class ErrorOut(BaseModel):
    error: str
    request_id: str | None = None

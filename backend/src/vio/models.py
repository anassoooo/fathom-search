"""Domain models shared by ingestion, search, the API, and evaluation."""

import math
import uuid
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PriceBucket = Literal["cheap", "mid", "premium"]

# CSV header (as written by notebooks/02_eda.ipynb) -> Product field.
# This is the only place that knows the raw column names.
CSV_COLUMNS: dict[str, str] = {
    "Product ID": "product_id",
    "Product Name": "name",
    "Product Category": "category",
    "Product Subcategory": "subcategory",
    "Product Price ($)": "price",
    "price_bucket": "price_bucket",
    "Product Rating": "rating",
    "Total Ratings": "total_ratings",
    "Product Bayes_rating": "bayes_rating",
    "Product Value_score": "value_score",
    "Product Image": "image_url",
}

# Kept identical to the legacy notebooks so v1 and v2 collections share point IDs.
_POINT_ID_NAMESPACE = uuid.NAMESPACE_URL


def point_id_for(product_id: str) -> str:
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, f"vio:{product_id}"))


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "null"}:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


class Product(BaseModel):
    product_id: str
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    subcategory: str | None = None
    price: float | None = Field(default=None, ge=0)
    price_bucket: PriceBucket | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    total_ratings: int | None = Field(default=None, ge=0)
    bayes_rating: float | None = None
    value_score: float | None = None
    image_url: str | None = None
    # A product listed under several categories is merged into one point at ingest
    # (ADR-0002). These hold every (canonical) category it was listed under, the
    # original category spellings, and the IDs of the merged source rows.
    categories: list[str] = Field(default_factory=list)
    subcategories: list[str] = Field(default_factory=list)
    raw_categories: list[str] = Field(default_factory=list)
    merged_ids: list[str] = Field(default_factory=list)
    # Source values kept for traceability after recomputation (ADR-0003).
    bayes_rating_source: float | None = None
    value_score_source: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_blanks(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            return {k: _blank_to_none(v) for k, v in data.items()}
        return data

    @field_validator("product_id", mode="before")
    @classmethod
    def _id_as_str(cls, v: Any) -> str:
        # pandas may have written integer IDs as "12.0"
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        s = str(v).strip()
        return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s

    @field_validator("total_ratings", mode="before")
    @classmethod
    def _int_from_float_str(cls, v: Any) -> Any:
        if isinstance(v, str):
            return int(float(v.replace(",", "")))
        return v

    @field_validator("name", "category", "subcategory")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v is not None else None

    @model_validator(mode="after")
    def _default_lists(self) -> "Product":
        if not self.categories:
            self.categories = [self.category]
        if not self.subcategories and self.subcategory:
            self.subcategories = [self.subcategory]
        if not self.raw_categories:
            self.raw_categories = [self.category]
        if not self.merged_ids:
            self.merged_ids = [self.product_id]
        return self

    @classmethod
    def from_csv_row(cls, row: Mapping[str, Any]) -> "Product":
        return cls.model_validate({CSV_COLUMNS[k]: v for k, v in row.items() if k in CSV_COLUMNS})

    @property
    def point_id(self) -> str:
        return point_id_for(self.product_id)

    def doc_text(self) -> str:
        """Text indexed by the text encoders. Price is excluded: it is a filter, not semantics.

        All subcategories a merged product was listed under add context
        (e.g. "Laptops, Gaming laptops").
        """
        subs = ", ".join(self.subcategories[:3])
        return " | ".join(p for p in (self.name, self.category, subs) if p)

    def payload(self) -> dict[str, Any]:
        return self.model_dump()


class Filters(BaseModel):
    """Hard constraints. Always applied inside Qdrant, never post-hoc."""

    category: str | None = None
    subcategory: str | None = None
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    price_bucket: PriceBucket | None = None
    min_rating: float | None = Field(default=None, ge=0, le=5)

    def is_empty(self) -> bool:
        return all(v is None for v in self.model_dump().values())


Variant = Literal["bm25", "dense", "hybrid", "hybrid_rerank", "full"]


class SearchRequest(BaseModel):
    query: str | None = Field(default=None, max_length=500)
    image_b64: str | None = None
    filters: Filters = Field(default_factory=Filters)
    k: int = Field(default=12, ge=1, le=100)
    variant: Variant = "hybrid_rerank"

    @model_validator(mode="after")
    def _needs_input(self) -> "SearchRequest":
        if not (self.query and self.query.strip()) and not self.image_b64:
            raise ValueError("provide a text query, an image, or both")
        return self


class SearchHit(BaseModel):
    product: Product
    score: float
    rank: int


class SearchResponse(BaseModel):
    results: list[SearchHit]
    variant: Variant
    applied_filters: Filters
    dropped_filters: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    degraded: list[str] = Field(default_factory=list)
    trace_id: str | None = None

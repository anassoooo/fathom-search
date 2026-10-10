"""Validate user/LLM-supplied filters against the real catalog and build Qdrant filters.

Filters may come from an LLM, so they are treated as untrusted (Constitution Art. V):
unknown categories are dropped (and reported), prices are clamped, and inverted
ranges are repaired.
"""

from dataclasses import dataclass, field

from qdrant_client import models as qm

from vio.catalog import CATEGORY_ALIASES
from vio.models import Filters


@dataclass(frozen=True)
class Taxonomy:
    categories: frozenset[str] = field(default_factory=frozenset)
    subcategories: frozenset[str] = field(default_factory=frozenset)
    price_buckets: frozenset[str] = frozenset({"cheap", "mid", "premium"})
    max_price: float = 100_000.0

    def canonical_category(self, value: str) -> str | None:
        """Resolve user/LLM text to a catalog category, following aliases ("Art Supplies")."""
        key = " ".join(value.split()).casefold()
        for raw, canonical in CATEGORY_ALIASES.items():
            if raw.casefold() == key:
                value = canonical
                break
        return _canonical(value, self.categories)

    def canonical_subcategory(self, value: str) -> str | None:
        return _canonical(value, self.subcategories)


def _canonical(value: str, allowed: frozenset[str]) -> str | None:
    """Case/whitespace-insensitive lookup that returns the catalog's own spelling."""
    needle = " ".join(value.split()).casefold()
    for candidate in allowed:
        if candidate.casefold() == needle:
            return candidate
    return None


def sanitize(filters: Filters, taxonomy: Taxonomy) -> tuple[Filters, list[str]]:
    """Return Qdrant-safe filters plus human-readable notes on what was changed or dropped."""
    dropped: list[str] = []
    data = filters.model_dump()

    if filters.category is not None:
        data["category"] = taxonomy.canonical_category(filters.category)
        if data["category"] is None:
            dropped.append(f"unknown category {filters.category!r}")

    if filters.subcategory is not None:
        data["subcategory"] = taxonomy.canonical_subcategory(filters.subcategory)
        if data["subcategory"] is None:
            dropped.append(f"unknown subcategory {filters.subcategory!r}")

    lo, hi = filters.price_min, filters.price_max
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
        dropped.append("swapped inverted price range")
    if hi is not None and hi > taxonomy.max_price:
        hi = None
        dropped.append("removed price_max above catalog maximum")
    if lo is not None and lo == 0:
        lo = None
    data["price_min"], data["price_max"] = lo, hi

    return Filters.model_validate(data), dropped


def to_qdrant(filters: Filters) -> qm.Filter | None:
    must: list[qm.Condition] = []
    # `categories`/`subcategories` are arrays (merged listings); MatchValue matches any element.
    for attr, key in (
        ("category", "categories"),
        ("subcategory", "subcategories"),
        ("price_bucket", "price_bucket"),
    ):
        value = getattr(filters, attr)
        if value is not None:
            must.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=value)))

    if filters.price_min is not None or filters.price_max is not None:
        must.append(
            qm.FieldCondition(
                key="price", range=qm.Range(gte=filters.price_min, lte=filters.price_max)
            )
        )
    if filters.min_rating is not None:
        must.append(qm.FieldCondition(key="rating", range=qm.Range(gte=filters.min_rating)))

    return qm.Filter(must=must) if must else None

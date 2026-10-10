"""Catalog normalization applied at ingest: category aliases and duplicate-listing merge.

Decisions and evidence: docs/adr/0002-dedup-and-category-aliases.md.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from vio.catalog import canonical_category
from vio.models import Product

_WS = re.compile(r"\s+")


def _key(text: str) -> str:
    return _WS.sub(" ", text).strip().casefold()


def image_key(url: str | None) -> str | None:
    """Amazon image ID without the size suffix: .../I/719v0Sii3JL._AC_UY218_.jpg -> 719v0Sii3JL."""
    if not url:
        return None
    return url.rstrip("/").rsplit("/", 1)[-1].split(".", 1)[0] or None


def _id_order(product_id: str) -> tuple[int, int | str]:
    return (0, int(product_id)) if product_id.isdigit() else (1, product_id)


@dataclass
class NormalizeReport:
    input_rows: int
    output_products: int
    merged_rows: int
    categories_before: int
    categories_after: int


def _subcategory_spellings(products: Iterable[Product]) -> dict[str, str]:
    """Map each casefolded subcategory to its most common spelling ('Oil paints'/'Oil Paints')."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for p in products:
        if p.subcategory:
            counts[_key(p.subcategory)][p.subcategory] += 1
    return {k: c.most_common(1)[0][0] for k, c in counts.items()}


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def normalize(products: Sequence[Product]) -> tuple[list[Product], NormalizeReport]:
    """Canonicalize categories, then merge listings of the same item.

    Identity = normalized title + price + image ID. Title + price alone falsely merged
    distinct items with brand-only titles (e.g. 23 different "PAVOI" pieces at one price);
    image alone merges different offers that reuse a photo ("Like-New" vs new).

    The merged product keeps the fields of its lowest-ID listing and gains the union of
    categories/subcategories, so a filter on any of them still matches.
    """
    spell = _subcategory_spellings(products)

    groups: dict[tuple[str, float | None, str | None], list[Product]] = defaultdict(list)
    for p in products:
        price = round(p.price, 2) if p.price is not None else None
        groups[(_key(p.name), price, image_key(p.image_url))].append(p)

    merged: list[Product] = []
    for listings in groups.values():
        listings.sort(key=lambda p: _id_order(p.product_id))
        primary = listings[0]
        subs = [spell[_key(p.subcategory)] for p in listings if p.subcategory]
        merged.append(
            primary.model_copy(
                update={
                    "category": canonical_category(primary.category),
                    "subcategory": subs[0] if subs else None,
                    "categories": _unique(canonical_category(p.category) for p in listings),
                    "subcategories": _unique(subs),
                    "raw_categories": _unique(p.category for p in listings),
                    "merged_ids": [p.product_id for p in listings],
                }
            )
        )

    merged.sort(key=lambda p: _id_order(p.product_id))
    report = NormalizeReport(
        input_rows=len(products),
        output_products=len(merged),
        merged_rows=len(products) - len(merged),
        categories_before=len({p.category for p in products}),
        categories_after=len({c for p in merged for c in p.categories}),
    )
    return merged, report

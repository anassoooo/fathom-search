"""Catalog-wide vocabulary shared by ingestion and search."""

from collections.abc import Mapping

# Raw category -> canonical category (ADR-0002). Only categories with clear overlap are
# merged: near-identical names and/or a large share of identical subcategories.
# Anything not listed maps to itself.
CATEGORY_ALIASES: Mapping[str, str] = {
    "Art & Craft": "Arts & Crafts",
    "Art Supplies": "Arts & Crafts",
    "Beauty & Personal": "Beauty & Personal Care",
    "Healthcare & Wellness": "Health & Household",
    "Music": "Music & Instruments",
    "Music Instruments": "Music & Instruments",
}


def canonical_category(raw: str) -> str:
    return CATEGORY_ALIASES.get(raw, raw)

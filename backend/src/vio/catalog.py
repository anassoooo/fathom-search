"""Catalog-wide vocabulary and derived-feature formulas shared by ingestion and search.

Pure Python on purpose: the production image does not ship pandas.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class RatingPrior:
    """Empirical-Bayes prior fitted by `vio data audit --refit` (ADR-0003)."""

    m: float
    category_means: Mapping[str, float]
    global_mean: float

    @classmethod
    def load(cls, path: Path) -> "RatingPrior":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(m=raw["m"], category_means=raw["category_means"], global_mean=raw["global_mean"])

    def bayes_rating(self, rating: float, reviews: int, category: str) -> float:
        mu = self.category_means.get(category, self.global_mean)
        return (reviews * rating + self.m * mu) / (reviews + self.m)


def value_score(bayes: float, reviews: int, price: float) -> float:
    """Quality x evidence per dollar (source definition, applied to the corrected rating)."""
    return bayes * math.log1p(reviews) / price

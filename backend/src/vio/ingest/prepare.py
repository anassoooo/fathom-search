"""One path from catalog CSV to the products that get indexed. Ingest and eval both use it,
so evaluation always sees exactly what search serves."""

import json
from dataclasses import dataclass
from pathlib import Path

from vio.catalog import RatingPrior
from vio.ingest.loader import LoadReport, load_products
from vio.ingest.normalize import NormalizeReport, apply_quality_flags, apply_rating_prior, normalize
from vio.models import Product


@dataclass
class PreparedCatalog:
    products: list[Product]
    loaded: LoadReport
    normalized: NormalizeReport
    prior_m: float | None  # None when data/derived_params.json is missing
    n_flagged: int | None  # None when data/quality_flags.json is missing


def prepare_catalog(csv_path: Path, data_dir: Path, limit: int | None = None) -> PreparedCatalog:
    loaded = load_products(csv_path, limit=limit)
    products, norm = normalize(loaded.products)

    prior_m = None
    params = data_dir / "derived_params.json"
    if params.exists():
        prior = RatingPrior.load(params)
        products = apply_rating_prior(products, prior)
        prior_m = prior.m

    n_flagged = None
    flags = data_dir / "quality_flags.json"
    if flags.exists():
        products = apply_quality_flags(products, json.loads(flags.read_text("utf-8")))
        n_flagged = sum(bool(p.quality_flags) for p in products)

    return PreparedCatalog(products, loaded, norm, prior_m, n_flagged)

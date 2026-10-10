"""Schema, completeness, uniqueness, and validity checks on the raw catalog."""

from pathlib import Path
from typing import Any

import pandas as pd

from vio.models import CSV_COLUMNS
from vio.quality.core import Dimension, Measurement, check

REQUIRED = list(CSV_COLUMNS.values())
_IMAGE_URL = r"^https://m\.media-amazon\.com/images/I/[\w\-\+%]+\.[\w\.\-]+$"


def load_raw(path: Path) -> pd.DataFrame:
    """Read the CSV with canonical field names. Values are left untouched (no coercion)."""
    df = pd.read_csv(path, dtype={"Product ID": str}, keep_default_na=True)
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])
    return df.rename(columns=CSV_COLUMNS)


def _examples(
    df: pd.DataFrame, mask: pd.Series, cols: list[str], n: int = 5
) -> list[dict[str, Any]]:
    present = [c for c in dict.fromkeys(["product_id", *cols]) if c in df.columns]
    records = df.loc[mask, present].head(n).to_dict("records")
    return [{str(k): v for k, v in r.items()} for r in records]


def _ids(df: pd.DataFrame, mask: pd.Series) -> list[str]:
    return df.loc[mask, "product_id"].astype(str).tolist() if "product_id" in df else []


@check("schema.required_columns", Dimension.VALIDITY, "All expected columns are present")
def required_columns(df: pd.DataFrame) -> Measurement:
    missing = [c for c in REQUIRED if c not in df.columns]
    return Measurement(metric=len(missing), n_affected=len(missing), details={"missing": missing})


@check(
    "completeness.required_fields",
    Dimension.COMPLETENESS,
    "Share of rows missing id, name, category, or price",
)
def required_fields(df: pd.DataFrame) -> Measurement:
    cols = [c for c in ("product_id", "name", "category", "price") if c in df]
    mask = df[cols].isna().any(axis=1)
    return Measurement(
        metric=float(mask.mean()) if len(df) else 0.0,
        n_affected=int(mask.sum()),
        examples=_examples(df, mask, cols),
        details={"null_counts": {c: int(df[c].isna().sum()) for c in cols}},
    )


@check(
    "completeness.optional_fields",
    Dimension.COMPLETENESS,
    "Null rate of optional fields (max over columns)",
)
def optional_fields(df: pd.DataFrame) -> Measurement:
    cols = [c for c in REQUIRED if c in df and c not in ("product_id", "name", "category", "price")]
    rates = {c: round(float(df[c].isna().mean()), 4) for c in cols}
    return Measurement(metric=max(rates.values(), default=0.0), details={"null_rates": rates})


@check("uniqueness.product_id", Dimension.UNIQUENESS, "Rows whose Product ID is not unique")
def unique_ids(df: pd.DataFrame) -> Measurement:
    mask = df["product_id"].duplicated(keep=False)
    return Measurement(
        metric=int(mask.sum()), n_affected=int(mask.sum()), examples=_examples(df, mask, ["name"])
    )


@check(
    "uniqueness.duplicate_listings",
    Dimension.UNIQUENESS,
    "Share of rows repeating another listing (title, price, image); merged at ingest (ADR-0002)",
)
def duplicate_listings(df: pd.DataFrame) -> Measurement:
    from vio.ingest.normalize import image_key

    key = pd.DataFrame(
        {
            "t": df["name"].astype(str).str.split().str.join(" ").str.casefold(),
            "p": df["price"].round(2),
            "i": df["image_url"].map(lambda u: image_key(u) if isinstance(u, str) else None),
        }
    )
    dup = key.duplicated(keep="first")
    return Measurement(
        metric=float(dup.mean()) if len(df) else 0.0,
        n_affected=int(dup.sum()),
        details={"groups": int(key[key.duplicated(keep=False)].drop_duplicates().shape[0])},
    )


@check("validity.rating_range", Dimension.VALIDITY, "Ratings outside [1, 5]")
def rating_range(df: pd.DataFrame) -> Measurement:
    r = pd.to_numeric(df["rating"], errors="coerce")
    mask = r.notna() & ~r.between(1, 5)
    return Measurement(
        metric=int(mask.sum()), n_affected=int(mask.sum()), examples=_examples(df, mask, ["rating"])
    )


@check(
    "validity.price_positive", Dimension.VALIDITY, "Prices that are non-numeric, zero, or negative"
)
def price_positive(df: pd.DataFrame) -> Measurement:
    p = pd.to_numeric(df["price"], errors="coerce")
    mask = df["price"].notna() & ~(p > 0)
    return Measurement(
        metric=int(mask.sum()), n_affected=int(mask.sum()), examples=_examples(df, mask, ["price"])
    )


@check(
    "validity.review_count",
    Dimension.VALIDITY,
    "Review counts that are negative or not whole numbers",
)
def review_count(df: pd.DataFrame) -> Measurement:
    v = pd.to_numeric(df["total_ratings"], errors="coerce")
    mask = df["total_ratings"].notna() & ~((v >= 0) & (v % 1 == 0))
    return Measurement(
        metric=int(mask.sum()),
        n_affected=int(mask.sum()),
        examples=_examples(df, mask, ["total_ratings"]),
    )


@check(
    "validity.price_bucket_domain",
    Dimension.VALIDITY,
    "price_bucket values outside {cheap, mid, premium}",
)
def bucket_domain(df: pd.DataFrame) -> Measurement:
    mask = df["price_bucket"].notna() & ~df["price_bucket"].isin(["cheap", "mid", "premium"])
    return Measurement(
        metric=int(mask.sum()),
        n_affected=int(mask.sum()),
        examples=_examples(df, mask, ["price_bucket"]),
    )


@check(
    "validity.image_url", Dimension.VALIDITY, "Share of image URLs matching the Amazon CDN pattern"
)
def image_url(df: pd.DataFrame) -> Measurement:
    ok = df["image_url"].astype(str).str.match(_IMAGE_URL)
    return Measurement(
        metric=float(ok.mean()) if len(df) else 1.0,
        n_affected=int((~ok).sum()),
        examples=_examples(df, ~ok, ["image_url"]),
    )


@check(
    "validity.rows_parse",
    Dimension.VALIDITY,
    "Rows rejected by the Product model (types, ranges, enums)",
)
def rows_parse(df: pd.DataFrame) -> Measurement:
    from pydantic import ValidationError

    from vio.models import Product

    bad: list[str] = []
    for rec in df.to_dict("records"):
        try:
            Product.model_validate(rec)
        except ValidationError:
            bad.append(str(rec.get("product_id")))
    return Measurement(metric=len(bad), n_affected=len(bad), affected_ids=bad[:1000])

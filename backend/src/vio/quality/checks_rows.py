"""Row-level plausibility and text-integrity checks. Each flags the products it affects."""

import numpy as np
import pandas as pd

from vio.quality.checks_basic import _examples, _ids
from vio.quality.core import Dimension, Measurement, check

ROBUST_Z = 3.5  # Iglewicz & Hoaglin (1993) cut-off for the modified z-score
MIN_GROUP = 10  # smaller subcategories fall back to their category
# MAD collapses when many items share one price (e.g. $1.99 novels), so a statistically
# extreme price must also be practically different: >= 3x away from the group median.
MIN_PRICE_RATIO = 3.0
LOW_EVIDENCE_REVIEWS = 5


def robust_z_log_price(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Modified z-score of log(price) and log(price / median) against the product's
    subcategory, or against its whole category when the subcategory is small."""
    logp = pd.Series(np.log(df["price"].astype(float).to_numpy()), index=df.index)

    def stats(keys: pd.Series) -> tuple[pd.Series, pd.Series]:
        med = logp.groupby(keys).transform("median")
        mad = (logp - med).abs().groupby(keys).transform("median")
        return med, mad

    sub_med, sub_mad = stats(df["subcategory"])
    cat_med, cat_mad = stats(df["category"])
    small = df.groupby("subcategory")["price"].transform("size") < MIN_GROUP
    med = cat_med.where(small, sub_med)
    mad = cat_mad.where(small, sub_mad)
    z = 0.6745 * (logp - med) / mad.replace(0, np.nan)
    return z.fillna(0.0), logp - med


@check(
    "plausibility.price_outlier",
    Dimension.PLAUSIBILITY,
    f"Share of prices with |robust z| > {ROBUST_Z} on log(price) within subcategory "
    f"and >= {MIN_PRICE_RATIO:g}x from its median",
    flag="price_outlier",
)
def price_outlier(df: pd.DataFrame) -> Measurement:
    z, log_ratio = robust_z_log_price(df)
    mask = (z.abs() > ROBUST_Z) & (log_ratio.abs() >= np.log(MIN_PRICE_RATIO))
    ex = (
        df.assign(robust_z=z.round(1), x_median=np.exp(log_ratio).round(3), _k=log_ratio.abs())
        .loc[mask]
        .sort_values("_k", ascending=False)
    )
    return Measurement(
        metric=float(mask.mean()),
        n_affected=int(mask.sum()),
        affected_ids=_ids(df, mask),
        examples=_examples(
            ex, ex.index == ex.index, ["name", "subcategory", "price", "x_median", "robust_z"], n=8
        ),
        details={"high": int((mask & (z > 0)).sum()), "low": int((mask & (z < 0)).sum())},
    )


@check(
    "plausibility.low_evidence_rating",
    Dimension.PLAUSIBILITY,
    f"Share of products rated by fewer than {LOW_EVIDENCE_REVIEWS} reviews",
    flag="low_evidence",
)
def low_evidence(df: pd.DataFrame) -> Measurement:
    mask = df["total_ratings"].astype(float) < LOW_EVIDENCE_REVIEWS
    return Measurement(
        metric=float(mask.mean()),
        n_affected=int(mask.sum()),
        affected_ids=_ids(df, mask),
        examples=_examples(df, mask, ["name", "rating", "total_ratings"]),
    )


def _text_check(df: pd.DataFrame, mask: pd.Series) -> Measurement:
    return Measurement(
        metric=float(mask.mean()) if len(df) else 0.0,
        n_affected=int(mask.sum()),
        affected_ids=_ids(df, mask),
        examples=_examples(df, mask, ["name"]),
    )


def _names(df: pd.DataFrame) -> pd.Series:
    return df["name"].astype(str)


@check(
    "text.mojibake", Dimension.TEXT, "Titles containing U+FFFD (encoding lost upstream)", "mojibake"
)
def mojibake(df: pd.DataFrame) -> Measurement:
    return _text_check(df, _names(df).str.contains("�", regex=False))


@check(
    "text.html_entities",
    Dimension.TEXT,
    "Titles with unescaped HTML entities (&amp;, &#39;)",
    "html_entity",
)
def html_entities(df: pd.DataFrame) -> Measurement:
    return _text_check(df, _names(df).str.contains(r"&(?:[a-z]+|#\d+);", regex=True))


@check(
    "text.brand_only_title",
    Dimension.TEXT,
    "Titles of two words or fewer (often just a brand): little text signal for search",
    "brand_only_title",
)
def brand_only(df: pd.DataFrame) -> Measurement:
    short = _names(df).str.count(r"\S+") <= 2
    m = _text_check(df, short)
    by_cat = df["category"][short].value_counts().head(5)
    m.details = {"top_categories": {str(k): int(v) for k, v in by_cat.items()}}
    return m


@check("text.all_caps", Dimension.TEXT, "Titles written entirely in capitals (> 10 letters)")
def all_caps(df: pd.DataFrame) -> Measurement:
    n = _names(df)
    letters = n.str.replace(r"[^A-Za-z]", "", regex=True)
    return _text_check(df, (letters.str.len() > 10) & (letters == letters.str.upper()))


@check("text.whitespace", Dimension.TEXT, "Titles with leading/trailing or repeated whitespace")
def whitespace(df: pd.DataFrame) -> Measurement:
    n = _names(df)
    return _text_check(df, (n != n.str.strip()) | n.str.contains(r"\s{2,}", regex=True))


@check("text.truncated", Dimension.TEXT, "Titles ending in an ellipsis (likely truncated)")
def truncated(df: pd.DataFrame) -> Measurement:
    return _text_check(df, _names(df).str.rstrip().str.endswith(("...", "…")))

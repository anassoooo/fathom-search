"""Verify the source's derived columns and recompute the Bayesian rating with an
empirical-Bayes prior (ADR-0003).

Model: product i in category c has latent quality θ_i ~ N(μ_c, τ²). Its displayed rating
averages v_i reviews: R_i | θ_i ~ N(θ_i, σ²/v_i). Hence Var(R_i - μ_c) = τ² + σ²·(1/v_i),
so a weighted regression of the binned variance on mean(1/v) yields τ² (intercept) and σ²
(slope). The posterior mean is the familiar shrinkage estimator with prior strength
m = σ²/τ²:   bayes_i = (v_i·R_i + m·μ_c) / (v_i + m).
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from vio.quality.core import Dimension, Measurement, check

N_BINS = 20
# The source formulas use catalog-wide statistics (global mean, median price, per-subcategory
# percentiles), so they can only be reproduced on the full catalog, not a sample.
POPULATION_MIN_ROWS = 5_000
_SKIP = {"skipped": f"needs the full catalog (>= {POPULATION_MIN_ROWS:,} rows)"}
MIN_EVIDENCE_FOR_MEAN = 50  # reviews needed for a product to inform its category mean


# --- verification of the source columns ---------------------------------------------------


def source_bayes(df: pd.DataFrame) -> pd.Series:
    """The notebook's formula: global mean C and prior strength m = median(price)."""
    r, v = df["rating"].astype(float), df["total_ratings"].astype(float)
    c, m = r.mean(), df["price"].astype(float).median()
    return v / (v + m) * r + m / (v + m) * c


@check(
    "consistency.bayes_rating_source",
    Dimension.CONSISTENCY,
    "Max |error| reproducing source bayes_rating from its notebook formula (m = median price)",
)
def bayes_source(df: pd.DataFrame) -> Measurement:
    if len(df) < POPULATION_MIN_ROWS:
        return Measurement(metric=0.0, details=dict(_SKIP))
    err = (source_bayes(df) - df["bayes_rating"].astype(float)).abs()
    return Measurement(
        metric=float(err.max()),
        details={
            "prior_strength_used": round(float(df["price"].median()), 2),
            "prior_strength_unit": "dollars (median price), a unit error; see ADR-0003",
        },
    )


@check(
    "consistency.value_score_source",
    Dimension.CONSISTENCY,
    "Max relative error reproducing value_score = bayes * ln(1 + reviews) / price",
)
def value_source(df: pd.DataFrame) -> Measurement:
    v = df["total_ratings"].astype(float)
    expected: pd.Series = df["bayes_rating"].astype(float) * np.log1p(v) / df["price"].astype(float)
    rel = ((expected - df["value_score"]) / df["value_score"]).abs()
    return Measurement(
        metric=float(rel.max()),
        details={
            "max_value_score": round(float(df["value_score"].max()), 2),
            "note": "upstream EDA dropped rows with value_score >= 1000 (very cheap items); "
            "how many cannot be recovered from this file",
        },
    )


@check(
    "consistency.price_bucket_source",
    Dimension.CONSISTENCY,
    "Share of price_bucket values matching per-subcategory 30th/70th price percentiles",
)
def bucket_source(df: pd.DataFrame) -> Measurement:
    if len(df) < POPULATION_MIN_ROWS:
        return Measurement(metric=1.0, details=dict(_SKIP))
    p = df["price"].astype(float)
    grp = p.groupby(df["subcategory"])
    q30, q70 = grp.transform(lambda s: s.quantile(0.3)), grp.transform(lambda s: s.quantile(0.7))
    expected = np.select([p <= q30, p <= q70], ["cheap", "mid"], "premium")
    ok = pd.Series(expected, index=df.index) == df["price_bucket"]
    return Measurement(metric=float(ok.mean()), n_affected=int((~ok).sum()))


# --- empirical-Bayes prior -----------------------------------------------------------------


@dataclass
class PriorEstimate:
    sigma2: float  # per-review variance of star ratings
    tau2: float  # between-product variance of true quality (within category)
    m: float  # prior strength in reviews = sigma2 / tau2
    m_ci95: tuple[float, float]
    m_without_lowest_bin: float  # sensitivity: the lowest-evidence bin dominates the slope
    category_means: dict[str, float]
    global_mean: float
    bins: list[dict[str, float]] = field(default_factory=list)
    method: str = (
        "WLS of binned Var(R - mu_c) on mean(1/v), 20 quantile bins of review count; "
        "95% CI from 200 bootstrap resamples of products"
    )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PriorEstimate":
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["m_ci95"] = tuple(raw["m_ci95"])
        return cls(**raw)


def _category_means(df: pd.DataFrame) -> pd.Series:
    precise = df[df["total_ratings"] >= MIN_EVIDENCE_FOR_MEAN]
    means = precise.groupby("category")["rating"].mean()
    # categories without enough precise products fall back to the global mean
    return means.reindex(df["category"].unique()).fillna(float(precise["rating"].mean()))


def _fit(
    r: np.ndarray, v: np.ndarray, *, drop_lowest: bool = False
) -> tuple[float, float, pd.DataFrame]:
    frame = pd.DataFrame({"r": r, "inv_v": 1.0 / v})
    frame["bin"] = pd.qcut(v, N_BINS, labels=False, duplicates="drop")
    g = frame.groupby("bin").agg(var=("r", "var"), inv_v=("inv_v", "mean"), n=("r", "size"))
    if drop_lowest:
        g = g.iloc[1:]
    w = g["n"].to_numpy(float)
    x = np.c_[np.ones(len(g)), g["inv_v"].to_numpy(float)]
    y = g["var"].to_numpy(float)
    tau2, sigma2 = np.linalg.solve(x.T @ (w[:, None] * x), x.T @ (w * y))
    return float(tau2), float(sigma2), g


def estimate_prior(df: pd.DataFrame, *, n_boot: int = 200, seed: int = 0) -> PriorEstimate:
    mu = _category_means(df)
    r = (df["rating"].astype(float) - df["category"].map(mu)).to_numpy()
    v = df["total_ratings"].astype(float).to_numpy()

    tau2, sigma2, bins = _fit(r, v)
    tau2_s, sigma2_s, _ = _fit(r, v, drop_lowest=True)

    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(r), len(r))
        t, s, _ = _fit(r[idx], v[idx])
        if t > 0:
            boot.append(s / t)
    lo, hi = np.percentile(boot, [2.5, 97.5])

    return PriorEstimate(
        sigma2=round(sigma2, 4),
        tau2=round(tau2, 5),
        m=round(sigma2 / tau2, 2),
        m_ci95=(round(float(lo), 2), round(float(hi), 2)),
        m_without_lowest_bin=round(sigma2_s / tau2_s, 2),
        category_means={str(k): round(float(x), 4) for k, x in sorted(mu.items())},
        global_mean=round(float(df["rating"].mean()), 4),
        bins=[
            {"inv_v": round(float(iv), 6), "var": round(float(var), 5), "n": int(n)}
            for iv, var, n in zip(bins["inv_v"], bins["var"], bins["n"], strict=True)
        ],
    )


def bayes_rating(
    rating: pd.Series, reviews: pd.Series, category: pd.Series, prior: PriorEstimate
) -> pd.Series:
    mu = category.map(prior.category_means).fillna(prior.global_mean)
    v = reviews.astype(float)
    return (v * rating.astype(float) + prior.m * mu) / (v + prior.m)


def value_score(bayes: pd.Series, reviews: pd.Series, price: pd.Series) -> pd.Series:
    """Same definition as the source (quality x evidence per dollar), on the corrected rating."""
    return bayes * np.log1p(reviews.astype(float)) / price.astype(float)


def report_section(prior: PriorEstimate, comparison: dict[str, float], refit: bool) -> str:
    rows = "\n".join(f"| {b['inv_v']:.5f} | {b['var']:.4f} | {b['n']:,} |" for b in prior.bins[:6])
    origin = "refitted in this run" if refit else "loaded from `data/derived_params.json`"
    lo, hi = prior.m_ci95
    rho = comparison["spearman_old_vs_new"]
    overlap = comparison["mean_top10_overlap_per_category"]
    mean_d, max_d = comparison["mean_abs_change"], comparison["max_abs_change"]
    m_s = prior.m_without_lowest_bin
    return f"""
The source `bayes_rating` reproduces exactly from the notebook formula, but that
formula sets the prior strength *m* to the **median price** ($), a unit error.
VIO recomputes it with an empirical-Bayes prior fitted on the catalog ({origin}).

**Model.** θ_i ~ N(μ_category, τ²), R_i | θ_i ~ N(θ_i, σ²/v_i), so
Var(R - μ_c) = τ² + σ²·(1/v). Method: {prior.method}.

| Parameter | Estimate |
|---|---|
| σ (per-review rating SD) | {prior.sigma2**0.5:.3f} stars |
| τ (between-product SD of true quality) | {prior.tau2**0.5:.3f} stars |
| **m = σ²/τ²** (prior strength, in reviews) | **{prior.m:.1f}** (95% CI {lo:.1f} to {hi:.1f}) |
| m without the lowest-evidence bin (sensitivity) | {m_s:.1f} |
| Source formula's m (median price) | 23.99 |

Lowest-evidence bins (variance falls with evidence, as the model predicts):

| mean 1/v | Var(R - μ_c) | products |
|---|---|---|
{rows}

**Impact vs the source column:** Spearman rank correlation {rho:.3f}; on average
{overlap:.0%} of each category's top 10 is unchanged; mean |Δ| {mean_d:.3f} stars,
max |Δ| {max_d:.2f}.

**Limitations.** (1) The 1/v model fits imperfectly: among popular products variance
keeps falling, so excluding the lowest-evidence bin raises m to {m_s:.0f}. The
full-range estimate is used because shrinkage only matters for low-evidence products.
(2) Products with < 50 reviews average ~0.13 stars lower than popular ones
(popularity bias), so shrinking them toward a mean computed from popular products
slightly flatters them.
"""


def compare_rankings(df: pd.DataFrame, prior: PriorEstimate, k: int = 10) -> dict[str, float]:
    """How much does the corrected rating change 'top rated' lists within categories?"""
    new = bayes_rating(df["rating"], df["total_ratings"], df["category"], prior)
    old = df["bayes_rating"].astype(float)
    spearman = float(old.rank().corr(new.rank()))
    overlaps = []
    for _, idx in df.groupby("category").groups.items():
        top_old = set(old.loc[idx].nlargest(k).index)
        top_new = set(new.loc[idx].nlargest(k).index)
        overlaps.append(len(top_old & top_new) / k)
    return {
        "spearman_old_vs_new": round(spearman, 4),
        f"mean_top{k}_overlap_per_category": round(float(np.mean(overlaps)), 3),
        "max_abs_change": round(float((new - old).abs().max()), 3),
        "mean_abs_change": round(float((new - old).abs().mean()), 4),
    }

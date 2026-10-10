# 0003 — Empirical-Bayes rating prior replaces the source's m = median(price)

- **Status:** accepted
- **Date:** 2026-10-10
- **Task:** T081

## Context
`Product Bayes_rating` in the source CSV is a shrinkage estimate
`(v·R + m·C) / (v + m)`. The audit reproduces it to within 7e-5, which confirms the
formula, and shows that the notebook set:
- **m = median(price) = 23.99.** Prior strength is a number of *virtual reviews*;
  a dollar amount here is a unit error that happened to land in a plausible range.
- **C = global mean rating.** Categories differ (category means range about 0.3 stars),
  so a phone and a sticker shrink toward the same value.

`value_score = bayes · ln(1+v) / price` inherits both.

## Decision
Fit the prior from the data with a normal–normal empirical-Bayes model:
θ_i ~ N(μ_category, τ²), R_i | θ_i ~ N(θ_i, σ²/v_i). Since
Var(R − μ_c) = τ² + σ²·(1/v), a weighted regression of the binned variance (20
quantile bins of review count) on mean(1/v) gives τ² (intercept) and σ² (slope);
m = σ²/τ². μ_c is the category mean over products with ≥ 50 reviews.

On the full catalog: σ = 1.43 stars per review, τ = 0.22, **m = 43.2
(95% bootstrap CI 38.2 to 50.5)**. Parameters are committed in
`data/derived_params.json`. `vio ingest` recomputes `bayes_rating` and `value_score`
and keeps the originals as `*_source`. The production path is pure Python
(`vio/catalog.py`); pandas is only used to fit.

## Validation
- The estimator recovers known parameters on simulated data: mean m 50.0 ± 3.4 over
  12 seeds vs a true value of 49 (unit test averages 5 seeds).
- The binned variances fall monotonically with evidence, as the model predicts
  (0.45 at ≤ 24 reviews down to 0.03 at > 30K).

## Alternatives considered
| Option | Why not |
|---|---|
| Keep source values | Right magnitude by accident, wrong method, global mean |
| m = median review count (1,542) | Far too strong: a product with 500 five-star reviews would barely move off the mean |
| m = fixed small quantile of v | Arbitrary; not grounded in the observed noise |
| Full hierarchical Bayes (Beta-Binomial on star counts) | Needs per-star counts, which we don't have |

## Consequences
- Low risk: Spearman 0.986 against the source ranking; 93% of each category's top 10
  is unchanged; mean |Δ| 0.011 stars, max 0.42.
- **Known limitation 1 (model fit):** variance keeps falling among popular products
  faster than 1/v. Dropping the lowest-evidence bin gives m ≈ 117. The full-range
  estimate is kept because shrinkage only matters at low evidence.
- **Known limitation 2 (popularity bias):** products with < 50 reviews average about
  0.13 stars lower, so shrinking them toward a mean from popular products slightly
  flatters them. A μ that depends on evidence is a possible refinement.
- Refitting is explicit (`vio data audit --refit`), so the parameters change only
  in a reviewed commit.

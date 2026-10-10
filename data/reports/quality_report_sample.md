# Catalog data-quality report

- **Source:** `data/sample/products.csv`
- **Rows:** 501
- **Generated:** 2026-10-10 by `vio data audit`
- **Verdict:** **TRUSTED**
- **Checks:** 23/23 passed; 0 blocking failures

Severity: *blocking* stops ingestion; *warning* is ingested with row-level quality flags; *info* is recorded only. Thresholds come from `data/contract.toml`.

## Completeness

| Check | Severity | Metric | Threshold | Status | Affected |
|---|---|---|---|---|---|
| `completeness.required_fields`<br>Share of rows missing id, name, category, or price | blocking | 0 | <= 0 | pass | 0 |
| `completeness.optional_fields`<br>Null rate of optional fields (max over columns) | warning | 0 | <= 0.05 | pass | 0 |

<details><summary><code>completeness.required_fields</code> details</summary>

- **null_counts:** `{"product_id": 0, "name": 0, "category": 0, "price": 0}`

</details>

<details><summary><code>completeness.optional_fields</code> details</summary>

- **null_rates:** `{"subcategory": 0.0, "price_bucket": 0.0, "rating": 0.0, "total_ratings": 0.0, "bayes_rating": 0.0, "value_score": 0.0, "image_url": 0.0}`

</details>

## Uniqueness

| Check | Severity | Metric | Threshold | Status | Affected |
|---|---|---|---|---|---|
| `uniqueness.product_id`<br>Rows whose Product ID is not unique | blocking | 0 | <= 0 | pass | 0 |
| `uniqueness.duplicate_listings`<br>Share of rows repeating another listing (title, price, image); merged at ingest (ADR-0002) | warning | 0.0220 | <= 0.2 | pass | 11 |

<details><summary><code>uniqueness.duplicate_listings</code> details</summary>

- **groups:** `11`

</details>

## Validity

| Check | Severity | Metric | Threshold | Status | Affected |
|---|---|---|---|---|---|
| `schema.required_columns`<br>All expected columns are present | blocking | 0 | <= 0 | pass | 0 |
| `validity.rating_range`<br>Ratings outside [1, 5] | blocking | 0 | <= 0 | pass | 0 |
| `validity.price_positive`<br>Prices that are non-numeric, zero, or negative | blocking | 0 | <= 0 | pass | 0 |
| `validity.review_count`<br>Review counts that are negative or not whole numbers | blocking | 0 | <= 0 | pass | 0 |
| `validity.price_bucket_domain`<br>price_bucket values outside {cheap, mid, premium} | blocking | 0 | <= 0 | pass | 0 |
| `validity.image_url`<br>Share of image URLs matching the Amazon CDN pattern | warning | 1 | >= 0.99 | pass | 0 |
| `validity.rows_parse`<br>Rows rejected by the Product model (types, ranges, enums) | blocking | 0 | <= 0 | pass | 0 |

<details><summary><code>schema.required_columns</code> details</summary>

- **missing:** `[]`

</details>

## Consistency

| Check | Severity | Metric | Threshold | Status | Affected |
|---|---|---|---|---|---|
| `consistency.bayes_rating_source`<br>Max |error| reproducing source bayes_rating from its notebook formula (m = median price) | warning | 0 | <= 0.001 | pass | 0 |
| `consistency.value_score_source`<br>Max relative error reproducing value_score = bayes * ln(1 + reviews) / price | warning | 0.0000 | <= 1e-06 | pass | 0 |
| `consistency.price_bucket_source`<br>Share of price_bucket values matching per-subcategory 30th/70th price percentiles | warning | 1 | >= 0.99 | pass | 0 |

<details><summary><code>consistency.bayes_rating_source</code> details</summary>

- **skipped:** `needs the full catalog (>= 5,000 rows)`

</details>

<details><summary><code>consistency.value_score_source</code> details</summary>

- **max_value_score:** `24.4`
- **note:** `upstream EDA dropped rows with value_score >= 1000 (very cheap item...`

</details>

<details><summary><code>consistency.price_bucket_source</code> details</summary>

- **skipped:** `needs the full catalog (>= 5,000 rows)`

</details>

## Plausibility

| Check | Severity | Metric | Threshold | Status | Affected |
|---|---|---|---|---|---|
| `plausibility.price_outlier`<br>Share of prices with |robust z| > 3.5 on log(price) within subcategory and >= 3x from its median | warning | 0.0220 | <= 0.03 | pass | 11 |
| `plausibility.low_evidence_rating`<br>Share of products rated by fewer than 5 reviews | warning | 0.0060 | <= 0.05 | pass | 3 |

<details><summary><code>plausibility.price_outlier</code> details</summary>

- **high:** `10`
- **low:** `1`

| product_id | name | subcategory | price | x_median | robust_z |
|---|---|---|---|---|---|
| 39754 | OURA | Rings | 499.0 | 38.473 | 6.5 |
| 40691 | The Diamond Channel | Diamond earrings | 279.99 | 21.588 | 5.5 |
| 39332 | MOUNTO 12-Inch Heavy Duty Cylinder Axial Fan with 25-Foot Vinyl Hos... | Industrial fans | 259.99 | 20.081 | 4.3 |
| 39972 | Bulova | Women's watches | 224.83 | 17.335 | 5.1 |
| 23395 | Shyft DualRide with Carryall Storage Infant Car Seat and Stroller C... | Baby strollers | 384.99 | 15.317 | 3.8 |
| 23472 | Babyletto Hudson 3-in-1 Convertible Baby Crib with Toddler Bed & Da... | Baby cribs | 379.0 | 15.079 | 3.7 |
| 11886 | Alberto VO5 Ocean Refresh Revitalizing Conditioner - Hair Condition... | Hair conditioner | 1.01 | 0.068 | -4.2 |
| 39570 | VIVOHOME Upgraded 4CFM 1/3 HP 1-Stage HVAC Vacuum Pump and 4 Way AC... | Vacuum pumps | 159.99 | 12.357 | 3.6 |

</details>

<details><summary><code>plausibility.low_evidence_rating</code> details</summary>


| product_id | name | rating | total_ratings |
|---|---|---|---|
| 5180 | DUMOS Bar Stools Set of 4, 24 inch Counter Height Bar Stools, Uphol... | 4.3 | 4 |
| 39570 | VIVOHOME Upgraded 4CFM 1/3 HP 1-Stage HVAC Vacuum Pump and 4 Way AC... | 5.0 | 4 |
| 40632 | Masedy | 5.0 | 2 |

</details>

## Text integrity

| Check | Severity | Metric | Threshold | Status | Affected |
|---|---|---|---|---|---|
| `text.mojibake`<br>Titles containing U+FFFD (encoding lost upstream) | warning | 0 | <= 0.001 | pass | 0 |
| `text.html_entities`<br>Titles with unescaped HTML entities (&amp;, &#39;) | warning | 0 | <= 0.001 | pass | 0 |
| `text.brand_only_title`<br>Titles of two words or fewer (often just a brand): little text signal for search | info | 0.1078 | measured | pass | 54 |
| `text.all_caps`<br>Titles written entirely in capitals (> 10 letters) | info | 0 | measured | pass | 0 |
| `text.whitespace`<br>Titles with leading/trailing or repeated whitespace | info | 0 | measured | pass | 0 |
| `text.truncated`<br>Titles ending in an ellipsis (likely truncated) | warning | 0.0040 | <= 0.01 | pass | 2 |

<details><summary><code>text.brand_only_title</code> details</summary>

- **top_categories:** `{"Footwear": 16, "Jewelry": 13, "Toys": 5, "Travel Accessories": 5, "Furniture": 2}`

| product_id | name |
|---|---|
| 1083 | The Silmarillion |
| 4727 | SHA CERLIN |
| 7371 | Grand patio |
| 8347 | MPLONG |
| 8678 | Nerf |

</details>

<details><summary><code>text.truncated</code> details</summary>


| product_id | name |
|---|---|
| 8898 | Micro Kickboard - Maxi Deluxe LED - Three Wheeled, Lean-to-Steer Sw... |
| 16267 | Camping Tent 2 Person, Waterproof Windproof Tent with Rainfly Easy ... |

</details>

## Label quality

| Check | Severity | Metric | Threshold | Status | Affected |
|---|---|---|---|---|---|
| `labels.category_disagreement`<br>Share of products whose title confidently points to a category they are not listed in (confident learning, 5-fold out-of-fold). A manual audit found most are taxonomy overlap, not errors: see data/reports/label_noise_audit.csv | warning | 0 | <= 0.08 | pass | 0 |

<details><summary><code>labels.category_disagreement</code> details</summary>

- **skipped:** `fewer than 2,000 scorable products; too few to train`

</details>

## Derived features: Bayesian rating

The source `bayes_rating` reproduces exactly from the notebook formula, but that
formula sets the prior strength *m* to the **median price** ($), a unit error.
VIO recomputes it with an empirical-Bayes prior fitted on the catalog (loaded from `data/derived_params.json`).

**Model.** θ_i ~ N(μ_category, τ²), R_i | θ_i ~ N(θ_i, σ²/v_i), so
Var(R - μ_c) = τ² + σ²·(1/v). Method: WLS of binned Var(R - mu_c) on mean(1/v), 20 quantile bins of review count; 95% CI from 200 bootstrap resamples of products.

| Parameter | Estimate |
|---|---|
| σ (per-review rating SD) | 1.425 stars |
| τ (between-product SD of true quality) | 0.217 stars |
| **m = σ²/τ²** (prior strength, in reviews) | **43.1** (95% CI 38.1 to 50.5) |
| m without the lowest-evidence bin (sensitivity) | 116.9 |
| Source formula's m (median price) | 23.99 |

Lowest-evidence bins (variance falls with evidence, as the model predicts):

| mean 1/v | Var(R - μ_c) | products |
|---|---|---|
| 0.20174 | 0.4479 | 2,135 |
| 0.02482 | 0.1470 | 2,159 |
| 0.01132 | 0.0974 | 2,085 |
| 0.00639 | 0.0815 | 2,115 |
| 0.00400 | 0.0677 | 2,119 |
| 0.00268 | 0.0592 | 2,126 |

**Impact vs the source column:** Spearman rank correlation 0.988; on average
97% of each category's top 10 is unchanged; mean |Δ| 0.009 stars,
max |Δ| 0.24.

**Limitations.** (1) The 1/v model fits imperfectly: among popular products variance
keeps falling, so excluding the lowest-evidence bin raises m to 117. The
full-range estimate is used because shrinkage only matters for low-evidence products.
(2) Products with < 50 reviews average ~0.13 stars lower than popular ones
(popularity bias), so shrinking them toward a mean computed from popular products
slightly flatters them.

## Row-level quality flags

64 of 501 rows (12.8%) carry at least one flag.

| Flag | Rows |
|---|---|
| `brand_only_title` | 54 |
| `price_outlier` | 11 |
| `low_evidence` | 3 |

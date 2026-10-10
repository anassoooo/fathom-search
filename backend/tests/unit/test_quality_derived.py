import numpy as np
import pandas as pd
import pytest

from vio.catalog import RatingPrior, value_score
from vio.ingest.normalize import apply_rating_prior
from vio.models import Product
from vio.quality import REGISTRY
from vio.quality.derived import bayes_rating, compare_rankings, estimate_prior, source_bayes


def _simulate(n: int, sigma: float, tau: float, seed: int = 1) -> pd.DataFrame:
    """Ratings drawn from exactly the model the estimator assumes."""
    rng = np.random.default_rng(seed)
    cats = rng.choice(["A", "B", "C"], n)
    mu = pd.Series(cats).map({"A": 4.2, "B": 4.4, "C": 4.6}).to_numpy()
    theta = rng.normal(mu, tau)
    v = np.maximum(1, rng.lognormal(5, 2, n).astype(int))
    r = rng.normal(theta, sigma / np.sqrt(v))
    df = pd.DataFrame({"category": cats, "rating": r, "total_ratings": v, "price": 20.0})
    df["bayes_rating"] = source_bayes(df)
    return df


def test_estimator_recovers_known_prior_strength() -> None:
    sigma, tau = 1.4, 0.2  # true m = 1.96 / 0.04 = 49
    priors = [estimate_prior(_simulate(20_000, sigma, tau, seed=s), n_boot=1) for s in range(5)]
    # Unbiased on average (a single 95% CI misses the truth ~5% of the time by design).
    assert np.mean([p.m for p in priors]) == pytest.approx(49, rel=0.08)
    assert np.mean([p.sigma2 for p in priors]) == pytest.approx(sigma**2, rel=0.05)
    assert np.mean([p.tau2 for p in priors]) == pytest.approx(tau**2, rel=0.08)
    assert priors[0].category_means["C"] == pytest.approx(4.6, abs=0.02)


def test_source_formula_check_detects_reproduction() -> None:
    df = _simulate(6_000, 1.4, 0.2)
    assert REGISTRY["consistency.bayes_rating_source"].fn(df).metric < 1e-9
    df["bayes_rating"] = df["bayes_rating"] + np.r_[0.5, np.zeros(len(df) - 1)]
    assert REGISTRY["consistency.bayes_rating_source"].fn(df).metric == pytest.approx(0.5)


def test_shrinkage_pulls_low_evidence_toward_category_mean() -> None:
    prior = RatingPrior(m=40, category_means={"Toys": 4.5}, global_mean=4.4)
    assert prior.bayes_rating(5.0, 2, "Toys") == pytest.approx((2 * 5 + 40 * 4.5) / 42)
    assert prior.bayes_rating(5.0, 100_000, "Toys") == pytest.approx(5.0, abs=0.001)
    assert prior.bayes_rating(3.0, 0, "Unknown") == pytest.approx(4.4)  # global fallback


def test_pandas_and_pure_python_formulas_agree() -> None:
    df = _simulate(500, 1.4, 0.2)
    est = estimate_prior(df, n_boot=10)
    prior = RatingPrior(m=est.m, category_means=est.category_means, global_mean=est.global_mean)
    vec = bayes_rating(df["rating"], df["total_ratings"], df["category"], est)
    one = [
        prior.bayes_rating(r, v, c)
        for r, v, c in zip(df.rating, df.total_ratings, df.category, strict=True)
    ]
    assert np.allclose(vec.to_numpy(), one)


def test_apply_rating_prior_keeps_source_values() -> None:
    prior = RatingPrior(m=40, category_means={"Art Supplies": 4.5}, global_mean=4.4)
    p = Product(
        product_id="1",
        name="Brush",
        category="Art Supplies",
        price=10.0,
        rating=5.0,
        total_ratings=2,
        bayes_rating=4.9,
        value_score=0.5,
    )
    [out] = apply_rating_prior([p], prior)
    assert out.bayes_rating_source == 4.9 and out.value_score_source == 0.5
    assert out.bayes_rating == pytest.approx((2 * 5 + 40 * 4.5) / 42, abs=1e-4)
    assert out.bayes_rating is not None
    assert out.value_score == pytest.approx(value_score(out.bayes_rating, 2, 10.0), abs=1e-4)


def test_compare_rankings_identity() -> None:
    df = _simulate(3_000, 1.4, 0.2)
    est = estimate_prior(df, n_boot=10)
    df["bayes_rating"] = bayes_rating(df["rating"], df["total_ratings"], df["category"], est)
    cmp = compare_rankings(df, est)
    assert cmp["spearman_old_vs_new"] == pytest.approx(1.0)
    assert cmp["max_abs_change"] == 0


def test_population_checks_skip_on_samples() -> None:
    small = _simulate(500, 1.4, 0.2)
    m = REGISTRY["consistency.bayes_rating_source"].fn(small)
    assert m.metric == 0 and "skipped" in m.details

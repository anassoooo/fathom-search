from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from vio.quality import REGISTRY, load_contract, run_audit
from vio.quality.checks_basic import load_raw
from vio.quality.core import Rule, Severity

CONTRACT = Path(__file__).parents[3] / "data" / "contract.toml"


@pytest.fixture
def raw(fixture_csv: Path) -> pd.DataFrame:
    return load_raw(fixture_csv)


def _metric(df: pd.DataFrame, name: str) -> float:
    return REGISTRY[name].fn(df).metric


def test_fixture_passes_the_contract(raw: pd.DataFrame) -> None:
    report = run_audit(raw, load_contract(CONTRACT), source="fixture")
    assert report.trusted, [r.name for r in report.blocking_failures]


def test_load_raw_uses_field_names(raw: pd.DataFrame) -> None:
    assert {"product_id", "name", "price", "image_url"} <= set(raw.columns)
    assert raw["product_id"].iloc[0] == "0"


def _set_head(col: str, *values: object) -> Callable[[pd.DataFrame], pd.DataFrame]:
    """Return a mutation that overwrites the first rows of `col`."""

    def mutate(d: pd.DataFrame) -> pd.DataFrame:
        series = d[col].astype(object).tolist()
        series[: len(values)] = values
        return d.assign(**{col: series})

    return mutate


@pytest.mark.parametrize(
    ("name", "mutate", "expected"),
    [
        ("uniqueness.product_id", lambda d: d.assign(product_id="1"), 24),
        ("validity.rating_range", _set_head("rating", 7.0), 1),
        ("validity.price_positive", _set_head("price", 0.0, -1.0), 2),
        ("validity.review_count", _set_head("total_ratings", 1.5), 1),
        ("validity.price_bucket_domain", _set_head("price_bucket", "lux"), 1),
        ("schema.required_columns", lambda d: d.drop(columns=["price_bucket"]), 1),
        ("validity.rows_parse", _set_head("rating", 9.0), 1),
    ],
)
def test_checks_detect_defects(
    raw: pd.DataFrame, name: str, mutate: Callable[[pd.DataFrame], pd.DataFrame], expected: float
) -> None:
    assert _metric(raw, name) == 0
    assert _metric(mutate(raw), name) == expected


def test_required_fields_rate(raw: pd.DataFrame) -> None:
    broken = raw.copy()
    broken.loc[0, "name"] = None
    assert _metric(broken, "completeness.required_fields") == pytest.approx(1 / 24)


def test_image_url_share(raw: pd.DataFrame) -> None:
    # fixture has one empty and one 'nan' image -> 22/24 match
    assert _metric(raw, "validity.image_url") == pytest.approx(22 / 24)


def test_duplicate_listings_rate(raw: pd.DataFrame) -> None:
    doubled = pd.concat([raw, raw.head(4).assign(product_id=["100", "101", "102", "103"])])
    m = REGISTRY["uniqueness.duplicate_listings"].fn(doubled)
    assert m.n_affected == 4 and m.details["groups"] == 4


def test_blocking_failure_makes_report_untrusted(raw: pd.DataFrame) -> None:
    contract = {"validity.rating_range": Rule(Severity.BLOCKING, max=0)}
    bad = raw.assign(rating=[6.0] * len(raw))
    report = run_audit(bad, contract, source="bad")
    assert not report.trusted
    assert [r.name for r in report.blocking_failures] == ["validity.rating_range"]


def test_rule_bounds() -> None:
    assert Rule(Severity.WARNING, min=0.99).passes(0.995)
    assert not Rule(Severity.WARNING, min=0.99).passes(0.98)
    assert Rule(Severity.WARNING, max=0, min=None).describe() == "<= 0"

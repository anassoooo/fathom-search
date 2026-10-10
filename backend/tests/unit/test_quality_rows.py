import pandas as pd
import pytest

from vio.quality import REGISTRY


def _df(names: list[str], prices: list[float] | None = None, sub: str = "Pens") -> pd.DataFrame:
    n = len(names)
    return pd.DataFrame(
        {
            "product_id": [str(i) for i in range(n)],
            "name": names,
            "category": "Office",
            "subcategory": sub,
            "price": prices or [10.0] * n,
            "total_ratings": [100] * n,
        }
    )


def _flagged(df: pd.DataFrame, name: str) -> list[str]:
    return REGISTRY[name].fn(df).affected_ids


def test_price_outlier_needs_both_statistical_and_practical_extremeness() -> None:
    rng = [9.0, 9.5, 10.0, 10.5, 11.0] * 4  # 20 normal pens around $10
    df = _df([f"pen {i}" for i in range(22)], [*rng, 500.0, 25.0])
    flagged = _flagged(df, "plausibility.price_outlier")
    assert flagged == ["20"]  # $500 is 50x the median; $25 is only 2.5x


def test_price_outlier_ignores_tied_prices_with_zero_mad() -> None:
    df = _df([f"novel {i}" for i in range(12)], [1.99] * 11 + [4.99])
    assert _flagged(df, "plausibility.price_outlier") == []  # MAD = 0: no z-score


def test_small_subcategories_fall_back_to_category() -> None:
    big = _df([f"pen {i}" for i in range(20)], [10.0 + i % 3 for i in range(20)])
    tiny = _df(["gold pen"], [900.0], sub="Luxury pens").assign(product_id="99")
    assert _flagged(pd.concat([big, tiny], ignore_index=True), "plausibility.price_outlier") == [
        "99"
    ]


@pytest.mark.parametrize(
    ("check", "names", "expected"),
    [
        ("text.mojibake", ["15.6� display", "fine"], ["0"]),
        ("text.html_entities", ["Salt &amp; Pepper", "Rock & Roll"], ["0"]),
        ("text.brand_only_title", ["PAVOI", "Nike Air", "Nike Air Max 90"], ["0", "1"]),
        ("text.truncated", ["A very long title...", "Done."], ["0"]),
    ],
)
def test_text_checks(check: str, names: list[str], expected: list[str]) -> None:
    assert _flagged(_df(names), check) == expected


def test_low_evidence_flag() -> None:
    df = _df(["a", "b"]).assign(total_ratings=[3, 300])
    assert _flagged(df, "plausibility.low_evidence_rating") == ["0"]

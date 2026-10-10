import pandas as pd

from vio.quality import REGISTRY
from vio.quality.checks_labels import detect_label_noise

KITCHEN = [
    "stainless steel chef knife set",
    "nonstick frying pan skillet",
    "cast iron dutch oven pot",
    "silicone spatula cooking utensil",
    "bamboo cutting board kitchen",
    "ceramic mixing bowl set baking",
]
GARDEN = [
    "garden hose nozzle sprayer",
    "flower seeds planting mix",
    "pruning shears garden clippers",
    "raised garden bed planter",
    "lawn sprinkler watering system",
    "organic compost soil fertilizer",
]


def _catalog() -> pd.DataFrame:
    rows = []
    for i in range(10):
        for j, t in enumerate(KITCHEN):
            rows.append(("Kitchenware", f"{t} model {i}{j} deluxe"))
        for j, t in enumerate(GARDEN):
            rows.append(("Gardening & Outdoor", f"{t} model {i}{j} deluxe"))
    rows.append(
        ("Gardening & Outdoor", "nonstick frying pan skillet chef knife set kitchen deluxe")
    )  # planted
    return pd.DataFrame(
        {
            "product_id": [str(i) for i in range(len(rows))],
            "category": [c for c, _ in rows],
            "name": [n for _, n in rows],
            "subcategory": "misc",
            "price": [10.0 + i for i in range(len(rows))],  # distinct prices: no merging
            "image_url": [
                f"https://m.media-amazon.com/images/I/img{i}.jpg" for i in range(len(rows))
            ],
            "rating": 4.5,
            "total_ratings": 100,
        }
    )


def test_planted_mislabel_is_flagged_with_suggestion() -> None:
    df = _catalog()
    r = detect_label_noise(df)
    planted = str(len(df) - 1)
    assert planted in r.flagged["product_id"].tolist()
    row = r.flagged.set_index("product_id").loc[planted]
    assert row["suggested"] == "Kitchenware"
    assert r.cv_accuracy > 0.9


def test_check_exposes_annotations_and_flag() -> None:
    m = REGISTRY["labels.category_disagreement"].fn(_catalog())
    planted = str(len(_catalog()) - 1)
    assert planted in m.affected_ids
    assert m.annotations[planted]["suggested_category"] == "Kitchenware"
    assert REGISTRY["labels.category_disagreement"].flag == "category_disagreement"


def test_too_little_data_is_skipped_not_crashed(fixture_csv: object) -> None:
    from pathlib import Path

    from vio.quality.checks_basic import load_raw

    assert isinstance(fixture_csv, Path)
    raw = load_raw(fixture_csv)
    small = raw[raw["category"].isin(["Sports & Outdoors", "Home & Kitchen"])]  # 4 items each
    m = REGISTRY["labels.category_disagreement"].fn(small)
    assert m.metric == 0 and m.affected_ids == []

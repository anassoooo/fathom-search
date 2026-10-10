import io
import json
import random
import re
from pathlib import Path

from PIL import Image

from vio.eval.queries import (
    add_typos,
    augment_image,
    generate,
    load,
    save,
    select_seeds,
    title_overlap,
)
from vio.llm.client import ChatResult, LLMClient, Message
from vio.models import Product


def _products(n_per_cat: int = 6) -> list[Product]:
    out = []
    for c, cat in enumerate(["Kitchenware", "Toys", "Footwear"]):
        for i in range(n_per_cat):
            pid = str(c * 100 + i)
            out.append(
                Product(
                    product_id=pid,
                    name=f"Item {pid} deluxe widget",
                    category=cat,
                    subcategory=f"{cat} sub",
                    price=10.0 + i,
                    image_url="https://x/I/a.jpg",
                )
            )
    out[0] = out[0].model_copy(update={"quality_flags": ["price_outlier"]})
    return out


class FakeLLM:
    """Answers the generation prompt for whatever products it is shown."""

    def __call__(
        self, model: str, messages: list[Message], temperature: float, json_mode: bool
    ) -> ChatResult:
        content = messages[-1]["content"]
        if "Categories:" in content:
            cats = [c for c in ["Kitchenware", "Toys", "Footwear"] if c in content]
            return ChatResult(
                json.dumps(
                    {"items": [{"category": c, "query": f"stuff for {c} fans"} for c in cats]}
                )
            )
        ids = re.findall(r'"product_id": "(\d+)"', content)
        items = [
            {
                "product_id": pid,
                "specific": f"deluxe widget {pid}",
                "descriptive": "something useful for everyday chores",
                "constrained": {"query": "useful everyday thing under 30", "price_max": 30},
            }
            for pid in ids
        ]
        return ChatResult(json.dumps({"items": items}))


def _img(path: Path) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (120, 100), "orange").save(buf, format="JPEG")
    path.write_bytes(buf.getvalue())


def test_seeds_exclude_flagged_and_are_stratified() -> None:
    seeds = select_seeds(_products(), per_category=3, seed=1)
    assert len(seeds) == 9
    assert "0" not in {p.product_id for p in seeds}  # flagged
    assert {p.category for p in seeds} == {"Kitchenware", "Toys", "Footwear"}
    assert select_seeds(_products(), 3, 1) == seeds  # deterministic


def test_generate_builds_all_buckets(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    for p in _products():
        _img(images / f"{p.product_id}.jpg")
    llm = LLMClient(FakeLLM(), sleep=lambda s: None)
    recs = generate(
        _products(), llm, "m", image_dir=images, out_dir=tmp_path / "eval", per_category=5
    )
    buckets = {r.bucket for r in recs}
    assert buckets == {"specific", "descriptive", "constrained", "noisy", "vague", "image"}
    assert [r.qid for r in recs] == [f"q{i:04d}" for i in range(1, len(recs) + 1)]
    constrained = [r for r in recs if r.bucket == "constrained"]
    assert all(r.filters.price_max == 30 for r in constrained)
    image_recs = [r for r in recs if r.bucket == "image"]
    assert all((tmp_path / "eval" / str(r.image_file)).exists() for r in image_recs)
    assert all(r.seed_product_id != "0" for r in recs)

    path = tmp_path / "q.jsonl"
    save(recs, path)
    assert load(path) == recs


def test_title_overlap() -> None:
    assert title_overlap("deluxe widget", "Item 5 deluxe widget") == 1.0
    assert title_overlap("something for chores", "Item 5 deluxe widget") == 0.0


def test_typos_are_deterministic_and_small() -> None:
    q = "comfortable shoes for walking all day"
    a, b = add_typos(q, random.Random(3)), add_typos(q, random.Random(3))
    assert a == b and a != q
    assert len(a.split()) == len(q.split())


def test_augmented_image_differs_but_is_valid() -> None:
    buf = io.BytesIO()
    Image.new("RGB", (200, 160), "red").save(buf, format="JPEG")
    out = augment_image(buf.getvalue(), random.Random(0))
    img = Image.open(io.BytesIO(out))
    assert img.size[0] < 200 and img.format == "JPEG"


def test_noisy_queries_come_from_every_other_descriptive(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    llm = LLMClient(FakeLLM(), sleep=lambda s: None)
    recs = generate(
        _products(30), llm, "m", image_dir=images, out_dir=tmp_path / "eval", per_category=20
    )
    n_desc = sum(r.bucket == "descriptive" for r in recs)
    n_noisy = sum(r.bucket == "noisy" for r in recs)
    assert n_noisy == n_desc // 2

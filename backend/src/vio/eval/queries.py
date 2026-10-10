"""Generate the evaluation query set (T031): data/eval/queries_v1.jsonl.

Seeds come only from *unflagged* products (data/README.md policy), stratified by category.
Six buckets so results can be broken down by query type:
  specific     names the product (brand allowed)          LLM
  descriptive  describes the need, no title words         LLM
  constrained  descriptive + a budget (price_max)         LLM
  noisy        descriptive with deterministic typos       derived
  vague        a shopping goal per category (no seed)     LLM
  image        an augmented photo of the seed product     derived

Lexical overlap with the seed title is measured per query, so a BM25 advantage from
copied title words would show up in the report rather than hide in the averages.
"""

import importlib.resources
import io
import json
import random
import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from vio.llm.client import LLMClient
from vio.models import Filters, Product

Bucket = Literal["specific", "descriptive", "constrained", "noisy", "vague", "image"]
PROMPT_VERSION = "v1"
_STOP = set(
    [
        "a",
        "an",
        "and",
        "the",
        "for",
        "with",
        "of",
        "to",
        "in",
        "on",
        "by",
        "at",
        "from",
        "or",
        "is",
        "are",
        "this",
        "that",
        "your",
        "my",
        "me",
        "i",
        "set",
        "pack",
        "piece",
        "pcs",
        "inch",
        "oz",
        "ft",
        "lb",
        "new",
        "best",
    ]
)


class QueryRecord(BaseModel):
    qid: str
    bucket: Bucket
    query: str | None = None  # None for image queries
    image_file: str | None = None  # path relative to data/eval/, for image queries
    seed_product_id: str | None = None
    category: str | None = None
    filters: Filters = Field(default_factory=Filters)  # ground-truth constraints (for T042)
    title_overlap: float | None = None
    prompt_version: str = PROMPT_VERSION


# --- LLM response schemas ---------------------------------------------------------------


class _Constrained(BaseModel):
    query: str = Field(min_length=3)
    price_max: float = Field(gt=0)


class _GenItem(BaseModel):
    product_id: str
    specific: str = Field(min_length=3)
    descriptive: str = Field(min_length=3)
    constrained: _Constrained


class _GenBatch(BaseModel):
    items: list[_GenItem]


class _VagueItem(BaseModel):
    category: str
    query: str = Field(min_length=3)


class _VagueBatch(BaseModel):
    items: list[_VagueItem]


# --- helpers ---------------------------------------------------------------------------


def prompt(name: str) -> str:
    return importlib.resources.files("vio.llm").joinpath(f"prompts/{name}").read_text("utf-8")


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1}


def title_overlap(query: str, title: str) -> float:
    """Share of the query's content words that also appear in the title."""
    q = content_words(query)
    return round(len(q & content_words(title)) / len(q), 3) if q else 0.0


def add_typos(text: str, rng: random.Random, n: int = 2) -> str:
    """Deterministic, realistic typos: swap, drop, or double one letter in n words."""
    words = text.split()
    candidates = [i for i, w in enumerate(words) if len(w) >= 4]
    for i in rng.sample(candidates, k=min(n, len(candidates))):
        w = words[i]
        j = rng.randrange(1, len(w) - 1)
        op = rng.choice(["swap", "drop", "double"])
        if op == "swap":
            w = w[:j] + w[j + 1] + w[j] + w[j + 2 :]
        elif op == "drop":
            w = w[:j] + w[j + 1 :]
        else:
            w = w[:j] + w[j] + w[j:]
        words[i] = w
    return " ".join(words)


def augment_image(data: bytes, rng: random.Random) -> bytes:
    """Simulate a shopper's photo: random crop (75-90%), horizontal flip, color jitter."""
    from PIL import Image, ImageEnhance

    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    scale = rng.uniform(0.75, 0.9)
    cw, ch = int(w * scale), int(h * scale)
    x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
    img = img.crop((x, y, x + cw, y + ch))
    if rng.random() < 0.5:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.8, 1.2))
    img = ImageEnhance.Color(img).enhance(rng.uniform(0.7, 1.3))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def select_seeds(products: Sequence[Product], per_category: int, seed: int) -> list[Product]:
    eligible = [
        p for p in products if not p.quality_flags and p.price and p.image_url and p.subcategory
    ]
    by_cat: dict[str, list[Product]] = defaultdict(list)
    for p in eligible:
        by_cat[p.category].append(p)
    rng = random.Random(seed)
    picked: list[Product] = []
    for cat in sorted(by_cat):
        pool = sorted(by_cat[cat], key=lambda p: p.product_id)
        picked += rng.sample(pool, k=min(per_category, len(pool)))
    return picked


def _describe(p: Product) -> str:
    return json.dumps(
        {"product_id": p.product_id, "title": p.name, "category": p.subcategory, "price": p.price}
    )


# --- generation --------------------------------------------------------------------------


def generate(
    products: Sequence[Product],
    llm: LLMClient,
    model: str,
    *,
    image_dir: Path,
    out_dir: Path,
    per_category: int = 10,
    batch_size: int = 10,
    seed: int = 13,
) -> list[QueryRecord]:
    """Build the query set. Bucket mix per seed is fixed by a seeded rotation."""
    rng = random.Random(seed)
    seeds = select_seeds(products, per_category, seed)
    rotation: list[Bucket] = ["descriptive", "specific", "constrained", "descriptive", "image"]
    assigned = {p.product_id: rotation[i % len(rotation)] for i, p in enumerate(seeds)}
    by_id = {p.product_id: p for p in seeds}
    records: list[QueryRecord] = []
    n_descriptive = 0

    text_seeds = [p for p in seeds if assigned[p.product_id] != "image"]
    template = prompt(f"eval_query_gen.{PROMPT_VERSION}.md")
    for start in range(0, len(text_seeds), batch_size):
        batch = text_seeds[start : start + batch_size]
        listing = "\n".join(_describe(p) for p in batch)
        resp = llm.structured(
            [{"role": "user", "content": template.replace("{products}", listing)}],
            _GenBatch,
            model=model,
            temperature=0.7,
        )
        for item in resp.items:
            p = by_id.get(item.product_id)
            if p is None or assigned[p.product_id] == "image":
                continue  # the model invented or repeated an ID: ignore it
            bucket = assigned[p.product_id]
            if bucket == "constrained":
                q, filters = item.constrained.query, Filters(price_max=item.constrained.price_max)
            else:
                q, filters = (
                    (item.specific if bucket == "specific" else item.descriptive),
                    Filters(),
                )
            n_descriptive += bucket == "descriptive"
            records.append(
                QueryRecord(
                    qid="",
                    bucket=bucket,
                    query=q.strip(),
                    seed_product_id=p.product_id,
                    category=p.category,
                    filters=filters,
                    title_overlap=title_overlap(q, p.name),
                )
            )
            # every other descriptive seed also yields a noisy (typo) variant
            if bucket == "descriptive" and n_descriptive % 2 == 0:
                noisy = add_typos(item.descriptive.strip(), rng)
                records.append(
                    QueryRecord(
                        qid="",
                        bucket="noisy",
                        query=noisy,
                        seed_product_id=p.product_id,
                        category=p.category,
                        title_overlap=title_overlap(noisy, p.name),
                    )
                )

    categories = sorted({p.category for p in products})
    vague = llm.structured(
        [
            {
                "role": "user",
                "content": prompt(f"eval_vague_gen.{PROMPT_VERSION}.md").replace(
                    "{categories}", "\n".join(categories)
                ),
            }
        ],
        _VagueBatch,
        model=model,
        temperature=0.7,
    )
    for v in vague.items:
        if v.category in categories:
            records.append(
                QueryRecord(qid="", bucket="vague", query=v.query.strip(), category=v.category)
            )

    img_out = out_dir / "images_v1"
    img_out.mkdir(parents=True, exist_ok=True)
    for p in seeds:
        if assigned[p.product_id] != "image":
            continue
        src = image_dir / f"{p.product_id}.jpg"
        if not src.exists():
            continue
        name = f"q_{p.product_id}.jpg"
        (img_out / name).write_bytes(augment_image(src.read_bytes(), rng))
        records.append(
            QueryRecord(
                qid="",
                bucket="image",
                image_file=f"images_v1/{name}",
                seed_product_id=p.product_id,
                category=p.category,
            )
        )

    for i, r in enumerate(records, start=1):
        r.qid = f"q{i:04d}"
    return records


def save(records: Sequence[QueryRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(r.model_dump_json(exclude_none=True) + "\n")


def load(path: Path) -> list[QueryRecord]:
    return [QueryRecord.model_validate_json(line) for line in path.read_text("utf-8").splitlines()]

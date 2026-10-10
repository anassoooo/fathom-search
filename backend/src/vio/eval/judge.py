"""Pooling and LLM relevance judging (T032): data/eval/qrels_v1.jsonl.

TREC-style pooling: every variant's top `depth` results (plus the seed product) form the
candidate pool for a query, so no variant is graded only on documents another one found.
An LLM judge grades each pooled product 0/1/2 with a fixed, versioned rubric. Results are
cached by the LLM client, so judging resumes where it stopped.
"""

import base64
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from vio.eval.queries import QueryRecord, prompt
from vio.llm.client import LLMClient
from vio.models import Product, SearchRequest, Variant
from vio.search.pipeline import SearchService

JUDGE_PROMPT_VERSION = "v1"
POOL_VARIANTS: tuple[Variant, ...] = ("bm25", "dense", "hybrid", "hybrid_rerank")


class Judgment(BaseModel):
    qid: str
    product_id: str
    grade: Literal[0, 1, 2]
    judge_model: str
    prompt_version: str = JUDGE_PROMPT_VERSION


class _Grade(BaseModel):
    id: str
    grade: int = Field(ge=0, le=2)


class _Grades(BaseModel):
    grades: list[_Grade]


def query_request(q: QueryRecord, eval_dir: Path, k: int, variant: Variant) -> SearchRequest:
    if q.bucket == "image":
        assert q.image_file
        data = (eval_dir / q.image_file).read_bytes()
        return SearchRequest(image_b64=base64.b64encode(data).decode(), k=k, variant=variant)
    return SearchRequest(query=q.query, k=k, variant=variant)


def build_pool(
    q: QueryRecord, service: SearchService, eval_dir: Path, depth: int = 20
) -> list[Product]:
    """Union of every variant's top-`depth` (image queries: the image search) plus the seed."""
    variants: Sequence[Variant] = ("hybrid",) if q.bucket == "image" else POOL_VARIANTS
    pool: dict[str, Product] = {}
    for v in variants:
        for hit in service.search(query_request(q, eval_dir, depth, v)).results:
            pool.setdefault(hit.product.product_id, hit.product)
    if q.seed_product_id and q.seed_product_id not in pool:
        seed = service.get(q.seed_product_id)
        if seed is not None:
            pool[seed.product_id] = seed
    return list(pool.values())


def describe_request(q: QueryRecord, seed: Product | None) -> str:
    if q.bucket == "image":
        name = seed.name if seed else "a product"
        return (
            "The shopper uploaded a photo of this product and wants it or close "
            f'alternatives: "{name}"'
        )
    text = q.query or ""
    if q.filters.price_max is not None:
        text += f" (budget: up to ${q.filters.price_max:g})"
    return text


def judge_pool(
    q: QueryRecord,
    pool: Sequence[Product],
    seed: Product | None,
    llm: LLMClient,
    model: str,
) -> list[Judgment]:
    # short positional ids keep the prompt small and stop the model echoing long IDs wrong
    ids = {f"c{i}": p for i, p in enumerate(pool, start=1)}
    candidates = "\n".join(
        json.dumps(
            {"id": cid, "title": p.name, "category": p.subcategory or p.category, "price": p.price}
        )
        for cid, p in ids.items()
    )
    content = (
        prompt(f"eval_judge.{JUDGE_PROMPT_VERSION}.md")
        .replace("{request}", describe_request(q, seed))
        .replace("{candidates}", candidates)
    )
    resp = llm.structured([{"role": "user", "content": content}], _Grades, model=model)
    graded = {g.id: g.grade for g in resp.grades if g.id in ids}
    missing = [cid for cid in ids if cid not in graded]
    if missing:  # one targeted follow-up for skipped candidates
        retry = llm.structured(
            [
                {"role": "user", "content": content},
                {"role": "assistant", "content": resp.model_dump_json()},
                {
                    "role": "user",
                    "content": f"You skipped these ids: {missing}. Grade them now, JSON only.",
                },
            ],
            _Grades,
            model=model,
        )
        graded.update({g.id: g.grade for g in retry.grades if g.id in ids})
    return [
        Judgment(qid=q.qid, product_id=ids[cid].product_id, grade=grade, judge_model=model)
        for cid, grade in graded.items()
    ]


def judge_all(
    queries: Sequence[QueryRecord],
    service: SearchService,
    llm: LLMClient,
    model: str,
    eval_dir: Path,
    *,
    depth: int = 20,
    on_query: Callable[[QueryRecord], None] | None = None,
) -> list[Judgment]:
    out: list[Judgment] = []
    for q in queries:
        pool = build_pool(q, service, eval_dir, depth)
        seed = service.get(q.seed_product_id) if q.seed_product_id else None
        out += judge_pool(q, pool, seed, llm, model)
        if on_query:
            on_query(q)
    return out


def save_qrels(judgments: Sequence[Judgment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for j in judgments:
            f.write(j.model_dump_json() + "\n")


def load_qrels(path: Path) -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = {}
    for line in path.read_text("utf-8").splitlines():
        j = Judgment.model_validate_json(line)
        qrels.setdefault(j.qid, {})[j.product_id] = j.grade
    return qrels

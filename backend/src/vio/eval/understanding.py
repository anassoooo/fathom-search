"""Evaluate LLM query understanding (T042) against ground truth built into queries_v1.

- price extraction: constrained queries carry the true budget (filters.price_max)
- false filters: no other text query states a price, so any inferred price is a false positive
- category: seeded queries should map to (one of) the seed product's categories; the parser
  may abstain (null), which is safe, so accuracy is reported *when it commits*
- typos: each noisy query was derived from a clean descriptive query of the same seed;
  we compare string similarity to the clean query before and after the rewrite
"""

import difflib
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vio.eval.metrics import percentile
from vio.eval.queries import QueryRecord
from vio.llm.client import QuotaExhaustedError
from vio.llm.query_understanding import ParsedQuery, QueryUnderstanding
from vio.models import Product


@dataclass
class Parsed:
    query: QueryRecord
    parsed: ParsedQuery | None
    latency_ms: float
    error: str | None = None


def run(
    queries: Sequence[QueryRecord],
    qu: QueryUnderstanding,
    on_step: Callable[[], None] | None = None,
) -> tuple[list[Parsed], str | None]:
    """Parse every text query; stop cleanly (returning partial results) on quota exhaustion."""
    out: list[Parsed] = []
    for q in queries:
        if q.bucket == "image" or not q.query:
            continue
        t = time.perf_counter()
        try:
            p = qu.parse(q.query)
            out.append(Parsed(q, p, (time.perf_counter() - t) * 1000))
        except QuotaExhaustedError as e:
            return out, str(e)
        except Exception as e:  # invalid output after repairs: counts as a failure
            out.append(Parsed(q, None, (time.perf_counter() - t) * 1000, str(e)[:200]))
        if on_step:
            on_step()
    return out, None


def _rate(num: int, den: int) -> str:
    return f"{num}/{den} = {num / den:.1%}" if den else "n/a"


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def metrics(results: Sequence[Parsed], products: dict[str, Product]) -> dict[str, str]:
    ok = [r for r in results if r.parsed is not None]
    m: dict[str, str] = {"parsed successfully": _rate(len(ok), len(results))}

    constrained = [r for r in ok if r.query.bucket == "constrained"]
    exact = sum(
        r.parsed.price_max is not None
        and r.query.filters.price_max is not None
        and abs(r.parsed.price_max - r.query.filters.price_max) <= 0.5
        for r in constrained
        if r.parsed
    )
    m["budget extracted exactly (constrained)"] = _rate(exact, len(constrained))

    others = [r for r in ok if r.query.bucket != "constrained"]
    false_price = sum(
        r.parsed is not None and (r.parsed.price_min is not None or r.parsed.price_max is not None)
        for r in others
    )
    false_intent = sum(r.parsed is not None and r.parsed.price_intent is not None for r in others)
    m["invented price filter (no budget stated)"] = _rate(false_price, len(others))
    m["invented price intent (no budget stated)"] = _rate(false_intent, len(others))

    seeded = [r for r in ok if r.query.seed_product_id in products]
    committed = [r for r in seeded if r.parsed and r.parsed.category]
    correct = sum(
        r.parsed is not None
        and r.parsed.category in products[str(r.query.seed_product_id)].categories
        for r in committed
    )
    m["category committed (seeded queries)"] = _rate(len(committed), len(seeded))
    m["category correct when committed"] = _rate(correct, len(committed))

    vague = [r for r in ok if r.query.bucket == "vague"]
    m["category abstained on vague goals"] = _rate(
        sum(r.parsed is not None and r.parsed.category is None for r in vague), len(vague)
    )

    clean = {
        r.query.seed_product_id: r.query.query
        for r in results
        if r.query.bucket == "descriptive" and r.query.query
    }
    noisy = [r for r in ok if r.query.bucket == "noisy" and r.query.seed_product_id in clean]
    if noisy:
        before = [similarity(r.query.query or "", clean[r.query.seed_product_id]) for r in noisy]
        after = [
            similarity(r.parsed.search_text if r.parsed else "", clean[r.query.seed_product_id])
            for r in noisy
        ]
        m["typo queries: similarity to clean query (before -> after)"] = (
            f"{sum(before) / len(before):.3f} -> {sum(after) / len(after):.3f} (n={len(noisy)})"
        )

    lat = [r.latency_ms for r in results if r.latency_ms > 5]  # exclude cache hits
    if lat:
        m["latency p50 / p95 (uncached)"] = (
            f"{percentile(lat, 50):.0f} / {percentile(lat, 95):.0f} ms (n={len(lat)})"
        )
    return m


def write_report(
    results: Sequence[Parsed],
    products: dict[str, Product],
    out_dir: Path,
    meta: dict[str, str],
    stopped: str | None,
) -> Path:
    m = metrics(results, products)
    rows = "\n".join(f"| {k} | {v} |" for k, v in m.items())
    failures = [r for r in results if r.parsed is None][:5]
    fail_md = "\n".join(f"- `{r.query.qid}` {r.query.query!r}: {r.error}" for r in failures)
    text = f"""# Query understanding evaluation, {date.today().isoformat()} ({meta.get("sha", "?")})

- **Model:** `{meta.get("model")}`, prompt `query_understanding.v1`,
  reasoning effort `{meta.get("effort")}`
- **Queries:** {len(results)} text queries from `data/eval/queries_v1.jsonl`
  (image queries excluded)
{f"- **Stopped early:** {stopped}" if stopped else ""}

| Metric | Value |
|---|---|
{rows}

Ground truth is built into the query set: constrained queries carry their generated budget,
other text queries state none, seeded queries belong to their seed product's categories,
and each noisy query was derived from a clean descriptive query of the same seed.

{"**Parse failures:**" + chr(10) + fail_md if failures else ""}
"""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"understanding-{date.today().isoformat()}-{meta.get('sha', 'x')}.md"
    path.write_text(text, encoding="utf-8")
    return path

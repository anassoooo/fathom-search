"""Human audit of the LLM judge (T033): data/eval/human_audit_v1.jsonl.

A stratified sample (by query bucket and judge grade) of judged pairs is shown to a human,
who grades them blind to the judge's grade. Agreement is reported as Cohen's kappa, both
unweighted and quadratic-weighted (0/1/2 is ordinal: confusing 0 with 2 is worse than 0
with 1). The audit is resumable: graded pairs are appended as they are entered.
"""

import json
import random
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel

from vio.eval.judge import Judgment
from vio.eval.queries import QueryRecord


class HumanLabel(BaseModel):
    qid: str
    product_id: str
    human_grade: int
    judge_grade: int


def stratified_sample(
    judgments: Sequence[Judgment], queries: dict[str, QueryRecord], n: int, seed: int = 7
) -> list[Judgment]:
    """Equal share per (bucket, judge grade) cell, so rare cells (e.g. vague/2) are covered."""
    cells: dict[tuple[str, int], list[Judgment]] = defaultdict(list)
    for j in judgments:
        q = queries.get(j.qid)
        if q is not None:
            cells[(q.bucket, j.grade)].append(j)
    rng = random.Random(seed)
    keys = sorted(cells)
    per_cell = max(1, n // max(len(keys), 1))
    picked: list[Judgment] = []
    for k in keys:
        pool = sorted(cells[k], key=lambda j: (j.qid, j.product_id))
        picked += rng.sample(pool, k=min(per_cell, len(pool)))
    rng.shuffle(picked)  # don't present cells in order: that would hint the grade
    return picked[:n]


def cohen_kappa(a: Sequence[int], b: Sequence[int], k: int = 3, weighted: bool = False) -> float:
    """Cohen's kappa for ordinal labels 0..k-1; quadratic weights when `weighted`."""
    n = len(a)
    if n == 0:
        return float("nan")
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        obs[x][y] += 1 / n
    pa = [sum(obs[i][j] for j in range(k)) for i in range(k)]
    pb = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def w(i: int, j: int) -> float:
        if weighted:
            return ((i - j) ** 2) / ((k - 1) ** 2)
        return 0.0 if i == j else 1.0

    observed = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    expected = sum(w(i, j) * pa[i] * pb[j] for i in range(k) for j in range(k))
    return 1.0 - observed / expected if expected else 1.0


def load_labels(path: Path) -> list[HumanLabel]:
    if not path.exists():
        return []
    return [HumanLabel.model_validate_json(x) for x in path.read_text("utf-8").splitlines() if x]


def run_audit(
    sample: Sequence[Judgment],
    describe: Callable[[Judgment], str],
    ask: Callable[[str], str],
    out: Path,
) -> list[HumanLabel]:
    """Prompt for each not-yet-labeled pair; append answers to `out` as they come."""
    done = {(x.qid, x.product_id) for x in load_labels(out)}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8", newline="\n") as f:
        todo = [j for j in sample if (j.qid, j.product_id) not in done]
        for i, j in enumerate(todo, start=1):
            answer = ""
            while answer not in {"0", "1", "2", "q"}:
                answer = ask(
                    f"\n[{i}/{len(todo)}]\n{describe(j)}\nGrade 0/1/2 (q to stop): "
                ).strip()
            if answer == "q":
                break
            label = HumanLabel(
                qid=j.qid, product_id=j.product_id, human_grade=int(answer), judge_grade=j.grade
            )
            f.write(label.model_dump_json() + "\n")
            f.flush()
    return load_labels(out)


def agreement(labels: Sequence[HumanLabel]) -> dict[str, float]:
    h = [x.human_grade for x in labels]
    j = [x.judge_grade for x in labels]
    exact = sum(a == b for a, b in zip(h, j, strict=True)) / len(labels) if labels else float("nan")
    binary = (
        sum((a > 0) == (b > 0) for a, b in zip(h, j, strict=True)) / len(labels)
        if labels
        else float("nan")
    )
    return {
        "n": float(len(labels)),
        "exact_agreement": round(exact, 3),
        "relevant_vs_not_agreement": round(binary, 3),
        "kappa": round(cohen_kappa(h, j), 3),
        "kappa_quadratic": round(cohen_kappa(h, j, weighted=True), 3),
    }


def summary_json(labels: Sequence[HumanLabel]) -> str:
    return json.dumps(agreement(labels), indent=2)

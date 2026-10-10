"""Build the committed sample: a small, reproducible, category-stratified slice of the catalog.

Rows are copied verbatim (same columns, same values) so the sample exercises exactly the
same loading code as the full CSV. A few whole duplicate-title groups are included on
purpose, because the full catalog lists many products under several categories.
"""

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

NAME_COL = "Product Name"
CATEGORY_COL = "Product Category"


@dataclass
class SampleReport:
    rows: int
    categories: int
    duplicate_groups: int


def make_sample(
    src: Path, dst: Path, *, size: int = 500, dup_groups: int = 10, seed: int = 42
) -> SampleReport:
    with src.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    rng = random.Random(seed)
    by_name: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_name[r[NAME_COL]].append(i)

    # 1) whole duplicate groups (small ones, so they don't dominate the sample)
    small_groups = sorted(
        (idx for idx in by_name.values() if 2 <= len(idx) <= 3), key=lambda g: g[0]
    )
    chosen: set[int] = set()
    for group in rng.sample(small_groups, k=min(dup_groups, len(small_groups))):
        chosen.update(group)

    # 2) fill the rest proportionally per category, at least 1 per category
    by_cat: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        if i not in chosen:
            by_cat[r[CATEGORY_COL]].append(i)
    remaining = max(size - len(chosen), 0)
    total = sum(len(v) for v in by_cat.values())
    for cat in sorted(by_cat):
        pool = by_cat[cat]
        quota = max(1, round(remaining * len(pool) / total))
        chosen.update(rng.sample(pool, k=min(quota, len(pool))))

    picked = sorted(chosen)[: max(size, len(chosen))]
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[i] for i in picked)

    names = [rows[i][NAME_COL] for i in picked]
    return SampleReport(
        rows=len(picked),
        categories=len({rows[i][CATEGORY_COL] for i in picked}),
        duplicate_groups=sum(1 for n in set(names) if names.count(n) > 1),
    )

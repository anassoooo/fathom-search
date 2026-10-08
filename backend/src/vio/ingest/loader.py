"""Read the processed catalog CSV into validated, de-duplicated Products."""

import csv
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from vio.models import Product


@dataclass
class LoadReport:
    products: list[Product]
    rows_read: int = 0
    duplicates: int = 0
    invalid: list[tuple[int, str]] = field(default_factory=list)  # (csv line, reason)


def load_products(path: Path, limit: int | None = None) -> LoadReport:
    report = LoadReport(products=[])
    seen: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            if limit is not None and len(report.products) >= limit:
                break
            report.rows_read += 1
            try:
                product = Product.from_csv_row(row)
            except ValidationError as e:
                first = e.errors()[0]
                loc = ".".join(str(p) for p in first["loc"])
                report.invalid.append((line_no, f"{loc}: {first['msg']}"))
                continue
            if product.product_id in seen:
                report.duplicates += 1
                continue
            seen.add(product.product_id)
            report.products.append(product)
    return report

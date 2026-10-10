"""Render an AuditReport as Markdown (for humans, committed) and JSON (for machines)."""

import json
from dataclasses import asdict
from datetime import date
from typing import Any

from vio.quality.core import AuditReport, CheckResult, Dimension, Severity

_STATUS = {True: "pass", False: "FAIL"}


def _fmt(x: float) -> str:
    if isinstance(x, float) and not x.is_integer():
        return f"{x:.4f}" if abs(x) < 1 else f"{x:,.2f}"
    return f"{int(x):,}"


def _cell(v: Any) -> str:
    s = str(v).replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= 70 else s[:67] + "..."


def to_markdown(report: AuditReport, sections: dict[str, str] | None = None) -> str:
    verdict = "TRUSTED" if report.trusted else "NOT TRUSTED (blocking failures)"
    lines = [
        "# Catalog data-quality report",
        "",
        f"- **Source:** `{report.source}`",
        f"- **Rows:** {report.n_rows:,}",
        f"- **Generated:** {date.today().isoformat()} by `vio data audit`",
        f"- **Verdict:** **{verdict}**",
        f"- **Checks:** {sum(r.passed for r in report.results)}/{len(report.results)} passed; "
        f"{len(report.blocking_failures)} blocking failures",
        "",
        "Severity: *blocking* stops ingestion; *warning* is ingested with row-level quality "
        "flags; *info* is recorded only. Thresholds come from `data/contract.toml`.",
        "",
    ]
    for dim in Dimension:
        rows = [r for r in report.results if r.dimension is dim]
        if not rows:
            continue
        lines += [
            f"## {dim.value.capitalize()}",
            "",
            "| Check | Severity | Metric | Threshold | Status | Affected |",
            "|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append(
                f"| `{r.name}`<br>{r.description} | {r.severity.value} | "
                f"{_fmt(r.measurement.metric)} | {r.threshold} | {_STATUS[r.passed]} | "
                f"{r.measurement.n_affected:,} |"
            )
        lines.append("")
        lines += _details(rows)

    if sections:
        for title, body in sections.items():
            lines += [f"## {title}", "", body.strip(), ""]

    flags = report.flags()
    if flags:
        counts: dict[str, int] = {}
        for fl in flags.values():
            for f in fl:
                counts[f] = counts.get(f, 0) + 1
        lines += [
            "## Row-level quality flags",
            "",
            f"{len(flags):,} of {report.n_rows:,} rows ({len(flags) / max(report.n_rows, 1):.1%}) "
            "carry at least one flag.",
            "",
            "| Flag | Rows |",
            "|---|---|",
        ]
        lines += [f"| `{f}` | {n:,} |" for f, n in sorted(counts.items(), key=lambda kv: -kv[1])]
        lines.append("")
    return "\n".join(lines)


def _details(rows: list[CheckResult]) -> list[str]:
    out: list[str] = []
    for r in rows:
        m = r.measurement
        if not m.examples and not m.details:
            continue
        out += [f"<details><summary><code>{r.name}</code> details</summary>", ""]
        for k, v in m.details.items():
            out.append(f"- **{k}:** `{_cell(v) if not isinstance(v, dict) else json.dumps(v)}`")
        if m.examples:
            cols = list(m.examples[0])
            out += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            out += ["| " + " | ".join(_cell(e.get(c)) for c in cols) + " |" for e in m.examples]
        out += ["", "</details>", ""]
    return out


def to_json(report: AuditReport) -> str:
    def result(r: CheckResult) -> dict[str, Any]:
        d = asdict(r)
        # row-level data lives in data/quality_flags.json, not the report
        d["measurement"].pop("affected_ids")
        d["measurement"].pop("annotations")
        d["dimension"], d["severity"] = r.dimension.value, r.severity.value
        return d

    return json.dumps(
        {
            "source": report.source,
            "n_rows": report.n_rows,
            "trusted": report.trusted,
            "blocking_failures": [r.name for r in report.blocking_failures],
            "results": [result(r) for r in report.results],
        },
        indent=2,
        default=str,
    )


__all__ = ["Severity", "to_json", "to_markdown"]

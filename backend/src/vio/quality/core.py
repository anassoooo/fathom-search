"""Check registry, contract evaluation, and report model for the data-quality audit.

A *check* measures one property of the raw catalog and returns a `Measurement`.
The *contract* (data/contract.toml) decides whether that measurement passes and how
severe a failure is. Keeping the two apart means thresholds are reviewed as data,
not buried in code.
"""

import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd


class Dimension(StrEnum):
    COMPLETENESS = "completeness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"
    CONSISTENCY = "consistency"
    PLAUSIBILITY = "plausibility"
    TEXT = "text integrity"
    LABELS = "label quality"


class Severity(StrEnum):
    BLOCKING = "blocking"  # the dataset must not be ingested
    WARNING = "warning"  # ingest, but the issue is flagged and reported
    INFO = "info"  # measured for the record


@dataclass
class Measurement:
    metric: float
    n_affected: int = 0
    affected_ids: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


CheckFn = Callable[[pd.DataFrame], Measurement]


@dataclass(frozen=True)
class Check:
    name: str
    dimension: Dimension
    description: str
    fn: CheckFn
    # Row-level flag written to products affected by this check (None = dataset-level only).
    flag: str | None = None


REGISTRY: dict[str, Check] = {}


def check(
    name: str, dimension: Dimension, description: str, flag: str | None = None
) -> Callable[[CheckFn], CheckFn]:
    def register(fn: CheckFn) -> CheckFn:
        if name in REGISTRY:
            raise ValueError(f"duplicate check {name}")
        REGISTRY[name] = Check(name, dimension, description, fn, flag)
        return fn

    return register


@dataclass(frozen=True)
class Rule:
    severity: Severity
    max: float | None = None
    min: float | None = None

    def passes(self, metric: float) -> bool:
        if self.max is not None and metric > self.max:
            return False
        return not (self.min is not None and metric < self.min)

    def describe(self) -> str:
        parts = []
        if self.min is not None:
            parts.append(f">= {self.min:g}")
        if self.max is not None:
            parts.append(f"<= {self.max:g}")
        return " and ".join(parts) or "measured"


def load_contract(path: Path) -> dict[str, Rule]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    rules: dict[str, Rule] = {}
    for name, spec in raw.get("checks", {}).items():
        rules[name] = Rule(
            severity=Severity(spec.get("severity", "warning")),
            max=spec.get("max"),
            min=spec.get("min"),
        )
    return rules


@dataclass
class CheckResult:
    name: str
    dimension: Dimension
    description: str
    severity: Severity
    threshold: str
    passed: bool
    measurement: Measurement
    flag: str | None


@dataclass
class AuditReport:
    source: str
    n_rows: int
    results: list[CheckResult]

    @property
    def blocking_failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity is Severity.BLOCKING]

    @property
    def trusted(self) -> bool:
        return not self.blocking_failures

    def flags(self) -> dict[str, list[str]]:
        """product_id -> sorted quality flags, from every check that defines a flag."""
        out: dict[str, set[str]] = {}
        for r in self.results:
            if r.flag:
                for pid in r.measurement.affected_ids:
                    out.setdefault(pid, set()).add(r.flag)
        return {pid: sorted(f) for pid, f in sorted(out.items())}


def run_audit(df: pd.DataFrame, contract: dict[str, Rule], source: str) -> AuditReport:
    results: list[CheckResult] = []
    for name, chk in REGISTRY.items():
        rule = contract.get(name, Rule(Severity.INFO))
        m = chk.fn(df)
        results.append(
            CheckResult(
                name=name,
                dimension=chk.dimension,
                description=chk.description,
                severity=rule.severity,
                threshold=rule.describe(),
                passed=rule.passes(m.metric),
                measurement=m,
                flag=chk.flag,
            )
        )
    return AuditReport(source=source, n_rows=len(df), results=results)

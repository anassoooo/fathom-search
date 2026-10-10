"""Data-quality audit of the raw catalog against data/contract.toml (milestone M1.5)."""

from vio.quality import checks_basic  # noqa: F401  (registers checks)
from vio.quality.core import REGISTRY, AuditReport, load_contract, run_audit

__all__ = ["REGISTRY", "AuditReport", "load_contract", "run_audit"]

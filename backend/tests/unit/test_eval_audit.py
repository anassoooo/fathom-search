from pathlib import Path

import pytest

from vio.eval.audit import agreement, cohen_kappa, load_labels, run_audit, stratified_sample
from vio.eval.judge import Judgment
from vio.eval.queries import QueryRecord


def test_kappa_known_values() -> None:
    assert cohen_kappa([0, 1, 2, 2], [0, 1, 2, 2]) == pytest.approx(1.0)
    # classic 2x2 example: po = 0.7, pe = 0.5 -> kappa 0.4
    a = [1] * 5 + [0] * 5
    b = [1] * 4 + [0] + [1] * 2 + [0] * 3
    assert cohen_kappa(a, b, k=2) == pytest.approx(0.4)


def test_quadratic_weights_penalize_big_disagreements_more() -> None:
    near = cohen_kappa([0, 1, 2, 2, 1, 0], [1, 1, 2, 1, 1, 0], weighted=True)
    far = cohen_kappa([0, 1, 2, 2, 1, 0], [2, 1, 2, 0, 1, 0], weighted=True)
    assert near > far


def _judgments() -> tuple[list[Judgment], dict[str, QueryRecord]]:
    qs = {
        f"q{i}": QueryRecord(qid=f"q{i}", bucket="vague" if i < 3 else "specific", query="x")
        for i in range(10)
    }
    js = [
        Judgment(qid=f"q{i}", product_id=str(p), grade=(i + p) % 3, judge_model="m")
        for i in range(10)
        for p in range(6)
    ]
    return js, qs


def test_stratified_sample_covers_every_cell() -> None:
    js, qs = _judgments()
    sample = stratified_sample(js, qs, n=12)
    cells = {(qs[j.qid].bucket, j.grade) for j in sample}
    assert cells == {(b, g) for b in ("vague", "specific") for g in (0, 1, 2)}
    assert stratified_sample(js, qs, n=12) == sample  # deterministic


def test_audit_is_resumable(tmp_path: Path) -> None:
    js, qs = _judgments()
    sample = stratified_sample(js, qs, n=6)
    out = tmp_path / "audit.jsonl"
    answers = iter(["2", "bad", "1", "q"])
    run_audit(sample, lambda j: j.qid, lambda prompt: next(answers), out)
    assert len(load_labels(out)) == 2  # invalid input re-asked, 'q' stops
    labels = run_audit(sample, lambda j: j.qid, lambda prompt: "0", out)
    assert len(labels) == 6
    stats = agreement(labels)
    assert stats["n"] == 6 and 0 <= stats["exact_agreement"] <= 1

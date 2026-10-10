import csv
import io
from pathlib import Path

from typer.testing import CliRunner

from vio.cli import app

SAMPLE = Path(__file__).parents[3] / "data" / "sample" / "products.csv"


def _audit(csv_path: Path, out: Path) -> int:
    result = CliRunner().invoke(
        app, ["data", "audit", "--csv", str(csv_path), "--out-dir", str(out), "--name", "t"]
    )
    return result.exit_code


def test_committed_sample_passes_the_contract(tmp_path: Path) -> None:
    assert _audit(SAMPLE, tmp_path) == 0
    assert "Verdict:** **TRUSTED" in (tmp_path / "t.md").read_text(encoding="utf-8")


def test_a_broken_row_fails_the_audit(tmp_path: Path) -> None:
    rows = list(csv.reader(io.StringIO(SAMPLE.read_text(encoding="utf-8"))))
    rows[1][rows[0].index("Product Rating")] = "9.5"  # outside [1, 5]: a blocking violation
    broken = tmp_path / "broken.csv"
    with broken.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    assert _audit(broken, tmp_path) == 1
    assert "NOT TRUSTED" in (tmp_path / "t.md").read_text(encoding="utf-8")

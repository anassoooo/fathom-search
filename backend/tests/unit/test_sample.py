from pathlib import Path

from vio.ingest.loader import load_products
from vio.ingest.sample import make_sample


def test_sample_is_stratified_reproducible_and_loadable(fixture_csv: Path, tmp_path: Path) -> None:
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    report = make_sample(fixture_csv, a, size=12, dup_groups=0, seed=1)
    make_sample(fixture_csv, b, size=12, dup_groups=0, seed=1)
    assert a.read_bytes() == b.read_bytes()
    assert report.categories == 6  # every category represented
    loaded = load_products(a)
    assert len(loaded.products) == report.rows and not loaded.invalid


def test_sample_keeps_header_verbatim(fixture_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "s.csv"
    make_sample(fixture_csv, out, size=5, dup_groups=0)
    assert (
        out.read_text(encoding="utf-8").splitlines()[0]
        == fixture_csv.read_text(encoding="utf-8").splitlines()[0]
    )

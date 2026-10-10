from pathlib import Path

from vio.quality import load_contract, run_audit
from vio.quality.checks_basic import load_raw
from vio.quality.derived import estimate_prior
from vio.quality.figures import make_figures

CONTRACT = Path(__file__).parents[3] / "data" / "contract.toml"
SAMPLE = Path(__file__).parents[3] / "data" / "sample" / "products.csv"


def test_figures_render(tmp_path: Path) -> None:
    df = load_raw(SAMPLE)
    report = run_audit(df, load_contract(CONTRACT), "sample")
    paths = make_figures(df, report, estimate_prior(df, n_boot=5), tmp_path)
    names = {p.name for p in paths}
    assert {"rating_variance.png", "quality_flags.png", "price_by_category.png"} <= names
    assert all(p.stat().st_size > 10_000 for p in paths)

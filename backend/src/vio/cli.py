"""`vio` command-line entry point."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TimeElapsedColumn

from vio import __version__
from vio.config import get_settings

app = typer.Typer(
    help="VIO: multimodal product search, assistant, and evaluation.", no_args_is_help=True
)
console = Console()

# backend/src/vio/cli.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_CSV = REPO_ROOT / "data" / "sample" / "products.csv"


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def config() -> None:
    """Print the effective configuration (secrets are masked)."""
    typer.echo(get_settings().model_dump_json(indent=2))


data_app = typer.Typer(help="Data quality and catalog utilities.", no_args_is_help=True)
app.add_typer(data_app, name="data")
CONTRACT = REPO_ROOT / "data" / "contract.toml"
DERIVED_PARAMS = REPO_ROOT / "data" / "derived_params.json"
REPORTS = REPO_ROOT / "data" / "reports"


@data_app.command("audit")
def data_audit(
    csv_path: Annotated[Path, typer.Option("--csv", help="Catalog CSV to audit.")] = REPO_ROOT
    / "data"
    / "processed"
    / "vio_EDA.csv",
    contract: Annotated[Path, typer.Option(help="Data contract (TOML).")] = CONTRACT,
    out_dir: Annotated[Path, typer.Option(help="Where to write the report.")] = REPORTS,
    name: Annotated[str, typer.Option(help="Report file stem.")] = "quality_report",
    refit: Annotated[
        bool, typer.Option(help="Re-estimate the rating prior from this CSV (full catalog only).")
    ] = False,
) -> None:
    """Audit a catalog CSV against the data contract; exit 1 on blocking failures."""
    from vio.quality import load_contract, run_audit
    from vio.quality.checks_basic import load_raw
    from vio.quality.derived import PriorEstimate, compare_rankings, estimate_prior, report_section
    from vio.quality.report import to_json, to_markdown

    if not csv_path.exists():
        raise typer.BadParameter(f"{csv_path} not found")
    df = load_raw(csv_path)
    try:
        source = csv_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        source = csv_path.name
    report = run_audit(df, load_contract(contract), source=source)

    sections: dict[str, str] = {}
    if refit or not DERIVED_PARAMS.exists():
        prior = estimate_prior(df)
        prior.save(DERIVED_PARAMS)
        console.print(f"Fitted rating prior m={prior.m} (CI {prior.m_ci95}) -> {DERIVED_PARAMS}")
        refit = True
    else:
        prior = PriorEstimate.load(DERIVED_PARAMS)
    sections["Derived features: Bayesian rating"] = report_section(
        prior, compare_rankings(df, prior), refit
    )
    label_audit = out_dir / "label_noise_audit.csv"
    labels = next(r for r in report.results if r.name == "labels.category_disagreement")
    if label_audit.exists() and labels.measurement.n_affected > 1000:  # full catalog only
        from vio.quality.checks_labels import audit_section

        sections["Label quality: manual audit of flags"] = audit_section(
            label_audit, labels.measurement.n_affected
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.md").write_text(to_markdown(report, sections), encoding="utf-8")
    (out_dir / f"{name}.json").write_text(to_json(report), encoding="utf-8")

    for r in report.results:
        style = "green" if r.passed else ("red" if r.severity.value == "blocking" else "yellow")
        console.print(f"[{style}]{'pass' if r.passed else 'FAIL'}[/] {r.severity.value:8} {r.name}")
    verdict = "[green]TRUSTED[/]" if report.trusted else "[red]NOT TRUSTED[/]"
    console.print(f"{verdict}: report written to {out_dir / name}.md")
    if not report.trusted:
        raise typer.Exit(code=1)


@app.command()
def make_sample(
    src: Annotated[Path, typer.Option(help="Full processed CSV.")] = REPO_ROOT
    / "data"
    / "processed"
    / "vio_EDA.csv",
    dst: Annotated[Path, typer.Option(help="Where to write the sample.")] = SAMPLE_CSV,
    size: Annotated[int, typer.Option(min=10)] = 500,
    seed: Annotated[int, typer.Option()] = 42,
) -> None:
    """Write a reproducible, category-stratified sample of the catalog (T002)."""
    from vio.ingest.sample import make_sample as build

    if not src.exists():
        raise typer.BadParameter(f"{src} not found")
    r = build(src, dst, size=size, seed=seed)
    console.print(
        f"Wrote {r.rows} rows across {r.categories} categories "
        f"({r.duplicate_groups} duplicate-title groups) to {dst}"
    )


@app.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8000,
    reload: Annotated[bool, typer.Option(help="Auto-reload on code changes (dev only).")] = False,
) -> None:
    """Run the HTTP API with uvicorn."""
    import uvicorn

    uvicorn.run("vio.api.main:app", host=host, port=port, reload=reload, log_config=None)


@app.command()
def ingest(
    csv_path: Annotated[
        Path | None, typer.Option("--csv", help="Processed catalog CSV (vio_EDA.csv format).")
    ] = None,
    sample: Annotated[bool, typer.Option(help=f"Use the committed sample ({SAMPLE_CSV}).")] = False,
    limit: Annotated[int | None, typer.Option(help="Only ingest the first N valid rows.")] = None,
    recreate: Annotated[
        bool, typer.Option(help="Drop and recreate the collection first (destructive).")
    ] = False,
    image_dir: Annotated[
        Path | None, typer.Option(help="Folder of {product_id}.jpg images (also the cache).")
    ] = None,
    fetch_images: Annotated[
        bool, typer.Option(help="Download missing images from image_url into --image-dir.")
    ] = False,
    batch_size: Annotated[int, typer.Option(min=1, max=1024)] = 64,
    fake_encoders: Annotated[
        bool, typer.Option(hidden=True, help="Use hash-based encoders (tests/offline CI).")
    ] = False,
) -> None:
    """Load the catalog CSV, embed it, and upsert into Qdrant. Safe to re-run."""
    from vio.catalog import RatingPrior
    from vio.embeddings.fake import fake_encoders as make_fake
    from vio.embeddings.fastembed_impl import build_encoders
    from vio.ingest.images import ImageSource
    from vio.ingest.loader import load_products
    from vio.ingest.normalize import apply_rating_prior, normalize
    from vio.ingest.pipeline import ingest as run_ingest
    from vio.store.qdrant import ProductStore, create_client

    if sample == (csv_path is not None):
        raise typer.BadParameter("pass exactly one of --csv PATH or --sample")
    path = SAMPLE_CSV if sample else csv_path
    assert path is not None
    if not path.exists():
        hint = " (see TASKS.md T002 to create the sample)" if sample else ""
        raise typer.BadParameter(f"{path} not found{hint}")

    settings = get_settings()
    loaded = load_products(path, limit=limit)
    console.print(
        f"Loaded [bold]{len(loaded.products)}[/] products from {path.name} "
        f"({loaded.rows_read} rows, {loaded.duplicates} duplicate IDs, "
        f"{len(loaded.invalid)} invalid)"
    )
    for line_no, reason in loaded.invalid[:5]:
        console.print(f"  [yellow]skipped line {line_no}[/]: {reason}")
    products, norm = normalize(loaded.products)
    console.print(
        f"Normalized to [bold]{norm.output_products}[/] products: merged {norm.merged_rows} "
        f"duplicate listings; {norm.categories_before} -> {norm.categories_after} categories"
    )
    params = REPO_ROOT / "data" / "derived_params.json"
    if params.exists():
        prior = RatingPrior.load(params)
        products = apply_rating_prior(products, prior)
        console.print(f"Recomputed bayes_rating/value_score with empirical-Bayes prior m={prior.m}")
    else:
        console.print("[yellow]No data/derived_params.json; keeping source bayes_rating[/]")

    store = ProductStore(create_client(settings), settings.qdrant_collection)
    encoders = make_fake() if fake_encoders else build_encoders(settings)
    if recreate:
        store.ensure_collection(encoders.dense.dim, encoders.image.dim, recreate=True)
        console.print(f"[red]Recreated[/] collection {settings.qdrant_collection}")

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Embedding + upserting", total=len(products))
        report = run_ingest(
            products,
            store,
            encoders,
            ImageSource(image_dir, fetch=fetch_images),
            batch_size=batch_size,
            on_batch=lambda n: progress.advance(task, n),
        )

    console.print(
        f"Upserted {report.upserted}, skipped {report.skipped_existing} existing, "
        f"{report.with_image} with image vectors, {report.image_errors} unreadable images. "
        f"Collection now holds {store.count()} points."
    )

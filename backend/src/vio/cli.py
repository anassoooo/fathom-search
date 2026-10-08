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
    from vio.embeddings.fake import fake_encoders as make_fake
    from vio.embeddings.fastembed_impl import build_encoders
    from vio.ingest.images import ImageSource
    from vio.ingest.loader import load_products
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
        task = progress.add_task("Embedding + upserting", total=len(loaded.products))
        report = run_ingest(
            loaded.products,
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

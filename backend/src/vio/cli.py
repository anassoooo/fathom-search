"""`vio` command-line entry point."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TimeElapsedColumn

from vio import __version__
from vio.config import get_settings

if TYPE_CHECKING:
    from vio.llm.client import LLMClient

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
QUALITY_FLAGS = REPO_ROOT / "data" / "quality_flags.json"
FULL_CATALOG_MIN_ROWS = 5_000
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
    figures: Annotated[bool, typer.Option(help="Render PNG figures into the report.")] = False,
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

    if report.n_rows >= FULL_CATALOG_MIN_ROWS:
        import json

        flags, notes = report.flags(), report.annotations()
        findings = {pid: {"flags": fl, **notes.get(pid, {})} for pid, fl in flags.items()}
        QUALITY_FLAGS.write_text(json.dumps(findings, indent=0, sort_keys=True) + "\n", "utf-8")
        console.print(f"Wrote findings for {len(findings):,} rows -> {QUALITY_FLAGS}")

    out_dir.mkdir(parents=True, exist_ok=True)
    if figures:
        from vio.quality.figures import make_figures

        paths = make_figures(df, report, prior, out_dir / "figures")
        sections["Figures"] = "\n\n".join(
            f"![{p.stem.replace('_', ' ')}](figures/{p.name})" for p in paths
        )
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
    from vio.embeddings.fake import fake_encoders as make_fake
    from vio.embeddings.fastembed_impl import build_encoders
    from vio.ingest.images import ImageSource
    from vio.ingest.pipeline import ingest as run_ingest
    from vio.ingest.prepare import prepare_catalog
    from vio.store.qdrant import ProductStore, create_client

    if sample == (csv_path is not None):
        raise typer.BadParameter("pass exactly one of --csv PATH or --sample")
    path = SAMPLE_CSV if sample else csv_path
    assert path is not None
    if not path.exists():
        hint = " (see TASKS.md T002 to create the sample)" if sample else ""
        raise typer.BadParameter(f"{path} not found{hint}")

    settings = get_settings()
    prep = prepare_catalog(path, REPO_ROOT / "data", limit=limit)
    loaded, norm, products = prep.loaded, prep.normalized, prep.products
    console.print(
        f"Loaded [bold]{len(loaded.products)}[/] products from {path.name} "
        f"({loaded.rows_read} rows, {loaded.duplicates} duplicate IDs, "
        f"{len(loaded.invalid)} invalid)"
    )
    for line_no, reason in loaded.invalid[:5]:
        console.print(f"  [yellow]skipped line {line_no}[/]: {reason}")
    console.print(
        f"Normalized to [bold]{norm.output_products}[/] products: merged {norm.merged_rows} "
        f"duplicate listings; {norm.categories_before} -> {norm.categories_after} categories"
    )
    if prep.prior_m is None:
        console.print("[yellow]No data/derived_params.json; keeping source bayes_rating[/]")
    else:
        console.print(
            f"Recomputed bayes_rating/value_score with empirical-Bayes prior m={prep.prior_m}"
        )
    if prep.n_flagged is None:
        console.print("[yellow]No data/quality_flags.json; run `vio data audit` first[/]")
    else:
        console.print(f"Attached quality flags to {prep.n_flagged} products")

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


eval_app = typer.Typer(help="Offline evaluation (milestone M2).", no_args_is_help=True)
app.add_typer(eval_app, name="eval")
EVAL_DATA = REPO_ROOT / "data" / "eval"
EVAL_REPORTS = REPO_ROOT / "eval" / "reports"
QUERIES_V1 = EVAL_DATA / "queries_v1.jsonl"
QRELS_V1 = EVAL_DATA / "qrels_v1.jsonl"
LLM_CACHE = EVAL_DATA / ".llm_cache.sqlite"


def _refuse_overwrite(path: Path, force: bool) -> None:
    # Constitution Art. VII.4: versioned eval sets are never regenerated silently.
    if path.exists() and not force:
        raise typer.BadParameter(f"{path.name} exists; bump the version or pass --force")


def _llm() -> "LLMClient":
    from vio.llm.client import LLMClient

    settings = get_settings()
    if "localhost" in settings.llm_base_url:
        console.print("[yellow]LLM_BASE_URL points at localhost; set Groq in backend/.env[/]")
    return LLMClient.from_settings(settings, cache_path=LLM_CACHE)


@eval_app.command("gen-queries")
def eval_gen_queries(
    csv_path: Annotated[Path, typer.Option("--csv")] = REPO_ROOT
    / "data"
    / "processed"
    / "vio_EDA.csv",
    per_category: Annotated[int, typer.Option(min=1)] = 10,
    image_dir: Annotated[Path, typer.Option()] = REPO_ROOT / "data" / "images",
    force: Annotated[bool, typer.Option(help="Overwrite queries_v1.jsonl.")] = False,
) -> None:
    """Generate data/eval/queries_v1.jsonl from unflagged seed products (T031)."""
    from vio.eval.queries import generate, save
    from vio.ingest.prepare import prepare_catalog

    _refuse_overwrite(QUERIES_V1, force)
    settings = get_settings()
    products = prepare_catalog(csv_path, REPO_ROOT / "data").products
    llm = _llm()
    records = generate(
        products,
        llm,
        settings.llm_model_eval,
        image_dir=image_dir,
        out_dir=EVAL_DATA,
        per_category=per_category,
    )
    save(records, QUERIES_V1)
    counts: dict[str, int] = {}
    for r in records:
        counts[r.bucket] = counts.get(r.bucket, 0) + 1
    console.print(f"Wrote {len(records)} queries -> {QUERIES_V1}: {counts}")
    console.print(f"LLM usage: {llm.usage}")


@eval_app.command("judge")
def eval_judge(
    depth: Annotated[int, typer.Option(min=1, max=50)] = 20,
    limit: Annotated[int | None, typer.Option(help="Judge only the first N queries.")] = None,
    restart: Annotated[
        bool, typer.Option(help="Discard qrels_v1.jsonl and judge from scratch.")
    ] = False,
) -> None:
    """Pool every variant's results and grade them with the LLM judge (T032).

    Resumable: pairs already in qrels_v1.jsonl are kept and never re-sent to the judge."""
    from vio.api.app import build_service
    from vio.eval.judge import judge_all, load_judgments, save_qrels
    from vio.eval.queries import load

    existing = [] if restart else load_judgments(QRELS_V1)
    settings = get_settings()
    queries = load(QUERIES_V1)[:limit]
    service = build_service(settings)
    service.warmup()
    llm = _llm()
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Pooling + judging", total=len(queries))
        run = judge_all(
            queries,
            service,
            llm,
            settings.llm_model_eval,
            EVAL_DATA,
            existing=existing,
            depth=depth,
            on_query=lambda q: progress.advance(task),
        )
    save_qrels(run.judgments, QRELS_V1)
    console.print(
        f"Judged {run.judged_queries}/{len(queries)} queries "
        f"({len(run.judgments):,} pairs) -> {QRELS_V1}; LLM usage: {llm.usage}"
    )
    if run.skipped_queries:
        console.print(
            f"[yellow]{run.skipped_queries} queries skipped: {run.quota_message}[/]\n"
            "Re-run `vio eval judge` after the quota resets; judgments are kept and resumed."
        )
        raise typer.Exit(code=2)


@eval_app.command("retrieval")
def eval_retrieval(
    variants: Annotated[
        str, typer.Option(help="Comma-separated variants.")
    ] = "bm25,dense,hybrid,hybrid_rerank",
) -> None:
    """Score retrieval variants on the judged set and write eval/reports/<date>-<sha>.md (T034)."""
    from vio.api.app import build_service
    from vio.eval.judge import load_qrels
    from vio.eval.queries import load
    from vio.eval.retrieval import run, write_report

    settings = get_settings()
    queries, qrels = load(QUERIES_V1), load_qrels(QRELS_V1)
    service = build_service(settings)
    service.warmup()
    from typing import get_args

    from vio.models import Variant

    allowed: tuple[Variant, ...] = get_args(Variant)
    names: list[Variant] = []
    for raw in variants.split(","):
        name = raw.strip()
        if name not in allowed:
            raise typer.BadParameter(f"unknown variant {name!r}; choose from {allowed}")
        names.append(name)
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scoring", total=len(queries) * len(names))
        results = run(
            queries, qrels, service, names, EVAL_DATA, on_step=lambda: progress.advance(task)
        )
    first = QRELS_V1.read_text("utf-8").splitlines()[0]
    judge_model = str(json.loads(first).get("judge_model", "?"))
    md = write_report(
        results,
        queries,
        qrels,
        EVAL_REPORTS,
        {
            "queries": QUERIES_V1.relative_to(REPO_ROOT).as_posix(),
            "judge_model": judge_model,
            "collection": settings.qdrant_collection,
            "n_points": str(service.store.count()),
        },
    )
    console.print(f"Report: {md}")


@eval_app.command("audit")
def eval_audit(
    n: Annotated[int, typer.Option(min=10, help="Pairs to grade (stratified).")] = 100,
) -> None:
    """Grade a stratified sample of judged pairs yourself; reports judge agreement (T033)."""
    from vio.eval.audit import agreement, run_audit, stratified_sample, summary_json
    from vio.eval.judge import Judgment, describe_request
    from vio.eval.queries import load
    from vio.ingest.prepare import prepare_catalog

    queries = {q.qid: q for q in load(QUERIES_V1)}
    judgments = [
        Judgment.model_validate_json(line) for line in QRELS_V1.read_text("utf-8").splitlines()
    ]
    products = {
        p.product_id: p
        for p in prepare_catalog(
            REPO_ROOT / "data" / "processed" / "vio_EDA.csv", REPO_ROOT / "data"
        ).products
    }

    def describe(j: Judgment) -> str:
        q = queries[j.qid]
        p = products.get(j.product_id)
        seed = products.get(q.seed_product_id or "")
        item = (
            f"{p.name}\n  category: {p.subcategory or p.category} | price: ${p.price}"
            if p
            else j.product_id
        )
        return f"REQUEST: {describe_request(q, seed)}\nPRODUCT: {item}"

    console.print(
        "Grade each product for the request: [bold]2[/] exact match, [bold]1[/] partial "
        "(related / over budget), [bold]0[/] irrelevant. The judge's grade is hidden."
    )
    out = EVAL_DATA / "human_audit_v1.jsonl"
    labels = run_audit(stratified_sample(judgments, queries, n), describe, input, out)
    (EVAL_DATA / "human_audit_v1_summary.json").write_text(summary_json(labels) + "\n", "utf-8")
    console.print(f"Agreement with the judge: {agreement(labels)}")


@eval_app.command("understanding")
def eval_understanding() -> None:
    """Measure LLM query understanding against ground truth in queries_v1 (T042)."""
    from vio.eval.queries import load
    from vio.eval.retrieval import _git_sha
    from vio.eval.understanding import run, write_report
    from vio.ingest.prepare import prepare_catalog
    from vio.llm.query_understanding import QueryUnderstanding

    settings = get_settings()
    products = {
        p.product_id: p
        for p in prepare_catalog(
            REPO_ROOT / "data" / "processed" / "vio_EDA.csv", REPO_ROOT / "data"
        ).products
    }
    categories = sorted({c for p in products.values() for c in p.categories})
    qu = QueryUnderstanding(_llm(), settings.llm_model_query, lambda: categories)
    queries = load(QUERIES_V1)
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing", total=sum(q.bucket != "image" for q in queries))
        results, stopped = run(queries, qu, on_step=lambda: progress.advance(task))
    path = write_report(
        results,
        products,
        EVAL_REPORTS,
        {
            "sha": _git_sha(),
            "model": settings.llm_model_query,
            "effort": str(settings.llm_reasoning_effort),
        },
        stopped,
    )
    console.print(f"Report: {path}")
    if stopped:
        console.print(f"[yellow]Stopped early: {stopped}. Re-run later; parses are cached.[/]")


@app.command("export-openapi")
def export_openapi(
    out: Annotated[Path, typer.Option(help="Where to write the schema.")] = REPO_ROOT
    / "backend"
    / "openapi.json",
) -> None:
    """Write the API's OpenAPI schema (consumed by web/ to generate TypeScript types)."""
    from vio.api.app import create_app

    schema = create_app(settings=get_settings()).openapi()
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    console.print(f"Wrote {out} ({len(schema.get('paths', {}))} paths)")

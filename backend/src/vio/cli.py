"""`vio` command-line entry point. Subcommands are added as their modules land."""

import typer

from vio import __version__
from vio.config import get_settings

app = typer.Typer(
    help="VIO: multimodal product search, assistant, and evaluation.", no_args_is_help=True
)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def config() -> None:
    """Print the effective configuration (secrets are masked)."""
    typer.echo(get_settings().model_dump_json(indent=2))

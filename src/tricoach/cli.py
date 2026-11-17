"""Command-line entry point. No logic here: parse arguments, call a module, report."""

from pathlib import Path
from typing import Annotated

import typer

from tricoach.ingest import format_blocks, load_epub

app = typer.Typer(help="Q&A assistant over The Triathlete's Training Bible.", no_args_is_help=True)

DEFAULT_DUMP = Path("data/processed/blocks_dump.txt")


@app.callback()
def main() -> None:
    """Keep subcommands explicit (`tricoach dump ...`) even while there is only one."""


@app.command()
def dump(
    book: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="ePub file.")],
    output: Annotated[Path, typer.Option(help="Where to write the dump.")] = DEFAULT_DUMP,
) -> None:
    """Write the raw loader output (before cleaning) to a text file for inspection."""
    blocks = load_epub(book)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_blocks(blocks), encoding="utf-8")
    typer.echo(f"{len(blocks)} blocks written to {output}")

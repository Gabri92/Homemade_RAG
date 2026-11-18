"""Command-line entry point. No logic here: parse arguments, call a module, report."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from tricoach.ingest import (
    clean,
    format_blocks,
    format_report,
    ingest_epub,
    inspect_epub,
    load_epub,
    save_book,
)

app = typer.Typer(help="Q&A assistant over The Triathlete's Training Bible.", no_args_is_help=True)

PROCESSED = Path("data/processed")


@app.callback()
def main() -> None:
    """Keep subcommands explicit (`tricoach dump ...`)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


@app.command()
def ingest(
    book: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="ePub file.")],
    output: Annotated[Path, typer.Option(help="Where to write the book.")] = PROCESSED
    / "book.json",
) -> None:
    """Load, clean and structure the book into sections; write book.json."""
    structured = ingest_epub(book)
    save_book(structured, output)
    included = sum(s.include for s in structured.sections)
    typer.echo(f"{len(structured.sections)} sections ({included} included) written to {output}")


@app.command()
def inspect(
    book: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="ePub file.")],
) -> None:
    """Print a generic ingestion quality report (counts only, no book text)."""
    report = inspect_epub(book)
    typer.echo(format_report(report), nl=False)
    if any(check.warning for check in report):
        raise typer.Exit(code=1)


@app.command()
def dump(
    book: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="ePub file.")],
    cleaned: Annotated[
        bool, typer.Option("--clean", help="Apply the Cleaner before dumping.")
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(help="Where to write the dump [default: data/processed/blocks_<stage>.txt]."),
    ] = None,
) -> None:
    """Write the loader output (raw, or cleaned with --clean) to a text file for inspection."""
    blocks = clean(load_epub(book)) if cleaned else load_epub(book)
    output = output or PROCESSED / f"blocks_{'clean' if cleaned else 'raw'}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_blocks(blocks), encoding="utf-8")
    typer.echo(f"{len(blocks)} blocks written to {output}")

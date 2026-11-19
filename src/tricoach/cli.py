"""Command-line entry point. No logic here: parse arguments, call a module, report."""

import logging
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from tricoach.eval.dataset import check_references, load_golden
from tricoach.ingest import (
    clean,
    format_blocks,
    format_report,
    format_sections,
    ingest_epub,
    inspect_epub,
    load_book,
    load_epub,
    save_book,
)

app = typer.Typer(help="Q&A assistant over The Triathlete's Training Bible.", no_args_is_help=True)
eval_app = typer.Typer(help="Golden dataset and evaluation.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")

PROCESSED = Path("data/processed")
GOLDEN = Path("eval/datasets/golden.jsonl")


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


@app.command()
def sections(
    book: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="book.json from `tricoach ingest`.")
    ] = PROCESSED / "book.json",
    output: Annotated[Path, typer.Option(help="Where to write the list.")] = PROCESSED
    / "sections.txt",
) -> None:
    """List section ids, pages and excluded flags (no book text): the ids the golden set cites."""
    structured = load_book(book)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_sections(structured), encoding="utf-8")
    typer.echo(f"{len(structured.sections)} sections written to {output}")


@eval_app.command("check")
def eval_check(
    golden: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="Golden-set JSONL file.")
    ] = GOLDEN,
    book: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="book.json from `tricoach ingest`.")
    ] = PROCESSED / "book.json",
) -> None:
    """Validate the golden set and check that every cited section is in the book index."""
    try:
        questions = load_golden(golden)
        problems = check_references(questions, load_book(book))
    except ValueError as error:
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    counts = Counter(question.category for question in questions)
    typer.echo(f"{len(questions)} questions: " + ", ".join(f"{c} {n}" for c, n in counts.items()))
    for problem in problems:
        typer.echo(f"ERROR {problem}")
    if problems:
        raise typer.Exit(code=1)

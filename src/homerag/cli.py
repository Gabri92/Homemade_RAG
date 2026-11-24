"""Command-line entry point. No logic here: parse arguments, call a module, report."""

import logging
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from homerag.config import load_experiment
from homerag.eval.dataset import check_references, load_golden
from homerag.eval.run import format_gate, format_metrics, run_experiment
from homerag.index import ensure_index
from homerag.ingest import (
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
from homerag.retrieval import format_results, search

app = typer.Typer(
    help="NotebookLM-style Q&A with citations over your documents.", no_args_is_help=True
)
eval_app = typer.Typer(help="Golden dataset and evaluation.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")

PROCESSED = Path("data/processed")
GOLDEN = Path("eval/datasets/golden.jsonl")
BASELINE = Path("configs/experiments/baseline.yaml")


@app.callback()
def main() -> None:
    """Keep subcommands explicit (`homerag dump ...`)."""
    # Our own progress messages at INFO; libraries (model hub requests, model loading) only
    # when something goes wrong.
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logging.getLogger("homerag").setLevel(logging.INFO)


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
        Path, typer.Option(exists=True, dir_okay=False, help="book.json from `homerag ingest`.")
    ] = PROCESSED / "book.json",
    output: Annotated[Path, typer.Option(help="Where to write the list.")] = PROCESSED
    / "sections.txt",
) -> None:
    """List section ids, pages and excluded flags (no book text): the ids the golden set cites."""
    structured = load_book(book)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_sections(structured), encoding="utf-8")
    typer.echo(f"{len(structured.sections)} sections written to {output}")


@app.command()
def index(
    config: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Experiment YAML.")
    ] = BASELINE,
) -> None:
    """Chunk and embed the document of an experiment, or reuse its index if up to date."""
    try:
        report = ensure_index(load_experiment(config))
    except (ValueError, OSError) as error:  # bad config, stale index, missing book.json
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    action = f"built in {report.seconds:.1f}s" if report.built else "up to date, reused"
    typer.echo(f"{report.chunks} chunks, {action}: {report.folder}")


@app.command("search")
def search_command(
    question: Annotated[str, typer.Argument(help="The question, in quotes.")],
    config: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Experiment YAML.")
    ] = BASELINE,
    text: Annotated[
        bool, typer.Option("--text", help="Show a short snippet of each chunk (local use).")
    ] = False,
) -> None:
    """Show which chunks the retriever ranks highest for a question (no LLM involved)."""
    try:
        results = search(question, load_experiment(config))
    except (ValueError, OSError) as error:  # bad config, missing index, missing book.json
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    typer.echo(format_results(results, show_text=text), nl=False)


@eval_app.command("check")
def eval_check(
    golden: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="Golden-set JSONL file.")
    ] = GOLDEN,
    book: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="book.json from `homerag ingest`.")
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


@eval_app.command("run")
def eval_run(
    config: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Experiment YAML.")
    ] = BASELINE,
    golden: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Golden-set JSONL file.")
    ] = GOLDEN,
) -> None:
    """Run an experiment on the golden set (retrieval + language gate) and save it in eval/runs/."""
    try:
        report = run_experiment(config, golden)
    except (ValueError, OSError) as error:  # bad config or golden set, missing book.json
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    typer.echo(format_metrics(report.metrics), nl=False)
    typer.echo(format_gate(report.gate, report.gate_errors), nl=False)
    if report.skipped:
        skipped = ", ".join(f"{c} {n}" for c, n in report.skipped.items())
        typer.echo(f"not scored on retrieval (no cited sections): {skipped}")
    typer.echo(f"saved to {report.folder}")

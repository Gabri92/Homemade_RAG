"""Command-line entry point. No logic here: parse arguments, call a module, report."""

import logging
from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from homerag.config import load_documents, load_experiment, load_settings
from homerag.eval.dataset import check_references, load_golden
from homerag.eval.report import compare_runs, format_cost, format_gate, format_metrics, load_run
from homerag.eval.run import RUNS_ROOT, run_experiment
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
from homerag.qa import answer, format_answer, load_resources
from homerag.retrieval import format_results, search

app = typer.Typer(
    help="NotebookLM-style Q&A with citations over your documents.", no_args_is_help=True
)
eval_app = typer.Typer(help="Golden dataset and evaluation.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")

PROCESSED = Path("data/processed")
GOLDEN = Path("eval/datasets/golden.jsonl")
BASELINE = Path("configs/experiments/baseline.yaml")
DOCUMENTS = Path("configs/documents.yaml")


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


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="The question, in English, in quotes.")],
    config: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Experiment YAML.")
    ] = BASELINE,
) -> None:
    """Answer one question from the document, with citations (calls the Claude API)."""
    try:
        cfg = load_experiment(config)
        resources = load_resources(cfg, load_settings())
        result = answer(question, resources, cfg)
    except (ValueError, OSError) as error:  # bad config, missing index or API key
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    typer.echo(format_answer(result), nl=False)


@app.command()
def chat(
    documents: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="Documents to offer (YAML).")
    ] = DOCUMENTS,
    port: Annotated[int, typer.Option(help="Port on this machine.")] = 7860,
) -> None:
    """Open the web chat on this machine: http://127.0.0.1:<port> (calls the Claude API)."""
    # Imported here: gradio takes seconds to import, and only this command needs it.
    from homerag.chat import launch, open_documents  # noqa: PLC0415

    try:
        opened = open_documents(load_documents(documents), load_settings())
    except (ValueError, OSError) as error:  # bad list or config, missing index or API key
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    typer.echo(f"Chat on http://127.0.0.1:{port} (Ctrl+C to stop)")
    launch(opened, port)


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
    retrieval_only: Annotated[
        bool,
        typer.Option("--retrieval-only", help="Skip answers and judge: free, no API key needed."),
    ] = False,
) -> None:
    """Run an experiment on the golden set and save it in eval/runs/.

    Gate, retrieval, then answers graded by the judge (about $1 the first time; a repeated
    run is served from the cache).
    """
    try:
        report = run_experiment(config, golden, retrieval_only=retrieval_only)
    except (ValueError, OSError) as error:  # bad config or golden set, missing book.json or key
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    typer.echo("retrieval")
    typer.echo(format_metrics(report.metrics["retrieval"]), nl=False)
    if report.skipped:
        skipped = ", ".join(f"{c} {n}" for c, n in report.skipped.items())
        typer.echo(f"not scored on retrieval (no cited sections): {skipped}")
    if report.metrics["generation"]:
        typer.echo("\ngeneration")
        typer.echo(format_metrics(report.metrics["generation"]), nl=False)
        typer.echo(format_cost(report.cost), nl=False)
    typer.echo("")
    typer.echo(format_gate(report.metrics["gate"]["all"], report.gate_errors), nl=False)
    typer.echo(f"saved to {report.folder}")


@eval_app.command("compare")
def eval_compare(
    run_a: Annotated[str, typer.Argument(help="First run: folder, or its name in eval/runs/.")],
    run_b: Annotated[str, typer.Argument(help="Second run, compared with the first.")],
) -> None:
    """Compare two saved runs: metric changes per category and the questions that changed."""
    try:
        a, b = (load_run(_run_folder(name)) for name in (run_a, run_b))
    except ValueError as error:
        typer.echo(f"ERROR {error}")
        raise typer.Exit(code=1) from error
    typer.echo(compare_runs(a, b), nl=False)


def _run_folder(name: str) -> Path:
    path = Path(name)
    return path if path.exists() else RUNS_ROOT / name

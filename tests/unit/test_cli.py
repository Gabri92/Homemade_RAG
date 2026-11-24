"""Smoke tests: each command starts, rejects bad input and reports. Logic is tested in modules."""

import json
from pathlib import Path

from typer.testing import CliRunner

from homerag.cli import app
from tests.conftest import MakeEpub

runner = CliRunner()


def test_dump_writes_blocks_to_output_file(make_epub: MakeEpub, tmp_path: Path) -> None:
    book = make_epub([("ch01.xhtml", "<h1>Chapter One</h1><p>First.</p>")])
    output = tmp_path / "out" / "dump.txt"

    result = runner.invoke(app, ["dump", str(book), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "2 blocks written" in result.output
    assert "Chapter One" in output.read_text(encoding="utf-8")


def test_dump_clean_applies_the_cleaner(make_epub: MakeEpub, tmp_path: Path) -> None:
    book = make_epub(
        [("ch01.xhtml", "<p>Scoring:</p><table><tr><td>A</td></tr><tr><td>1</td></tr></table>")]
    )
    output = tmp_path / "clean.txt"

    result = runner.invoke(app, ["dump", str(book), "--clean", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "1 blocks written" in result.output  # intro paragraph attached to its table


def test_ingest_writes_book_json(make_epub: MakeEpub, tmp_path: Path) -> None:
    book = make_epub([("ch01.xhtml", "<h1>Chapter One</h1><p>First.</p>")])
    output = tmp_path / "book.json"

    result = runner.invoke(app, ["ingest", str(book), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "1 sections (1 included)" in result.output
    assert '"schema_version": 2' in output.read_text(encoding="utf-8")


def test_inspect_prints_the_report_and_exits_0_without_warnings(make_epub: MakeEpub) -> None:
    page = '<span epub:type="pagebreak" aria-label=" page 1. "></span>'
    book = make_epub([("ch01.xhtml", f"{page}<h1>Chapter One</h1><p>First.</p>")])

    result = runner.invoke(app, ["inspect", str(book)])

    assert result.exit_code == 0, result.output
    assert "text coverage" in result.output


def test_inspect_exits_1_when_there_are_warnings(make_epub: MakeEpub) -> None:
    book = make_epub([("ch01.xhtml", "<p>No headings at all.</p>")])

    result = runner.invoke(app, ["inspect", str(book)])

    assert result.exit_code == 1
    assert "WARNING" in result.output


def test_sections_lists_ids_without_book_text(make_epub: MakeEpub, tmp_path: Path) -> None:
    book = tmp_path / "book.json"
    runner.invoke(
        app,
        [
            "ingest",
            str(make_epub([("ch01.xhtml", "<h1>Chapter One</h1><p>First.</p>")])),
            "--output",
            str(book),
        ],
    )
    output = tmp_path / "sections.txt"

    result = runner.invoke(app, ["sections", "--book", str(book), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "1 sections written" in result.output
    listing = output.read_text(encoding="utf-8")
    assert listing.startswith("chapter-one")
    assert "First." not in listing


def test_sections_rejects_missing_book(tmp_path: Path) -> None:
    result = runner.invoke(app, ["sections", "--book", str(tmp_path / "missing.json")])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def _golden_and_book(make_epub: MakeEpub, tmp_path: Path, section_id: str) -> list[str]:
    book = tmp_path / "book.json"
    epub = make_epub([("ch01.xhtml", "<h1>Chapter One</h1><p>First.</p>")])
    runner.invoke(app, ["ingest", str(epub), "--output", str(book)])
    question = {
        "id": "q-001",
        "question": "What comes first?",
        "category": "factual",
        "reference_answer": "The first paragraph.",
        "relevant_section_ids": [section_id],
    }
    golden = tmp_path / "golden.jsonl"
    golden.write_text(json.dumps(question) + "\n", encoding="utf-8")
    return ["eval", "check", str(golden), "--book", str(book)]


def test_eval_check_reports_counts_and_exits_0(make_epub: MakeEpub, tmp_path: Path) -> None:
    result = runner.invoke(app, _golden_and_book(make_epub, tmp_path, "chapter-one"))

    assert result.exit_code == 0, result.output
    assert "1 questions: factual 1" in result.output


def test_eval_check_exits_1_on_unknown_section(make_epub: MakeEpub, tmp_path: Path) -> None:
    result = runner.invoke(app, _golden_and_book(make_epub, tmp_path, "renamed"))

    assert result.exit_code == 1
    assert "unknown section 'renamed'" in result.output


def test_eval_check_exits_1_on_invalid_golden_file(make_epub: MakeEpub, tmp_path: Path) -> None:
    args = _golden_and_book(make_epub, tmp_path, "chapter-one")
    Path(args[2]).write_text("{not json\n", encoding="utf-8")

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_dump_rejects_missing_book(tmp_path: Path) -> None:
    result = runner.invoke(app, ["dump", str(tmp_path / "missing.epub")])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_index_exits_1_on_invalid_config(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("name: bad\n", encoding="utf-8")

    result = runner.invoke(app, ["index", "--config", str(config)])

    assert result.exit_code == 1
    assert "ERROR" in result.output


def test_search_exits_1_when_the_index_is_missing(tmp_path: Path) -> None:
    config = tmp_path / "exp.yaml"
    baseline = Path("configs/experiments/baseline.yaml").read_text(encoding="utf-8")
    config.write_text(
        baseline.replace("data/processed/book.json", (tmp_path / "none.json").as_posix()),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["search", "How long is the base period?", "--config", str(config)])

    assert result.exit_code == 1
    assert "ERROR" in result.output


def test_eval_run_exits_1_on_invalid_config(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("name: bad\n", encoding="utf-8")
    golden = tmp_path / "golden.jsonl"
    golden.write_text("", encoding="utf-8")

    result = runner.invoke(app, ["eval", "run", "--config", str(config), "--golden", str(golden)])

    assert result.exit_code == 1
    assert "ERROR" in result.output


def test_ask_exits_1_on_invalid_config(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("name: bad\n", encoding="utf-8")

    result = runner.invoke(app, ["ask", "How long is the base period?", "--config", str(config)])

    assert result.exit_code == 1
    assert "ERROR" in result.output

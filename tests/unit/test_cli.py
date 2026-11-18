"""Smoke tests: each command starts, rejects bad input and reports. Logic is tested in modules."""

from pathlib import Path

from typer.testing import CliRunner

from tests.conftest import MakeEpub
from tricoach.cli import app

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
    assert '"schema_version": 1' in output.read_text(encoding="utf-8")


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


def test_dump_rejects_missing_book(tmp_path: Path) -> None:
    result = runner.invoke(app, ["dump", str(tmp_path / "missing.epub")])

    assert result.exit_code != 0
    assert "does not exist" in result.output

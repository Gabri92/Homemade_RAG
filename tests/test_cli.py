"""Smoke tests: each command starts, rejects bad input and reports. Logic is tested in modules."""

from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from tricoach.cli import app

runner = CliRunner()


def test_dump_writes_blocks_to_output_file(
    make_epub: Callable[[list[tuple[str, str]]], Path], tmp_path: Path
) -> None:
    book = make_epub([("ch01.xhtml", "<h1>Chapter One</h1><p>First.</p>")])
    output = tmp_path / "out" / "dump.txt"

    result = runner.invoke(app, ["dump", str(book), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "2 blocks written" in result.output
    assert "Chapter One" in output.read_text(encoding="utf-8")


def test_dump_clean_applies_the_cleaner(
    make_epub: Callable[[list[tuple[str, str]]], Path], tmp_path: Path
) -> None:
    book = make_epub(
        [("ch01.xhtml", "<p>Scoring:</p><table><tr><td>A</td></tr><tr><td>1</td></tr></table>")]
    )
    output = tmp_path / "clean.txt"

    result = runner.invoke(app, ["dump", str(book), "--clean", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert "1 blocks written" in result.output  # intro paragraph attached to its table


def test_dump_rejects_missing_book(tmp_path: Path) -> None:
    result = runner.invoke(app, ["dump", str(tmp_path / "missing.epub")])

    assert result.exit_code != 0
    assert "does not exist" in result.output

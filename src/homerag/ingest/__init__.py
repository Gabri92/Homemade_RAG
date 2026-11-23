"""Ingestion: source file -> blocks -> cleaning -> sections (Book) -> book.json.

Callers import from `homerag.ingest`, never from the submodules: the split into
files is an internal detail that can change.
"""

from pathlib import Path

from homerag.ingest.book_file import SCHEMA_VERSION, load_book, save_book
from homerag.ingest.cleaning import (
    CLEANING_STEPS,
    attach_intro_to_untitled_tables,
    clean,
    merge_continued_tables,
    remove_pull_quotes,
)
from homerag.ingest.dump import format_blocks, format_sections
from homerag.ingest.epub import epub_text, html_to_blocks, load_epub
from homerag.ingest.quality import Check, format_report, quality_report
from homerag.ingest.structure import mark_front_matter, structure
from homerag.models import Book


def ingest_epub(path: Path) -> Book:
    """The whole ingestion of an ePub: load, clean, structure."""
    return structure(clean(load_epub(path)), source=path.name)


def inspect_epub(path: Path) -> list[Check]:
    """Ingest an ePub and return its generic quality report."""
    raw = load_epub(path)
    return quality_report(raw, structure(clean(raw), source=path.name), epub_text(path))


__all__ = [
    "CLEANING_STEPS",
    "SCHEMA_VERSION",
    "Check",
    "attach_intro_to_untitled_tables",
    "clean",
    "epub_text",
    "format_blocks",
    "format_report",
    "format_sections",
    "html_to_blocks",
    "ingest_epub",
    "inspect_epub",
    "load_book",
    "load_epub",
    "mark_front_matter",
    "merge_continued_tables",
    "quality_report",
    "remove_pull_quotes",
    "save_book",
    "structure",
]

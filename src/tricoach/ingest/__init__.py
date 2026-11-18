"""Ingestion: source file -> blocks -> cleaning -> sections (Book) -> book.json.

Callers import from `tricoach.ingest`, never from the submodules: the split into
files is an internal detail that can change.
"""

from pathlib import Path

from tricoach.ingest.book_file import SCHEMA_VERSION, load_book, save_book
from tricoach.ingest.cleaning import (
    CLEANING_STEPS,
    attach_intro_to_untitled_tables,
    clean,
    merge_continued_tables,
    remove_pull_quotes,
)
from tricoach.ingest.dump import format_blocks
from tricoach.ingest.epub import html_to_blocks, load_epub
from tricoach.ingest.structure import mark_front_matter, structure
from tricoach.models import Book


def ingest_epub(path: Path) -> Book:
    """The whole ingestion of an ePub: load, clean, structure."""
    return structure(clean(load_epub(path)), source=path.name)


__all__ = [
    "CLEANING_STEPS",
    "SCHEMA_VERSION",
    "attach_intro_to_untitled_tables",
    "clean",
    "format_blocks",
    "html_to_blocks",
    "ingest_epub",
    "load_book",
    "load_epub",
    "mark_front_matter",
    "merge_continued_tables",
    "remove_pull_quotes",
    "save_book",
    "structure",
]

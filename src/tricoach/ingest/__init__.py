"""Ingestion: source file -> blocks -> (cleaning) -> sections.

Callers import from `tricoach.ingest`, never from the submodules: the split into
files is an internal detail that can change.
"""

from tricoach.ingest.cleaning import (
    CLEANING_STEPS,
    attach_intro_to_untitled_tables,
    clean,
    merge_continued_tables,
)
from tricoach.ingest.dump import format_blocks
from tricoach.ingest.epub import html_to_blocks, load_epub

__all__ = [
    "CLEANING_STEPS",
    "attach_intro_to_untitled_tables",
    "clean",
    "format_blocks",
    "html_to_blocks",
    "load_epub",
    "merge_continued_tables",
]

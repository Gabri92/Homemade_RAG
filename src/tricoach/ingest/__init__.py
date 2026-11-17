"""Ingestion: source file -> blocks -> (cleaning) -> sections.

Callers import from `tricoach.ingest`, never from the submodules: the split into
files is an internal detail that can change.
"""

from tricoach.ingest.dump import format_blocks
from tricoach.ingest.epub import html_to_blocks, load_epub

__all__ = ["format_blocks", "html_to_blocks", "load_epub"]

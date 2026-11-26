"""Shared fixtures. All book content here is synthetic: never use text from the real book."""

from collections.abc import Callable
from pathlib import Path

import pytest
from ebooklib import epub

from homerag.ingest import html_to_blocks
from homerag.models import Block

MakeEpub = Callable[[list[tuple[str, str]]], Path]


@pytest.fixture
def make_epub(tmp_path: Path) -> MakeEpub:
    """Build a minimal ePub from (file_name, body_html) chapters, in the given spine order."""

    def build(chapters: list[tuple[str, str]]) -> Path:
        book = epub.EpubBook()
        book.set_identifier("synthetic-book")
        book.set_title("Synthetic Training Book")
        book.set_language("en")

        items = []
        for file_name, body in chapters:
            item = epub.EpubHtml(title=file_name, file_name=file_name, lang="en")
            item.content = f"<html><body>{body}</body></html>"
            book.add_item(item)
            items.append(item)

        book.toc = items
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", *items]

        path = tmp_path / "book.epub"
        epub.write_epub(str(path), book)
        return path

    return build


SOURCE = "ch01.xhtml"


def blocks_of(html: str) -> list[Block]:
    """Blocks of a synthetic document body, as the loader converts one file."""
    return html_to_blocks(f"<html><body>{html}</body></html>", source=SOURCE)


def page_marker(label: str) -> str:
    """An EPUB printed-page marker, as publishers write it."""
    return f'<span epub:type="pagebreak" id="page_{label}" aria-label=" page {label}. "></span>'

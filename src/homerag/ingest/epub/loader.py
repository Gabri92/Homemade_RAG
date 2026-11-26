"""ePub container -> blocks: spine order, navigation, roles and pages across files.

The only ingestion code that reads the ePub container; each document is converted by
`html.py`, and everything downstream works on `Block`s.
"""

import posixpath
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub

from homerag.ingest.epub.html import last_page, parse, soup_to_blocks
from homerag.ingest.epub.roles import file_types, landmark_types, role_from_types
from homerag.models import Block


def load_epub(path: Path) -> list[Block]:
    """Read an ePub and return its content blocks in reading (spine) order.

    Navigation documents (table of contents) are skipped: they are not book content.
    Each block gets the role of its file (from the landmarks and the file's own
    epub:type) and the printed page where it starts (from the page markers); the page
    carries over between files.
    """
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    landmarks = _book_landmark_types(book)
    blocks: list[Block] = []
    page: str | None = None
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None or not _is_book_content(item):
            continue
        name = item.get_name()
        soup = parse(item.get_content())
        role = role_from_types(landmarks.get(posixpath.basename(name), []) + file_types(soup))
        blocks.extend(soup_to_blocks(soup, name, role, page))
        page = last_page(soup, page)
    return blocks


def epub_text(path: Path) -> str:
    """All visible text of the book's content documents: the reference for text coverage."""
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    texts = []
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is not None and _is_book_content(item):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            texts.append((soup.body or soup).get_text(" "))
    return "\n".join(texts)


def _is_book_content(item: epub.EpubItem) -> bool:
    # ebooklib types the EPUB3 navigation page as a regular document (ITEM_DOCUMENT):
    # only its class tells it apart.
    return item.get_type() == ebooklib.ITEM_DOCUMENT and not isinstance(item, epub.EpubNav)


def _book_landmark_types(book: epub.EpubBook) -> dict[str, list[str]]:
    for item in book.get_items():
        if isinstance(item, epub.EpubNav):
            return landmark_types(item.get_content())
    return {}

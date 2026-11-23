"""Tests on the real book: every test in this folder is marked `book` and skipped when the
book is not in data/raw/ (it is never committed). Shared fixtures load it once per session.
"""

from pathlib import Path

import pytest

from homerag.ingest import clean, load_epub, structure
from homerag.models import Block, Book
from tests.book import expectations as expected

_HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip = pytest.mark.skip(reason="book not in data/raw/")
    for item in items:
        if _HERE in item.path.parents:
            item.add_marker(pytest.mark.book)
            if not expected.BOOK_PATH.exists():
                item.add_marker(skip)


@pytest.fixture(scope="session")
def blocks() -> list[Block]:
    """Raw loader output."""
    return load_epub(expected.BOOK_PATH)


@pytest.fixture(scope="session")
def cleaned(blocks: list[Block]) -> list[Block]:
    """Output after the Cleaner."""
    return clean(blocks)


@pytest.fixture(scope="session")
def book(cleaned: list[Block]) -> Book:
    """Output after the Structurer."""
    return structure(cleaned, source=expected.BOOK_PATH.name)

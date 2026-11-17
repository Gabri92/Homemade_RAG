"""Regression checks on the real book: findings in docs/ingestion-findings.md must not come back.

Skipped automatically when the book is not in data/raw/ (it is never committed).
"""

import book_expectations as expected  # tests/ is on sys.path (pytest rootdir-relative import)
import pytest

from tricoach.ingest import clean, load_epub
from tricoach.models import Block

pytestmark = [
    pytest.mark.book,
    pytest.mark.skipif(not expected.BOOK_PATH.exists(), reason="book not in data/raw/"),
]


@pytest.fixture(scope="module")
def blocks() -> list[Block]:
    """Raw loader output."""
    return load_epub(expected.BOOK_PATH)


@pytest.fixture(scope="module")
def cleaned(blocks: list[Block]) -> list[Block]:
    """Output after the Cleaner."""
    return clean(blocks)


def tables(blocks: list[Block]) -> list[Block]:
    return [b for b in blocks if b.kind == "table"]


def figures(blocks: list[Block]) -> list[Block]:
    return [b for b in blocks if b.kind == "figure"]


def first_word(block: Block) -> str:
    return block.text.split(" ", 1)[0]


# --- finding #1: table titles ------------------------------------------------------


def test_book_tables_keep_their_titles(blocks: list[Block]) -> None:
    titled = [t for t in tables(blocks) if t.text.startswith("TABLE ")]

    assert len(tables(blocks)) == expected.TABLES
    assert len(titled) == expected.TABLES_WITH_TITLE


def test_book_table_title_is_on_the_same_block_as_its_rows(blocks: list[Block]) -> None:
    table = next(t for t in tables(blocks) if t.text.startswith(expected.TABLE_11_1_TITLE))

    assert table.text.splitlines()[1].startswith("| ")


# --- finding #2: merged cells ------------------------------------------------------


def test_book_table_9_2_rows_keep_their_period(blocks: list[Block]) -> None:
    table = next(t for t in tables(blocks) if t.text.startswith("TABLE 9.2"))
    body_rows = table.text.splitlines()[3:]  # skip title, header and separator

    first_cells = {row.split("|")[1].strip() for row in body_rows}

    assert first_cells == expected.TABLE_9_2_PERIODS


# --- finding #3: figures -----------------------------------------------------------


def test_book_figures_are_kept(blocks: list[Block]) -> None:
    by_first_word = [first_word(f) for f in figures(blocks)]

    assert len(by_first_word) == expected.FIGURES
    assert by_first_word.count("FIGURE") == expected.FIGURES_CAPTIONED_FIGURE
    assert by_first_word.count("TABLE") == expected.TABLES_PUBLISHED_AS_IMAGES


def test_book_captions_are_not_duplicated_as_paragraphs(blocks: list[Block]) -> None:
    leaked = [b for b in blocks if b.kind == "paragraph" and first_word(b) in ("FIGURE", "TABLE")]

    assert leaked == []


# --- finding #8: split tables (after cleaning) -------------------------------------


def test_book_split_weekly_plans_are_one_table(cleaned: list[Block]) -> None:
    for title in expected.SPLIT_PLAN_TABLES:
        plan = next(t for t in tables(cleaned) if t.text.startswith(title))

        assert all(week in plan.text for week in expected.SPLIT_PLAN_WEEKS), title


def test_book_cleaner_merges_only_the_continuation_tables(
    blocks: list[Block], cleaned: list[Block]
) -> None:
    assert len(tables(cleaned)) == len(tables(blocks)) - expected.CONTINUATION_TABLES


# --- finding #9: untitled tables (after cleaning) ----------------------------------


def test_book_no_table_is_left_without_a_title(cleaned: list[Block]) -> None:
    untitled = [t for t in tables(cleaned) if t.text.startswith("|")]

    assert untitled == []


def test_book_cleaner_attaches_one_intro_per_untitled_table(
    blocks: list[Block], cleaned: list[Block]
) -> None:
    def paragraphs(bs: list[Block]) -> int:
        return sum(b.kind == "paragraph" for b in bs)

    assert paragraphs(blocks) - paragraphs(cleaned) == expected.UNTITLED_TABLES

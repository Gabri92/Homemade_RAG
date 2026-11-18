"""Regression checks on the real book: findings in docs/ingestion-findings.md must not come back.

Marker, skip and the `blocks`/`cleaned` fixtures come from tests/book/conftest.py.
"""

import zipfile

from bs4 import BeautifulSoup

from tests.book import expectations as expected
from tricoach.ingest import attach_intro_to_untitled_tables, remove_pull_quotes
from tricoach.models import Block, Book


def tables(blocks: list[Block]) -> list[Block]:
    return [b for b in blocks if b.kind == "table"]


def paragraphs(blocks: list[Block]) -> int:
    return sum(b.kind == "paragraph" for b in blocks)


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


def test_book_cleaner_attaches_one_intro_per_untitled_table(blocks: list[Block]) -> None:
    attached = attach_intro_to_untitled_tables(blocks)

    assert paragraphs(blocks) - paragraphs(attached) == expected.UNTITLED_TABLES


# --- finding #4: pull quotes ---------------------------------------------------------


def sidenote_texts() -> set[tuple[str, str]]:
    """(file name, text) of every paragraph inside a div.sidenote: the labels for #4."""
    labels = set()
    with zipfile.ZipFile(expected.BOOK_PATH) as book:
        for name in (n for n in book.namelist() if n.endswith(".xhtml")):
            soup = BeautifulSoup(book.read(name), "html.parser")
            for p in soup.select("div.sidenote p"):
                labels.add((name.rsplit("/", 1)[-1], " ".join(p.get_text().split())))
    return labels


def test_book_pull_quotes_are_removed_and_nothing_else(blocks: list[Block]) -> None:
    kept = remove_pull_quotes(blocks)
    removed = [b for b in blocks if b not in kept]
    labels = sidenote_texts()

    assert len(labels) == expected.SIDENOTES
    assert len(removed) == expected.PULL_QUOTES_REMOVED
    # precision: every removed block is a sidenote, never body text
    assert all((b.source.rsplit("/", 1)[-1], b.text) in labels for b in removed)


# --- findings #5, #6, #10: roles, pages, glossary ----------------------------------


def test_book_every_body_block_has_a_page(blocks: list[Block]) -> None:
    assert [b for b in blocks if b.role == "body" and not b.page] == []


def test_book_table_11_1_is_on_its_printed_page(cleaned: list[Block]) -> None:
    table = next(t for t in tables(cleaned) if t.text.startswith(expected.TABLE_11_1_TITLE))

    assert table.page == expected.TABLE_11_1_PAGE


def test_book_landmark_roles_are_assigned(blocks: list[Block]) -> None:
    roles = {b.role for b in blocks}

    assert {"body", "glossary", "index", "bibliography", "acknowledgments"} <= roles


def test_book_glossary_keeps_every_definition(blocks: list[Block]) -> None:
    terms = [b for b in blocks if b.role == "glossary" and b.kind == "paragraph"]

    assert len(terms) == expected.GLOSSARY_TERMS
    assert all(": " in t.text for t in terms)


# --- Structurer (findings #5, #11 and edge cases) --------------------------------


def test_book_has_its_chapters(book: Book) -> None:
    chapters = [s for s in book.sections if s.level == 2 and s.title.split()[0].isdigit()]

    assert len(chapters) == expected.CHAPTERS


def test_book_section_ids_are_unique(book: Book) -> None:
    ids = [s.id for s in book.sections]

    assert len(ids) == len(set(ids))


def test_book_table_11_1_is_cited_with_its_section_and_pages(book: Book) -> None:
    section = next(
        s
        for s in book.sections
        if any(b.text.startswith(expected.TABLE_11_1_TITLE) for b in s.blocks)
    )

    assert section.id == expected.MORNING_WARNINGS_ID
    assert section.first_page is not None
    assert section.last_page == expected.TABLE_11_1_PAGE


def test_book_excludes_only_non_content_parts(book: Book) -> None:
    excluded = {s.role for s in book.sections if not s.include}

    assert excluded == expected.EXCLUDED_ROLES


def test_book_glossary_and_appendices_are_included(book: Book) -> None:
    glossary = [s for s in book.sections if s.role == "glossary"]
    appendices = [s for s in book.sections if s.path[0].startswith("APPENDIX")]

    assert glossary
    assert all(s.include for s in glossary)
    assert appendices
    assert all(s.include for s in appendices)


def test_book_same_workout_for_different_sports_has_distinct_sections(book: Book) -> None:
    recovery = [s.id for s in book.sections if s.id.endswith("/ae1-recovery")]

    assert len(set(recovery)) == expected.AE1_RECOVERY_SECTIONS


def test_book_every_included_section_has_pages(book: Book) -> None:
    assert [s.id for s in book.sections if s.include and not s.first_page] == []

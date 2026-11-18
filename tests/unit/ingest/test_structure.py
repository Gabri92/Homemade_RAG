from pathlib import Path

import pytest

from tricoach.ingest import load_book, mark_front_matter, save_book, structure
from tricoach.models import Block, Book


def heading(text: str, level: int, source: str = "ch01.xhtml", **kw: str) -> Block:
    return Block("heading", text, source, level=level, **kw)


def para(text: str, source: str = "ch01.xhtml", **kw: str) -> Block:
    return Block("paragraph", text, source, **kw)


def paths(book: Book) -> list[tuple[str, ...]]:
    return [s.path for s in book.sections]


# --- hierarchy -------------------------------------------------------------------


def test_each_heading_opens_a_section_with_the_content_up_to_the_next() -> None:
    book = structure(
        [
            heading("PART I", 1),
            heading("1 READINESS", 2),
            para("A."),
            para("B."),
            heading("2 PREP", 2),
        ],
        source="book.epub",
    )

    assert [(s.title, [b.text for b in s.blocks]) for s in book.sections] == [
        ("PART I", []),
        ("1 READINESS", ["A.", "B."]),
        ("2 PREP", []),
    ]
    assert paths(book) == [("PART I",), ("PART I", "1 READINESS"), ("PART I", "2 PREP")]


def test_skipped_levels_attach_to_the_nearest_higher_heading() -> None:
    book = structure([heading("CH", 2), heading("Deep", 4), heading("Mid", 3)], "b")

    assert paths(book) == [("CH",), ("CH", "Deep"), ("CH", "Mid")]


def test_hierarchy_continues_across_files() -> None:
    blocks = [
        heading("13 MUSCULAR FORCE", 2, "ch13.xhtml"),
        heading("Squat", 3, "ch13_sub01.xhtml"),
        para("Lead-in before the first heading.", "ch13_sub02.xhtml"),
        heading("Lunge", 3, "ch13_sub02.xhtml"),
    ]

    book = structure(blocks, "b")

    assert paths(book) == [
        ("13 MUSCULAR FORCE",),
        ("13 MUSCULAR FORCE", "Squat"),
        ("13 MUSCULAR FORCE", "Lunge"),
    ]
    assert [b.text for b in book.sections[1].blocks] == ["Lead-in before the first heading."]


# --- ids -------------------------------------------------------------------------


def test_ids_are_built_from_the_title_path() -> None:
    book = structure([heading("11 REST AND RECOVERY", 1), heading("Morning Warnings", 2)], "b")

    assert [s.id for s in book.sections] == [
        "11-rest-and-recovery",
        "11-rest-and-recovery/morning-warnings",
    ]


def test_same_title_under_different_parents_gets_different_ids() -> None:
    blocks = [
        heading("SWIM", 1),
        heading("AE1: Recovery", 2),
        heading("BIKE", 1),
        heading("AE1: Recovery", 2),
    ]

    ids = [s.id for s in structure(blocks, "b").sections]

    assert ids == ["swim", "swim/ae1-recovery", "bike", "bike/ae1-recovery"]


def test_duplicate_paths_get_a_numeric_suffix() -> None:
    blocks = [heading("CH", 1), heading("Summary", 2), heading("Summary", 2)]

    assert [s.id for s in structure(blocks, "b").sections] == ["ch", "ch/summary", "ch/summary-2"]


# --- roles, files without headings, inclusion ------------------------------------


def test_section_without_heading_is_not_an_ancestor_of_later_chapters() -> None:
    # #12: a headingless title page must not swallow the chapters that follow it.
    blocks = [
        para("Sailing Alone", "titlepage.xhtml", role="titlepage"),
        heading("I", 2, "chapter-1.xhtml"),
        para("Text.", "chapter-1.xhtml"),
        heading("II", 2, "chapter-2.xhtml"),
    ]

    book = structure(blocks, "b")

    assert [s.id for s in book.sections] == ["titlepage", "i", "ii"]
    assert [s.path for s in book.sections] == [("titlepage",), ("I",), ("II",)]


def test_content_without_heading_and_a_new_role_opens_a_section_named_after_the_role() -> None:
    blocks = [
        heading("INDEX", 1, "index.xhtml", role="index"),
        para("LTHR, 45", "index.xhtml", role="index"),
        para("© 2026", "copyright.xhtml", role="copyright-page"),
    ]

    last = structure(blocks, "b").sections[-1]

    assert (last.title, last.role, last.path, last.id) == (
        "copyright-page",
        "copyright-page",
        ("copyright-page",),
        "copyright-page",
    )


@pytest.mark.parametrize(
    ("role", "included"),
    [
        ("body", True),
        ("glossary", True),
        ("preface", True),
        ("epilogue", True),
        ("appendix", True),
        ("endnotes", True),
        ("index", False),
        ("imprint", False),
        ("colophon", False),
        ("loi", False),
        ("bibliography", False),
        ("acknowledgments", False),
        ("copyright-page", False),
        ("frontmatter", False),
    ],
)
def test_inclusion_depends_on_the_role(role: str, included: bool) -> None:
    section = structure([heading("X", 1, role=role)], "b").sections[0]

    assert section.include is included


def test_unlisted_file_between_front_matter_files_becomes_front_matter() -> None:
    blocks = [
        para("Cover", "cover.xhtml", role="cover"),
        para("A must-read.", "praise.xhtml"),
        para("Title", "title.xhtml", role="titlepage"),
        heading("PREFACE", 1, "preface.xhtml", role="preface"),
        heading("PART I", 1, "part01.xhtml"),
        heading("EPILOGUE", 1, "epilogue.xhtml", role="epilogue"),
    ]

    roles = [(b.source, b.role) for b in mark_front_matter(blocks)]

    assert roles == [
        ("cover.xhtml", "cover"),
        ("praise.xhtml", "frontmatter"),
        ("title.xhtml", "titlepage"),
        ("preface.xhtml", "preface"),
        ("part01.xhtml", "body"),
        ("epilogue.xhtml", "epilogue"),
    ]


# --- pages -----------------------------------------------------------------------


def test_section_pages_span_from_its_heading_to_its_last_block() -> None:
    blocks = [heading("CH", 1, page="170"), para("A.", page="171"), para("B.", page="173")]

    section = structure(blocks, "b").sections[0]

    assert (section.first_page, section.last_page) == ("170", "173")


# --- book.json -------------------------------------------------------------------


def test_book_round_trips_through_json(tmp_path: Path) -> None:
    book = structure([heading("CH", 1, page="3"), para("Text.", page="3")], "book.epub")
    path = tmp_path / "book.json"

    save_book(book, path)

    assert load_book(path) == book


def test_book_with_another_schema_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "book.json"
    path.write_text('{"schema_version": 0, "source": "x", "sections": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="schema"):
        load_book(path)

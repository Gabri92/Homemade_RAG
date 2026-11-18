from tricoach.ingest import format_report, quality_report, structure
from tricoach.models import Block


def heading(text: str, **kw: str) -> Block:
    return Block("heading", text, "ch01.xhtml", level=1, **kw)


def para(text: str, **kw: str) -> Block:
    return Block("paragraph", text, "ch01.xhtml", **kw)


def checks_for(blocks: list[Block], source_text: str) -> dict[str, tuple[str, str | None]]:
    report = quality_report(blocks, structure(blocks, "b"), source_text)
    return {c.name: (c.value, c.warning) for c in report}


GOOD = [heading("Base", page="1"), para("Train easy most of the time.", page="1")]


def test_a_clean_book_has_no_warnings() -> None:
    checks = checks_for(GOOD, source_text="Base Train easy most of the time.")

    assert [name for name, (_, warning) in checks.items() if warning] == []


def test_text_lost_by_the_loader_lowers_coverage_and_warns() -> None:
    value, warning = checks_for(
        GOOD, source_text="Base Train easy most of the time. LOST TITLE " * 2
    )["text coverage"]

    assert value.endswith("%")
    assert warning is not None


def test_no_headings_warns_that_there_is_no_structure() -> None:
    _, warning = checks_for([para("Only text.", page="1")], "Only text.")["headings"]

    assert warning is not None


def test_untitled_table_in_included_sections_warns() -> None:
    blocks = [*GOOD, Block("table", "| A |\n| --- |\n| 1 |", "ch01.xhtml", page="1")]

    value, warning = checks_for(blocks, "Base Train easy most of the time. A 1")["untitled tables"]

    assert (value, warning is not None) == ("1", True)


def test_duplicate_paragraphs_left_after_cleaning_warn() -> None:
    sentence = "Recovery is where the adaptation to training actually happens."
    blocks = [*GOOD, para(sentence, page="2"), para(sentence, page="3")]

    value, warning = checks_for(blocks, "x")["duplicate paragraphs"]

    assert (value, warning is not None) == ("1 in the same section, 0 across sections", True)


def test_same_note_under_two_sections_is_counted_but_not_a_warning() -> None:
    note = "This workout is recommended for short-course athletes only."
    blocks = [
        heading("AC1", page="1"),
        para(note, page="1"),
        heading("AC2", page="1"),
        para(note, page="1"),
    ]

    value, warning = checks_for(blocks, "x")["duplicate paragraphs"]

    assert (value, warning) == ("0 in the same section, 1 across sections", None)


def test_numbers_glued_to_words_warn_as_leftover_note_references() -> None:
    blocks = [*GOOD, para("We reached the summit.12 Then we rested13 for an hour.", page="2")]

    value, warning = checks_for(blocks, "x")["words glued to numbers"]

    assert value.startswith("2")
    assert warning is not None


def test_codes_like_workout_names_are_not_glued_numbers() -> None:
    blocks = [*GOOD, para("Do AE1 and TE1 this week, then MF2 if fresh.", page="2")]

    value, warning = checks_for(blocks, "x")["words glued to numbers"]

    assert (value.startswith("0"), warning) == (True, None)


def test_missing_page_markers_warn_about_citations() -> None:
    blocks = [heading("Base"), para("Train easy most of the time.")]

    value, warning = checks_for(blocks, "Base Train easy most of the time.")["blocks with page"]

    assert value == "0%"
    assert warning is not None


def test_excluded_sections_are_not_checked() -> None:
    index = [
        Block("heading", "INDEX", "index.xhtml", level=1, role="index", page="300"),
        Block("table", "| LTHR | 45 |", "index.xhtml", role="index", page="300"),
    ]

    _, warning = checks_for(GOOD + index, "Base Train easy most of the time. INDEX LTHR 45")[
        "untitled tables"
    ]

    assert warning is None


def test_format_report_marks_warnings() -> None:
    report = quality_report(GOOD, structure(GOOD, "b"), "Base Train easy most of the time.")

    text = format_report(report)

    assert "text coverage" in text
    assert "WARNING" not in text

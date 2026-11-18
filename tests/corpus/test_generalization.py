"""The ingestion must work on ePubs it was not designed on (findings #12-#15)."""

from pathlib import Path

from tests.corpus import expectations as expected
from tricoach.ingest import ingest_epub, inspect_epub

Corpus = tuple[str, Path]


def test_only_missing_page_markers_are_reported(corpus_book: Corpus) -> None:
    # #15: these ePubs have no printed-page markers; anything else is a regression.
    _, path = corpus_book

    warnings = [c.name for c in inspect_epub(path) if c.warning]

    assert warnings == ["blocks with page"]


def test_headingless_sections_are_never_ancestors(corpus_book: Corpus) -> None:
    # #12: a title page without heading must not swallow the chapters.
    _, path = corpus_book
    sections = ingest_epub(path).sections
    pseudo = {s.title for s in sections if s.path == (s.role,)}

    nested_under_pseudo = [s.id for s in sections if len(s.path) > 1 and s.path[0] in pseudo]

    assert nested_under_pseudo == []


def test_non_content_parts_are_excluded_and_content_included(corpus_book: Corpus) -> None:
    # #13: roles come from each file's own epub:type, not only from the landmarks.
    key, path = corpus_book
    sections = ingest_epub(path).sections

    excluded = {s.role for s in sections if not s.include}
    appendices = [s for s in sections if s.role == "appendix"]

    assert excluded <= expected.NON_CONTENT_ROLES
    assert sum(s.include for s in sections) == expected.INCLUDED_SECTIONS[key]
    assert len(appendices) == expected.APPENDICES[key]
    assert all(s.include for s in appendices)

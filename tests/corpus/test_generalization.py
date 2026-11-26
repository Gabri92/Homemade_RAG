"""The ingestion must work on ePubs it was not designed on (findings #12-#19)."""

import hashlib
from pathlib import Path

import pytest

from homerag.ingest import ingest_epub, inspect_epub
from tests.corpus import expectations as expected

Corpus = tuple[str, Path]


def test_only_known_warnings_are_reported(corpus_book: Corpus) -> None:
    # #15: these ePubs have no printed-page markers; any new warning is a regression.
    key, path = corpus_book

    warnings = [c.name for c in inspect_epub(path) if c.warning]

    assert warnings == expected.EXPECTED_WARNINGS[key]


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


def test_golden_set_books_are_the_cited_edition(corpus_book: Corpus) -> None:
    # ADR 0010: the committed golden set cites section ids of one edition.
    key, path = corpus_book
    if key not in expected.EDITION_SHA256:
        pytest.skip(f"{key} has no committed golden set")

    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    assert digest == expected.EDITION_SHA256[key], f"{path.name} is not the cited edition"

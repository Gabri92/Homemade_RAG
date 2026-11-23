import re
from typing import get_args

import pytest

from tricoach.chunking import BLOCK_SEPARATOR, CHUNKERS, fixed_size_chunks
from tricoach.config import ChunkingConfig
from tricoach.models import Block, Book, Section


def word_spans(text: str) -> list[tuple[int, int]]:
    """Fake tokenizer: one token per word, so sizes are easy to count in tests."""
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def words(prefix: str, n: int) -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def section(sid: str, *texts: str, include: bool = True, pages: tuple[str, ...] = ()) -> Section:
    blocks = tuple(
        Block("paragraph", text, "ch.xhtml", page=pages[i] if i < len(pages) else None)
        for i, text in enumerate(texts)
    )
    return Section(sid, sid.title(), 1, (sid.title(),), "body", include, blocks)


def cfg(size: int, overlap: int) -> ChunkingConfig:
    return ChunkingConfig(strategy="fixed", size_tokens=size, overlap_tokens=overlap)


def test_windows_have_the_size_and_overlap_of_the_config() -> None:
    book = Book("b", (section("a", words("w", 25)),))

    chunks = fixed_size_chunks(book, cfg(10, 2), word_spans)

    tokens = [c.text.split() for c in chunks]
    assert [len(t) for t in tokens] == [10, 10, 9]
    assert tokens[0][-2:] == tokens[1][:2]
    assert tokens[1][-2:] == tokens[2][:2]
    assert tokens[-1][-1] == "w24"


def test_short_document_is_one_chunk() -> None:
    book = Book("b", (section("a", words("w", 5)),))

    assert [c.text for c in fixed_size_chunks(book, cfg(10, 2), word_spans)] == [words("w", 5)]


def test_empty_document_has_no_chunks() -> None:
    assert fixed_size_chunks(Book("b", ()), cfg(10, 2), word_spans) == []


def test_chunk_crossing_a_boundary_lists_both_sections_in_order() -> None:
    book = Book("b", (section("a", words("a", 6)), section("b", words("b", 6))))

    first = fixed_size_chunks(book, cfg(10, 2), word_spans)[0]

    assert [s.id for s in first.sections] == ["a", "b"]
    assert first.id == "a#1"
    assert first.text == words("a", 6) + BLOCK_SEPARATOR + words("b", 4)


def test_ids_count_per_first_section() -> None:
    book = Book("b", (section("a", words("a", 25)),))

    assert [c.id for c in fixed_size_chunks(book, cfg(10, 2), word_spans)] == ["a#1", "a#2", "a#3"]


def test_excluded_sections_are_left_out() -> None:
    book = Book("b", (section("index", "zebra 12", include=False), section("a", "base text")))

    chunks = fixed_size_chunks(book, cfg(10, 2), word_spans)

    assert [c.text for c in chunks] == ["base text"]
    assert [s.id for s in chunks[0].sections] == ["a"]


def test_page_is_where_the_chunk_starts() -> None:
    book = Book("b", (section("a", words("x", 8), words("y", 8), pages=("12", "13")),))

    pages = [c.page for c in fixed_size_chunks(book, cfg(10, 2), word_spans)]

    assert pages == ["12", "13"]


def test_registry_matches_the_strategies_the_config_accepts() -> None:
    accepted = set(get_args(ChunkingConfig.model_fields["strategy"].annotation))

    assert set(CHUNKERS) == accepted


@pytest.mark.parametrize("name", sorted(CHUNKERS))
def test_every_chunker_gives_unique_ids_and_keeps_all_the_words(name: str) -> None:
    book = Book("b", (section("a", words("a", 30)), section("b", words("b", 17))))

    chunks = CHUNKERS[name](book, cfg(10, 2), word_spans)

    assert len({c.id for c in chunks}) == len(chunks)
    expected = set(words("a", 30).split()) | set(words("b", 17).split())
    assert {w for c in chunks for w in c.text.split()} == expected

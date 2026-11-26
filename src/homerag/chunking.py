"""Chunking strategies: split a `Book` into `Chunk`s.

Each strategy is a function with the same signature, registered by name in `CHUNKERS` so an
experiment config can pick it. Token counts come from a `TokenSpans` function passed in by the
caller (the embedding model's tokenizer, see `index.token_spans_for`), so this module stays
pure and its tests need no model.
"""

from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from homerag.config import ChunkingConfig
from homerag.models import Book, Chunk, Section, SectionRef

TokenSpans = Callable[[str], list[tuple[int, int]]]
"""Maps a text to the (start, end) character offsets of each of its tokens."""

Chunker = Callable[[Book, ChunkingConfig, TokenSpans], list[Chunk]]

BLOCK_SEPARATOR = "\n\n"


@dataclass(frozen=True, slots=True)
class _Piece:
    """Where one block sits in the running text, and which section and page it belongs to."""

    start: int
    end: int
    section: SectionRef
    page: str | None


def fixed_size_chunks(book: Book, cfg: ChunkingConfig, token_spans: TokenSpans) -> list[Chunk]:
    """Windows of `size_tokens` tokens, each starting `size - overlap` tokens after the last.

    The naive baseline: the included sections are joined into one running text and cut
    wherever the window ends, across section boundaries, tables and sentences alike.
    A chunk lists every section it covers (ADR 0005).
    """
    text, pieces = _running_text(book)
    spans = token_spans(text)
    step = cfg.size_tokens - cfg.overlap_tokens
    # Stop once the remaining tokens are all inside the previous window's overlap.
    starts = range(0, max(len(spans) - cfg.overlap_tokens, 1), step)
    piece_starts = [p.start for p in pieces]
    numbers: Counter[str] = Counter()
    chunks = []
    for i in starts:
        window = spans[i : i + cfg.size_tokens]
        if not window:
            break
        start, end = window[0][0], window[-1][1]
        covered = pieces[bisect_right(piece_starts, start) - 1 : bisect_left(piece_starts, end)]
        sections = tuple(dict.fromkeys(p.section for p in covered))
        numbers[sections[0].id] += 1
        chunk_id = f"{sections[0].id}#{numbers[sections[0].id]}"
        chunks.append(Chunk(chunk_id, sections, text[start:end], covered[0].page))
    return chunks


def section_text(section: Section) -> str:
    """A section's blocks joined as in the running text, so a chunk's text can be found in it."""
    return BLOCK_SEPARATOR.join(block.text for block in section.blocks)


def _running_text(book: Book) -> tuple[str, list[_Piece]]:
    """Join the blocks of the included sections, remembering where each block sits."""
    parts: list[str] = []
    pieces: list[_Piece] = []
    offset = 0
    for section in book.sections:
        if not section.include:
            continue
        ref = SectionRef(section.id, section.path)
        for block in section.blocks:
            if parts:
                parts.append(BLOCK_SEPARATOR)
                offset += len(BLOCK_SEPARATOR)
            parts.append(block.text)
            pieces.append(_Piece(offset, offset + len(block.text), ref, block.page))
            offset += len(block.text)
    return "".join(parts), pieces


CHUNKERS: dict[str, Chunker] = {
    "fixed": fixed_size_chunks,
}

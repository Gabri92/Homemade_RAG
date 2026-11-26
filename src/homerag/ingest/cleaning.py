"""Cleaner: structural fixes on blocks, independent of the source format.

It repairs defects of the source and its layout (split tables, context detached from
its table, ...). It does not normalise characters: the text stays faithful to the book,
because it is what the LLM reads and cites. See docs/ingestion-findings.md.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import replace

from homerag.models import Block

logger = logging.getLogger(__name__)

CleaningStep = Callable[[list[Block]], list[Block]]

# Pull-quote rule (#4). Values measured on the book against the 214 HTML sidenotes:
# 157 pull quotes removed, 0 body paragraphs removed (see docs/ingestion-findings.md).
PULL_QUOTE_MIN_OVERLAP = 0.5  # share of the quote's word trigrams found in the original
PULL_QUOTE_MIN_WORDS = 5
PULL_QUOTE_MAX_LENGTH_RATIO = 0.6  # a pull quote is much shorter than its original
_SENTENCE_END = (".", "!", "?", "”", '"', ")")
_TRIGRAM = 3


def remove_pull_quotes(blocks: list[Block]) -> list[Block]:
    """#4: drop paragraphs that repeat a sentence of a longer block in the same file.

    Pull quotes are layout emphasis: the same words, shown twice. They are recognised
    by content only (no CSS classes), so the rule also works for other formats.
    """
    words = [_words(block.text) for block in blocks]
    trigrams = [_trigrams(w) for w in words]
    candidates = [i for i, b in enumerate(blocks) if b.kind in ("paragraph", "list_item")]
    return [
        block
        for i, block in enumerate(blocks)
        if not _is_pull_quote(i, blocks, words, trigrams, candidates)
    ]


def _is_pull_quote(
    i: int,
    blocks: list[Block],
    words: list[list[str]],
    trigrams: list[set[tuple[str, ...]]],
    candidates: list[int],
) -> bool:
    block = blocks[i]
    if block.kind != "paragraph" or len(words[i]) < PULL_QUOTE_MIN_WORDS:
        return False
    if not block.text.rstrip().endswith(_SENTENCE_END):
        return False  # labels such as "SIDEBAR 1.1 ..." are not sentences
    for j in candidates:
        if j == i or blocks[j].source != block.source:
            continue
        if len(words[i]) > PULL_QUOTE_MAX_LENGTH_RATIO * len(words[j]):
            continue
        overlap = len(trigrams[i] & trigrams[j]) / len(trigrams[i])
        if overlap >= PULL_QUOTE_MIN_OVERLAP:
            return True
    return False


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _trigrams(words: list[str]) -> set[tuple[str, ...]]:
    # Trigrams survive small rewordings of a pull quote better than exact matching.
    return {tuple(words[k : k + _TRIGRAM]) for k in range(max(1, len(words) - _TRIGRAM + 1))}


def merge_continued_tables(blocks: list[Block]) -> list[Block]:
    """#8: an untitled table right after a table (same file) is its continuation."""
    result: list[Block] = []
    for block in blocks:
        previous = result[-1] if result else None
        if previous and previous.kind == "table" and _is_untitled_table(block, previous.source):
            result[-1] = replace(previous, text=f"{previous.text}\n\n{block.text}")
        else:
            result.append(block)
    return result


def attach_intro_to_untitled_tables(blocks: list[Block]) -> list[Block]:
    """#9: the paragraph right before an untitled table (same file) becomes its title."""
    result: list[Block] = []
    for block in blocks:
        previous = result[-1] if result else None
        if previous and previous.kind == "paragraph" and _is_untitled_table(block, previous.source):
            # The merged block starts where the intro starts: keep the intro's page.
            result[-1] = replace(block, text=f"{previous.text}\n{block.text}", page=previous.page)
        else:
            result.append(block)
    return result


def _is_untitled_table(block: Block, source: str) -> bool:
    # A titled table starts with its title line; an untitled one starts with a Markdown row.
    return block.kind == "table" and block.source == source and block.text.startswith("|")


def remove_repeated_headings(blocks: list[Block]) -> list[Block]:
    """#18: a heading right after a heading with the same text (same file) is a repeat.

    Pressbooks prints the chapter title, then the same title again as the first
    heading of the text: kept twice, it would open an empty section.
    """
    result: list[Block] = []
    for block in blocks:
        previous = result[-1] if result else None
        if not (
            previous
            and block.kind == previous.kind == "heading"
            and block.source == previous.source
            and block.text.casefold() == previous.text.casefold()
        ):
            result.append(block)
    return result


def title_from_spanning_row(blocks: list[Block]) -> list[Block]:
    """#20: a table still untitled whose first row is one cell spanning every column.

    After merged cells are expanded, that cell repeats in each column ("| T | T |"):
    it is the table's title. Runs after #9, so an intro paragraph wins and the row stays
    (in some tables it is a group label, not a title).
    """
    return [_with_spanning_title(b) if _is_untitled_table(b, b.source) else b for b in blocks]


def _with_spanning_title(block: Block) -> Block:
    first_row, separator, *rows = block.text.split("\n")
    cells = [c.strip() for c in _PIPE.split(first_row.strip().strip("|"))]
    if len(cells) < _MIN_SPANNED_COLUMNS or len(set(cells)) > 1 or not rows:
        return block  # one column, different cells, or no row left to be the header
    header, *body = rows
    return replace(block, text="\n".join([cells[0], header, separator, *body]))


_PIPE = re.compile(r"(?<!\\)\|")  # a cell separator, not an escaped pipe in the text
_MIN_SPANNED_COLUMNS = 2  # a one-column table has no spanning row to tell apart


CLEANING_STEPS: list[CleaningStep] = [
    remove_repeated_headings,
    remove_pull_quotes,
    merge_continued_tables,
    attach_intro_to_untitled_tables,
    title_from_spanning_row,
]


def clean(blocks: list[Block]) -> list[Block]:
    """Apply every cleaning step in order, logging how many blocks each one changed."""
    for step in CLEANING_STEPS:
        cleaned = step(blocks)
        logger.info("%s: %d -> %d blocks", step.__name__, len(blocks), len(cleaned))
        blocks = cleaned
    return blocks

"""Cleaner: structural fixes on blocks, independent of the source format.

It repairs defects of the source and its layout (split tables, context detached from
its table, ...). It does not normalise characters: the text stays faithful to the book,
because it is what the LLM reads and cites. See docs/ingestion-findings.md.
"""

import logging
from collections.abc import Callable
from dataclasses import replace

from tricoach.models import Block

logger = logging.getLogger(__name__)

CleaningStep = Callable[[list[Block]], list[Block]]


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
            result[-1] = replace(block, text=f"{previous.text}\n{block.text}")
        else:
            result.append(block)
    return result


def _is_untitled_table(block: Block, source: str) -> bool:
    # A titled table starts with its title line; an untitled one starts with a Markdown row.
    return block.kind == "table" and block.source == source and block.text.startswith("|")


CLEANING_STEPS: list[CleaningStep] = [
    merge_continued_tables,
    attach_intro_to_untitled_tables,
]


def clean(blocks: list[Block]) -> list[Block]:
    """Apply every cleaning step in order, logging how many blocks each one changed."""
    for step in CLEANING_STEPS:
        cleaned = step(blocks)
        logger.info("%s: %d -> %d blocks", step.__name__, len(blocks), len(cleaned))
        blocks = cleaned
    return blocks

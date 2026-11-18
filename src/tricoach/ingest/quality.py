"""Quality report: generic checks that need no expected values, so they work on any source.

Used by `tricoach inspect` today; meant to become the automatic check on user-added
sources. Only counts and section ids are reported, never book text.
"""

import re
from collections import Counter
from dataclasses import dataclass

from tricoach.models import Block, Book, Section

MIN_TEXT_COVERAGE = 0.98  # below this, the loader is silently dropping content
MIN_PAGE_SHARE = 0.95
DUPLICATE_MIN_WORDS = 8  # shorter repeats ("See Table 4.1.") are normal
LONG_SECTION_WORDS = 2000  # informational: such sections must be split by the chunker
# A lowercase word followed (maybe after punctuation) by a number: "summit.12", "pass5".
# Codes such as "AE1" are uppercase and do not match. Measured: 0 on the reference book,
# 3-277 per book on ePubs whose note references were not stripped (#14).
_CLOSING_PUNCTUATION = ".,;:!?)" + chr(0x2019) + chr(0x201D)  # incl. typographic quotes
_GLUED_NUMBER = re.compile(rf"\b[a-z]{{3,}}[{re.escape(_CLOSING_PUNCTUATION)}]?\d{{1,3}}\b")
MAX_GLUED_PER_10K_WORDS = 0.2


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    value: str
    warning: str | None = None


def quality_report(raw_blocks: list[Block], book: Book, source_text: str) -> list[Check]:
    """Checks on the loader output (vs the source text) and on the included sections."""
    included = [s for s in book.sections if s.include]
    blocks = [b for s in included for b in s.blocks]
    return [
        _text_coverage(raw_blocks, source_text),
        _headings(raw_blocks),
        Check("sections included", f"{len(included)} / {len(book.sections)}"),
        _untitled_tables(blocks),
        _figures_without_caption(blocks),
        _duplicate_paragraphs(included),
        _words_glued_to_numbers(blocks),
        _blocks_with_page(blocks),
        _long_sections(included),
        Check("empty sections", str(sum(not s.blocks for s in book.sections))),
    ]


def format_report(checks: list[Check]) -> str:
    lines = []
    for check in checks:
        status = "WARN" if check.warning else "ok  "
        note = f"  -> WARNING: {check.warning}" if check.warning else ""
        lines.append(f"[{status}] {check.name}: {check.value}{note}")
    return "\n".join(lines) + "\n"


def _text_coverage(raw_blocks: list[Block], source_text: str) -> Check:
    # Letters and digits only: markup, whitespace and Markdown pipes do not count.
    source = _alnum(source_text)
    ratio = sum(_alnum(b.text) for b in raw_blocks) / source if source else 1.0
    warning = "the loader drops part of the source text" if ratio < MIN_TEXT_COVERAGE else None
    return Check("text coverage", f"{ratio:.1%}", warning)


def _headings(raw_blocks: list[Block]) -> Check:
    levels = Counter(b.level for b in raw_blocks if b.kind == "heading")
    value = ", ".join(f"L{level}: {n}" for level, n in sorted(levels.items())) or "0"
    warning = None if levels else "no headings: no sections, citations without location"
    return Check("headings", value, warning)


def _untitled_tables(blocks: list[Block]) -> Check:
    count = sum(b.kind == "table" and b.text.startswith("|") for b in blocks)
    warning = "tables without title or intro lose meaning when chunked" if count else None
    return Check("untitled tables", str(count), warning)


def _figures_without_caption(blocks: list[Block]) -> Check:
    figures = [b for b in blocks if b.kind == "figure"]
    return Check("figures without caption", f"{sum(not f.text for f in figures)} / {len(figures)}")


def _duplicate_paragraphs(sections: list[Section]) -> Check:
    """Repeats inside one section are defects (e.g. pull quotes); across sections they are
    often intended (the same note under two workouts), so they are only counted."""
    within = across = 0
    seen_in: dict[str, set[str]] = {}
    for section in sections:
        local = Counter(
            b.text
            for b in section.blocks
            if b.kind == "paragraph" and len(b.text.split()) >= DUPLICATE_MIN_WORDS
        )
        within += sum(n > 1 for n in local.values())
        for text in local:
            seen_in.setdefault(text, set()).add(section.id)
    across = sum(len(ids) > 1 for ids in seen_in.values())
    warning = "repeated text inside a section takes retrieval slots" if within else None
    return Check(
        "duplicate paragraphs", f"{within} in the same section, {across} across sections", warning
    )


def _words_glued_to_numbers(blocks: list[Block]) -> Check:
    count = sum(len(_GLUED_NUMBER.findall(b.text)) for b in blocks)
    words = sum(len(b.text.split()) for b in blocks) or 1
    rate = 10_000 * count / words
    warning = (
        "note references left in the text: words like 'summit12' miss keyword search"
        if rate > MAX_GLUED_PER_10K_WORDS
        else None
    )
    return Check("words glued to numbers", f"{count} ({rate:.1f} per 10k words)", warning)


def _blocks_with_page(blocks: list[Block]) -> Check:
    share = sum(b.page is not None for b in blocks) / len(blocks) if blocks else 1.0
    warning = "citations will lack page numbers" if share < MIN_PAGE_SHARE else None
    return Check("blocks with page", f"{share:.0%}", warning)


def _long_sections(sections: list[Section]) -> Check:
    words = {s.id: sum(len(b.text.split()) for b in s.blocks) for s in sections}
    long = sorted((w, i) for i, w in words.items() if w > LONG_SECTION_WORDS)
    value = str(len(long)) + (f" (longest: {long[-1][1]}, {long[-1][0]} words)" if long else "")
    return Check(f"sections over {LONG_SECTION_WORDS} words", value)


def _alnum(text: str) -> int:
    return sum(ch.isalnum() for ch in text)

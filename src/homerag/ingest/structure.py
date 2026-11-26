"""Structurer: cleaned blocks -> sections with hierarchy, stable ids, roles and pages.

Works on `Block`s only, so it is the same for every source format.
See docs/ingestion-findings.md ("Structurer: casi limite") for the cases handled here.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field, replace
from itertools import groupby

from homerag.models import Block, Book, Section

logger = logging.getLogger(__name__)

# Landmark types that belong to the front of a book (EPUB structural semantics).
FRONT_ROLES = frozenset(
    {
        "cover",
        "halftitlepage",
        "titlepage",
        "copyright-page",
        "dedication",
        "epigraph",
        "frontispiece",
        "imprint",
        "toc",
        "foreword",
        "preface",
        "acknowledgments",
        "frontmatter",
    }
)
# Roles that go into the search index. Rule: when in doubt, include; never the
# back-of-book index, whose term lists would outrank real answers in keyword search.
INCLUDED_ROLES = frozenset(
    {
        "body",
        "foreword",
        "preface",
        "introduction",
        "epilogue",
        "afterword",
        "conclusion",
        "appendix",
        "glossary",
        # Notes explain the text; their references are stripped from it (#14).
        "endnotes",
        "footnotes",
        "rearnotes",
        "translator-note",
    }
)
_ARABIC_PAGE = re.compile(r"\d+")

# Multiple-choice quizzes (#21): a role found from the content, never searched.
QUIZ = "quiz"
QUIZ_MIN_QUESTIONS = 2
QUIZ_MIN_SHARE = 0.6  # of the section's paragraphs and list items
_QUESTION = re.compile(r"\d{1,2}[.)]\s")
_OPTION = re.compile(r"[a-eA-E][.)]\s")


@dataclass
class _Draft:
    title: str
    level: int
    path: tuple[str, ...]
    role: str
    heading_page: str | None
    blocks: list[Block] = field(default_factory=list)


def structure(blocks: list[Block], source: str) -> Book:
    """Group blocks into sections: one per heading, plus one per headingless change of role."""
    drafts: list[_Draft] = []
    stack: list[tuple[int, str]] = []  # (level, title) of the open headings
    for block in mark_front_matter(blocks):
        if block.kind == "heading" and block.level is not None:
            while stack and stack[-1][0] >= block.level:
                stack.pop()
            stack.append((block.level, block.text))
            path = tuple(title for _, title in stack)
            drafts.append(_Draft(block.text, block.level, path, block.role, block.page))
        elif not drafts or block.role != drafts[-1].role:
            # Content without a heading in a new part of the book (cover, copyright, ...).
            # The section is named after its role but is not a heading: it must not
            # become the parent of the chapters that follow (#12), so the stack is reset.
            stack = []
            drafts.append(_Draft(block.role, 1, (block.role,), block.role, None, [block]))
        else:
            # Includes content before the first heading of a file: it continues the
            # section opened earlier (the hierarchy spans files).
            drafts[-1].blocks.append(block)

    sections = _finalise(drafts)
    logger.info(
        "structure: %d sections, %d included", len(sections), sum(s.include for s in sections)
    )
    return Book(source=source, sections=tuple(sections))


def _finalise(drafts: list[_Draft]) -> list[Section]:
    used: set[str] = set()
    sections = []
    for draft in drafts:
        section_id = _unique_id("/".join(_slug(title) for title in draft.path), used)
        pages = [p for p in (draft.heading_page, *(b.page for b in draft.blocks)) if p]
        role = QUIZ if _is_quiz(draft.blocks) else draft.role
        sections.append(
            Section(
                id=section_id,
                title=draft.title,
                level=draft.level,
                path=draft.path,
                role=role,
                include=role in INCLUDED_ROLES,
                blocks=tuple(draft.blocks),
                first_page=pages[0] if pages else None,
                last_page=pages[-1] if pages else None,
            )
        )
    return sections


def _is_quiz(blocks: list[Block]) -> bool:
    """#21: mostly numbered questions with lettered options ("1. ...", "a. ...").

    Recognised by content, for any publisher (ADR 0009). A quiz reads like the user's
    question, so it would outrank the sections that hold the answer.
    """
    texts = [b.text for b in blocks if b.kind in ("paragraph", "list_item")]
    questions = sum(bool(_QUESTION.match(t)) for t in texts)
    options = sum(bool(_OPTION.match(t)) for t in texts)
    return (
        questions >= QUIZ_MIN_QUESTIONS
        and options >= 2 * questions
        and questions + options >= QUIZ_MIN_SHARE * len(texts)
    )


def _unique_id(base: str, used: set[str]) -> str:
    # A counter per base is not enough: a later title may itself slug to "base-2".
    section_id, n = base, 1
    while section_id in used:
        n += 1
        section_id = f"{base}-{n}"
    used.add(section_id)
    return section_id


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "section"


def mark_front_matter(blocks: list[Block]) -> list[Block]:
    """#11: a file without landmark enclosed between front-matter files is front matter.

    E.g. a "praise" page between the cover and the title page. Chapters are safe: they
    sit between the preface and the epilogue/back matter.
    """
    files = [(source, list(group)) for source, group in groupby(blocks, key=lambda b: b.source)]
    roles = [group[0].role for _, group in files]
    result: list[Block] = []
    for i, (source, group) in enumerate(files):
        before = next((r for r in reversed(roles[:i]) if r != "body"), None)
        after = next((r for r in roles[i + 1 :] if r != "body"), None)
        if roles[i] == "body" and before in FRONT_ROLES and after in FRONT_ROLES:
            _warn_if_numbered(source, group)
            result.extend(replace(b, role="frontmatter") for b in group)
        else:
            result.extend(group)
    return result


def _warn_if_numbered(source: str, blocks: list[Block]) -> None:
    # Cross-check (rule B): front matter is paginated with letters or roman numerals.
    if any(b.page and _ARABIC_PAGE.fullmatch(b.page) for b in blocks):
        logger.warning("%s marked as front matter but has arabic page numbers", source)

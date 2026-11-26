"""Expected facts about the generalization corpus: openly licensed ePubs from other publishers.

They are not committed. Download each ePub into data/corpus/<key>/ (the folder name is
the key below). Standard Ebooks (public domain): the "Compatible epub" from its page.
- whymper: https://standardebooks.org/ebooks/edward-whymper/scrambles-amongst-the-alps-in-the-years-1860-69
- slocum:  https://standardebooks.org/ebooks/joshua-slocum/sailing-alone-around-the-world
- engels:  https://standardebooks.org/ebooks/friedrich-engels/the-condition-of-the-working-class-in-england/florence-kelley-wischnewetzky

Pressbooks (open textbooks, no epub:type): the EPUB export from the book's home page.
- exercise-science: https://mhcc.pressbooks.pub/hpe172 (CC BY 4.0)
"""

from pathlib import Path

CORPUS_DIR = Path(__file__).parents[2] / "data" / "corpus"

# Parts of a book that are not content: they must never be searched.
NON_CONTENT_ROLES = {
    "titlepage",
    "halftitlepage",
    "imprint",
    "dedication",
    "epigraph",
    "frontispiece",
    "loi",
    "colophon",
    "copyright-page",
    # Pressbooks (#17): files recognised from their first <div>.
    "cover",
    "toc",
    "frontmatter",
    "backmatter",
    "bibliography",
    # Found from the content, for any publisher (#21).
    "quiz",
}

INCLUDED_SECTIONS = {"engels": 15, "slocum": 23, "whymper": 34, "exercise-science": 418}
APPENDICES = {"engels": 0, "slocum": 0, "whymper": 9, "exercise-science": 0}

# SHA-256 of the edition a committed golden set cites (ADR 0010): a new edition can change
# the section ids, so a different file must fail loudly instead of skewing the evaluation.
EDITION_SHA256 = {
    "exercise-science": "292827f057899c17cffdd7ae91dd02b25670d73d0ea06872588638f10d3e1da4",
}

# `inspect` warnings each book is known to raise: no page markers anywhere (#15); the
# Pressbooks book also has open defects, see docs/ingestion-findings.md (#20).
EXPECTED_WARNINGS = {
    "engels": ["blocks with page"],
    "slocum": ["blocks with page"],
    "whymper": ["blocks with page"],
    "exercise-science": [
        "untitled tables",
        "duplicate paragraphs",
        "words glued to numbers",
        "blocks with page",
    ],
}

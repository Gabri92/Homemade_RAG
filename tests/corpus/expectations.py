"""Expected facts about the generalization corpus: public-domain ePubs from Standard Ebooks.

They are not committed. Download each "Compatible epub" from its page into
data/corpus/<key>/ (the folder name is the key below):
- whymper: https://standardebooks.org/ebooks/edward-whymper/scrambles-amongst-the-alps-in-the-years-1860-69
- slocum:  https://standardebooks.org/ebooks/joshua-slocum/sailing-alone-around-the-world
- engels:  https://standardebooks.org/ebooks/friedrich-engels/the-condition-of-the-working-class-in-england/florence-kelley-wischnewetzky
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
}

INCLUDED_SECTIONS = {"engels": 15, "slocum": 23, "whymper": 34}
APPENDICES = {"engels": 0, "slocum": 0, "whymper": 9}

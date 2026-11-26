"""Roles of the ePub's files: landmarks and the EPUB structural types each file declares.

The role decides whether a file's blocks are searched (see `structure.INCLUDED_ROLES`).
"""

import posixpath

from bs4 import BeautifulSoup, Tag

from homerag.ingest.epub.pressbooks import pressbooks_types

BODY = "body"

_DIVISIONS = {"frontmatter": "frontmatter", "bodymatter": BODY, "backmatter": "backmatter"}
_BODY_TYPES = frozenset({"chapter", "part", "volume", "division", "subchapter"})
_GENRES = frozenset({"fiction", "non-fiction"})


def role_from_types(types: list[str]) -> str:
    """Role from EPUB structural types, most specific first (#13).

    The first specific type wins ("glossary", "titlepage", "colophon"; "chapter" and
    similar mean body); otherwise the division (front/body/back matter); otherwise body.
    Vocabulary prefixes ("z3998:") and genres ("non-fiction") are ignored.
    """
    terms = [t.rsplit(":", 1)[-1] for t in types]
    specific = [t for t in terms if t not in _DIVISIONS and t not in _GENRES]
    if specific:
        return BODY if specific[0] in _BODY_TYPES else specific[0]
    return next((_DIVISIONS[t] for t in terms if t in _DIVISIONS), BODY)


def landmark_types(nav_html: str | bytes) -> dict[str, list[str]]:
    """File name -> every landmark type listed for it in an EPUB3 navigation page."""
    soup = BeautifulSoup(nav_html, "html.parser")
    types: dict[str, list[str]] = {}
    for nav in soup.find_all("nav"):
        if not isinstance(nav, Tag) or "landmarks" not in epub_types(nav):
            continue
        for link in nav.find_all("a", href=True):
            if isinstance(link, Tag):
                file_name = posixpath.basename(str(link["href"]).split("#")[0])
                types.setdefault(file_name, []).extend(epub_types(link))
    return types


def file_types(soup: BeautifulSoup) -> list[str]:
    """Types a document declares about itself: its top-level section first, then <body>.

    Without any epub:type, the Pressbooks markers are used instead (#17).
    """
    body = soup.body
    if body is None:
        return []
    top = body.find(["section", "article"], recursive=False)
    types = (epub_types(top) if isinstance(top, Tag) else []) + epub_types(body)
    return types or pressbooks_types(body)


def epub_types(tag: Tag) -> list[str]:
    """The element's epub:type values (several are allowed, space-separated)."""
    return str(tag.get("epub:type", "")).split()

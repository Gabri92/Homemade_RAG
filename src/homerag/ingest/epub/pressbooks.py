"""Pressbooks conventions (the open-textbook platform): used only where EPUB semantics are missing.

Pressbooks writes no epub:type: each file says what it is in the id or the classes of its
first <div> (#17), and every chapter opens with a title block whose number and authors are
layout, not content (#18). Mapped here to the EPUB vocabulary the rest of the loader uses.
"""

from bs4 import BeautifulSoup, Tag

_PRESSBOOKS_IDS = {
    "cover-image": "cover",
    "half-title-page": "halftitlepage",
    "title-page": "titlepage",
    "copyright-page": "copyright-page",
    "toc": "toc",
}
_PRESSBOOKS_BODY_CLASSES = frozenset({"chapter", "part"})
_PRESSBOOKS_DIVISIONS = {"front-matter": "frontmatter", "back-matter": "backmatter"}
_PRESSBOOKS_NEUTRAL_CLASSES = frozenset({"standard", "miscellaneous"})
# Paragraphs of the chapter title block that are layout, not content (#18).
_PRESSBOOKS_TITLE_EXTRAS = ["chapter-number", "chapter-author"]


def pressbooks_types(body: Tag) -> list[str]:
    """Types from the first <div>: a known id, else a Pressbooks kind class.

    Any other <div> (a sidebar, a figure) says nothing about the file: no types.
    """
    div = body.find("div")
    if not isinstance(div, Tag):
        return []
    if (file_id := str(div.get("id", ""))) in _PRESSBOOKS_IDS:
        return [_PRESSBOOKS_IDS[file_id]]
    classes = [c for c in div.get_attribute_list("class") if c]
    if _PRESSBOOKS_BODY_CLASSES & set(classes):
        return ["chapter"]
    division = next((_PRESSBOOKS_DIVISIONS[c] for c in classes if c in _PRESSBOOKS_DIVISIONS), None)
    if division is None:
        return []
    others = [c for c in classes if c not in _PRESSBOOKS_DIVISIONS]
    return [c for c in others if c not in _PRESSBOOKS_NEUTRAL_CLASSES] + [division]


def remove_title_extras(soup: BeautifulSoup) -> None:
    """#18: drop the chapter number and authors printed under each chapter title."""
    for byline in soup.find_all("p", class_=_PRESSBOOKS_TITLE_EXTRAS):
        byline.decompose()

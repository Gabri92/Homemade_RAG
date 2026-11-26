"""One (X)HTML document -> blocks: headings, paragraphs, lists, tables, figures, pages.

Generic HTML rules, valid for any ePub; tool conventions only through `pressbooks`.
"""

import re
from dataclasses import replace

from bs4 import BeautifulSoup, Tag
from bs4.element import PageElement

from homerag.ingest.epub import pressbooks
from homerag.ingest.epub.roles import BODY, epub_types
from homerag.ingest.epub.tables import table_text
from homerag.models import Block

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_BLOCK_TAGS = (*_HEADING_TAGS, "p", "li", "table", "img", "dt")
_LIST_TAGS = ("ul", "ol")
_FIGURE_CONTAINERS = ("figure", "div")


def html_to_blocks(
    html: str | bytes, source: str, role: str = BODY, start_page: str | None = None
) -> list[Block]:
    """Convert one (X)HTML document into blocks, keeping headings, lists, tables and figures.

    `start_page` is the page in effect before the document's first page marker.
    """
    return soup_to_blocks(parse(html), source, role, start_page)


def parse(html: str | bytes) -> BeautifulSoup:
    """Parse a document and remove what is markup, not text (line breaks, note numbers)."""
    soup = BeautifulSoup(html, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with(" ")
    for link in soup.find_all(_is_note_link):
        # #14: note numbers would stick to words ("summit.12"); notes keep their own text.
        link.decompose()
    for marker in soup.find_all(_is_heading_note_marker):
        # #18: "Protein Metabolism4" in a heading is a bare note number, not a title.
        marker.decompose()
    pressbooks.remove_title_extras(soup)
    return soup


def _is_heading_note_marker(tag: Tag) -> bool:
    return (
        tag.name == "sup"
        and tag.get_text().strip().isdigit()
        and tag.find_parent(_HEADING_TAGS) is not None
    )


_NOTE_LINK_TYPES = frozenset({"noteref", "backlink"})
_NOTE_LINK_ROLES = frozenset({"doc-noteref", "doc-backlink"})


def _is_note_link(tag: Tag) -> bool:
    return bool(_NOTE_LINK_TYPES & set(epub_types(tag))) or tag.get("role") in _NOTE_LINK_ROLES


def soup_to_blocks(
    soup: BeautifulSoup, source: str, role: str, start_page: str | None
) -> list[Block]:
    """Blocks of a parsed document, in document order, each with its role and page."""
    figure_containers = {id(c) for img in soup.find_all("img") if (c := _figure_container(img))}
    blocks: list[Block] = []
    for element in soup.find_all(_is_block_element):
        if not isinstance(element, Tag) or _is_nested_content(element, figure_containers):
            continue
        block = _element_to_block(element, source)
        if block.text or block.kind == "figure":
            blocks.append(replace(block, role=role, page=_page_at(element, start_page)))
    return blocks


# --- pages (printed-page markers) ------------------------------------------------


def _page_at(element: Tag, start_page: str | None) -> str | None:
    """Page where the element starts: the last page marker before its first text.

    A marker in the middle of a paragraph therefore applies to the blocks after it,
    while a marker at the very start of a heading applies to the heading itself.
    """
    first_text = element.find(string=_has_text)
    anchor: PageElement = first_text if first_text is not None else element
    marker = anchor.find_previous(_is_page_marker)
    return _page_label(marker) if isinstance(marker, Tag) else start_page


def last_page(soup: BeautifulSoup, current: str | None) -> str | None:
    """Page in effect at the end of the document: it carries over to the next file."""
    markers = [m for m in soup.find_all(_is_page_marker) if isinstance(m, Tag)]
    return (_page_label(markers[-1]) or current) if markers else current


def _is_page_marker(tag: Tag) -> bool:
    return "pagebreak" in epub_types(tag) or tag.get("role") == "doc-pagebreak"


def _page_label(marker: Tag) -> str | None:
    """ " page 224. " -> "224"; falls back to the id ("page_224")."""
    label = str(marker.get("aria-label") or marker.get("title") or "").strip()
    label = re.sub(r"^page\s*", "", label, flags=re.IGNORECASE).rstrip(".").strip()
    if not label:
        label = re.sub(r"^page[_-]?", "", str(marker.get("id", "")), flags=re.IGNORECASE)
    return label or None


def _has_text(text: str | None) -> bool:
    return bool(text and text.strip())


# --- blocks ---------------------------------------------------------------------


def _figure_container(img: Tag) -> Tag | None:
    """The small element grouping an image with its caption, if any.

    The enclosing `<figure>`, even when the image is wrapped in a `<p>` or `<span>`
    (#19), else a parent `div`. It qualifies only if it holds no structure of its own
    (headings, tables, other images): otherwise it is a section, not a figure.
    """
    figure = img.find_parent("figure")
    container = figure if figure is not None else img.parent
    if not isinstance(container, Tag) or container.name not in _FIGURE_CONTAINERS:
        return None
    if container.find([*_HEADING_TAGS, "table"]) or len(container.find_all("img")) > 1:
        return None
    return container


_CONTAINER_TAGS = ("div", "section", "figure", "ul", "ol", "dl", "blockquote")


def _is_block_element(tag: Tag) -> bool:
    return tag.name in _BLOCK_TAGS or _is_text_only_div(tag)


def _is_text_only_div(tag: Tag) -> bool:
    """#19: a <div> holding text but no blocks or containers is a paragraph without <p>."""
    return (
        tag.name == "div"
        and tag.find([*_BLOCK_TAGS, *_CONTAINER_TAGS]) is None
        and bool(tag.get_text().strip())
    )


def _is_nested_content(element: Tag, figure_containers: set[int]) -> bool:
    """True if the element is already covered by an enclosing table, list item or figure."""
    if element.find_parent(["table", "dd"]) is not None:
        return True  # tables and definitions are read as a whole by their own block
    if element.name != "img" and any(id(p) in figure_containers for p in element.parents):
        return True
    return element.name != "li" and element.find_parent("li") is not None


def _element_to_block(element: Tag, source: str) -> Block:
    name = element.name
    if name in _HEADING_TAGS:
        return Block("heading", _text(element), source, level=int(name[1]))
    if name == "li":
        return Block("list_item", _list_item_text(element), source)
    if name == "table":
        return Block("table", table_text(element), source)
    if name == "img":
        return Block("figure", _figure_caption(element), source)
    if name == "dt":
        return Block("paragraph", _definition_text(element), source)
    return Block("paragraph", _text(element), source)


def _definition_text(term: Tag) -> str:
    """Definition-list entry (glossary): "term: definition", with all its <dd> siblings."""
    definitions = []
    for sibling in term.find_next_siblings(["dt", "dd"]):
        if sibling.name == "dt":
            break
        definitions.append(_text(sibling))
    name = _text(term).rstrip(".:")  # terms often end with "." in the markup
    return f"{name}: {' '.join(definitions)}" if definitions else name


def _text(element: Tag) -> str:
    # HTML collapses whitespace: do the same so markup indentation does not leak into text.
    return " ".join(element.get_text().split())


def _list_item_text(item: Tag) -> str:
    """Text of a list item without its nested lists (they become their own blocks)."""
    parts = [
        child.get_text()
        for child in item.children
        if not (isinstance(child, Tag) and child.name in _LIST_TAGS)
    ]
    return " ".join("".join(parts).split())


def _figure_caption(img: Tag) -> str:
    """Caption of an image: the whole text of its <figure> (title and caption, #19);
    in a `div`, its <figcaption>, else the text of the div (the image has none)."""
    container = _figure_container(img)
    if container is None:
        return ""
    if container.name == "figure":
        # Joined part by part: title and caption are separate elements with no space.
        parts = (" ".join(c.get_text().split()) for c in container)
        return " ".join(part for part in parts if part)
    figcaption = container.find("figcaption")
    return _text(figcaption if isinstance(figcaption, Tag) else container)

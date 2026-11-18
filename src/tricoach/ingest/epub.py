"""ePub loader: ePub file -> list of format-independent blocks.

The only ingestion code that knows about ePub/HTML; everything downstream works on `Block`s.
"""

import posixpath
import re
from dataclasses import replace
from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, Tag
from bs4.element import PageElement
from ebooklib import epub

from tricoach.models import Block

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_BLOCK_TAGS = (*_HEADING_TAGS, "p", "li", "table", "img", "dt")
_LIST_TAGS = ("ul", "ol")
_FIGURE_CONTAINERS = ("figure", "div")
BODY = "body"


def load_epub(path: Path) -> list[Block]:
    """Read an ePub and return its content blocks in reading (spine) order.

    Navigation documents (table of contents) are skipped: they are not book content.
    Each block gets the role of its file (from the landmarks and the file's own
    epub:type) and the printed page where it starts (from the page markers); the page
    carries over between files.
    """
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    landmarks = _book_landmark_types(book)
    blocks: list[Block] = []
    page: str | None = None
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is None or not _is_book_content(item):
            continue
        name = item.get_name()
        soup = _parse(item.get_content())
        role = role_from_types(landmarks.get(posixpath.basename(name), []) + _file_types(soup))
        blocks.extend(_soup_to_blocks(soup, name, role, page))
        page = _last_page(soup, page)
    return blocks


def epub_text(path: Path) -> str:
    """All visible text of the book's content documents: the reference for text coverage."""
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    texts = []
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is not None and _is_book_content(item):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            texts.append((soup.body or soup).get_text(" "))
    return "\n".join(texts)


def _is_book_content(item: epub.EpubItem) -> bool:
    # ebooklib types the EPUB3 navigation page as a regular document (ITEM_DOCUMENT):
    # only its class tells it apart.
    return item.get_type() == ebooklib.ITEM_DOCUMENT and not isinstance(item, epub.EpubNav)


def html_to_blocks(
    html: str | bytes, source: str, role: str = BODY, start_page: str | None = None
) -> list[Block]:
    """Convert one (X)HTML document into blocks, keeping headings, lists, tables and figures.

    `start_page` is the page in effect before the document's first page marker.
    """
    return _soup_to_blocks(_parse(html), source, role, start_page)


def _parse(html: str | bytes) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with(" ")
    for link in soup.find_all(_is_note_link):
        # #14: note numbers would stick to words ("summit.12"); notes keep their own text.
        link.decompose()
    return soup


_NOTE_LINK_TYPES = frozenset({"noteref", "backlink"})
_NOTE_LINK_ROLES = frozenset({"doc-noteref", "doc-backlink"})


def _is_note_link(tag: Tag) -> bool:
    return bool(_NOTE_LINK_TYPES & set(_epub_types(tag))) or tag.get("role") in _NOTE_LINK_ROLES


def _soup_to_blocks(
    soup: BeautifulSoup, source: str, role: str, start_page: str | None
) -> list[Block]:
    figure_containers = {id(c) for img in soup.find_all("img") if (c := _figure_container(img))}
    blocks: list[Block] = []
    for element in soup.find_all(_BLOCK_TAGS):
        if not isinstance(element, Tag) or _is_nested_content(element, figure_containers):
            continue
        block = _element_to_block(element, source)
        if block.text or block.kind == "figure":
            blocks.append(replace(block, role=role, page=_page_at(element, start_page)))
    return blocks


# --- roles (landmarks + each file's own epub:type) -------------------------------

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
        if not isinstance(nav, Tag) or "landmarks" not in _epub_types(nav):
            continue
        for link in nav.find_all("a", href=True):
            if isinstance(link, Tag):
                file_name = posixpath.basename(str(link["href"]).split("#")[0])
                types.setdefault(file_name, []).extend(_epub_types(link))
    return types


def _file_types(soup: BeautifulSoup) -> list[str]:
    """Types a document declares about itself: its top-level section first, then <body>."""
    body = soup.body
    if body is None:
        return []
    top = body.find(["section", "article"], recursive=False)
    return (_epub_types(top) if isinstance(top, Tag) else []) + _epub_types(body)


def _book_landmark_types(book: epub.EpubBook) -> dict[str, list[str]]:
    for item in book.get_items():
        if isinstance(item, epub.EpubNav):
            return landmark_types(item.get_content())
    return {}


def _epub_types(tag: Tag) -> list[str]:
    return str(tag.get("epub:type", "")).split()


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


def _last_page(soup: BeautifulSoup, current: str | None) -> str | None:
    markers = [m for m in soup.find_all(_is_page_marker) if isinstance(m, Tag)]
    return (_page_label(markers[-1]) or current) if markers else current


def _is_page_marker(tag: Tag) -> bool:
    return "pagebreak" in _epub_types(tag) or tag.get("role") == "doc-pagebreak"


def _page_label(marker: Tag) -> str | None:
    """ " page 224. " -> "224"; falls back to the id ("page_224")."""
    label = str(marker.get("aria-label") or marker.get("title") or "").strip()
    label = re.sub(r"^page\s*", "", label, flags=re.IGNORECASE).rstrip(".").strip()
    if not label:
        label = re.sub(r"^page[_-]?", "", str(marker.get("id", "")), flags=re.IGNORECASE)
    return label or None


def _has_text(text: str | None) -> bool:
    return bool(text and text.strip())


def _figure_container(img: Tag) -> Tag | None:
    """The small element grouping an image with its caption, if any.

    A parent `div`/`figure` qualifies only if it holds no structure of its own
    (headings, tables, other images): otherwise it is a section, not a figure.
    """
    parent = img.parent
    if not isinstance(parent, Tag) or parent.name not in _FIGURE_CONTAINERS:
        return None
    if parent.find([*_HEADING_TAGS, "table"]) or len(parent.find_all("img")) > 1:
        return None
    return parent


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
        return Block("table", _table_text(element), source)
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
    """Caption of an image: <figcaption>, else the text of its container (the image has none)."""
    container = _figure_container(img)
    if container is None:
        return ""
    figcaption = container.find("figcaption")
    return _text(figcaption if isinstance(figcaption, Tag) else container)


# --- tables ---------------------------------------------------------------------


def _table_text(table: Tag) -> str:
    """Table as Markdown, preceded by its <caption> (e.g. "TABLE 11.1 ...") when present."""
    caption = table.find("caption")
    title = _text(caption) if isinstance(caption, Tag) else ""
    markdown = _grid_to_markdown(_table_grid(table))
    return "\n".join(part for part in (title, markdown) if part)


def _table_grid(table: Tag) -> list[list[str]]:
    """Rows of cell texts, with merged cells (rowspan/colspan) expanded.

    A merged cell's value is repeated in every cell it covers, so each row stays
    self-contained (e.g. every week row still says which period it belongs to).
    """
    grid: list[list[str]] = []
    carried: dict[int, tuple[int, str]] = {}  # column -> (rows still covered, text)
    for tr in table.find_all("tr"):
        row: list[str] = []
        for cell in tr.find_all(["th", "td"]):
            _fill_carried(row, carried)
            text = _text(cell).replace("|", r"\|")
            rowspan = _span(cell, "rowspan")
            for _ in range(_span(cell, "colspan")):
                if rowspan > 1:
                    carried[len(row)] = (rowspan - 1, text)
                row.append(text)
        _fill_carried(row, carried)
        grid.append(row)
    return [row for row in grid if any(row)]


def _fill_carried(row: list[str], carried: dict[int, tuple[int, str]]) -> None:
    """Append values of cells merged down from previous rows at the current position."""
    while len(row) in carried:
        rows_left, text = carried[len(row)]
        if rows_left == 1:
            del carried[len(row)]
        else:
            carried[len(row)] = (rows_left - 1, text)
        row.append(text)


def _span(cell: Tag, attribute: str) -> int:
    try:
        return max(1, int(str(cell.get(attribute, "1"))))
    except ValueError:
        return 1


def _grid_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    header, *body = padded
    lines = [_markdown_row(header), "|" + " --- |" * width]
    lines += [_markdown_row(row) for row in body]
    return "\n".join(lines)


def _markdown_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"

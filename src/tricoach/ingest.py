"""Ingestion: book file -> list of format-independent blocks.

Only the loader knows the file format; everything downstream works on `Block`s.
"""

from pathlib import Path

import ebooklib
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from tricoach.models import Block

_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_BLOCK_TAGS = (*_HEADING_TAGS, "p", "li", "table", "img")
_LIST_TAGS = ("ul", "ol")
_FIGURE_CONTAINERS = ("figure", "div")


def load_epub(path: Path) -> list[Block]:
    """Read an ePub and return its content blocks in reading (spine) order.

    Navigation documents (table of contents) are skipped: they are not book content.
    """
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    blocks: list[Block] = []
    for item_id, _linear in book.spine:
        item = book.get_item_with_id(item_id)
        if item is not None and _is_book_content(item):
            blocks.extend(html_to_blocks(item.get_content(), source=item.get_name()))
    return blocks


def _is_book_content(item: epub.EpubItem) -> bool:
    # ebooklib types the EPUB3 navigation page as a regular document (ITEM_DOCUMENT):
    # only its class tells it apart.
    return item.get_type() == ebooklib.ITEM_DOCUMENT and not isinstance(item, epub.EpubNav)


def html_to_blocks(html: str | bytes, source: str) -> list[Block]:
    """Convert one (X)HTML document into blocks, keeping headings, lists, tables and figures."""
    soup = BeautifulSoup(html, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with(" ")

    figure_containers = {id(c) for img in soup.find_all("img") if (c := _figure_container(img))}
    blocks: list[Block] = []
    for element in soup.find_all(_BLOCK_TAGS):
        if not isinstance(element, Tag) or _is_nested_content(element, figure_containers):
            continue
        block = _element_to_block(element, source)
        if block.text or block.kind == "figure":
            blocks.append(block)
    return blocks


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
    if element.find_parent("table") is not None:
        return True
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
    return Block("paragraph", _text(element), source)


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


# --- dump -----------------------------------------------------------------------


def format_blocks(blocks: list[Block]) -> str:
    """Human-readable dump: one block per entry, tagged with kind, level and source."""
    return "\n".join(_format_block(block) for block in blocks) + "\n"


def _format_block(block: Block) -> str:
    tag = block.kind if block.level is None else f"{block.kind} L{block.level}"
    # Multi-line blocks (tables) are indented so each entry stays visually separate.
    text = block.text.replace("\n", "\n    ")
    return f"[{tag}] {block.source}\n    {text}"

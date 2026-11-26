"""HTML tables -> Markdown, with merged cells (rowspan/colspan) expanded (#1, #2)."""

from bs4 import Tag


def table_text(table: Tag) -> str:
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


def _text(element: Tag) -> str:
    # Same whitespace rule as html.py, repeated to keep this module free of imports.
    return " ".join(element.get_text().split())

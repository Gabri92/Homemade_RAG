from collections.abc import Callable
from pathlib import Path

from tricoach.ingest import format_blocks, html_to_blocks, load_epub
from tricoach.models import Block

SOURCE = "ch01.xhtml"
MakeEpub = Callable[[list[tuple[str, str]]], Path]  # see the `make_epub` fixture in conftest.py


def blocks_of(html: str) -> list[Block]:
    return html_to_blocks(f"<html><body>{html}</body></html>", source=SOURCE)


# --- html_to_blocks -------------------------------------------------------------


def test_headings_keep_their_level() -> None:
    blocks = blocks_of("<h1>Part One</h1><h2>The Base Period</h2>")

    assert blocks == [
        Block("heading", "Part One", SOURCE, level=1),
        Block("heading", "The Base Period", SOURCE, level=2),
    ]


def test_paragraph_whitespace_and_inline_markup_are_normalized() -> None:
    blocks = blocks_of("<p>Train   <em>easy</em>,\n   then\n<b>hard</b>.</p>")

    assert blocks == [Block("paragraph", "Train easy, then hard.", SOURCE)]


def test_line_break_becomes_a_space() -> None:
    blocks = blocks_of("<p>first line<br/>second line</p>")

    assert blocks[0].text == "first line second line"


def test_empty_elements_are_dropped() -> None:
    assert blocks_of("<p>   </p><h2></h2><p>Kept.</p>") == [Block("paragraph", "Kept.", SOURCE)]


def test_list_items_become_separate_blocks_in_order() -> None:
    blocks = blocks_of("<ul><li>Swim</li><li>Bike</li><li>Run</li></ul>")

    assert [b.text for b in blocks] == ["Swim", "Bike", "Run"]
    assert all(b.kind == "list_item" for b in blocks)


def test_nested_list_items_are_not_duplicated() -> None:
    blocks = blocks_of("<ul><li>Abilities<ul><li>Endurance</li><li>Force</li></ul></li></ul>")

    assert [b.text for b in blocks] == ["Abilities", "Endurance", "Force"]


def test_paragraph_inside_list_item_is_not_duplicated() -> None:
    blocks = blocks_of("<ul><li><p>Only once.</p></li></ul>")

    assert blocks == [Block("list_item", "Only once.", SOURCE)]


def test_table_becomes_one_markdown_block() -> None:
    blocks = blocks_of(
        "<p>Before.</p>"
        "<table>"
        "<tr><th>Zone</th><th>% LTHR</th></tr>"
        "<tr><td>1</td><td>&lt;81</td></tr>"
        "<tr><td><p>2</p></td><td>81-89</td></tr>"
        "</table>"
        "<p>After.</p>"
    )

    assert [b.kind for b in blocks] == ["paragraph", "table", "paragraph"]
    assert blocks[1].text == ("| Zone | % LTHR |\n| --- | --- |\n| 1 | <81 |\n| 2 | 81-89 |")


def test_table_rows_are_padded_and_pipes_escaped() -> None:
    blocks = blocks_of(
        "<table><tr><th>A</th><th>B</th></tr><tr><td>x|y</td></tr><tr><td></td></tr></table>"
    )

    assert blocks[0].text == "| A | B |\n| --- | --- |\n| x\\|y |  |"


def test_table_caption_becomes_first_line_of_the_table_block() -> None:
    blocks = blocks_of(
        "<table><caption><p><span>TABLE 3.1</span> Weekly Hours</p></caption>"
        "<tr><th>Week</th><th>Hours</th></tr><tr><td>1</td><td>8</td></tr></table>"
    )

    assert blocks == [
        Block(
            "table",
            "TABLE 3.1 Weekly Hours\n| Week | Hours |\n| --- | --- |\n| 1 | 8 |",
            SOURCE,
        )
    ]


def test_table_rowspan_repeats_the_value_in_covered_rows() -> None:
    blocks = blocks_of(
        "<table>"
        "<tr><th>Period</th><th>Week</th></tr>"
        '<tr><td rowspan="2">Base 1</td><td>Week 1</td></tr>'
        "<tr><td>Week 2</td></tr>"
        "<tr><td>Build 1</td><td>Week 1</td></tr>"
        "</table>"
    )

    assert blocks[0].text == (
        "| Period | Week |\n| --- | --- |\n"
        "| Base 1 | Week 1 |\n| Base 1 | Week 2 |\n| Build 1 | Week 1 |"
    )


def test_table_colspan_repeats_the_value_across_columns() -> None:
    blocks = blocks_of(
        "<table>"
        "<tr><th>Day</th><th>Swim</th><th>Bike</th></tr>"
        '<tr><td>Mon</td><td colspan="2">Rest</td></tr>'
        "</table>"
    )

    assert blocks[0].text == "| Day | Swim | Bike |\n| --- | --- | --- |\n| Mon | Rest | Rest |"


def test_table_rowspan_in_middle_column_keeps_later_cells_aligned() -> None:
    blocks = blocks_of(
        "<table>"
        "<tr><th>A</th><th>B</th><th>C</th></tr>"
        '<tr><td>a1</td><td rowspan="2">b</td><td>c1</td></tr>'
        "<tr><td>a2</td><td>c2</td></tr>"
        "</table>"
    )

    assert blocks[0].text.splitlines()[2:] == ["| a1 | b | c1 |", "| a2 | b | c2 |"]


# --- figures --------------------------------------------------------------------


def test_figure_takes_the_caption_from_its_container() -> None:
    blocks = blocks_of(
        "<p>Before.</p>"
        '<div><img src="f1.jpg" alt="Image"/><p>FIGURE 4.1 Fitness over a season</p></div>'
        "<p>After.</p>"
    )

    assert blocks == [
        Block("paragraph", "Before.", SOURCE),
        Block("figure", "FIGURE 4.1 Fitness over a season", SOURCE),
        Block("paragraph", "After.", SOURCE),
    ]


def test_figure_caption_before_the_image_is_not_duplicated() -> None:
    blocks = blocks_of('<div><p>TABLE 7.3 Annual Hours</p><img src="t.jpg"/></div>')

    assert blocks == [Block("figure", "TABLE 7.3 Annual Hours", SOURCE)]


def test_figure_uses_figcaption_when_present() -> None:
    blocks = blocks_of('<figure><img src="f.jpg"/><figcaption>Swim drill</figcaption></figure>')

    assert blocks == [Block("figure", "Swim drill", SOURCE)]


def test_figure_without_caption_is_kept_with_empty_text() -> None:
    blocks = blocks_of('<p>Text.</p><img src="photo.jpg"/>')

    assert blocks == [Block("paragraph", "Text.", SOURCE), Block("figure", "", SOURCE)]


# --- load_epub ------------------------------------------------------------------


def test_load_epub_follows_spine_order_and_skips_navigation(make_epub: MakeEpub) -> None:
    path = make_epub(
        [
            ("ch01.xhtml", "<h1>Chapter One</h1><p>First.</p>"),
            ("ch02.xhtml", "<h1>Chapter Two</h1><p>Second.</p>"),
        ]
    )

    blocks = load_epub(path)

    assert [b.text for b in blocks] == ["Chapter One", "First.", "Chapter Two", "Second."]
    assert [b.source for b in blocks] == ["ch01.xhtml"] * 2 + ["ch02.xhtml"] * 2


# --- format_blocks --------------------------------------------------------------


def test_format_blocks_tags_each_block_and_indents_multiline_text() -> None:
    blocks = [
        Block("heading", "Base Period", SOURCE, level=2),
        Block("table", "| A |\n| --- |", SOURCE),
    ]

    assert format_blocks(blocks) == (
        "[heading L2] ch01.xhtml\n    Base Period\n[table] ch01.xhtml\n    | A |\n    | --- |\n"
    )

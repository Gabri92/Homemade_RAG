import pytest

from tests.conftest import MakeEpub
from tricoach.ingest import html_to_blocks, load_epub
from tricoach.ingest.epub import landmark_types, role_from_types
from tricoach.models import Block

SOURCE = "ch01.xhtml"


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


# --- note references (#14) -------------------------------------------------------


def test_note_references_are_removed_from_the_text() -> None:
    blocks = blocks_of(
        '<p>We reached the summit.<a href="endnotes.xhtml#n12" epub:type="noteref">12</a> '
        'Then we rested<a href="#n13" role="doc-noteref">13</a> for an hour.</p>'
    )

    assert blocks[0].text == "We reached the summit. Then we rested for an hour."


def test_backlinks_in_notes_are_removed() -> None:
    backlink = '<a href="#r12" epub:type="backlink">↩</a>'
    blocks = blocks_of(f"<ol><li><p>Whymper climbed it in 1865. {backlink}</p></li></ol>")

    assert blocks[0].text == "Whymper climbed it in 1865."


# --- definition lists (glossary) -------------------------------------------------


def test_definition_list_entry_becomes_term_and_definition() -> None:
    blocks = blocks_of(
        "<dl>"
        "<dt>LTHR</dt><dd>Lactate threshold heart rate.</dd>"
        "<dt>Base period.</dt><dd><p>The general preparation phase.</p></dd>"
        "</dl>"
    )

    assert blocks == [
        Block("paragraph", "LTHR: Lactate threshold heart rate.", SOURCE),
        Block("paragraph", "Base period: The general preparation phase.", SOURCE),
    ]


def test_term_with_several_definitions_keeps_them_all() -> None:
    blocks = blocks_of("<dl><dt>Zone</dt><dd>An intensity range.</dd><dd>See Chapter 4.</dd></dl>")

    assert blocks == [Block("paragraph", "Zone: An intensity range. See Chapter 4.", SOURCE)]


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


# --- pages ----------------------------------------------------------------------


def marker(label: str) -> str:
    return f'<span epub:type="pagebreak" id="page_{label}" aria-label=" page {label}. "></span>'


def pages_of(html: str, start_page: str | None = None) -> list[tuple[str, str | None]]:
    blocks = html_to_blocks(f"<html><body>{html}</body></html>", SOURCE, start_page=start_page)
    return [(b.text, b.page) for b in blocks]


def test_block_takes_the_page_of_the_last_marker_before_it() -> None:
    html = f"{marker('11')}<p>First.</p><p>Second.</p>{marker('12')}<p>Third.</p>"

    assert pages_of(html) == [("First.", "11"), ("Second.", "11"), ("Third.", "12")]


def test_marker_in_the_middle_of_a_paragraph_applies_to_the_next_block() -> None:
    html = f"{marker('224')}<p>Starts on 224 {marker('225')} ends on 225.</p><p>Next.</p>"

    assert pages_of(html) == [("Starts on 224 ends on 225.", "224"), ("Next.", "225")]


def test_marker_at_the_start_of_a_heading_applies_to_the_heading() -> None:
    html = f"<p>Before.</p><h2>{marker('30')}Chapter Two</h2>"

    assert pages_of(html, start_page="29") == [("Before.", "29"), ("Chapter Two", "30")]


def test_page_labels_keep_roman_numerals_and_letters() -> None:
    html = f"{marker('A')}<p>Blank.</p>{marker('xii')}<p>Preface.</p>"

    assert pages_of(html) == [("Blank.", "A"), ("Preface.", "xii")]


def test_without_markers_pages_are_unknown() -> None:
    assert pages_of("<p>No markers.</p>") == [("No markers.", None)]


def test_load_epub_carries_the_page_into_the_next_file(make_epub: MakeEpub) -> None:
    path = make_epub(
        [
            ("ch01.xhtml", f"{marker('7')}<p>One.</p>{marker('8')}"),
            ("ch02.xhtml", "<p>Two.</p>"),
        ]
    )

    assert [(b.text, b.page) for b in load_epub(path)] == [("One.", "7"), ("Two.", "8")]


# --- roles ----------------------------------------------------------------------

NAV = """<html><body>
<nav epub:type="toc"><ol><li><a href="ch01.xhtml">Chapter 1</a></li></ol></nav>
<nav epub:type="landmarks"><ol>
  <li><a epub:type="cover" href="cover.xhtml">Cover</a></li>
  <li><a epub:type="bodymatter" href="cover.xhtml">Start of Content</a></li>
  <li><a epub:type="glossary" href="glossary.xhtml#g1">Glossary</a></li>
  <li><a epub:type="index" href="../xhtml/index.xhtml">Index</a></li>
</ol></nav></body></html>"""


def test_landmark_types_map_files_to_all_their_landmark_types() -> None:
    assert landmark_types(NAV) == {
        "cover.xhtml": ["cover", "bodymatter"],
        "glossary.xhtml": ["glossary"],
        "index.xhtml": ["index"],
    }


@pytest.mark.parametrize(
    ("types", "role"),
    [
        (["glossary"], "glossary"),
        (["cover", "bodymatter"], "cover"),  # a division never hides a specific type
        (["backmatter", "endnotes"], "endnotes"),  # "backmatter endnotes" landmark
        (["frontmatter", "titlepage"], "titlepage"),  # generic landmark + file's own type
        (["bodymatter", "z3998:non-fiction", "chapter"], "body"),  # chapters are body
        (["frontmatter", "z3998:frontispiece"], "frontispiece"),  # vocabulary prefix dropped
        (["backmatter", "z3998:non-fiction"], "backmatter"),  # only a division
        (["bodymatter"], "body"),
        ([], "body"),
    ],
)
def test_role_comes_from_the_most_specific_declared_type(types: list[str], role: str) -> None:
    assert role_from_types(types) == role


def test_load_epub_reads_the_type_each_file_declares(make_epub: MakeEpub) -> None:
    path = make_epub(
        [
            ("dedication.xhtml", '<section epub:type="dedication"><p>To my family.</p></section>'),
            ("chapter-1.xhtml", '<section epub:type="chapter"><h2>I</h2><p>Text.</p></section>'),
            ("colophon.xhtml", '<section epub:type="colophon"><p>Set in Times.</p></section>'),
        ]
    )

    roles = {b.source.rsplit("/", 1)[-1]: b.role for b in load_epub(path)}

    assert roles == {
        "dedication.xhtml": "dedication",
        "chapter-1.xhtml": "body",
        "colophon.xhtml": "colophon",
    }


def test_blocks_get_the_role_passed_by_the_loader() -> None:
    blocks = html_to_blocks("<p>Term: definition.</p>", "glossary.xhtml", role="glossary")

    assert blocks[0].role == "glossary"


def test_load_epub_defaults_to_body_without_landmarks(make_epub: MakeEpub) -> None:
    path = make_epub([("ch01.xhtml", "<p>Text.</p>")])

    assert {b.role for b in load_epub(path)} == {"body"}


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

from homerag.ingest import html_to_blocks
from homerag.models import Block
from tests.conftest import SOURCE, blocks_of, page_marker


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


def pages_of(html: str, start_page: str | None = None) -> list[tuple[str, str | None]]:
    blocks = html_to_blocks(f"<html><body>{html}</body></html>", SOURCE, start_page=start_page)
    return [(b.text, b.page) for b in blocks]


def test_block_takes_the_page_of_the_last_marker_before_it() -> None:
    html = f"{page_marker('11')}<p>First.</p><p>Second.</p>{page_marker('12')}<p>Third.</p>"

    assert pages_of(html) == [("First.", "11"), ("Second.", "11"), ("Third.", "12")]


def test_marker_in_the_middle_of_a_paragraph_applies_to_the_next_block() -> None:
    html = f"{page_marker('224')}<p>Starts on 224 {page_marker('225')} ends on 225.</p><p>Next.</p>"

    assert pages_of(html) == [("Starts on 224 ends on 225.", "224"), ("Next.", "225")]


def test_marker_at_the_start_of_a_heading_applies_to_the_heading() -> None:
    html = f"<p>Before.</p><h2>{page_marker('30')}Chapter Two</h2>"

    assert pages_of(html, start_page="29") == [("Before.", "29"), ("Chapter Two", "30")]


def test_page_labels_keep_roman_numerals_and_letters() -> None:
    html = f"{page_marker('A')}<p>Blank.</p>{page_marker('xii')}<p>Preface.</p>"

    assert pages_of(html) == [("Blank.", "A"), ("Preface.", "xii")]


def test_without_markers_pages_are_unknown() -> None:
    assert pages_of("<p>No markers.</p>") == [("No markers.", None)]


def test_blocks_get_the_role_passed_by_the_loader() -> None:
    blocks = html_to_blocks("<p>Term: definition.</p>", "glossary.xhtml", role="glossary")

    assert blocks[0].role == "glossary"


def test_note_number_in_a_heading_is_removed_but_not_in_text() -> None:
    blocks = blocks_of("<h1>Lactate Threshold<sup>4</sup></h1><p>Area in m<sup>2</sup>.</p>")

    assert [b.text for b in blocks] == ["Lactate Threshold", "Area in m2."]


def test_figure_keeps_title_and_caption_when_the_image_is_wrapped() -> None:
    blocks = blocks_of(
        '<figure><div data-type="title">Atrophy</div><p><span><img src="a.png"/></span></p>'
        "<figcaption>Muscles shrink with disuse.</figcaption></figure><p>After.</p>"
    )

    assert blocks == [
        Block("figure", "Atrophy Muscles shrink with disuse.", SOURCE),
        Block("paragraph", "After.", SOURCE),
    ]


def test_text_only_divs_become_paragraphs() -> None:
    blocks = blocks_of(
        '<div class="box"><span>Stretch daily.</span></div>'
        "<div><div>Inner text.</div><p>A real paragraph.</p></div>"
    )

    assert [(b.kind, b.text) for b in blocks] == [
        ("paragraph", "Stretch daily."),
        ("paragraph", "Inner text."),
        ("paragraph", "A real paragraph."),
    ]

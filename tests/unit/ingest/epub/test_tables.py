from homerag.models import Block
from tests.conftest import SOURCE, blocks_of


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

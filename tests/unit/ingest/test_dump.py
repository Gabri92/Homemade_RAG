from tricoach.ingest import format_blocks
from tricoach.models import Block


def test_format_blocks_tags_each_block_and_indents_multiline_text() -> None:
    blocks = [
        Block("heading", "Base Period", "ch01.xhtml", level=2, page="12"),
        Block("table", "| A |\n| --- |", "ch01.xhtml"),
    ]

    assert format_blocks(blocks) == (
        "[heading L2] ch01.xhtml · p. 12 · body\n    Base Period\n"
        "[table] ch01.xhtml · body\n    | A |\n    | --- |\n"
    )

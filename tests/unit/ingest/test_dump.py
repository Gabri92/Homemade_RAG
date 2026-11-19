from tricoach.ingest import format_blocks, format_sections
from tricoach.models import Block, Book, Section


def test_format_blocks_tags_each_block_and_indents_multiline_text() -> None:
    blocks = [
        Block("heading", "Base Period", "ch01.xhtml", level=2, page="12"),
        Block("table", "| A |\n| --- |", "ch01.xhtml"),
    ]

    assert format_blocks(blocks) == (
        "[heading L2] ch01.xhtml · p. 12 · body\n    Base Period\n"
        "[table] ch01.xhtml · body\n    | A |\n    | --- |\n"
    )


def _section(id_: str, pages: tuple[str | None, str | None], include: bool = True) -> Section:
    first, last = pages
    return Section(id_, id_, 1, (id_,), "body", include, (), first_page=first, last_page=last)


def test_format_sections_lists_ids_pages_and_excluded_flag() -> None:
    book = Book(
        "synthetic.epub",
        (
            _section("cover", (None, None), include=False),
            _section("chapter-one", ("1", "9")),
            _section("chapter-one/base", ("4", "4")),
        ),
    )

    assert format_sections(book) == (
        "cover  no page  [EXCLUDED]\nchapter-one  p. 1-9\nchapter-one/base  p. 4\n"
    )

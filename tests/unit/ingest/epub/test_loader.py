from homerag.ingest import load_epub
from tests.conftest import MakeEpub, page_marker


def test_load_epub_carries_the_page_into_the_next_file(make_epub: MakeEpub) -> None:
    path = make_epub(
        [
            ("ch01.xhtml", f"{page_marker('7')}<p>One.</p>{page_marker('8')}"),
            ("ch02.xhtml", "<p>Two.</p>"),
        ]
    )

    assert [(b.text, b.page) for b in load_epub(path)] == [("One.", "7"), ("Two.", "8")]


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

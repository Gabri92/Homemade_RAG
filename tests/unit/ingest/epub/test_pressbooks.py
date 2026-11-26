from homerag.ingest import load_epub
from tests.conftest import MakeEpub, blocks_of


def test_pressbooks_files_get_their_role_from_the_first_div(make_epub: MakeEpub) -> None:
    path = make_epub(
        [
            ("title-page.xhtml", '<section><div id="title-page"><h1>Fit</h1></div></section>'),
            ("toc.xhtml", '<section><div id="toc"><ul><li>1. Warm-up</li></ul></div></section>'),
            (
                "front-matter-001.xhtml",
                '<section><div class="front-matter miscellaneous"><p>About.</p></div></section>',
            ),
            (
                "chapter-001.xhtml",
                '<section><div class="chapter standard"><h1>Warm-up</h1></div></section>',
            ),
            (
                "back-matter-001.xhtml",
                '<section><div class="back-matter glossary"><p>VO2: oxygen.</p></div></section>',
            ),
        ]
    )

    roles = {b.source.rsplit("/", 1)[-1]: b.role for b in load_epub(path)}

    assert roles == {
        "title-page.xhtml": "titlepage",
        "toc.xhtml": "toc",
        "front-matter-001.xhtml": "frontmatter",
        "chapter-001.xhtml": "body",
        "back-matter-001.xhtml": "glossary",
    }


def test_epub_type_wins_over_pressbooks_markers(make_epub: MakeEpub) -> None:
    path = make_epub(
        [("a.xhtml", '<section epub:type="chapter"><div id="toc"><p>Text.</p></div></section>')]
    )

    assert load_epub(path)[0].role == "body"


def test_pressbooks_chapter_number_and_authors_are_dropped() -> None:
    blocks = blocks_of(
        '<div class="chapter-title-wrap"><p class="chapter-number">3</p>'
        '<h1 class="chapter-title">Warm-up</h1><p class="chapter-author">A. Coach</p></div>'
        "<p>Start easy.</p>"
    )

    assert [b.text for b in blocks] == ["Warm-up", "Start easy."]


def test_other_first_divs_say_nothing_about_the_role(make_epub: MakeEpub) -> None:
    path = make_epub([("a.xhtml", '<div class="sidenote"><p>Rest days count.</p></div>')])

    assert load_epub(path)[0].role == "body"

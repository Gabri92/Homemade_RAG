import pytest

from homerag.ingest import load_epub
from homerag.ingest.epub import landmark_types, role_from_types
from tests.conftest import MakeEpub

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


def test_load_epub_defaults_to_body_without_landmarks(make_epub: MakeEpub) -> None:
    path = make_epub([("ch01.xhtml", "<p>Text.</p>")])

    assert {b.role for b in load_epub(path)} == {"body"}

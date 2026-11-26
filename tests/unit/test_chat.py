"""The chat's handlers and layout with a fake LLM: no browser, no server, no API call."""

from pathlib import Path

import gradio as gr

from homerag.chat import ChatDocument, build_app, header, respond, source_panel
from homerag.config import DocumentEntry
from homerag.models import Block, Book, Citation, Passage, Section
from tests.unit.test_qa import BASE, BUILD, CFG, CHUNKS, FakeLLM, resources

ENTRY = DocumentEntry(
    title="Synthetic Training Book",
    author="A. Author",
    url="https://example.org/book",
    license="CC BY 4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    config=Path("configs/experiments/baseline.yaml"),
)
QUESTION = "How long is the base period?"
# The two sections the synthetic chunks of test_qa were cut from.
BOOK = Book(
    "b",
    (
        Section(
            "base",
            "Base",
            2,
            BASE.path,
            "body",
            True,
            (
                Block("paragraph", CHUNKS[0].text, "ch.xhtml"),
                Block("paragraph", "Synthetic text across base and", "ch.xhtml"),
            ),
        ),
        Section(
            "build", "Build", 2, BUILD.path, "body", True, (Block("paragraph", "build.", "x"),)
        ),
    ),
)


def document(reply: str) -> ChatDocument:
    return ChatDocument(ENTRY, CFG, resources(FakeLLM(reply)), BOOK)


def test_respond_adds_the_turn_with_each_cited_chunk_and_its_panel() -> None:
    history, labels, panels = respond(QUESTION, [], document("Weeks [1]."))

    assert [m["role"] for m in history] == ["user", "assistant", "assistant"]
    assert "$0.0004 (paid)" in history[1]["content"]  # the cost under the answer
    assert history[2]["metadata"]["title"] == "[1] Training periods > Base, p. 12"
    assert history[2]["content"] == CHUNKS[0].text  # the whole chunk the model read
    assert labels == ["[1] Training periods > Base, p. 12"]
    assert f"<mark>{CHUNKS[0].text}</mark>" in panels[labels[0]]


def test_respond_ignores_an_empty_question() -> None:
    assert respond("   ", [], document("never used")) == ([], [], {})


def test_a_chunk_across_two_sections_opens_once_in_chat_and_twice_in_the_panel() -> None:
    history, labels, _ = respond(QUESTION, [], document("Both [2]."))

    assert len(history) == 3
    assert labels == ["[2] Training periods > Base", "[2] Training periods > Build"]


def test_panel_escapes_the_text_and_links_the_book_and_license() -> None:
    citation = Citation(1, "base#1", "base", BASE.path, "12")

    html = source_panel(Passage(citation, "a < b ", "read", " after"), ENTRY)

    assert "a &lt; b <mark>read</mark> after" in html
    assert 'href="https://example.org/book"' in html
    assert 'href="https://creativecommons.org/licenses/by/4.0/"' in html


def test_header_links_the_book_online() -> None:
    assert "[Read the book online](https://example.org/book)" in header(ENTRY)


def test_build_app_lays_out_the_page() -> None:
    assert isinstance(build_app([document("unused")]), gr.Blocks)

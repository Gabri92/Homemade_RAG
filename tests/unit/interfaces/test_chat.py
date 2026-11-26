"""The chat's handlers and layout with a fake LLM: no browser, no server, no API call."""

from pathlib import Path

import gradio as gr
import numpy as np

from homerag.chunking import BLOCK_SEPARATOR
from homerag.config import DocumentEntry, load_experiment
from homerag.index import VectorIndex
from homerag.interfaces.chat import (
    ChatDocument,
    build_app,
    header,
    respond,
    source_panel,
    suggestions,
)
from homerag.models import Block, Book, Chunk, Citation, Passage, Section, SectionRef
from tests.conftest import FakeLLM, fake_resources

CFG = load_experiment(Path("configs/experiments/baseline.yaml"))
ENTRY = DocumentEntry(
    title="Synthetic Training Book",
    author="A. Author",
    url="https://example.org/book",
    license="CC BY 4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    config=Path("configs/experiments/baseline.yaml"),
    suggested_questions=("How long is the base period?", "What comes after base?"),
)
QUESTION = "How long is the base period?"

BASE = SectionRef("base", ("Training periods", "Base"))
BUILD = SectionRef("build", ("Training periods", "Build"))
# A synthetic book and two chunks cut from it: the second runs from "base" into "build".
BOOK = Book(
    "b",
    (
        Section("base", "Base", 2, BASE.path, "body", True, (
            Block("paragraph", "Base lasts eight synthetic weeks.", "ch.xhtml"),
            Block("paragraph", "Then comes", "ch.xhtml"),
        )),
        Section("build", "Build", 2, BUILD.path, "body", True, (
            Block("paragraph", "the build period.", "ch.xhtml"),
        )),
    ),
)  # fmt: skip
CHUNKS = (
    Chunk("base#1", (BASE,), "Base lasts eight synthetic weeks.", "12"),
    Chunk("base#2", (BASE, BUILD), f"Then comes{BLOCK_SEPARATOR}the build period.", None),
)
INDEX = VectorIndex(CHUNKS, np.array([[1.0, 0.0], [0.6, 0.8]], dtype=np.float32))


def document(reply: str) -> ChatDocument:
    return ChatDocument(ENTRY, CFG, fake_resources(INDEX, FakeLLM(reply), CFG.language_gate), BOOK)


def test_respond_adds_the_turn_with_each_cited_chunk_and_its_panel() -> None:
    history, labels, panels = respond(QUESTION, [], document("Eight weeks [1]."))

    assert [m["role"] for m in history] == ["user", "assistant", "assistant"]
    assert "$0.0004 (paid)" in history[1]["content"]  # the cost under the answer
    assert history[2]["metadata"]["title"] == "[1] Training periods > Base, p. 12"
    assert history[2]["content"] == CHUNKS[0].text  # the whole chunk the model read
    assert labels == ["[1] Training periods > Base, p. 12"]
    assert f"<mark>{CHUNKS[0].text}</mark>" in panels[labels[0]]


def test_respond_ignores_an_empty_question() -> None:
    assert respond("   ", [], document("never used")) == ([], [], {})


def test_a_chunk_across_two_sections_opens_once_per_section_in_the_panel() -> None:
    history, labels, panels = respond(QUESTION, [], document("Then build [2]."))

    assert len(history) == 3
    assert labels == ["[2] Training periods > Base", "[2] Training periods > Build"]
    assert "<mark>Then comes</mark>" in panels[labels[0]]
    assert "<mark>the build period.</mark>" in panels[labels[1]]


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


def test_suggested_questions_become_chat_examples() -> None:
    assert suggestions(ENTRY) == [
        {"text": "How long is the base period?"},
        {"text": "What comes after base?"},
    ]


def test_the_empty_chat_shows_the_suggested_questions() -> None:
    app = build_app([document("unused")])
    chats = [b for b in app.blocks.values() if isinstance(b, gr.Chatbot)]

    assert [chat.examples for chat in chats] == [suggestions(ENTRY)]

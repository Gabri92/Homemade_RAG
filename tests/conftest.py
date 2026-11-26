"""Shared fixtures. All book content here is synthetic: never use text from the real book."""

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from ebooklib import epub

from homerag.config import LanguageGateConfig
from homerag.embedding import Vectors
from homerag.eval.dataset import GoldenQuestion
from homerag.index import VectorIndex
from homerag.ingest import html_to_blocks
from homerag.language import build_detector
from homerag.llm import Completion, LLMRequest
from homerag.models import Block, Chunk, SectionRef, Usage
from homerag.qa import Resources

MakeEpub = Callable[[list[tuple[str, str]]], Path]


@pytest.fixture
def make_epub(tmp_path: Path) -> MakeEpub:
    """Build a minimal ePub from (file_name, body_html) chapters, in the given spine order."""

    def build(chapters: list[tuple[str, str]]) -> Path:
        book = epub.EpubBook()
        book.set_identifier("synthetic-book")
        book.set_title("Synthetic Training Book")
        book.set_language("en")

        items = []
        for file_name, body in chapters:
            item = epub.EpubHtml(title=file_name, file_name=file_name, lang="en")
            item.content = f"<html><body>{body}</body></html>"
            book.add_item(item)
            items.append(item)

        book.toc = items
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", *items]

        path = tmp_path / "book.epub"
        epub.write_epub(str(path), book)
        return path

    return build


SOURCE = "ch01.xhtml"


def blocks_of(html: str) -> list[Block]:
    """Blocks of a synthetic document body, as the loader converts one file."""
    return html_to_blocks(f"<html><body>{html}</body></html>", source=SOURCE)


def page_marker(label: str) -> str:
    """An EPUB printed-page marker, as publishers write it."""
    return f'<span epub:type="pagebreak" id="page_{label}" aria-label=" page {label}. "></span>'


# --- fakes for the pipeline: passed as parameters, never monkeypatched -------------------

Reply = Callable[[LLMRequest], Completion]


class FakeLLM:
    """Stands in for `llm.LLM`: records every request and answers with `reply`.

    `reply` is either a fixed text, answered with `stop_reason` and a small usage costing
    `cost_usd`, or a function from the request to a whole `Completion`, for tests that
    answer different requests differently.
    """

    def __init__(
        self, reply: str | Reply, stop_reason: str = "end_turn", cost_usd: float = 0.0004
    ) -> None:
        self.reply, self.stop_reason, self.cost_usd = reply, stop_reason, cost_usd
        self.requests: list[LLMRequest] = []

    def __call__(self, request: LLMRequest) -> Completion:
        self.requests.append(request)
        if callable(self.reply):
            return self.reply(request)
        usage = Usage(request.model, 100, 20, self.cost_usd)
        return Completion(self.reply, self.stop_reason, usage)


def embed_on_first_axis(texts: list[str]) -> Vectors:
    """A fake embedder: every text points along the first axis of a 2-d index."""
    return np.array([[1.0, 0.0]] * len(texts), dtype=np.float32)


def fake_resources(index: VectorIndex, llm: FakeLLM, gate: LanguageGateConfig) -> Resources:
    """What `qa.answer` needs: a real language gate, the fake embedder and the given LLM."""
    return Resources(index, embed_on_first_axis, build_detector(gate), llm)


# --- a synthetic golden set for the eval tests ------------------------------------------


def golden_question(qid: str, category: str, *sections: str, **extra: str) -> GoldenQuestion:
    """A valid golden question; a `non_english` one is in Italian, with no reference answer."""
    fields: dict[str, object] = {
        "id": qid,
        "question": f"question {qid}",
        "category": category,
        "relevant_section_ids": sections,
        "reference_answer": "a paraphrase",
        **extra,
    }
    if category == "non_english":
        fields.update(language="it", reference_answer=None)
    return GoldenQuestion.model_validate(fields)


GOLDEN_QUESTIONS = [
    golden_question("q-001", "factual", "base"),
    golden_question("q-002", "follow_up", "base", previous_id="q-001"),
    golden_question("q-003", "out_of_scope"),
    golden_question("q-004", "non_english"),
]

# Two chunks; embed_on_first_axis points every question at the "base" chunk.
EVAL_INDEX = VectorIndex(
    (
        Chunk("base#1", (SectionRef("base", ("Base",)),), "synthetic chunk text", "1"),
        Chunk(
            "swim#1",
            (SectionRef("swim", ("Swim",)), SectionRef("bike", ("Bike",))),
            "other synthetic text",
            "2",
        ),
    ),
    np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
)

VERDICT = {"reasoning": "ok", "correctness": "partial", "faithful": True, "declined": False}


def answer_or_verdict(request: LLMRequest) -> Completion:
    """A `FakeLLM` reply: a cited sentence for an answer (cached, $0.01), the `VERDICT` for a
    judge request ($0.02)."""
    if request.output_schema is not None:
        return Completion(json.dumps(VERDICT), "end_turn", Usage(request.model, 50, 30, 0.02))
    return Completion(
        "A synthetic answer for this test [1].",
        "end_turn",
        Usage(request.model, 100, 20, 0.01, latency_s=1.5, cached=True),
    )

import re
from pathlib import Path

import numpy as np
import pytest

from homerag.chunking import BLOCK_SEPARATOR, fixed_size_chunks, section_text
from homerag.config import ChunkingConfig, load_experiment
from homerag.index import VectorIndex, Vectors
from homerag.language import NOTICE, build_detector
from homerag.llm import Completion, LLMRequest
from homerag.models import (
    Answer,
    Block,
    Book,
    Chunk,
    Citation,
    RetrievedChunk,
    Section,
    SectionRef,
    Usage,
)
from homerag.qa import (
    REFUSAL_NOTICE,
    Resources,
    answer,
    build_user_message,
    cite,
    format_answer,
    passages,
    read_span,
)

CFG = load_experiment(Path("configs/experiments/baseline.yaml"))

BASE = SectionRef("base", ("Training periods", "Base"))
BUILD = SectionRef("build", ("Training periods", "Build"))
CHUNKS = (
    Chunk("base#1", (BASE,), "Synthetic text about the base period.", "12"),
    Chunk("base#2", (BASE, BUILD), "Synthetic text across base and build.", None),
)
RETRIEVED = [RetrievedChunk(chunk, 0.9 - i / 10, i + 1) for i, chunk in enumerate(CHUNKS)]
QUESTION = "How long should the base period last for a beginner?"


def embed(texts: list[str]) -> Vectors:
    return np.array([[1.0, 0.0]] * len(texts), dtype=np.float32)


INDEX = VectorIndex(CHUNKS, np.array([[1.0, 0.0], [0.6, 0.8]], dtype=np.float32))


class FakeLLM:
    """Records requests and replies with a fixed text and stop reason."""

    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.text, self.stop_reason = text, stop_reason
        self.requests: list[LLMRequest] = []

    def __call__(self, request: LLMRequest) -> Completion:
        self.requests.append(request)
        return Completion(self.text, self.stop_reason, Usage(request.model, 100, 20, 0.0004))


def resources(llm: FakeLLM) -> Resources:
    return Resources(INDEX, embed, build_detector(CFG.language_gate), llm)


def test_user_message_numbers_the_sources_with_section_and_page() -> None:
    message = build_user_message(QUESTION, RETRIEVED)

    assert '<source id="1" section="Training periods &gt; Base" page="12">' in message
    assert '<source id="2" section="Training periods &gt; Base; Training periods &gt; Build">' in (
        message
    )
    assert message.endswith(f"Question: {QUESTION}")


def test_cite_maps_numbers_to_chunks_in_order_of_first_use() -> None:
    citations = cite("Short [2]. Longer [1][2], see [1, 2].", RETRIEVED)

    assert [(c.source, c.section_id) for c in citations] == [(2, "base"), (2, "build"), (1, "base")]
    assert citations[2].page == "12"


def test_cite_ignores_numbers_without_a_source() -> None:
    assert cite("Claim [9]. No citation here.", RETRIEVED) == ()


def test_answer_sends_the_prompt_and_sources_and_builds_citations() -> None:
    llm = FakeLLM("About eight weeks [1].")

    result = answer(QUESTION, resources(llm), CFG)

    request = llm.requests[0]
    assert request.model == CFG.generation.model
    assert "square brackets" in request.system  # the answer_v1 prompt
    assert '<source id="1"' in request.user
    assert [c.chunk_id for c in result.citations] == ["base#1"]
    assert result.usage is not None
    assert len(result.retrieved) == len(CHUNKS)  # top_k is 5, the index holds 2


def test_non_english_question_gets_the_notice_and_no_llm_call() -> None:
    llm = FakeLLM("never used")

    result = answer(
        "Quanto deve durare il periodo di base per un principiante?", resources(llm), CFG
    )

    assert result.blocked_by_gate
    assert result.text == NOTICE
    assert llm.requests == []


def test_refusal_gets_a_plain_notice_without_citations() -> None:
    result = answer(QUESTION, resources(FakeLLM("[1]", stop_reason="refusal")), CFG)

    assert result.text == REFUSAL_NOTICE
    assert result.citations == ()


def test_format_answer_lists_sources_and_cost() -> None:
    result = answer(QUESTION, resources(FakeLLM("About eight weeks [1].")), CFG)

    text = format_answer(result)

    assert "[1] Training periods > Base, p. 12" in text
    assert "$0.0004 (paid)" in text


# --- passages: what the source panel shows ------------------------------------------------

SEP = BLOCK_SEPARATOR


@pytest.mark.parametrize(
    ("section", "chunk", "expected"),
    [
        (f"aa{SEP}bb cc{SEP}dd", "bb cc", "bb cc"),  # inside the section
        (f"bb{SEP}cc", f"aa{SEP}bb{SEP}cc{SEP}dd", f"bb{SEP}cc"),  # covers it whole
        (f"aa{SEP}bb cc", f"b cc{SEP}dd{SEP}ee", "b cc"),  # starts in it, runs on
        (f"aa bb{SEP}cc", f"zz{SEP}yy{SEP}aa bb", "aa bb"),  # starts earlier, ends in it
        ("aa bb", "zz", ""),  # no overlap (a stale index): nothing marked
    ],
)
def test_read_span_finds_the_part_of_the_chunk_in_the_section(
    section: str, chunk: str, expected: str
) -> None:
    start, end = read_span(section, chunk)

    assert section[start:end] == expected


def test_every_chunk_is_marked_in_every_section_it_covers() -> None:
    def spans(text: str) -> list[tuple[int, int]]:
        return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]

    def make(sid: str, *texts: str) -> Section:
        blocks = tuple(Block("paragraph", t, "ch.xhtml") for t in texts)
        return Section(sid, sid, 1, (sid,), "body", True, blocks)

    text = " ".join(f"w{i}" for i in range(9))
    book = Book("b", (make("a", text, text), make("b", text), make("c", text, text)))
    cfg = ChunkingConfig(strategy="fixed", size_tokens=12, overlap_tokens=3)
    sections = {s.id: section_text(s) for s in book.sections}

    for chunk in fixed_size_chunks(book, cfg, spans):
        for ref in chunk.sections:
            start, end = read_span(sections[ref.id], chunk.text)
            assert end > start
            assert sections[ref.id][start:end] in chunk.text


def test_passages_split_each_cited_section_around_what_the_model_read() -> None:
    intro = Block("paragraph", "Intro.", "ch.xhtml")
    block = Block("paragraph", CHUNKS[0].text, "ch.xhtml")
    book = Book("b", (Section("base", "Base", 2, BASE.path, "body", True, (intro, block)),))
    citation = Citation(1, "base#1", "base", BASE.path, "12")
    result = Answer(QUESTION, "Eight weeks [1].", (citation,), (RETRIEVED[0],))

    (passage,) = passages(result, book)

    assert passage.citation == citation
    assert (passage.before, passage.read, passage.after) == ("Intro." + SEP, CHUNKS[0].text, "")

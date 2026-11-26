"""Question answering: language gate -> retrieval -> grounded generation with citations.

`answer(question, resources, cfg) -> Answer` is the entry point used by the CLI, the eval
runner and the web chat. The model sees the retrieved chunks as numbered sources and
cites them as "[n]"; citations are then built from the chunks' metadata, never from model
text, so a citation always points at a real section (ADR 0007).
"""

import logging
import re
from dataclasses import dataclass
from html import escape

from homerag.chunking import BLOCK_SEPARATOR, section_text
from homerag.config import ExperimentConfig, Settings
from homerag.index import Embed, VectorIndex, load_embedder_for, open_index
from homerag.language import NOTICE, Detector, build_detector, is_english
from homerag.llm import LLM, LLMRequest, anthropic_llm, cached, load_prompt
from homerag.models import Answer, Book, Citation, Passage, RetrievedChunk, Usage
from homerag.retrieval import RETRIEVERS

logger = logging.getLogger(__name__)

REFUSAL_NOTICE = "Sorry, I can't answer this question."

# "[2]", "[1][3]" and "[1, 3]" all cite sources by number.
_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True, slots=True)
class Resources:
    """What answering needs, built once and reused for every question."""

    index: VectorIndex
    embed: Embed
    detector: Detector
    llm: LLM


def load_resources(cfg: ExperimentConfig, settings: Settings) -> Resources:
    """Open the index (first: a missing index fails before any model loads), then the rest."""
    index = open_index(cfg)
    return Resources(
        index,
        load_embedder_for(cfg.embedding),
        build_detector(cfg.language_gate),
        cached(anthropic_llm(settings.anthropic_api_key)),
    )


def answer(question: str, resources: Resources, cfg: ExperimentConfig) -> Answer:
    """Answer one question from the document, or return the gate notice without any query."""
    if not is_english(question, resources.detector, cfg.language_gate):
        return Answer(question, NOTICE, blocked_by_gate=True)
    retrieve = RETRIEVERS[cfg.retrieval.strategy]
    retrieved = retrieve(question, resources.index, resources.embed, cfg.retrieval)
    request = LLMRequest(
        model=cfg.generation.model,
        effort=cfg.generation.effort,
        max_tokens=cfg.generation.max_tokens,
        system=load_prompt(cfg.generation.prompt),
        user=build_user_message(question, retrieved),
    )
    completion = resources.llm(request)
    if completion.stop_reason == "refusal":
        return Answer(question, REFUSAL_NOTICE, (), tuple(retrieved), usage=completion.usage)
    if completion.stop_reason == "max_tokens":
        logger.warning("answer cut at max_tokens (%d): raise it", cfg.generation.max_tokens)
    citations = cite(completion.text, retrieved)
    return Answer(question, completion.text, citations, tuple(retrieved), usage=completion.usage)


def build_user_message(question: str, retrieved: list[RetrievedChunk]) -> str:
    """The numbered sources (1 = best ranked), then the question."""
    return format_sources(retrieved) + f"\n\nQuestion: {question}"


def format_sources(retrieved: list[RetrievedChunk]) -> str:
    """`<sources>` with one numbered `<source>` per chunk, with its section path and page."""
    sources = [
        f'<source id="{n}" section="{escape(_section_label(r))}"{_page_attr(r)}>\n'
        f"{r.chunk.text}\n</source>"
        for n, r in enumerate(retrieved, start=1)
    ]
    return "<sources>\n" + "\n".join(sources) + "\n</sources>"


def source_numbers(text: str) -> list[int]:
    """Every source number cited in `text`, in order, with repeats ("[1][2] [1]" -> 1, 2, 1)."""
    return [int(part) for match in _CITATION.finditer(text) for part in match.group(1).split(",")]


def cite(text: str, retrieved: list[RetrievedChunk]) -> tuple[Citation, ...]:
    """Citations for the source numbers in `text`, in order of first use, without repeats.

    A number with no matching source is ignored (and logged): it cannot be checked.
    """
    numbers: list[int] = []
    for n in source_numbers(text):
        if not 1 <= n <= len(retrieved):
            logger.warning("answer cites source [%d], but there are %d", n, len(retrieved))
        elif n not in numbers:
            numbers.append(n)
    return tuple(
        Citation(n, chunk.id, section.id, section.path, chunk.page)
        for n in numbers
        for chunk in [retrieved[n - 1].chunk]
        for section in chunk.sections
    )


def format_answer(result: Answer) -> str:
    """The answer, its sources ("[n] Chapter > Section, p. 12") and what it cost."""
    lines = [result.text]
    if result.citations:
        lines += ["", "Sources:"]
        lines += [f"  {format_citation(c)}" for c in result.citations]
    if result.usage:
        lines += ["", format_usage(result.usage)]
    return "\n".join(lines) + "\n"


def format_citation(citation: Citation) -> str:
    """ "[2] Chapter > Section, p. 12": how a citation is named to the reader."""
    page = f", p. {citation.page}" if citation.page else ""
    return f"[{citation.source}] {' > '.join(citation.section_path)}{page}"


def format_usage(usage: Usage) -> str:
    """ "model: 900 in, 120 out, $0.0045 (paid)": what one answer used and cost."""
    paid = "cached, not paid again" if usage.cached else "paid"
    return (
        f"{usage.model}: {usage.input_tokens} in, {usage.output_tokens} out, "
        f"${usage.cost_usd:.4f} ({paid})"
    )


def passages(result: Answer, book: Book) -> tuple[Passage, ...]:
    """Each citation of an answer as its whole section, with the cited chunk's part marked.

    This is what lets a reader who does not know the document check the answer: the claim
    next to "[n]" must be in the marked text, which is exactly what the model read.
    """
    sections = {section.id: section for section in book.sections}
    chunks = {r.chunk.id: r.chunk for r in result.retrieved}
    found = []
    for citation in result.citations:
        text = section_text(sections[citation.section_id])
        start, end = read_span(text, chunks[citation.chunk_id].text)
        found.append(Passage(citation, text[:start], text[start:end], text[end:]))
    return tuple(found)


def read_span(section: str, chunk: str) -> tuple[int, int]:
    """Where `chunk` overlaps `section`, both cut from the same running text (`chunking.py`).

    A chunk lies inside the section, covers it whole, starts in it and runs into the next
    sections, or starts earlier and ends in it. The last two meet the section at a block
    separator. Returns (0, 0) if they do not overlap, which only a stale index can cause.
    """
    if (start := section.find(chunk)) >= 0:
        return start, start + len(chunk)
    if section in chunk:
        return 0, len(section)
    cuts = [i for i in range(len(chunk)) if chunk.startswith(BLOCK_SEPARATOR, i)]
    for cut in reversed(cuts):  # the longest head of the chunk that ends the section
        if cut and section.endswith(chunk[:cut]):
            return len(section) - cut, len(section)
    for cut in cuts:  # the longest tail of the chunk that starts the section
        tail = chunk[cut + len(BLOCK_SEPARATOR) :]
        if tail and section.startswith(tail):
            return 0, len(tail)
    logger.warning("chunk not found in its section: is the index up to date?")
    return 0, 0


def _section_label(result: RetrievedChunk) -> str:
    return "; ".join(" > ".join(s.path) for s in result.chunk.sections)


def _page_attr(result: RetrievedChunk) -> str:
    return f' page="{escape(result.chunk.page)}"' if result.chunk.page else ""

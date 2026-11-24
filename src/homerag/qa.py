"""Question answering: language gate -> retrieval -> grounded generation with citations.

`answer(question, resources, cfg) -> Answer` is the entry point used by the CLI, the eval
runner and, later, the chat UI. The model sees the retrieved chunks as numbered sources and
cites them as "[n]"; citations are then built from the chunks' metadata, never from model
text, so a citation always points at a real section (ADR 0007).
"""

import logging
import re
from dataclasses import dataclass
from html import escape

from homerag.config import ExperimentConfig, Settings
from homerag.index import Embed, VectorIndex, load_embedder_for, open_index
from homerag.language import NOTICE, Detector, build_detector, is_english
from homerag.llm import LLM, LLMRequest, anthropic_llm, cached, load_prompt
from homerag.models import Answer, Citation, RetrievedChunk
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
        lines += [
            f"  [{c.source}] {' > '.join(c.section_path)}" + (f", p. {c.page}" if c.page else "")
            for c in result.citations
        ]
    if result.usage:
        u = result.usage
        paid = "cached, not paid again" if u.cached else "paid"
        lines += [
            "",
            f"{u.model}: {u.input_tokens} in, {u.output_tokens} out, ${u.cost_usd:.4f} ({paid})",
        ]
    return "\n".join(lines) + "\n"


def _section_label(result: RetrievedChunk) -> str:
    return "; ".join(" > ".join(s.path) for s in result.chunk.sections)


def _page_attr(result: RetrievedChunk) -> str:
    return f' page="{escape(result.chunk.page)}"' if result.chunk.page else ""

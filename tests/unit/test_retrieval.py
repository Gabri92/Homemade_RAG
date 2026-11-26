from typing import get_args

import numpy as np
import pytest

from homerag.config import RetrievalConfig
from homerag.embedding import Vectors
from homerag.index import VectorIndex
from homerag.models import Chunk, RetrievedChunk, SectionRef
from homerag.retrieval import RETRIEVERS, dense_search, format_results


def chunk(n: int, *section_ids: str, page: str | None = "1") -> Chunk:
    sections = tuple(SectionRef(s, (s.title(),)) for s in section_ids or ("s",))
    return Chunk(f"{sections[0].id}#{n}", sections, f"text {n}", page)


def unit(*values: float) -> list[float]:
    vector = np.array(values, dtype=np.float32)
    return list(vector / np.linalg.norm(vector))


# Three chunks pointing along x, between x and y, along y.
INDEX = VectorIndex(
    (chunk(1), chunk(2), chunk(3)),
    np.array([unit(1, 0), unit(1, 1), unit(0, 1)], dtype=np.float32),
)


def embed_as(*values: float) -> object:
    def embed(texts: list[str]) -> Vectors:
        return np.array([unit(*values)] * len(texts), dtype=np.float32)

    return embed


def ids(results: list[RetrievedChunk]) -> list[str]:
    return [r.chunk.id for r in results]


def test_results_are_ranked_by_similarity() -> None:
    results = dense_search("q", INDEX, embed_as(1, 0.1), RetrievalConfig(strategy="dense", top_k=3))

    assert ids(results) == ["s#1", "s#2", "s#3"]
    assert [r.rank for r in results] == [1, 2, 3]
    assert results[0].score > results[1].score > results[2].score


def test_top_k_limits_the_results() -> None:
    results = dense_search("q", INDEX, embed_as(0, 1), RetrievalConfig(strategy="dense", top_k=1))

    assert ids(results) == ["s#3"]


def test_top_k_larger_than_the_index_returns_everything() -> None:
    results = dense_search("q", INDEX, embed_as(1, 1), RetrievalConfig(strategy="dense", top_k=50))

    assert len(results) == 3


def test_ties_keep_reading_order() -> None:
    twins = VectorIndex((chunk(1), chunk(2)), np.array([unit(1, 0), unit(1, 0)], dtype=np.float32))

    results = dense_search("q", twins, embed_as(1, 0), RetrievalConfig(strategy="dense", top_k=2))

    assert ids(results) == ["s#1", "s#2"]


def test_question_from_another_model_is_refused() -> None:
    with pytest.raises(ValueError, match="another embedding model"):
        dense_search("q", INDEX, embed_as(1, 0, 0), RetrievalConfig(strategy="dense", top_k=1))


def test_empty_index_gives_no_results() -> None:
    empty = VectorIndex((), np.zeros((0, 0), dtype=np.float32))

    cfg = RetrievalConfig(strategy="dense", top_k=5)

    assert dense_search("q", empty, embed_as(1, 0), cfg) == []


def test_registry_matches_the_strategies_the_config_accepts() -> None:
    accepted = set(get_args(RetrievalConfig.model_fields["strategy"].annotation))

    assert set(RETRIEVERS) == accepted


def test_format_shows_ids_sections_and_pages_but_text_only_on_request() -> None:
    results = [RetrievedChunk(chunk(1, "base", "build", page="12"), 0.75, 1)]

    plain = format_results(results)
    with_text = format_results(results, show_text=True)

    assert "s#1" not in plain
    assert "base#1" in plain
    assert "Base" in plain
    assert "(+1 sections)" in plain
    assert "p. 12" in plain
    assert "text 1" not in plain
    assert "text 1" in with_text

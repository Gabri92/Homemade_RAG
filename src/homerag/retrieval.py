"""Retrieval strategies: from a question to the ranked chunks most likely to answer it.

Each strategy is a function with the same signature, registered by name in `RETRIEVERS` so an
experiment config can pick it. Today: dense search (cosine similarity between normalized
embeddings). BM25, hybrid fusion (RRF) and reranking arrive with Phase 5; BM25 needs another
index, which will be the signal to revisit the signature (structure.md, "When to grow").
"""

from collections.abc import Callable

import numpy as np

from homerag.config import ExperimentConfig, RetrievalConfig
from homerag.embedding import Embed, load_embedder_for
from homerag.index import VectorIndex, open_index
from homerag.models import RetrievedChunk

Retriever = Callable[[str, VectorIndex, Embed, RetrievalConfig], list[RetrievedChunk]]

SNIPPET_CHARS = 200


def dense_search(
    question: str, index: VectorIndex, embed: Embed, cfg: RetrievalConfig
) -> list[RetrievedChunk]:
    """The `top_k` chunks whose vectors point most in the direction of the question's.

    Vectors are normalized, so one matrix-vector product gives every cosine similarity.
    Ties keep reading order, so the same input always gives the same ranking.
    """
    if not index.chunks:
        return []
    query = embed([question])[0]
    if query.shape[0] != index.vectors.shape[1]:
        raise ValueError(
            f"question vector has {query.shape[0]} dimensions, the index {index.vectors.shape[1]}:"
            " the index was built with another embedding model"
        )
    scores = index.vectors @ query
    order = np.argsort(-scores, kind="stable")[: cfg.top_k]
    return [
        RetrievedChunk(index.chunks[i], float(scores[i]), rank)
        for rank, i in enumerate(order, start=1)
    ]


RETRIEVERS: dict[str, Retriever] = {
    "dense": dense_search,
}


def search(question: str, cfg: ExperimentConfig) -> list[RetrievedChunk]:
    """Open the experiment's index and embedder, then run its retriever on one question."""
    index = open_index(cfg)  # first: a missing index fails before the model loads
    embed = load_embedder_for(cfg.embedding)
    return RETRIEVERS[cfg.retrieval.strategy](question, index, embed, cfg.retrieval)


def format_results(results: list[RetrievedChunk], show_text: bool = False) -> str:
    """One line per result: rank, score, chunk id, first section path (+ others), page.

    With `show_text`, a short snippet of each chunk follows: for the local terminal only.
    """
    lines = []
    for result in results:
        chunk = result.chunk
        path = " > ".join(chunk.sections[0].path)
        more = f" (+{len(chunk.sections) - 1} sections)" if len(chunk.sections) > 1 else ""
        page = f"p. {chunk.page}" if chunk.page else "no page"
        lines.append(f"{result.rank:>2}  {result.score:.3f}  {chunk.id}  {path}{more}  {page}")
        if show_text:
            snippet = " ".join(chunk.text.split())[:SNIPPET_CHARS]
            lines.append(f"    {snippet}...")
    return "\n".join(lines) + "\n"

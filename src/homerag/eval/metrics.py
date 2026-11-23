"""Evaluation metrics as pure functions: a ranking and the cited sections in, numbers out.

Retrieval works at section granularity (ADR 0003): a retrieved chunk is relevant when it
covers at least one section the question cites (ADR 0005).
- hit@k: is there at least one relevant chunk in the first k? (1 or 0)
- recall@k: which share of the cited sections do the first k chunks cover?
- reciprocal rank: 1 / position of the first relevant chunk (0 if none); its mean is MRR.
Language-gate accuracy and the judge's scores arrive with Phase 3b.
"""

from collections import defaultdict
from collections.abc import Iterable

from homerag.models import RetrievedChunk

ALL = "all"


def is_relevant(result: RetrievedChunk, cited: frozenset[str]) -> bool:
    """True when the chunk covers at least one cited section."""
    return any(section.id in cited for section in result.chunk.sections)


def hit_at(results: list[RetrievedChunk], cited: frozenset[str], k: int) -> float:
    return 1.0 if any(is_relevant(r, cited) for r in results[:k]) else 0.0


def recall_at(results: list[RetrievedChunk], cited: frozenset[str], k: int) -> float:
    if not cited:
        raise ValueError("recall needs at least one cited section")
    found = {s.id for r in results[:k] for s in r.chunk.sections} & cited
    return len(found) / len(cited)


def reciprocal_rank(results: list[RetrievedChunk], cited: frozenset[str]) -> float:
    for position, result in enumerate(results, start=1):
        if is_relevant(result, cited):
            return 1.0 / position
    return 0.0


def retrieval_metrics(
    results: list[RetrievedChunk], cited: frozenset[str], ks: Iterable[int]
) -> dict[str, float]:
    """Every retrieval metric for one question, e.g. {"hit@1": 0.0, ..., "mrr": 0.5}."""
    metrics: dict[str, float] = {}
    for k in ks:
        metrics[f"hit@{k}"] = hit_at(results, cited, k)
        metrics[f"recall@{k}"] = recall_at(results, cited, k)
    metrics["mrr"] = reciprocal_rank(results, cited)
    return metrics


def aggregate(rows: Iterable[tuple[str, dict[str, float]]]) -> dict[str, dict[str, float]]:
    """Mean of each metric per category and over all questions, plus the count `n`.

    `rows` are (category, metrics of one question). Categories keep their first-seen order;
    "all" comes last.
    """
    groups: dict[str, list[dict[str, float]]] = defaultdict(list)
    for category, metrics in rows:
        groups[category].append(metrics)
        groups[ALL].append(metrics)
    order = [c for c in groups if c != ALL] + ([ALL] if ALL in groups else [])
    return {category: _mean(groups[category]) for category in order}


def _mean(items: list[dict[str, float]]) -> dict[str, float]:
    names = list(items[0])
    means = {name: sum(item[name] for item in items) / len(items) for name in names}
    return {"n": float(len(items)), **means}

"""Evaluation metrics as pure functions: a ranking and the cited sections in, numbers out.

Retrieval works at section granularity (ADR 0003): a retrieved chunk is relevant when it
covers at least one section the question cites (ADR 0005).
- hit@k: is there at least one relevant chunk in the first k? (1 or 0)
- recall@k: which share of the cited sections do the first k chunks cover?
- reciprocal rank: 1 / position of the first relevant chunk (0 if none); its mean is MRR.
The language gate is scored on every question: English must pass, non-English must be
blocked. Its two errors are counted apart, because blocking English is the worse one.
Generated answers get code-based checks (free and deterministic) next to the judge's grades
(`eval/judge.py`): cites a source, cites only real sources, is in English, paraphrases.
"""

import re
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


def gate_metrics(outcomes: Iterable[tuple[bool, bool]]) -> dict[str, float]:
    """Language-gate scores from `(expected_english, passed)` pairs, one per message."""
    pairs = list(outcomes)
    english_blocked = sum(expected and not passed for expected, passed in pairs)
    non_english_passed = sum(passed and not expected for expected, passed in pairs)
    errors = english_blocked + non_english_passed
    return {
        "n": float(len(pairs)),
        "accuracy": (len(pairs) - errors) / len(pairs) if pairs else 0.0,
        "english_blocked": float(english_blocked),
        "non_english_passed": float(non_english_passed),
    }


_WORD = re.compile(r"[a-z0-9']+")
_CITATION_MARK = re.compile(r"\[[\d,\s]+\]")


def answer_checks(
    text: str, numbers: list[int], sources: list[str], english: bool, max_copied_words: int
) -> dict[str, float]:
    """Code-based checks on one answer.

    `numbers` are the source numbers the answer cites, `sources` the texts it was given.
    - cites: it cites at least one real source (1 or 0);
    - cites_ok: every cited number has a source (1 or 0);
    - english: the answer is in English (1 or 0);
    - copied: the longest run of words copied from one source;
    - paraphrase: that run is at most `max_copied_words` long (1 or 0).
    """
    copied = longest_copied_run(text, sources)
    valid = [n for n in numbers if 1 <= n <= len(sources)]
    return {
        "cites": float(bool(valid)),
        "cites_ok": float(len(valid) == len(numbers)),
        "english": float(english),
        "copied": float(copied),
        "paraphrase": float(copied <= max_copied_words),
    }


def longest_copied_run(text: str, sources: list[str]) -> int:
    """Length in words of the longest run of `text` found word for word in one source.

    Case and punctuation are ignored, and citation marks ("[2]") are removed first.
    """
    words = _words(_CITATION_MARK.sub(" ", text))
    return max((_longest_common_run(words, _words(source)) for source in sources), default=0)


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _longest_common_run(a: list[str], b: list[str]) -> int:
    # Classic longest-common-substring table, one row at a time: O(len(a) * len(b)).
    best = 0
    previous = [0] * (len(b) + 1)
    for word in a:
        current = [0] * (len(b) + 1)
        for j, other in enumerate(b, start=1):
            if word == other:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best

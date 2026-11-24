import pytest

from homerag.eval.metrics import (
    aggregate,
    gate_metrics,
    hit_at,
    recall_at,
    reciprocal_rank,
    retrieval_metrics,
)
from homerag.models import Chunk, RetrievedChunk, SectionRef


def ranking(*sections_per_chunk: tuple[str, ...]) -> list[RetrievedChunk]:
    """One retrieved chunk per argument, covering the given section ids, ranked in order."""
    results = []
    for rank, section_ids in enumerate(sections_per_chunk, start=1):
        refs = tuple(SectionRef(s, (s,)) for s in section_ids)
        results.append(RetrievedChunk(Chunk(f"{refs[0].id}#{rank}", refs, "t"), 1.0 / rank, rank))
    return results


# The three questions of the worked example: wrong chunks cover "x".
FACTUAL = ranking(("x",), ("base",), ("x",), ("x",), ("x",))  # cites {"base"}
MULTI_HOP = ranking(("a",), ("x",), ("x",), ("x",), ("x",))  # cites {"a", "b"}
TABLE = ranking(("x",), ("x",), ("x",), ("x",), ("x",))  # cites {"zones"}


def test_hit_counts_one_relevant_chunk_in_the_first_k() -> None:
    assert hit_at(FACTUAL, frozenset({"base"}), 1) == 0.0
    assert hit_at(FACTUAL, frozenset({"base"}), 3) == 1.0
    assert hit_at(TABLE, frozenset({"zones"}), 5) == 0.0


def test_recall_is_the_share_of_cited_sections_found() -> None:
    assert recall_at(FACTUAL, frozenset({"base"}), 5) == 1.0
    assert recall_at(MULTI_HOP, frozenset({"a", "b"}), 5) == 0.5


def test_reciprocal_rank_is_one_over_the_first_relevant_position() -> None:
    assert reciprocal_rank(FACTUAL, frozenset({"base"})) == 0.5
    assert reciprocal_rank(MULTI_HOP, frozenset({"a", "b"})) == 1.0
    assert reciprocal_rank(TABLE, frozenset({"zones"})) == 0.0


def test_chunk_covering_a_cited_section_among_others_is_relevant() -> None:
    results = ranking(("x", "base"))

    assert hit_at(results, frozenset({"base"}), 1) == 1.0


def test_one_chunk_can_cover_several_cited_sections() -> None:
    results = ranking(("a", "b"))

    assert recall_at(results, frozenset({"a", "b"}), 1) == 1.0


def test_recall_needs_cited_sections() -> None:
    with pytest.raises(ValueError, match="at least one cited section"):
        recall_at(FACTUAL, frozenset(), 5)


def test_worked_example_means() -> None:
    rows = [
        ("factual", retrieval_metrics(FACTUAL, frozenset({"base"}), [5])),
        ("multi_hop", retrieval_metrics(MULTI_HOP, frozenset({"a", "b"}), [5])),
        ("table", retrieval_metrics(TABLE, frozenset({"zones"}), [5])),
    ]

    overall = aggregate(rows)["all"]

    assert overall["n"] == 3
    assert overall["hit@5"] == pytest.approx(2 / 3)
    assert overall["recall@5"] == pytest.approx(0.5)
    assert overall["mrr"] == pytest.approx(0.5)


def test_aggregate_keeps_category_order_and_puts_all_last() -> None:
    rows = [("table", {"mrr": 1.0}), ("factual", {"mrr": 0.0}), ("table", {"mrr": 0.0})]

    result = aggregate(rows)

    assert list(result) == ["table", "factual", "all"]
    assert result["table"] == {"n": 2.0, "mrr": 0.5}


def test_gate_metrics_count_the_two_errors_apart() -> None:
    # (expected_english, passed): one correct each way, one English blocked, one foreign passed.
    outcomes = [(True, True), (False, False), (True, False), (False, True)]

    scores = gate_metrics(outcomes)

    assert scores == {
        "n": 4.0,
        "accuracy": 0.5,
        "english_blocked": 1.0,
        "non_english_passed": 1.0,
    }


def test_gate_metrics_on_no_messages_is_zero() -> None:
    assert gate_metrics([])["accuracy"] == 0.0

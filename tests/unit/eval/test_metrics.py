import pytest

from homerag.eval.metrics import (
    aggregate,
    answer_checks,
    gate_metrics,
    hit_at,
    longest_copied_run,
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


SOURCE = "Synthetic training text: the base period builds endurance, force and speed skills."


def test_longest_copied_run_ignores_case_punctuation_and_citation_marks() -> None:
    answer = "The Base Period builds endurance, [1] force and speed - in short."

    # "the base period builds endurance force and speed"
    assert longest_copied_run(answer, [SOURCE, "unrelated words"]) == 8


def test_answer_checks_flags_missing_and_invalid_citations_and_copying() -> None:
    copied = "the base period builds endurance force and speed skills [1]"

    checks = answer_checks(copied, [1, 7], [SOURCE], english=True, max_copied_words=5)

    assert checks == {
        "cites": 1.0,
        "cites_ok": 0.0,
        "english": 1.0,
        "copied": 9.0,
        "paraphrase": 0.0,
    }


def test_answer_without_citations_does_not_cite() -> None:
    checks = answer_checks("The book does not cover this.", [], [SOURCE], True, 20)

    assert (checks["cites"], checks["cites_ok"], checks["paraphrase"]) == (0.0, 1.0, 1.0)

import pytest

from tricoach.models import Answer, Block, Chunk


def test_heading_requires_level() -> None:
    with pytest.raises(ValueError, match="level"):
        Block("heading", "Base Period", "ch01.xhtml")


def test_non_heading_rejects_level() -> None:
    with pytest.raises(ValueError, match="level"):
        Block("paragraph", "Some text.", "ch01.xhtml", level=2)


def test_chunk_id_must_belong_to_its_section() -> None:
    with pytest.raises(ValueError, match="must start with"):
        Chunk("other#1", "base-period", ("Base Period",), "Some text.")


def test_chunk_needs_text() -> None:
    with pytest.raises(ValueError, match="no text"):
        Chunk("base-period#1", "base-period", ("Base Period",), "   ")


def test_answer_defaults_to_no_citations_and_no_retrieval() -> None:
    answer = Answer("Question?", "Notice.", blocked_by_gate=True)

    assert answer.citations == ()
    assert answer.retrieved == ()

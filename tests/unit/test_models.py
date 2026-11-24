import pytest

from homerag.models import Answer, Block, Chunk, SectionRef

BASE = SectionRef("base-period", ("Base Period",))


def test_heading_requires_level() -> None:
    with pytest.raises(ValueError, match="level"):
        Block("heading", "Base Period", "ch01.xhtml")


def test_non_heading_rejects_level() -> None:
    with pytest.raises(ValueError, match="level"):
        Block("paragraph", "Some text.", "ch01.xhtml", level=2)


def test_chunk_id_must_belong_to_its_section() -> None:
    with pytest.raises(ValueError, match="must start with"):
        Chunk("other#1", (BASE,), "Some text.")


def test_chunk_needs_a_section() -> None:
    with pytest.raises(ValueError, match="no section"):
        Chunk("base-period#1", (), "Some text.")


def test_chunk_needs_text() -> None:
    with pytest.raises(ValueError, match="no text"):
        Chunk("base-period#1", (BASE,), "   ")


def test_answer_defaults_to_no_citations_and_no_retrieval() -> None:
    answer = Answer("Question?", "Notice.", blocked_by_gate=True)

    assert answer.citations == ()
    assert answer.retrieved == ()

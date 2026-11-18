"""Golden dataset schema and loader, on synthetic questions (never text from the book)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tricoach.eval.dataset import GoldenQuestion, load_golden

EXAMPLE = Path(__file__).parents[3] / "eval" / "datasets" / "example.jsonl"


def _question(**overrides: Any) -> dict[str, Any]:  # Any: free-form JSON fields under test
    fields: dict[str, Any] = {
        "id": "q-001",
        "question": "How long is the synthetic base period?",
        "category": "factual",
        "reference_answer": "Eight weeks.",
        "relevant_section_ids": ["chapter-one/base"],
    }
    return {**fields, **overrides}


def _write(path: Path, *questions: dict[str, Any]) -> Path:
    path.write_text("\n".join(json.dumps(q) for q in questions) + "\n", encoding="utf-8")
    return path


def test_valid_question_defaults_to_english() -> None:
    question = GoldenQuestion.model_validate(_question())

    assert question.language == "en"
    assert question.relevant_section_ids == ("chapter-one/base",)


@pytest.mark.parametrize(
    "fields",
    [
        _question(category="multi_hop", relevant_section_ids=["a", "b"]),
        _question(category="out_of_scope", relevant_section_ids=[]),
        _question(category="follow_up", previous_id="q-000"),
        {"id": "q-001", "question": "Ciao?", "category": "non_english", "language": "it"},
    ],
)
def test_category_rules_accept(fields: dict[str, Any]) -> None:
    GoldenQuestion.model_validate(fields)


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        (_question(id="42"), "pattern"),
        (_question(question="  "), "at least 1 character"),
        (_question(category="opinion"), "category"),
        (_question(language="EN"), "pattern"),
        (_question(unknown_field=1), "Extra inputs"),
        (_question(reference_answer=None), "needs a reference_answer"),
        (_question(language="it"), "needs language 'en'"),
        (_question(relevant_section_ids=[]), "at least 1 section"),
        (_question(category="multi_hop"), "at least 2 section"),
        (_question(category="out_of_scope"), "cites no sections"),
        (_question(category="follow_up"), "previous_id is required"),
        (_question(previous_id="q-000"), "previous_id is required"),
        (_question(category="non_english", relevant_section_ids=[]), "other than 'en'"),
        (
            _question(category="non_english", language="it", relevant_section_ids=[]),
            "no reference_answer",
        ),
    ],
)
def test_category_rules_reject(fields: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        GoldenQuestion.model_validate(fields)


def test_load_golden_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    path.write_text("\n" + json.dumps(_question()) + "\n\n", encoding="utf-8")

    assert [q.id for q in load_golden(path)] == ["q-001"]


def test_load_golden_reports_the_line_number(tmp_path: Path) -> None:
    path = _write(tmp_path / "golden.jsonl", _question(), _question(id="q-002", category="?"))

    with pytest.raises(ValueError, match=r"golden\.jsonl:2:"):
        load_golden(path)


def test_load_golden_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    path.write_text("{not json\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"(?s)jsonl:1:.*Invalid JSON"):
        load_golden(path)


def test_load_golden_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = _write(tmp_path / "golden.jsonl", _question(), _question())

    with pytest.raises(ValueError, match="q-001: duplicate id"):
        load_golden(path)


@pytest.mark.parametrize("previous_id", ["q-009", "q-003", "q-002"])
def test_follow_up_must_point_to_an_earlier_question(tmp_path: Path, previous_id: str) -> None:
    follow_up = _question(id="q-002", category="follow_up", previous_id=previous_id)
    path = _write(tmp_path / "golden.jsonl", _question(), follow_up, _question(id="q-003"))

    with pytest.raises(ValueError, match="is not an earlier question"):
        load_golden(path)


def test_example_file_is_valid() -> None:
    questions = load_golden(EXAMPLE)

    assert {q.category for q in questions} == {"factual", "follow_up", "non_english"}

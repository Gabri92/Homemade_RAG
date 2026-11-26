import json
from pathlib import Path

import pytest

from homerag.config import load_experiment
from homerag.eval.dataset import GoldenQuestion
from homerag.eval.judge import judge, judge_request, verdict_scores
from homerag.models import Answer, Chunk, RetrievedChunk, SectionRef
from tests.conftest import FakeLLM

CFG = load_experiment(Path("configs/experiments/baseline.yaml")).judge

QUESTION = GoldenQuestion.model_validate(
    {
        "id": "q-001",
        "question": "How long is the synthetic base period?",
        "category": "factual",
        "reference_answer": "Eight synthetic weeks.",
        "relevant_section_ids": ["base"],
    }
)
CHUNK = Chunk("base#1", (SectionRef("base", ("Base",)),), "Synthetic source text.", "3")
RESULT = Answer(QUESTION.question, "Eight weeks [1].", retrieved=(RetrievedChunk(CHUNK, 0.9, 1),))
VERDICT = {"reasoning": "matches", "correctness": "correct", "faithful": True, "declined": False}


def fake_llm(text: str, stop_reason: str = "end_turn") -> FakeLLM:
    return FakeLLM(text, stop_reason, cost_usd=0.02)


def test_judge_request_holds_question_reference_sources_answer_and_schema() -> None:
    request = judge_request(QUESTION, RESULT, CFG)

    assert request.model == CFG.model
    assert "<reference_answer>\nEight synthetic weeks." in request.user
    assert '<source id="1" section="Base" page="3">' in request.user
    assert "<answer>\nEight weeks [1].\n</answer>" in request.user
    assert request.output_schema is not None
    properties = request.output_schema["properties"]
    assert isinstance(properties, dict)
    assert list(properties) == ["reasoning", "correctness", "faithful", "declined"]


def test_judge_parses_the_verdict() -> None:
    verdict, usage = judge(QUESTION, RESULT, fake_llm(json.dumps(VERDICT)), CFG)

    assert verdict.correctness == "correct"
    assert usage.cost_usd == 0.02
    assert verdict_scores(verdict) == {"correct": 1.0, "faithful": 1.0, "declined": 0.0}


def test_judge_that_stops_early_fails_with_the_question_id() -> None:
    with pytest.raises(ValueError, match="q-001: judge stopped with 'refusal'"):
        judge(QUESTION, RESULT, fake_llm("", "refusal"), CFG)


def test_judge_output_that_is_not_a_verdict_fails_clearly() -> None:
    with pytest.raises(ValueError, match="q-001: judge output is not a valid verdict"):
        judge(QUESTION, RESULT, fake_llm('{"reasoning": "x"}'), CFG)

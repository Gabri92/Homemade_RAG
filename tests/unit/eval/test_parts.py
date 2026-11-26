"""The parts of a run (gate, retrieval, generation) on a synthetic golden set."""

from pathlib import Path

from homerag.config import load_experiment
from homerag.eval.parts import (
    retrieval_questions,
    run_gate,
    run_generation,
    run_retrieval,
    score_gate,
)
from homerag.language import build_detector
from tests.conftest import (
    EVAL_INDEX,
    GOLDEN_QUESTIONS,
    FakeLLM,
    answer_or_verdict,
    embed_on_first_axis,
    fake_resources,
    golden_question,
)

CFG = load_experiment(Path("configs/experiments/baseline.yaml"))
DETECTOR = build_detector(CFG.language_gate)


def test_only_questions_citing_sections_are_scored_on_retrieval() -> None:
    ids = [q.id for q in retrieval_questions(GOLDEN_QUESTIONS)]

    assert ids == ["q-001", "q-002"]


def test_run_retrieval_scores_each_question() -> None:
    runs = run_retrieval(GOLDEN_QUESTIONS, EVAL_INDEX, embed_on_first_axis, CFG)

    assert [r.question.id for r in runs] == ["q-001", "q-002"]
    assert runs[0].retrieved[0].chunk.id == "base#1"
    assert runs[0].metrics["hit@1"] == 1.0
    assert runs[0].metrics["mrr"] == 1.0


def test_run_gate_scores_every_question_including_non_english() -> None:
    english = golden_question("q-001", "factual", "base").model_copy(
        update={"question": "How long should the base period last for a beginner?"}
    )
    italian = golden_question("q-004", "non_english").model_copy(
        update={"question": "Quanto deve durare il periodo di base per un principiante?"}
    )

    runs = run_gate([english, italian], DETECTOR, CFG.language_gate)

    assert [(r.question.id, r.passed, r.correct) for r in runs] == [
        ("q-001", True, True),
        ("q-004", False, True),
    ]
    assert score_gate(runs)["accuracy"] == 1.0


def test_run_generation_answers_and_grades_all_but_non_english() -> None:
    llm = FakeLLM(answer_or_verdict)

    runs = run_generation(GOLDEN_QUESTIONS, fake_resources(EVAL_INDEX, llm, CFG.language_gate), CFG)

    assert [r.question.id for r in runs] == ["q-001", "q-002", "q-003"]
    judge_requests = [r for r in llm.requests if r.output_schema is not None]
    assert len(judge_requests) == 3
    assert judge_requests[0].model == CFG.judge.model
    metrics = runs[0].metrics
    assert (metrics["correct"], metrics["faithful"], metrics["cites"]) == (0.5, 1.0, 1.0)
    assert metrics["cost_usd"] == 0.03  # answer 0.01 + judge 0.02
    assert metrics["latency_s"] == 1.5

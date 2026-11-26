import json
from pathlib import Path

import numpy as np

from homerag.config import load_experiment
from homerag.eval.dataset import GoldenQuestion
from homerag.eval.report import load_run, save_run
from homerag.eval.run import (
    result_rows,
    retrieval_questions,
    run_cost,
    run_gate,
    run_generation,
    run_retrieval,
    score_gate,
)
from homerag.index import VectorIndex
from homerag.language import build_detector
from homerag.llm import Completion, LLMRequest
from homerag.models import Chunk, SectionRef, Usage
from homerag.qa import Resources
from tests.conftest import FakeLLM, embed_on_first_axis, fake_resources

BASELINE = Path("configs/experiments/baseline.yaml")
CFG = load_experiment(BASELINE)
DETECTOR = build_detector(CFG.language_gate)


def question(qid: str, category: str, *sections: str, **extra: str) -> GoldenQuestion:
    fields: dict[str, object] = {
        "id": qid,
        "question": f"question {qid}",
        "category": category,
        "relevant_section_ids": sections,
        "reference_answer": "a paraphrase",
        **extra,
    }
    if category == "non_english":
        fields.update(language="it", reference_answer=None)
    return GoldenQuestion.model_validate(fields)


QUESTIONS = [
    question("q-001", "factual", "base"),
    question("q-002", "follow_up", "base", previous_id="q-001"),
    question("q-003", "out_of_scope"),
    question("q-004", "non_english"),
]

# Two chunks; the fake embedder points every question at the "base" chunk.
INDEX = VectorIndex(
    (
        Chunk("base#1", (SectionRef("base", ("Base",)),), "synthetic chunk text", "1"),
        Chunk(
            "swim#1",
            (SectionRef("swim", ("Swim",)), SectionRef("bike", ("Bike",))),
            "other synthetic text",
            "2",
        ),
    ),
    np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
)

VERDICT = {"reasoning": "ok", "correctness": "partial", "faithful": True, "declined": False}


def reply(request: LLMRequest) -> Completion:
    """Answers generation requests with a cited sentence and judge requests with a verdict."""
    if request.output_schema is not None:
        return Completion(json.dumps(VERDICT), "end_turn", Usage(request.model, 50, 30, 0.02))
    return Completion(
        "A synthetic answer for this test [1].",
        "end_turn",
        Usage(request.model, 100, 20, 0.01, latency_s=1.5, cached=True),
    )


def resources(llm: FakeLLM) -> Resources:
    return fake_resources(INDEX, llm, CFG.language_gate)


def test_only_questions_citing_sections_are_scored_on_retrieval() -> None:
    ids = [q.id for q in retrieval_questions(QUESTIONS)]

    assert ids == ["q-001", "q-002"]


def test_run_retrieval_scores_each_question() -> None:
    runs = run_retrieval(QUESTIONS, INDEX, embed_on_first_axis, CFG)

    assert [r.question.id for r in runs] == ["q-001", "q-002"]
    assert runs[0].retrieved[0].chunk.id == "base#1"
    assert runs[0].metrics["hit@1"] == 1.0
    assert runs[0].metrics["mrr"] == 1.0


def test_run_gate_scores_every_question_including_non_english() -> None:
    english = question("q-001", "factual", "base").model_copy(
        update={"question": "How long should the base period last for a beginner?"}
    )
    italian = question("q-004", "non_english").model_copy(
        update={"question": "Quanto deve durare il periodo di base per un principiante?"}
    )

    runs = run_gate([english, italian], DETECTOR, CFG.language_gate)

    assert [(r.question.id, r.passed, r.correct) for r in runs] == [
        ("q-001", True, True),
        ("q-004", False, True),
    ]
    assert score_gate(runs)["accuracy"] == 1.0


def test_run_generation_answers_and_grades_all_but_non_english() -> None:
    llm = FakeLLM(reply)

    runs = run_generation(QUESTIONS, resources(llm), CFG)

    assert [r.question.id for r in runs] == ["q-001", "q-002", "q-003"]
    judge_requests = [r for r in llm.requests if r.output_schema is not None]
    assert len(judge_requests) == 3
    assert judge_requests[0].model == CFG.judge.model
    metrics = runs[0].metrics
    assert (metrics["correct"], metrics["faithful"], metrics["cites"]) == (0.5, 1.0, 1.0)
    assert metrics["cost_usd"] == 0.03  # answer 0.01 + judge 0.02
    assert metrics["latency_s"] == 1.5


def test_run_cost_counts_cached_answers_as_not_paid_now() -> None:
    runs = run_generation(QUESTIONS, resources(FakeLLM(reply)), CFG)

    assert run_cost(runs) == {"answers": 0.03, "judge": 0.06, "paid_now": 0.06}


def test_saved_run_has_one_row_per_question_and_no_chunk_text(tmp_path: Path) -> None:
    rows = result_rows(
        QUESTIONS,
        run_gate(QUESTIONS, DETECTOR, CFG.language_gate),
        run_retrieval(QUESTIONS, INDEX, embed_on_first_axis, CFG),
        run_generation(QUESTIONS, resources(FakeLLM(reply)), CFG),
    )
    meta = {"run_format": 2, "cost_usd": {"answers": 0.0, "judge": 0.0, "paid_now": 0.0}}

    save_run(tmp_path / "run", CFG, rows, {"retrieval": {}, "generation": {}, "gate": {}}, meta)

    saved = load_run(tmp_path / "run")
    assert [row["id"] for row in saved.rows] == ["q-001", "q-002", "q-003", "q-004"]
    assert saved.rows[0]["retrieval"]["retrieved"][0]["sections"] == ["base"]
    assert saved.rows[0]["generation"]["verdict"]["correctness"] == "partial"
    assert saved.rows[2]["retrieval"] is None  # out_of_scope cites no section
    assert saved.rows[3]["generation"] is None  # non_english is only gated
    text = (tmp_path / "run" / "results.jsonl").read_text(encoding="utf-8")
    assert "synthetic chunk text" not in text

import json
from pathlib import Path

import numpy as np

from homerag.config import load_experiment
from homerag.eval.dataset import GoldenQuestion
from homerag.eval.run import (
    format_gate,
    format_metrics,
    retrieval_questions,
    run_gate,
    run_retrieval,
    save_gate,
    save_run,
    score_gate,
)
from homerag.index import VectorIndex, Vectors
from homerag.language import build_detector
from homerag.models import Chunk, SectionRef

BASELINE = Path("configs/experiments/baseline.yaml")


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
        Chunk("base#1", (SectionRef("base", ("Base",)),), "t", "1"),
        Chunk("swim#1", (SectionRef("swim", ("Swim",)), SectionRef("bike", ("Bike",))), "t", "2"),
    ),
    np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
)


def embed(texts: list[str]) -> Vectors:
    return np.array([[1.0, 0.0]] * len(texts), dtype=np.float32)


def test_only_questions_citing_sections_are_scored_on_retrieval() -> None:
    ids = [q.id for q in retrieval_questions(QUESTIONS)]

    assert ids == ["q-001", "q-002"]


def test_run_retrieval_scores_each_question() -> None:
    runs = run_retrieval(QUESTIONS, INDEX, embed, load_experiment(BASELINE))

    assert [r.question.id for r in runs] == ["q-001", "q-002"]
    assert runs[0].retrieved[0].chunk.id == "base#1"
    assert runs[0].metrics["hit@1"] == 1.0
    assert runs[0].metrics["mrr"] == 1.0


def test_saved_run_has_config_results_metrics_and_meta_but_no_chunk_text(tmp_path: Path) -> None:
    cfg = load_experiment(BASELINE)
    runs = run_retrieval(QUESTIONS, INDEX, embed, cfg)

    gate_runs = run_gate(GATE_QUESTIONS, build_detector(cfg.language_gate), cfg.language_gate)

    save_run(tmp_path / "run", cfg, runs, {"all": {"n": 2.0}}, {"seed": "meta"})
    save_gate(tmp_path / "run", gate_runs)

    files = sorted(p.name for p in (tmp_path / "run").iterdir())
    assert files == ["config.yaml", "gate.json", "meta.json", "metrics.json", "results.jsonl"]
    gate = json.loads((tmp_path / "run" / "gate.json").read_text(encoding="utf-8"))
    assert gate["metrics"]["accuracy"] == 1.0
    assert [row["passed"] for row in gate["questions"]] == [True, False]
    results = (tmp_path / "run" / "results.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in results.splitlines()]
    assert rows[0]["retrieved"][0]["sections"] == ["base"]
    assert "text" not in rows[0]["retrieved"][0]


def test_format_metrics_prints_one_row_per_category() -> None:
    table = format_metrics({"factual": {"n": 2.0, "hit@1": 0.5}, "all": {"n": 2.0, "hit@1": 0.5}})

    lines = table.splitlines()
    assert "hit@1" in lines[0]
    assert lines[1].split() == ["factual", "2", "0.50"]
    assert lines[2].split()[0] == "all"


GATE_QUESTIONS = [
    question("q-001", "factual", "base").model_copy(
        update={"question": "How long should the base period last for a beginner?"}
    ),
    question("q-004", "non_english").model_copy(
        update={"question": "Quanto deve durare il periodo di base per un principiante?"}
    ),
]


def test_run_gate_scores_every_question_including_non_english() -> None:
    gate = load_experiment(BASELINE).language_gate

    runs = run_gate(GATE_QUESTIONS, build_detector(gate), gate)

    assert [(r.question.id, r.passed, r.correct) for r in runs] == [
        ("q-001", True, True),
        ("q-004", False, True),
    ]
    assert score_gate(runs)["accuracy"] == 1.0


def test_format_gate_names_the_misjudged_questions() -> None:
    gate = {"n": 2.0, "accuracy": 0.5, "english_blocked": 1.0, "non_english_passed": 0.0}

    text = format_gate(gate, ["q-001"])

    assert "accuracy 0.50" in text
    assert "English blocked 1" in text
    assert "misjudged: q-001" in text

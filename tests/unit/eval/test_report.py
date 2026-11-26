import json
from pathlib import Path
from typing import Any

import pytest

from homerag.config import load_experiment
from homerag.eval.parts import run_gate, run_generation, run_retrieval
from homerag.eval.report import (
    SavedRun,
    compare_runs,
    format_cost,
    format_gate,
    format_metrics,
    load_run,
    result_rows,
    save_run,
)
from homerag.language import build_detector
from tests.conftest import (
    EVAL_INDEX,
    GOLDEN_QUESTIONS,
    FakeLLM,
    answer_or_verdict,
    embed_on_first_axis,
    fake_resources,
)

GATE = {"all": {"n": 2.0, "accuracy": 1.0, "english_blocked": 0.0, "non_english_passed": 0.0}}


def saved(name: str, mrr: float, correct: float, cost: float) -> SavedRun:
    row: dict[str, Any] = {
        "id": "q-001",
        "category": "factual",
        "retrieval": {"metrics": {"mrr": mrr}},
        "generation": {"metrics": {"correct": correct, "faithful": 1.0}},
    }
    metrics = {
        "retrieval": {"factual": {"n": 1.0, "mrr": mrr}, "all": {"n": 1.0, "mrr": mrr}},
        "generation": {"factual": {"n": 1.0, "correct": correct}},
        "gate": GATE,
    }
    meta = {"run_format": 2, "cost_usd": {"answers": cost, "judge": cost, "paid_now": 0.0}}
    return SavedRun(Path(name), meta, metrics, [row])


def test_compare_shows_deltas_and_the_questions_that_changed() -> None:
    text = compare_runs(saved("run-a", 1.0, 1.0, 0.5), saved("run-b", 0.5, 0.5, 0.25))

    assert "A: run-a" in text
    assert "0.50 -0.50" in text  # mrr and correct both dropped by 0.5
    assert "cost per run (answers + judge): $1.00 -> $0.50" in text
    assert "q-001 (factual): mrr 1.00 -> 0.50; correct 1.00 -> 0.50" in text
    assert "better in B:\n  none" in text


def test_load_run_refuses_an_older_format(tmp_path: Path) -> None:
    (tmp_path / "meta.json").write_text(json.dumps({"questions_evaluated": 26}), encoding="utf-8")

    with pytest.raises(ValueError, match="older run format"):
        load_run(tmp_path)


def test_load_run_refuses_a_folder_that_is_not_a_run(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a run folder"):
        load_run(tmp_path)


def test_format_metrics_prints_one_row_per_category() -> None:
    table = format_metrics({"factual": {"n": 2.0, "hit@1": 0.5}, "all": {"n": 2.0, "hit@1": 0.5}})

    assert table.splitlines()[0].split() == ["category", "n", "hit@1"]
    assert table.splitlines()[1].split() == ["factual", "2", "0.50"]


def test_format_gate_names_the_misjudged_questions() -> None:
    gate = {"n": 2.0, "accuracy": 0.5, "english_blocked": 1.0, "non_english_passed": 0.0}

    text = format_gate(gate, ["q-001"])

    assert "accuracy 0.50" in text
    assert "misjudged: q-001" in text


def test_format_cost_says_what_was_paid_in_this_run() -> None:
    text = format_cost({"answers": 0.31, "judge": 0.74, "paid_now": 0.2})

    assert "answers $0.31, judge $0.74 (paid in this run $0.20" in text


# --- the rows of a run ------------------------------------------------------------

RUN_CFG = load_experiment(Path("configs/experiments/baseline.yaml"))


def test_saved_run_has_one_row_per_question_and_no_chunk_text(tmp_path: Path) -> None:
    rows = result_rows(
        GOLDEN_QUESTIONS,
        run_gate(GOLDEN_QUESTIONS, build_detector(RUN_CFG.language_gate), RUN_CFG.language_gate),
        run_retrieval(GOLDEN_QUESTIONS, EVAL_INDEX, embed_on_first_axis, RUN_CFG),
        run_generation(
            GOLDEN_QUESTIONS,
            fake_resources(EVAL_INDEX, FakeLLM(answer_or_verdict), RUN_CFG.language_gate),
            RUN_CFG,
        ),
    )
    meta = {"run_format": 2, "cost_usd": {"answers": 0.0, "judge": 0.0, "paid_now": 0.0}}

    save_run(tmp_path / "run", RUN_CFG, rows, {"retrieval": {}, "generation": {}, "gate": {}}, meta)

    loaded = load_run(tmp_path / "run")
    assert [row["id"] for row in loaded.rows] == ["q-001", "q-002", "q-003", "q-004"]
    assert loaded.rows[0]["retrieval"]["retrieved"][0]["sections"] == ["base"]
    assert loaded.rows[0]["generation"]["verdict"]["correctness"] == "partial"
    assert loaded.rows[2]["retrieval"] is None  # out_of_scope cites no section
    assert loaded.rows[3]["generation"] is None  # non_english is only gated
    text = (tmp_path / "run" / "results.jsonl").read_text(encoding="utf-8")
    assert "synthetic chunk text" not in text

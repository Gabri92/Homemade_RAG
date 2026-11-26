"""Experiment runs: an experiment config over the golden set, saved to `eval/runs/`.

`run_experiment` runs the parts (`eval/parts.py`), aggregates their metrics per question
category, adds what the run was computed from and what it cost, and saves it with
`eval/report.py`. Answers and judge are skipped with `retrieval_only` (no API cost).
"""

import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

from homerag.config import ExperimentConfig, load_experiment, load_settings
from homerag.embedding import load_embedder_for
from homerag.eval.dataset import GoldenQuestion, load_golden
from homerag.eval.metrics import aggregate
from homerag.eval.parts import (
    GateRun,
    GenerationRun,
    QuestionRun,
    run_gate,
    run_generation,
    run_retrieval,
    score_gate,
)
from homerag.eval.report import RUN_FORMAT, Metrics, result_rows, save_run
from homerag.index import VectorIndex, ensure_index, fingerprint, open_index
from homerag.language import build_detector
from homerag.llm import LLM, anthropic_llm, cached
from homerag.qa import Resources

RUNS_ROOT = Path("eval/runs")


@dataclass(frozen=True, slots=True)
class RunReport:
    """What `run_experiment` did, for the CLI to print."""

    folder: Path
    metrics: dict[str, Metrics]
    gate_errors: list[str]
    skipped: dict[str, int]
    cost: dict[str, float]


def run_experiment(
    config_path: Path,
    golden_path: Path,
    runs_root: Path = RUNS_ROOT,
    retrieval_only: bool = False,
    llm: LLM | None = None,
) -> RunReport:
    """Run the experiment on the golden set and save it.

    Without `llm`, the real cached Claude client is built from `.env` (unless
    `retrieval_only`), before any slow step, so a missing key fails at once.
    """
    start, started_at = time.perf_counter(), datetime.now()
    cfg = load_experiment(config_path)
    questions = load_golden(golden_path)
    if llm is None and not retrieval_only:
        llm = cached(anthropic_llm(load_settings().anthropic_api_key))
    index_report = ensure_index(cfg)
    index = open_index(cfg)
    gate_runs, retrieval_runs, generation_runs = _run_parts(questions, cfg, index, llm)
    metrics = run_metrics(gate_runs, retrieval_runs, generation_runs)
    skipped = _skipped(questions, retrieval_runs)
    cost = run_cost(generation_runs)
    meta = {
        "run_format": RUN_FORMAT,
        "homerag_version": version("homerag"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "retrieval_only": llm is None,
        **_provenance(cfg.document, golden_path, index_report.folder, index),
        "retrieval_skipped": skipped,
        "cost_usd": cost,
        "seconds": round(time.perf_counter() - start, 1),
    }
    folder = runs_root / f"{started_at:%Y%m%d-%H%M%S}-{cfg.name}"
    rows = result_rows(questions, gate_runs, retrieval_runs, generation_runs)
    save_run(folder, cfg, rows, metrics, meta)
    gate_errors = [run.question.id for run in gate_runs if not run.correct]
    return RunReport(folder, metrics, gate_errors, skipped, cost)


def _run_parts(
    questions: list[GoldenQuestion], cfg: ExperimentConfig, index: VectorIndex, llm: LLM | None
) -> tuple[list[GateRun], list[QuestionRun], list[GenerationRun]]:
    """Gate and retrieval on every question; answers and judge only with an `llm`."""
    embed = load_embedder_for(cfg.embedding)
    detector = build_detector(cfg.language_gate)
    resources = Resources(index, embed, detector, llm) if llm else None
    return (
        run_gate(questions, detector, cfg.language_gate),
        run_retrieval(questions, index, embed, cfg),
        run_generation(questions, resources, cfg) if resources else [],
    )


def _skipped(questions: list[GoldenQuestion], runs: list[QuestionRun]) -> dict[str, int]:
    """Per category, the questions not scored on retrieval: they cite no section."""
    retrieved = {r.question.id for r in runs}
    return dict(Counter(q.category for q in questions if q.id not in retrieved))


def run_metrics(
    gate_runs: list[GateRun],
    retrieval_runs: list[QuestionRun],
    generation_runs: list[GenerationRun],
) -> dict[str, Metrics]:
    """Each part's metrics per question category: retrieval, generation, and the gate."""
    return {
        "retrieval": aggregate((r.question.category, r.metrics) for r in retrieval_runs),
        "generation": aggregate(
            (r.question.category, r.metrics) for r in generation_runs if r.metrics
        ),
        "gate": {"all": score_gate(gate_runs)},
    }


def _provenance(
    document: Path, golden_path: Path, index_folder: Path, index: VectorIndex
) -> dict[str, object]:
    """What the run was computed from: the document, the golden set and the index."""
    return {
        "document_fingerprint": fingerprint(document),
        "golden": str(golden_path),
        "golden_fingerprint": fingerprint(golden_path),
        "index_folder": str(index_folder),
        "index_chunks": len(index.chunks),
        "multi_section_chunk_share": _multi_section_share(index),
    }


def run_cost(runs: list[GenerationRun]) -> dict[str, float]:
    """Total cost of the answers and of the judge, and how much of it was paid in this run."""
    usages = [(r.answer.usage, "answers") for r in runs] + [(r.judge_usage, "judge") for r in runs]
    cost = {"answers": 0.0, "judge": 0.0, "paid_now": 0.0}
    for usage, part in usages:
        if usage is not None:
            cost[part] += usage.cost_usd
            cost["paid_now"] += 0.0 if usage.cached else usage.cost_usd
    return {part: round(value, 4) for part, value in cost.items()}


def _multi_section_share(index: VectorIndex) -> float:
    # ADR 0005: "at least one cited section" is lenient with chunks covering several.
    if not index.chunks:
        return 0.0
    return round(sum(len(c.sections) > 1 for c in index.chunks) / len(index.chunks), 3)

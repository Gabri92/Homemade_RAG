"""Experiment runs: an experiment config over the golden set, saved to `eval/runs/`.

Every question that cites sections is retrieved and scored (`eval/metrics.py`);
`out_of_scope` questions cite none, so they wait for the generator (Phase 3b). Every question
also goes through the language gate, scored on its own: retrieval metrics do not depend on the
gate, so a gate change never moves them. A run folder holds:
- `config.yaml`: the full experiment config;
- `results.jsonl`: one line per question, with the ranking (ids, sections, scores) and metrics;
- `metrics.json`: retrieval means per category and overall;
- `gate.json`: gate metrics and, per question, the expected and the actual outcome;
- `meta.json`: versions and fingerprints, so two runs can be checked for comparability.
No chunk text is saved: ids and section ids are enough to analyse a run.
"""

import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import yaml

from homerag.config import ExperimentConfig, LanguageGateConfig, load_experiment
from homerag.eval.dataset import ENGLISH, GoldenQuestion, load_golden
from homerag.eval.metrics import aggregate, gate_metrics, retrieval_metrics
from homerag.index import (
    Embed,
    VectorIndex,
    ensure_index,
    fingerprint,
    load_embedder_for,
    open_index,
)
from homerag.language import Detector, build_detector, is_english
from homerag.models import RetrievedChunk
from homerag.retrieval import RETRIEVERS

RUNS_ROOT = Path("eval/runs")


@dataclass(frozen=True, slots=True)
class QuestionRun:
    """What one golden question produced, and how it scored."""

    question: GoldenQuestion
    retrieved: tuple[RetrievedChunk, ...]
    metrics: dict[str, float]


@dataclass(frozen=True, slots=True)
class GateRun:
    """One golden question through the language gate."""

    question: GoldenQuestion
    passed: bool

    @property
    def correct(self) -> bool:
        return self.passed == (self.question.language == ENGLISH)


@dataclass(frozen=True, slots=True)
class RunReport:
    """What `run_experiment` did, for the CLI to print."""

    folder: Path
    metrics: dict[str, dict[str, float]]
    skipped: dict[str, int]
    gate: dict[str, float]
    gate_errors: list[str]


def retrieval_questions(questions: list[GoldenQuestion]) -> list[GoldenQuestion]:
    """The questions retrieval can be scored on: those citing at least one section."""
    return [q for q in questions if q.relevant_section_ids]


def run_retrieval(
    questions: list[GoldenQuestion], index: VectorIndex, embed: Embed, cfg: ExperimentConfig
) -> list[QuestionRun]:
    """Retrieve and score each question. Follow-ups are retrieved as written (no rewriting)."""
    selected = retrieval_questions(questions)
    embed([q.question for q in selected])  # one batch fills the cache; each search reads it
    retrieve = RETRIEVERS[cfg.retrieval.strategy]
    runs = []
    for question in selected:
        retrieved = retrieve(question.question, index, embed, cfg.retrieval)
        cited = frozenset(question.relevant_section_ids)
        metrics = retrieval_metrics(retrieved, cited, cfg.evaluation.ks)
        runs.append(QuestionRun(question, tuple(retrieved), metrics))
    return runs


def run_gate(
    questions: list[GoldenQuestion], detector: Detector, cfg: LanguageGateConfig
) -> list[GateRun]:
    """Pass every question through the language gate."""
    return [GateRun(q, is_english(q.question, detector, cfg)) for q in questions]


def score_gate(runs: list[GateRun]) -> dict[str, float]:
    return gate_metrics((run.question.language == ENGLISH, run.passed) for run in runs)


def run_experiment(config_path: Path, golden_path: Path, runs_root: Path = RUNS_ROOT) -> RunReport:
    """Build or reuse the index, run retrieval on the golden set, save the run."""
    start, started_at = time.perf_counter(), datetime.now()
    cfg = load_experiment(config_path)
    questions = load_golden(golden_path)
    index_report = ensure_index(cfg)
    index = open_index(cfg)
    gate_runs = run_gate(questions, build_detector(cfg.language_gate), cfg.language_gate)
    runs = run_retrieval(questions, index, load_embedder_for(cfg.embedding), cfg)
    metrics = aggregate((run.question.category, run.metrics) for run in runs)
    evaluated = {run.question.id for run in runs}
    skipped: Counter[str] = Counter(q.category for q in questions if q.id not in evaluated)
    meta = {
        "homerag_version": version("homerag"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "document_fingerprint": fingerprint(cfg.document),
        "golden": str(golden_path),
        "golden_fingerprint": fingerprint(golden_path),
        "index_folder": str(index_report.folder),
        "index_chunks": len(index.chunks),
        "multi_section_chunk_share": _multi_section_share(index),
        "questions_evaluated": len(runs),
        "questions_skipped": dict(skipped),
        "seconds": round(time.perf_counter() - start, 1),
    }
    folder = runs_root / f"{started_at:%Y%m%d-%H%M%S}-{cfg.name}"
    save_run(folder, cfg, runs, metrics, meta)
    save_gate(folder, gate_runs)
    gate_errors = [run.question.id for run in gate_runs if not run.correct]
    return RunReport(folder, metrics, dict(skipped), score_gate(gate_runs), gate_errors)


def save_run(
    folder: Path,
    cfg: ExperimentConfig,
    runs: list[QuestionRun],
    metrics: dict[str, dict[str, float]],
    meta: dict[str, Any],
) -> None:
    """Write the four run files; refuses to overwrite an existing run."""
    folder.mkdir(parents=True, exist_ok=False)
    config = yaml.safe_dump(cfg.model_dump(mode="json"), sort_keys=False)
    (folder / "config.yaml").write_text(config, encoding="utf-8")
    lines = [json.dumps(_result_row(run), ensure_ascii=False) for run in runs]
    (folder / "results.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
    (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def save_gate(folder: Path, gate_runs: list[GateRun]) -> None:
    """Write `gate.json` into an existing run folder."""
    gate = {"metrics": score_gate(gate_runs), "questions": [_gate_row(r) for r in gate_runs]}
    (folder / "gate.json").write_text(json.dumps(gate, indent=1), encoding="utf-8")


def _result_row(run: QuestionRun) -> dict[str, Any]:
    return {
        "id": run.question.id,
        "category": run.question.category,
        "question": run.question.question,
        "cited": list(run.question.relevant_section_ids),
        "retrieved": [
            {
                "rank": r.rank,
                "score": round(r.score, 4),
                "chunk_id": r.chunk.id,
                "sections": [s.id for s in r.chunk.sections],
                "page": r.chunk.page,
            }
            for r in run.retrieved
        ],
        "metrics": run.metrics,
    }


def _gate_row(run: GateRun) -> dict[str, Any]:
    return {
        "id": run.question.id,
        "category": run.question.category,
        "language": run.question.language,
        "passed": run.passed,
        "correct": run.correct,
    }


def _multi_section_share(index: VectorIndex) -> float:
    # ADR 0005: "at least one cited section" is lenient with chunks covering several.
    if not index.chunks:
        return 0.0
    return round(sum(len(c.sections) > 1 for c in index.chunks) / len(index.chunks), 3)


def format_metrics(metrics: dict[str, dict[str, float]]) -> str:
    """A plain-text table: one row per category (then "all"), one column per metric."""
    if not metrics:
        return "no questions evaluated\n"
    names = [name for name in next(iter(metrics.values())) if name != "n"]
    header = f"{'category':<12} {'n':>3}  " + "  ".join(f"{name:>9}" for name in names)
    rows = [
        f"{category:<12} {int(values['n']):>3}  "
        + "  ".join(f"{values[name]:>9.2f}" for name in names)
        for category, values in metrics.items()
    ]
    return "\n".join([header, *rows]) + "\n"


def format_gate(gate: dict[str, float], errors: list[str]) -> str:
    """One line with the gate scores, plus the ids of the misjudged questions if any."""
    line = (
        f"language gate: {int(gate['n'])} messages, accuracy {gate['accuracy']:.2f}, "
        f"English blocked {int(gate['english_blocked'])}, "
        f"non-English passed {int(gate['non_english_passed'])}\n"
    )
    return line + (f"  misjudged: {', '.join(errors)}\n" if errors else "")

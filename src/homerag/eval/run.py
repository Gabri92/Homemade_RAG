"""Experiment runs: an experiment config over the golden set, saved to `eval/runs/`.

Phase 3a runs retrieval only: every question that cites sections is retrieved and scored
(`eval/metrics.py`). `out_of_scope` and `non_english` questions cite none, so they wait for
the generator and the language gate (Phase 3b). A run folder holds:
- `config.yaml`: the full experiment config;
- `results.jsonl`: one line per question, with the ranking (ids, sections, scores) and metrics;
- `metrics.json`: means per category and overall;
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

from homerag.config import ExperimentConfig, load_experiment
from homerag.eval.dataset import GoldenQuestion, load_golden
from homerag.eval.metrics import aggregate, retrieval_metrics
from homerag.index import (
    Embed,
    VectorIndex,
    ensure_index,
    fingerprint,
    load_embedder_for,
    open_index,
)
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
class RunReport:
    """What `run_experiment` did, for the CLI to print."""

    folder: Path
    metrics: dict[str, dict[str, float]]
    skipped: dict[str, int]


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


def run_experiment(config_path: Path, golden_path: Path, runs_root: Path = RUNS_ROOT) -> RunReport:
    """Build or reuse the index, run retrieval on the golden set, save the run."""
    start, started_at = time.perf_counter(), datetime.now()
    cfg = load_experiment(config_path)
    questions = load_golden(golden_path)
    index_report = ensure_index(cfg)
    index = open_index(cfg)
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
    return RunReport(folder, metrics, dict(skipped))


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

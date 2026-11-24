"""Experiment runs: an experiment config over the golden set, saved to `eval/runs/`.

Each part is scored on its own, so a change to one never moves the numbers of another:
- language gate: every question (`gate_metrics`);
- retrieval: the questions that cite sections (`retrieval_metrics`);
- generation: every question meant to pass the gate (all but `non_english`) is answered by
  `qa.answer`, graded by the judge (`eval/judge.py`) and by code-based checks
  (`answer_checks`), with cost and latency. Skipped with `retrieval_only` (no API cost).
Follow-ups are retrieved and answered as written, without the earlier question.

The run is saved with `eval/report.py`; no chunk text is saved, ids and section ids are
enough to analyse a run.
"""

import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from homerag.config import ExperimentConfig, LanguageGateConfig, load_experiment, load_settings
from homerag.eval.dataset import ENGLISH, GoldenQuestion, load_golden
from homerag.eval.judge import Verdict, judge, verdict_scores
from homerag.eval.metrics import aggregate, answer_checks, gate_metrics, retrieval_metrics
from homerag.eval.report import RUN_FORMAT, Metrics, save_run
from homerag.index import (
    Embed,
    VectorIndex,
    ensure_index,
    fingerprint,
    load_embedder_for,
    open_index,
)
from homerag.language import Detector, build_detector, is_english
from homerag.llm import LLM, anthropic_llm, cached
from homerag.models import Answer, RetrievedChunk, Usage
from homerag.qa import Resources, answer, source_numbers
from homerag.retrieval import RETRIEVERS

RUNS_ROOT = Path("eval/runs")


@dataclass(frozen=True, slots=True)
class QuestionRun:
    """One golden question through retrieval, and how the ranking scored."""

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
class GenerationRun:
    """One golden question answered and graded. Without a verdict when the gate blocked it."""

    question: GoldenQuestion
    answer: Answer
    verdict: Verdict | None
    judge_usage: Usage | None
    metrics: dict[str, float]


@dataclass(frozen=True, slots=True)
class RunReport:
    """What `run_experiment` did, for the CLI to print."""

    folder: Path
    metrics: dict[str, Metrics]
    gate_errors: list[str]
    skipped: dict[str, int]
    cost: dict[str, float]


def retrieval_questions(questions: list[GoldenQuestion]) -> list[GoldenQuestion]:
    """The questions retrieval can be scored on: those citing at least one section."""
    return [q for q in questions if q.relevant_section_ids]


def run_retrieval(
    questions: list[GoldenQuestion], index: VectorIndex, embed: Embed, cfg: ExperimentConfig
) -> list[QuestionRun]:
    """Retrieve and score each question that cites sections."""
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


def run_generation(
    questions: list[GoldenQuestion], resources: Resources, cfg: ExperimentConfig
) -> list[GenerationRun]:
    """Answer and grade every question meant to pass the gate."""
    runs = []
    for question in questions:
        if question.category == "non_english":
            continue
        result = answer(question.question, resources, cfg)
        if result.blocked_by_gate:  # an English question blocked: a gate error, counted there
            runs.append(GenerationRun(question, result, None, None, {}))
            continue
        verdict, judge_usage = judge(question, result, resources.llm, cfg.judge)
        runs.append(
            GenerationRun(
                question,
                result,
                verdict,
                judge_usage,
                generation_metrics(result, verdict, judge_usage, resources.detector, cfg),
            )
        )
    return runs


def generation_metrics(
    result: Answer, verdict: Verdict, judge_usage: Usage, detector: Detector, cfg: ExperimentConfig
) -> dict[str, float]:
    """Judge grades, code-based checks, and the question's cost (answer + judge) and latency."""
    english = is_english(result.text, detector, cfg.language_gate)
    sources = [r.chunk.text for r in result.retrieved]
    checks = answer_checks(
        result.text, source_numbers(result.text), sources, english, cfg.evaluation.max_copied_words
    )
    usage = result.usage
    return {
        **verdict_scores(verdict),
        **checks,
        "cost_usd": (usage.cost_usd if usage else 0.0) + judge_usage.cost_usd,
        "latency_s": usage.latency_s if usage else 0.0,
    }


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
    embed = load_embedder_for(cfg.embedding)
    detector = build_detector(cfg.language_gate)
    gate_runs = run_gate(questions, detector, cfg.language_gate)
    retrieval_runs = run_retrieval(questions, index, embed, cfg)
    generation_runs = (
        []
        if llm is None
        else run_generation(questions, Resources(index, embed, detector, llm), cfg)
    )
    metrics = {
        "retrieval": aggregate((r.question.category, r.metrics) for r in retrieval_runs),
        "generation": aggregate(
            (r.question.category, r.metrics) for r in generation_runs if r.metrics
        ),
        "gate": {"all": score_gate(gate_runs)},
    }
    retrieved_ids = {r.question.id for r in retrieval_runs}
    skipped: dict[str, int] = dict(
        Counter(q.category for q in questions if q.id not in retrieved_ids)
    )
    cost = run_cost(generation_runs)
    meta = {
        "run_format": RUN_FORMAT,
        "homerag_version": version("homerag"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "retrieval_only": llm is None,
        "document_fingerprint": fingerprint(cfg.document),
        "golden": str(golden_path),
        "golden_fingerprint": fingerprint(golden_path),
        "index_folder": str(index_report.folder),
        "index_chunks": len(index.chunks),
        "multi_section_chunk_share": _multi_section_share(index),
        "retrieval_skipped": skipped,
        "cost_usd": cost,
        "seconds": round(time.perf_counter() - start, 1),
    }
    folder = runs_root / f"{started_at:%Y%m%d-%H%M%S}-{cfg.name}"
    rows = result_rows(questions, gate_runs, retrieval_runs, generation_runs)
    save_run(folder, cfg, rows, metrics, meta)
    gate_errors = [run.question.id for run in gate_runs if not run.correct]
    return RunReport(folder, metrics, gate_errors, skipped, cost)


def run_cost(runs: list[GenerationRun]) -> dict[str, float]:
    """Total cost of the answers and of the judge, and how much of it was paid in this run."""
    usages = [(r.answer.usage, "answers") for r in runs] + [(r.judge_usage, "judge") for r in runs]
    cost = {"answers": 0.0, "judge": 0.0, "paid_now": 0.0}
    for usage, part in usages:
        if usage is not None:
            cost[part] += usage.cost_usd
            cost["paid_now"] += 0.0 if usage.cached else usage.cost_usd
    return {part: round(value, 4) for part, value in cost.items()}


def result_rows(
    questions: list[GoldenQuestion],
    gate_runs: list[GateRun],
    retrieval_runs: list[QuestionRun],
    generation_runs: list[GenerationRun],
) -> list[dict[str, Any]]:
    """One JSON-ready row per golden question, with whichever parts ran for it."""
    gate = {r.question.id: r for r in gate_runs}
    retrieval = {r.question.id: r for r in retrieval_runs}
    generation = {r.question.id: r for r in generation_runs}
    return [
        {
            "id": q.id,
            "category": q.category,
            "question": q.question,
            "gate": {"passed": gate[q.id].passed, "correct": gate[q.id].correct},
            "retrieval": _retrieval_row(retrieval[q.id]) if q.id in retrieval else None,
            "generation": _generation_row(generation[q.id]) if q.id in generation else None,
        }
        for q in questions
    ]


def _retrieval_row(run: QuestionRun) -> dict[str, Any]:
    return {
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


def _generation_row(run: GenerationRun) -> dict[str, Any]:
    result = run.answer
    return {
        "blocked_by_gate": result.blocked_by_gate,
        "answer": result.text,
        "citations": [
            {"source": c.source, "chunk_id": c.chunk_id, "section_id": c.section_id}
            for c in result.citations
        ],
        "usage": asdict(result.usage) if result.usage else None,
        "verdict": run.verdict.model_dump() if run.verdict else None,
        "judge_usage": asdict(run.judge_usage) if run.judge_usage else None,
        "metrics": run.metrics,
    }


def _multi_section_share(index: VectorIndex) -> float:
    # ADR 0005: "at least one cited section" is lenient with chunks covering several.
    if not index.chunks:
        return 0.0
    return round(sum(len(c.sections) > 1 for c in index.chunks) / len(index.chunks), 3)

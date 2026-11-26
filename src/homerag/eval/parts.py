"""The parts of an experiment run, each scored on its own over the golden set.

A change to one part never moves the numbers of another:
- language gate: every question (`run_gate`, `score_gate`);
- retrieval: the questions that cite sections (`run_retrieval`);
- generation: every question meant to pass the gate (all but `non_english`) is answered by
  `qa.answer`, graded by the judge (`eval/judge.py`) and by code-based checks
  (`answer_checks`), with cost and latency (`run_generation`).
Follow-ups are retrieved and answered as written, without the earlier question.
"""

from dataclasses import dataclass

from homerag.config import ExperimentConfig, LanguageGateConfig
from homerag.embedding import Embed
from homerag.eval.dataset import ENGLISH, GoldenQuestion
from homerag.eval.judge import Verdict, judge, verdict_scores
from homerag.eval.metrics import answer_checks, gate_metrics, retrieval_metrics
from homerag.index import VectorIndex
from homerag.language import Detector, is_english
from homerag.models import Answer, RetrievedChunk, Usage
from homerag.qa import Resources, answer, source_numbers
from homerag.retrieval import RETRIEVERS


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

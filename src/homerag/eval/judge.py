"""LLM-as-judge: a stronger model grades each generated answer against the golden set.

One call per answer (prompt `judge_v1`) returns a `Verdict` through structured outputs, so
the JSON always matches the schema:
- `reasoning` first: the judge compares and checks before it grades;
- `correctness` against the hand-written reference answer: correct / partial / incorrect;
- `faithful`: every claim is supported by the sources the generator received;
- `declined`: the answer says the book does not cover the question. Right on `out_of_scope`,
  a false refusal anywhere else.
Judgements go through the cached LLM, so a repeated run is not paid again.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from homerag.config import JudgeConfig
from homerag.eval.dataset import GoldenQuestion
from homerag.llm import LLM, LLMRequest, load_prompt
from homerag.models import Answer, Usage
from homerag.qa import format_sources

CORRECTNESS_SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


class Verdict(BaseModel):
    """The judge's output. Field order matters: the model writes `reasoning` first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reasoning: str
    correctness: Literal["correct", "partial", "incorrect"]
    faithful: bool
    declined: bool


def judge_request(question: GoldenQuestion, result: Answer, cfg: JudgeConfig) -> LLMRequest:
    """The judge call for one answer: question, reference, sources, answer."""
    user = (
        f"<question>\n{question.question}\n</question>\n\n"
        f"<reference_answer>\n{question.reference_answer}\n</reference_answer>\n\n"
        f"{format_sources(list(result.retrieved))}\n\n"
        f"<answer>\n{result.text}\n</answer>"
    )
    return LLMRequest(
        model=cfg.model,
        effort=cfg.effort,
        max_tokens=cfg.max_tokens,
        system=load_prompt(cfg.prompt),
        user=user,
        output_schema=Verdict.model_json_schema(),
    )


def judge(
    question: GoldenQuestion, result: Answer, llm: LLM, cfg: JudgeConfig
) -> tuple[Verdict, Usage]:
    """Grade one answer; fails with the question id if the judge gives no usable verdict."""
    completion = llm(judge_request(question, result, cfg))
    if completion.stop_reason != "end_turn":
        raise ValueError(f"{question.id}: judge stopped with '{completion.stop_reason}'")
    try:
        return Verdict.model_validate_json(completion.text), completion.usage
    except ValidationError as error:
        raise ValueError(f"{question.id}: judge output is not a valid verdict\n{error}") from error


def verdict_scores(verdict: Verdict) -> dict[str, float]:
    """The verdict as numbers, so it can be averaged per category."""
    return {
        "correct": CORRECTNESS_SCORES[verdict.correctness],
        "faithful": float(verdict.faithful),
        "declined": float(verdict.declined),
    }

"""Real calls to the Claude API (a few cents): check the request shapes against the installed
SDK and the account. Skipped when no API key is configured."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from homerag.config import load_experiment, load_settings
from homerag.eval.dataset import GoldenQuestion
from homerag.eval.judge import judge
from homerag.llm import LLM, LLMRequest, anthropic_llm
from homerag.models import Answer, Chunk, RetrievedChunk, SectionRef


@pytest.fixture(scope="module")
def llm() -> LLM:
    try:
        settings = load_settings()
    except ValidationError:
        pytest.skip("ANTHROPIC_API_KEY is not set")
    return anthropic_llm(settings.anthropic_api_key)


def test_a_real_call_returns_text_and_usage(llm: LLM) -> None:
    completion = llm(
        LLMRequest(
            "claude-sonnet-5-5",
            "low",
            1024,
            "Answer with one word.",
            "Which sport combines swimming, cycling and running?",
        )
    )

    assert completion.stop_reason == "end_turn"
    assert "triathlon" in completion.text.lower()
    assert completion.usage.input_tokens > 0
    assert completion.usage.cost_usd > 0
    assert completion.usage.latency_s > 0


def test_the_real_judge_returns_a_valid_verdict(llm: LLM) -> None:
    cfg = load_experiment(Path("configs/experiments/baseline.yaml")).judge
    question = GoldenQuestion.model_validate(
        {
            "id": "q-001",
            "question": "How many sports make up a triathlon?",
            "category": "factual",
            "reference_answer": "Three: swimming, cycling and running.",
            "relevant_section_ids": ["intro"],
        }
    )
    chunk = Chunk(
        "intro#1",
        (SectionRef("intro", ("Intro",)),),
        "A triathlon is a race made of three sports done in a row: swim, bike and run.",
        "1",
    )
    result = Answer(
        question.question,
        "Three sports: swimming, cycling and running [1].",
        retrieved=(RetrievedChunk(chunk, 0.9, 1),),
    )

    verdict, usage = judge(question, result, llm, cfg)

    assert verdict.correctness == "correct"
    assert verdict.faithful
    assert not verdict.declined
    assert usage.model.startswith("claude-opus")

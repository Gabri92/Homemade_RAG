from pathlib import Path

import pytest

from homerag.llm import Completion, LLMRequest, cached, cost_usd, load_prompt
from homerag.models import Usage

REQUEST = LLMRequest("claude-sonnet-5-5", "low", 4096, "system rules", "question one")


class FakeLLM:
    """Counts calls and answers with the user message, so each request is recognisable."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request: LLMRequest) -> Completion:
        self.calls += 1
        return Completion(
            f"answer to {request.user}", "end_turn", Usage(request.model, 10, 5, 0.01)
        )


def test_cost_uses_the_price_per_million_tokens() -> None:
    # Sonnet 5.5: $2 in, $10 out per million tokens.
    assert cost_usd("claude-sonnet-5-5", 1_000_000, 100_000) == pytest.approx(3.0)


def test_cost_of_a_model_without_a_price_is_zero() -> None:
    assert cost_usd("model-without-price", 1000, 1000) == 0.0


def test_cache_pays_a_request_once_and_marks_the_repeat(tmp_path: Path) -> None:
    fake = FakeLLM()
    llm = cached(fake, tmp_path)

    first = llm(REQUEST)
    second = llm(REQUEST)

    assert fake.calls == 1
    assert (first.text, first.usage.cached) == ("answer to question one", False)
    assert (second.text, second.usage.cached) == ("answer to question one", True)
    assert second.usage.cost_usd == first.usage.cost_usd


def test_cache_key_covers_the_whole_request(tmp_path: Path) -> None:
    fake = FakeLLM()
    llm = cached(fake, tmp_path)

    llm(REQUEST)
    llm(LLMRequest("claude-sonnet-5-5", "medium", 4096, "system rules", "question one"))
    llm(LLMRequest("claude-sonnet-5-5", "low", 4096, "system rules v2", "question one"))

    assert fake.calls == 3
    assert not list(tmp_path.glob("*.tmp"))


def test_answer_prompt_v1_exists_and_asks_for_numbered_citations() -> None:
    assert "[2]" in load_prompt("answer_v1")


def test_unknown_prompt_fails_with_a_clear_message() -> None:
    with pytest.raises(ValueError, match="unknown prompt 'answer_v99'"):
        load_prompt("answer_v99")

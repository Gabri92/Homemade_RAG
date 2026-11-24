"""One real call to the Claude API (about a cent): checks the request shape against the
installed SDK and the account. Skipped when no API key is configured."""

import pytest
from pydantic import ValidationError

from homerag.config import load_settings
from homerag.llm import LLMRequest, anthropic_llm


def test_a_real_call_returns_text_and_usage() -> None:
    try:
        settings = load_settings()
    except ValidationError:
        pytest.skip("ANTHROPIC_API_KEY is not set")
    llm = anthropic_llm(settings.anthropic_api_key)

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

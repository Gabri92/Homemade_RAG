"""The single access point to the Anthropic API: the only module that imports `anthropic`.

An `LLM` is a function from an `LLMRequest` to a `Completion`. `anthropic_llm` builds the real
one; `cached` wraps any LLM with an on-disk cache; tests pass a fake function instead.
- Retries: the SDK retries connection errors, 429 and 5xx with backoff.
- Reproducibility: the API no longer accepts `temperature`, so a repeated request is served
  from the cache (key = the whole request) and is never paid twice.
- Cost and latency: tokens from the response times `PRICES`, and the call's duration; both
  are kept in the cache, so a cached answer still reports what it cost when it was made.
- Structured outputs: with `output_schema`, the API guarantees the text is JSON valid
  against that schema (used by the judge).
- Refusals: on the models that support it, a declined request is re-run server-side on a
  fallback model (`fallbacks: "default"`); `Usage.model` records which model answered.
"""

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import anthropic
from anthropic.types.beta import BetaOutputConfigParam
from pydantic import SecretStr

from homerag.config import Effort
from homerag.models import Usage

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
CACHE_ROOT = Path("data/cache/llm")

# USD per million tokens (input, output), first-party API rates as of 2026-11-24. A provider
# fact, not an experiment parameter, so it lives here. Update when prices change.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-5-5": (4.00, 20.00),
}

# Models that accept server-side refusal fallbacks (Haiku 5.5 does not).
_FALLBACK_MODELS = frozenset({"claude-sonnet-5-5", "claude-opus-5-5"})
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """One single-turn call: everything that determines the answer, and so the cache key."""

    model: str
    effort: Effort
    max_tokens: int
    system: str
    user: str
    # A JSON schema the answer must follow (structured outputs), or None for free text.
    output_schema: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class Completion:
    """The model's text, why it stopped (`end_turn`, `max_tokens`, `refusal`, ...) and usage."""

    text: str
    stop_reason: str
    usage: Usage


LLM = Callable[[LLMRequest], Completion]


def load_prompt(name: str) -> str:
    """The text of `prompts/<name>.md`. Prompts are versioned files, never edited after use."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise ValueError(f"unknown prompt '{name}': no file {path}")
    return path.read_text(encoding="utf-8").strip()


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """What the tokens cost at `PRICES`; 0 with a warning for a model without a price."""
    if model not in PRICES:
        logger.warning("no price for model %s: cost counted as 0", model)
        return 0.0
    price_in, price_out = PRICES[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def anthropic_llm(api_key: SecretStr) -> LLM:
    """The real LLM. Building it makes no call; each request is one Messages API call."""
    client = anthropic.Anthropic(api_key=api_key.get_secret_value())

    def complete(request: LLMRequest) -> Completion:
        fallback = request.model in _FALLBACK_MODELS
        output_config: BetaOutputConfigParam = {"effort": request.effort}
        if request.output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": request.output_schema}
        start = time.perf_counter()
        response = client.beta.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.user}],
            output_config=output_config,
            betas=[_FALLBACK_BETA] if fallback else anthropic.omit,
            fallbacks="default" if fallback else anthropic.omit,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = _usage(
            response.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            time.perf_counter() - start,
        )
        return Completion(text, response.stop_reason or "", usage)

    return complete


def _usage(model: str, tokens_in: int, tokens_out: int, seconds: float) -> Usage:
    """What one call used and cost, logged.

    With a fallback, the totals are priced at the model that answered: close enough for a
    rare event, and the answering model is recorded.
    """
    usage = Usage(
        model, tokens_in, tokens_out, cost_usd(model, tokens_in, tokens_out), round(seconds, 2)
    )
    logger.info(
        "llm %s: %d in, %d out, $%.4f, %.1f s",
        model,
        tokens_in,
        tokens_out,
        usage.cost_usd,
        usage.latency_s,
    )
    return usage


def cached(llm: LLM, cache_dir: Path = CACHE_ROOT) -> LLM:
    """Wrap `llm` with an on-disk cache: one JSON file per request. A hit is marked `cached`.

    The file is written under a temporary name and then renamed, so an interrupted run never
    leaves a half-written answer.
    """

    def complete_with_cache(request: LLMRequest) -> Completion:
        path = cache_dir / f"{_request_key(request)}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return Completion(
                data["text"], data["stop_reason"], Usage(**data["usage"], cached=True)
            )
        completion = llm(request)
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "text": completion.text,
            "stop_reason": completion.stop_reason,
            "usage": {k: v for k, v in asdict(completion.usage).items() if k != "cached"},
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
        return completion

    return complete_with_cache


def _request_key(request: LLMRequest) -> str:
    payload = json.dumps(asdict(request), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

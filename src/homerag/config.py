"""Settings (.env) and experiment configs (YAML), both validated with pydantic.

Settings hold secrets and machine-specific values. An experiment config holds every parameter
that can change between experiments: nothing of the kind is hard-coded elsewhere.
"""

from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    """Secrets and machine-specific settings. Experiment parameters live in YAML configs."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr


def load_settings() -> Settings:
    """Load settings, failing fast with a clear error if a required value is missing."""
    return Settings()


class _Section(BaseModel):
    # Frozen: a config never changes during a run. Forbid: a typo ("top_kk") fails the run
    # instead of being silently ignored.
    model_config = ConfigDict(frozen=True, extra="forbid")


class LanguageGateConfig(_Section):
    # ISO 639-1 codes the detector chooses among; a small set makes detection more accurate.
    languages: tuple[str, ...] = Field(min_length=2)
    # Messages with fewer words are let through: detection on very short text is unreliable.
    min_words: int = Field(gt=0)
    # A message is blocked only if a non-English language reaches this confidence.
    min_confidence: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _english_among_unique_codes(self) -> Self:
        if "en" not in self.languages or len(set(self.languages)) != len(self.languages):
            raise ValueError("languages must include 'en' and have no repeats")
        return self


class ChunkingConfig(_Section):
    strategy: Literal["fixed"]
    size_tokens: int = Field(gt=0)
    overlap_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _overlap_smaller_than_size(self) -> Self:
        if self.overlap_tokens >= self.size_tokens:
            raise ValueError("overlap_tokens must be smaller than size_tokens")
        return self


class EmbeddingConfig(_Section):
    strategy: Literal["local"]
    model: str
    device: Literal["auto", "cuda", "cpu"] = "auto"
    batch_size: int = Field(default=16, gt=0)


class RetrievalConfig(_Section):
    strategy: Literal["dense"]
    top_k: int = Field(gt=0)


class GenerationConfig(_Section):
    model: str
    effort: Effort
    max_tokens: int = Field(gt=0)
    prompt: str


class JudgeConfig(_Section):
    model: str
    effort: Effort
    prompt: str


class EvaluationConfig(_Section):
    # Cut-offs for hit rate and recall: all computed from the same top_k ranking.
    ks: tuple[int, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sorted_positive_unique(self) -> Self:
        if any(k <= 0 for k in self.ks) or list(self.ks) != sorted(set(self.ks)):
            raise ValueError("ks must be positive, increasing and without repeats")
        return self


class ExperimentConfig(_Section):
    """One experiment: which document, the language gate, how to chunk, embed, retrieve,
    generate, judge."""

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    document: Path
    language_gate: LanguageGateConfig
    chunking: ChunkingConfig
    embedding: EmbeddingConfig
    retrieval: RetrievalConfig
    generation: GenerationConfig
    judge: JudgeConfig
    evaluation: EvaluationConfig

    @model_validator(mode="after")
    def _ks_within_top_k(self) -> Self:
        if self.evaluation.ks[-1] > self.retrieval.top_k:
            raise ValueError(
                f"evaluation.ks goes up to {self.evaluation.ks[-1]}, "
                f"but retrieval.top_k is {self.retrieval.top_k}"
            )
        return self


def load_experiment(path: Path) -> ExperimentConfig:
    """Read and validate an experiment YAML; any error names the file and the bad field."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping at the top level")
    try:
        return ExperimentConfig.model_validate(data)
    except ValidationError as error:
        raise ValueError(f"{path}: invalid experiment config\n{error}") from error

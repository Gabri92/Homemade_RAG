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


class ExperimentConfig(_Section):
    """One experiment: which document, and how to chunk, embed, retrieve, generate, judge."""

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    document: Path
    chunking: ChunkingConfig
    embedding: EmbeddingConfig
    retrieval: RetrievalConfig
    generation: GenerationConfig
    judge: JudgeConfig


def load_experiment(path: Path) -> ExperimentConfig:
    """Read and validate an experiment YAML; any error names the file and the bad field."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping at the top level")
    try:
        return ExperimentConfig.model_validate(data)
    except ValidationError as error:
        raise ValueError(f"{path}: invalid experiment config\n{error}") from error

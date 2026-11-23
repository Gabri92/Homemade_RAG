from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from homerag.config import Settings, load_experiment


def test_reads_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.anthropic_api_key.get_secret_value() == "test-key"


def test_missing_api_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="anthropic_api_key"):
        Settings(_env_file=None)  # type: ignore[call-arg]


# --- experiment configs ------------------------------------------------------------

BASELINE = Path("configs/experiments/baseline.yaml")


def write_config(tmp_path: Path, **changes: dict[str, object]) -> Path:
    data = yaml.safe_load(BASELINE.read_text(encoding="utf-8"))
    for section, values in changes.items():
        data[section] = {**data[section], **values}
    path = tmp_path / "exp.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_baseline_config_is_valid() -> None:
    cfg = load_experiment(BASELINE)

    assert cfg.name == "baseline"
    assert cfg.chunking.overlap_tokens < cfg.chunking.size_tokens


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    path = write_config(tmp_path, retrieval={"top_kk": 3})

    with pytest.raises(ValueError, match=r"exp\.yaml(.|\n)*top_kk"):
        load_experiment(path)


def test_unknown_strategy_is_rejected(tmp_path: Path) -> None:
    path = write_config(tmp_path, chunking={"strategy": "magic"})

    with pytest.raises(ValueError, match="strategy"):
        load_experiment(path)


def test_overlap_must_be_smaller_than_size(tmp_path: Path) -> None:
    path = write_config(tmp_path, chunking={"size_tokens": 50, "overlap_tokens": 50})

    with pytest.raises(ValueError, match="overlap_tokens"):
        load_experiment(path)


def test_config_cannot_change_during_a_run() -> None:
    cfg = load_experiment(BASELINE)

    with pytest.raises(ValidationError, match="frozen"):
        cfg.retrieval.top_k = 10  # type: ignore[misc]


def test_top_level_must_be_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        load_experiment(path)


def test_evaluation_ks_must_be_increasing(tmp_path: Path) -> None:
    path = write_config(tmp_path, evaluation={"ks": [3, 1]})

    with pytest.raises(ValueError, match="increasing"):
        load_experiment(path)


def test_evaluation_ks_cannot_exceed_top_k(tmp_path: Path) -> None:
    path = write_config(tmp_path, evaluation={"ks": [1, 10]})

    with pytest.raises(ValueError, match="top_k"):
        load_experiment(path)

import pytest
from pydantic import ValidationError

from tricoach.config import Settings


def test_reads_api_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.anthropic_api_key.get_secret_value() == "test-key"


def test_missing_api_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="anthropic_api_key"):
        Settings(_env_file=None)  # type: ignore[call-arg]

import logging
from pathlib import Path

import numpy as np
import pytest

from homerag.embedding import Vectors, cached, resolve_device


def test_explicit_device_is_kept_without_probing() -> None:
    def must_not_probe() -> bool:
        raise AssertionError("explicit devices must not probe the GPU")

    assert resolve_device("cpu", must_not_probe) == "cpu"
    assert resolve_device("cuda", must_not_probe) == "cuda"


def test_auto_uses_cuda_when_the_probe_succeeds() -> None:
    assert resolve_device("auto", lambda: True) == "cuda"


def test_auto_falls_back_to_cpu_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assert resolve_device("auto", lambda: False) == "cpu"

    assert "falling back to cpu" in caplog.text


# --- on-disk cache -------------------------------------------------------------------


def fake_embed(texts: list[str]) -> Vectors:
    """One distinct, deterministic vector per text length: enough to compare cache reads."""
    return np.array([[float(len(t)), 1.0] for t in texts], dtype=np.float32)


class CountingEmbed:
    """Wraps fake_embed and records which texts were actually computed."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, texts: list[str]) -> Vectors:
        self.seen.extend(texts)
        return fake_embed(texts)


def test_cache_computes_only_new_texts(tmp_path: Path) -> None:
    counting = CountingEmbed()
    embed = cached(counting, "model-a", tmp_path)

    first = embed(["alpha beta", "gamma"])
    second = embed(["gamma", "delta"])

    assert counting.seen == ["alpha beta", "gamma", "delta"]
    assert np.allclose(first[1], second[0])


def test_cache_keeps_models_apart(tmp_path: Path) -> None:
    counting = CountingEmbed()

    cached(counting, "model-a", tmp_path)(["same text"])
    cached(counting, "model-b", tmp_path)(["same text"])

    assert counting.seen == ["same text", "same text"]

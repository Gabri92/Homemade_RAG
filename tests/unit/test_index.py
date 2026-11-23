import logging

import pytest

from tricoach.index import resolve_device


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

"""Tests with real models or APIs: every test in this folder is marked `integration`, so the
default run (`addopts = -m 'not integration'`) skips them. Run them with `pytest -m integration`.
"""

from pathlib import Path

import pytest

_HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if _HERE in item.path.parents:
            item.add_marker(pytest.mark.integration)

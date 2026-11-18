"""Generalization tests on other publishers' ePubs: every test in this folder is marked
`corpus`; a book missing from data/corpus/ is skipped (they are never committed).
"""

from pathlib import Path

import pytest

from tests.corpus import expectations as expected

_HERE = Path(__file__).parent


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if _HERE in item.path.parents:
            item.add_marker(pytest.mark.corpus)


@pytest.fixture(params=sorted(expected.INCLUDED_SECTIONS))
def corpus_book(request: pytest.FixtureRequest) -> tuple[str, Path]:
    """(key, path) of one corpus ePub; skipped when it has not been downloaded."""
    key: str = request.param
    found = sorted((expected.CORPUS_DIR / key).glob("*.epub"))
    if not found:
        pytest.skip(f"{key} not in data/corpus/{key}/")
    return key, found[0]

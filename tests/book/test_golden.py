"""The golden set cites only sections that the current ingestion produces and indexes.

Runs with the full suite (and so before every commit): an ingestion change that renames or
drops a cited section fails here instead of silently orphaning a golden-set reference.
"""

from pathlib import Path

import pytest

from tricoach.eval.dataset import check_references, load_golden
from tricoach.models import Book

GOLDEN = Path(__file__).parents[2] / "eval" / "datasets" / "golden.jsonl"


@pytest.mark.skipif(not GOLDEN.exists(), reason="eval/datasets/golden.jsonl not written yet")
def test_golden_set_references_exist_in_the_book(book: Book) -> None:
    assert check_references(load_golden(GOLDEN), book) == []

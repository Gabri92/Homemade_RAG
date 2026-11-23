import pytest

from homerag.models import Block


def test_heading_requires_level() -> None:
    with pytest.raises(ValueError, match="level"):
        Block("heading", "Base Period", "ch01.xhtml")


def test_non_heading_rejects_level() -> None:
    with pytest.raises(ValueError, match="level"):
        Block("paragraph", "Some text.", "ch01.xhtml", level=2)

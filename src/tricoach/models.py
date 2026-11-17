"""Core data types shared across the pipeline. Imports nothing else from the project."""

from dataclasses import dataclass
from typing import Literal

BlockKind = Literal["heading", "paragraph", "list_item", "table", "figure"]


@dataclass(frozen=True, slots=True)
class Block:
    """One unit of book content, independent of the source file format (ePub, PDF, ...).

    `text` is plain text; tables are Markdown (preceded by their title, if any);
    figures carry only their caption, which may be empty. `level` is set only for
    headings (1 = highest). `source` is a free-form location used for debugging only.
    """

    kind: BlockKind
    text: str
    source: str
    level: int | None = None

    def __post_init__(self) -> None:
        if (self.kind == "heading") != (self.level is not None):
            raise ValueError(f"level must be set for headings only, got {self.kind=} {self.level=}")

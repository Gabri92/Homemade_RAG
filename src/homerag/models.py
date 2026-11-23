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
    `role` says which part of the book the block belongs to: "body" for the main
    content, otherwise a landmark type such as "glossary", "index", "acknowledgments".
    `page` is the printed-page label where the block starts ("224", "xii"), if known.
    """

    kind: BlockKind
    text: str
    source: str
    level: int | None = None
    role: str = "body"
    page: str | None = None

    def __post_init__(self) -> None:
        if (self.kind == "heading") != (self.level is not None):
            raise ValueError(f"level must be set for headings only, got {self.kind=} {self.level=}")


@dataclass(frozen=True, slots=True)
class Section:
    """A heading and the content up to the next heading: the unit for chunking and citations.

    `id` is stable across runs (built from the title path, not from positions): the
    golden set refers to it. `path` holds the titles from the top level down to this
    section. `include` says whether the section goes into the search index.
    """

    id: str
    title: str
    level: int
    path: tuple[str, ...]
    role: str
    include: bool
    blocks: tuple[Block, ...]
    first_page: str | None = None
    last_page: str | None = None


@dataclass(frozen=True, slots=True)
class Book:
    """Structured book: the hand-off between ingestion and everything downstream."""

    source: str
    sections: tuple[Section, ...]

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


@dataclass(frozen=True, slots=True)
class SectionRef:
    """The part of a section a chunk needs: its id (for the golden set) and title path (for
    citations)."""

    id: str
    path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Chunk:
    """A piece of the document: the unit that is embedded, retrieved and cited.

    `sections` are the sections the chunk covers, in reading order: one for most chunks,
    more when a strategy cuts across section boundaries (ADR 0005). `id` is
    `<first section id>#<n>`, unique in a document because section ids are unique and never
    contain "#". `page` is the printed page where the chunk starts, if known.
    """

    id: str
    sections: tuple[SectionRef, ...]
    text: str
    page: str | None = None

    def __post_init__(self) -> None:
        if not self.sections:
            raise ValueError(f"chunk {self.id!r} covers no section")
        prefix = f"{self.sections[0].id}#"
        if not self.id.startswith(prefix):
            raise ValueError(f"chunk id {self.id!r} must start with {prefix!r}")
        if not self.text.strip():
            raise ValueError(f"chunk {self.id!r} has no text")


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk as returned by a retriever: `rank` starts at 1, higher `score` is better."""

    chunk: Chunk
    score: float
    rank: int


@dataclass(frozen=True, slots=True)
class Citation:
    """Where a claim comes from, built from the chunk's metadata, never from model text.

    `source` is the number the answer uses for it ("[2]"): the chunk's position in the
    context. A chunk covering several sections gives one citation per section (ADR 0005).
    """

    source: int
    chunk_id: str
    section_id: str
    section_path: tuple[str, ...]
    page: str | None = None


@dataclass(frozen=True, slots=True)
class Usage:
    """What one LLM call used and cost. `model` is the model that answered: with refusal
    fallbacks it may differ from the one requested. `cached` means it came from the on-disk
    cache, so nothing was paid this time; `cost_usd` is still what the call cost when made."""

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cached: bool = False


@dataclass(frozen=True, slots=True)
class Answer:
    """Everything one question produced: what the reader sees and what the eval scores.

    `blocked_by_gate` is True when the language gate stopped the question: then `retrieved`
    and `citations` are empty and `text` is the notice.
    """

    question: str
    text: str
    citations: tuple[Citation, ...] = ()
    retrieved: tuple[RetrievedChunk, ...] = ()
    blocked_by_gate: bool = False
    usage: Usage | None = None

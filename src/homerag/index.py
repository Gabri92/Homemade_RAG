"""The vector index: the chunks of one document and their vectors, saved per document.

`build_index`, `save_index`, `load_index`, `ensure_index`: chunks + vectors, saved per
document and per index key, refused when built from another book.json. The vectors come
from `embedding.py`. BM25 arrives with experiment 5.3.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any  # JSON metadata and chunks: values of mixed types, checked when read

import numpy as np

from homerag.chunking import CHUNKERS, TokenSpans
from homerag.config import EmbeddingConfig, ExperimentConfig
from homerag.embedding import CACHE_ROOT, Embed, Vectors, load_embedder_for, token_spans_for
from homerag.ingest import load_book
from homerag.models import Book, Chunk, SectionRef

logger = logging.getLogger(__name__)

# --- the index ------------------------------------------------------------------------

# Bump whenever the files of an index change shape: old indexes must be rebuilt.
SCHEMA_VERSION = 1
INDEX_ROOT = Path("data/index")


@dataclass(frozen=True, slots=True)
class VectorIndex:
    """The chunks of one document and their vectors: row i of `vectors` is `chunks[i]`."""

    chunks: tuple[Chunk, ...]
    vectors: Vectors


class StaleIndexError(ValueError):
    """The index on disk is missing or does not match the current document or format."""


def build_index(book: Book, cfg: ExperimentConfig, embed: Embed, spans: TokenSpans) -> VectorIndex:
    """Chunk the book with the configured strategy and embed every chunk."""
    chunks = CHUNKERS[cfg.chunking.strategy](book, cfg.chunking, spans)
    return VectorIndex(tuple(chunks), embed([chunk.text for chunk in chunks]))


def index_key(cfg: ExperimentConfig) -> str:
    """Name of the index folder: the strategy plus a hash of what changes the vectors.

    Only chunking and the embedding model count. Retrieval, generation and judge settings
    reuse the same index; device and batch size change speed, not the vectors.
    """
    relevant = {
        "chunking": cfg.chunking.model_dump(),
        "embedding": {"strategy": cfg.embedding.strategy, "model": cfg.embedding.model},
    }
    digest = hashlib.sha256(json.dumps(relevant, sort_keys=True).encode("utf-8"))
    return f"{cfg.chunking.strategy}-{digest.hexdigest()[:8]}"


def index_dir(book: Book, cfg: ExperimentConfig, root: Path = INDEX_ROOT) -> Path:
    """`<root>/<document>/<index key>`: one folder per document and per index key."""
    return root / _slug(Path(book.source).stem) / index_key(cfg)


def fingerprint(path: Path) -> str:
    """Hash of a file's bytes: changes whenever the document is re-ingested differently."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_index(index: VectorIndex, folder: Path, meta: dict[str, Any]) -> None:
    """Write vectors.npy, chunks.json and meta.json (format version + the caller's metadata)."""
    folder.mkdir(parents=True, exist_ok=True)
    np.save(folder / "vectors.npy", index.vectors)
    chunks = [asdict(chunk) for chunk in index.chunks]
    (folder / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    full_meta = {"schema_version": SCHEMA_VERSION, "homerag_version": version("homerag"), **meta}
    (folder / "meta.json").write_text(json.dumps(full_meta, indent=1), encoding="utf-8")


def load_index(folder: Path, document_fingerprint: str) -> VectorIndex:
    """Load an index, refusing one built in another format or from another book.json."""
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        raise StaleIndexError(f"{folder}: no index here. Build it with `homerag index`.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("schema_version") != SCHEMA_VERSION:
        raise StaleIndexError(f"{folder}: index format changed. Rebuild it with `homerag index`.")
    if meta.get("document_fingerprint") != document_fingerprint:
        raise StaleIndexError(
            f"{folder}: built from a different book.json. Rebuild it with `homerag index`."
        )
    data = json.loads((folder / "chunks.json").read_text(encoding="utf-8"))
    return VectorIndex(tuple(_chunk(item) for item in data), np.load(folder / "vectors.npy"))


def _chunk(item: dict[str, Any]) -> Chunk:
    # JSON has lists where the dataclasses have tuples.
    sections = tuple(SectionRef(s["id"], tuple(s["path"])) for s in item["sections"])
    return Chunk(item["id"], sections, item["text"], item["page"])


@dataclass(frozen=True, slots=True)
class IndexReport:
    """What `ensure_index` did, for the CLI to print."""

    folder: Path
    chunks: int
    built: bool
    seconds: float


def ensure_index(
    cfg: ExperimentConfig,
    root: Path = INDEX_ROOT,
    cache_dir: Path = CACHE_ROOT,
    load_embedder: Callable[[EmbeddingConfig], Embed] | None = None,
    spans: TokenSpans | None = None,
) -> IndexReport:
    """Reuse the index for this document and config if it is up to date, else build it.

    `load_embedder` and `spans` default to the configured model; tests pass fakes.
    """
    book = load_book(cfg.document)
    folder = index_dir(book, cfg, root)
    document_fingerprint = fingerprint(cfg.document)
    try:
        existing = load_index(folder, document_fingerprint)
        return IndexReport(folder, len(existing.chunks), built=False, seconds=0.0)
    except StaleIndexError as reason:
        logger.info("building index: %s", reason)
    start = time.perf_counter()
    embed = load_embedder_for(cfg.embedding, cache_dir, load_embedder)
    index = build_index(book, cfg, embed, spans or token_spans_for(cfg.embedding.model))
    seconds = time.perf_counter() - start
    meta = {
        "document": str(cfg.document),
        "document_fingerprint": document_fingerprint,
        "config": json.loads(cfg.model_dump_json(include={"chunking", "embedding"})),
        "chunks": len(index.chunks),
        "dimensions": int(index.vectors.shape[1]) if index.chunks else 0,
        "seconds": round(seconds, 1),
    }
    save_index(index, folder, meta)
    return IndexReport(folder, len(index.chunks), built=True, seconds=seconds)


def open_index(cfg: ExperimentConfig, root: Path = INDEX_ROOT) -> VectorIndex:
    """The up-to-date index for this document and config; StaleIndexError if there is none."""
    return load_index(index_dir(load_book(cfg.document), cfg, root), fingerprint(cfg.document))


def _slug(text: str) -> str:
    words = "".join(c if c.isalnum() else " " for c in text.lower()).split()
    return "-".join(words) or "document"

"""Embeddings and the vector index.

The pieces, in the order the pipeline uses them:
- `resolve_device`, `token_spans_for`: where the model runs, and its tokenizer for the chunker;
- `EMBEDDERS`: loaders that return an `Embed` function (texts -> normalized vectors), keeping
  the loaded model in a closure; `cached` wraps any of them with an on-disk cache;
- `build_index`, `save_index`, `load_index`, `ensure_index`: chunks + vectors, saved per
  document and per index key, refused when built from another book.json.

The only module, with `retrieval.py`, that imports `sentence_transformers`, `transformers`
and `torch`. BM25 arrives with experiment 5.3.
"""

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from homerag.chunking import CHUNKERS, TokenSpans
from homerag.config import EmbeddingConfig, ExperimentConfig
from homerag.ingest import load_book
from homerag.models import Book, Chunk, SectionRef

logger = logging.getLogger(__name__)

Device = Literal["cuda", "cpu"]


def resolve_device(
    requested: Literal["auto", "cuda", "cpu"], cuda_works: Callable[[], bool] | None = None
) -> Device:
    """Turn the config's `device` into a real one.

    "auto" picks cuda only if a test computation on the GPU succeeds: torch can report CUDA
    as available and still fail on the first operation (e.g. with an outdated driver).
    `cuda_works` is a parameter so tests do not need a GPU.
    """
    if requested != "auto":
        return requested
    if (cuda_works or _cuda_works)():
        return "cuda"
    logger.warning("device auto: CUDA is not usable, falling back to cpu (much slower)")
    return "cpu"


def _cuda_works() -> bool:
    # Imported here: torch takes seconds to import, and most commands never need it.
    import torch  # noqa: PLC0415

    if not torch.cuda.is_available():
        return False
    try:
        probe = torch.ones(8, device="cuda")
        return bool((probe @ probe).item() == 8)  # noqa: PLR2004
    except RuntimeError:
        return False


def token_spans_for(model_name: str) -> TokenSpans:
    """The embedding model's tokenizer as a `chunking.TokenSpans` function.

    Only the tokenizer is loaded (a few MB), not the model. Offsets point into the original
    text, so chunkers cut the text itself instead of rebuilding it from tokens.
    """
    from transformers import AutoTokenizer  # noqa: PLC0415 (slow import, see _cuda_works)

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    def spans(text: str) -> list[tuple[int, int]]:
        # The whole document is tokenized at once: longer than the model's limit, but these
        # tokens are only counted, never fed to the model (hence verbose=False).
        encoded = tokenizer(
            text, add_special_tokens=False, return_offsets_mapping=True, verbose=False
        )
        return [(start, end) for start, end in encoded["offset_mapping"] if end > start]

    return spans


# --- embedders ------------------------------------------------------------------------

Vectors = npt.NDArray[np.float32]
Embed = Callable[[list[str]], Vectors]
"""Texts -> one row per text, normalized to length 1 (so a dot product is a cosine)."""


def load_local_embedder(cfg: EmbeddingConfig) -> Embed:
    """Load a sentence-transformers model once and return the function that uses it.

    On the GPU the model runs in half precision: half the memory, faster, and differences in
    the vectors far below what changes a ranking.
    """
    import torch  # noqa: PLC0415 (slow imports, see _cuda_works)
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    device = resolve_device(cfg.device)
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = SentenceTransformer(cfg.model, device=device, model_kwargs={"dtype": dtype})
    logger.info("embedder %s on %s (%s)", cfg.model, device, dtype)

    def embed(texts: list[str]) -> Vectors:
        vectors = model.encode(
            texts,
            batch_size=cfg.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > cfg.batch_size,  # a bar for indexing, not for a question
        )
        return np.asarray(vectors, dtype=np.float32).reshape(len(texts), -1)

    return embed


EMBEDDERS: dict[str, Callable[[EmbeddingConfig], Embed]] = {
    "local": load_local_embedder,
}

CACHE_ROOT = Path("data/cache/embeddings")


def cached(embed: Embed, model: str, cache_dir: Path = CACHE_ROOT) -> Embed:
    """Wrap `embed` with an on-disk cache: one .npy file per (model, text).

    Only the texts not seen before reach `embed`. A file is written under a temporary name
    and then renamed, so an interrupted run never leaves a half-written vector.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    def embed_with_cache(texts: list[str]) -> Vectors:
        paths = [cache_dir / f"{_digest(model, text)}.npy" for text in texts]
        missing = [i for i, path in enumerate(paths) if not path.exists()]
        if missing:
            fresh = embed([texts[i] for i in missing])
            for i, vector in zip(missing, fresh, strict=True):
                temporary = paths[i].with_suffix(".tmp.npy")
                np.save(temporary, vector)
                os.replace(temporary, paths[i])
        # INFO only when something was computed: a cached question per search is just noise.
        level = logging.INFO if missing else logging.DEBUG
        cached_count = len(texts) - len(missing)
        logger.log(level, "embeddings: %d cached, %d computed", cached_count, len(missing))
        if not paths:
            return np.zeros((0, 0), dtype=np.float32)
        return np.stack([np.load(path) for path in paths])

    return embed_with_cache


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


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
    return f"{cfg.chunking.strategy}-{_digest(json.dumps(relevant, sort_keys=True))[:8]}"


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


def load_embedder_for(
    cfg: EmbeddingConfig,
    cache_dir: Path = CACHE_ROOT,
    load_embedder: Callable[[EmbeddingConfig], Embed] | None = None,
) -> Embed:
    """The configured embedder wrapped in the cache: the same one for chunks and questions."""
    loader = load_embedder or EMBEDDERS[cfg.strategy]
    return cached(loader(cfg), cfg.model, cache_dir)


def _slug(text: str) -> str:
    words = "".join(c if c.isalnum() else " " for c in text.lower()).split()
    return "-".join(words) or "document"

import re
from pathlib import Path

import numpy as np
import pytest

from homerag.config import ChunkingConfig, ExperimentConfig, load_experiment
from homerag.embedding import Vectors
from homerag.index import (
    StaleIndexError,
    build_index,
    ensure_index,
    fingerprint,
    index_key,
    load_index,
    save_index,
)
from homerag.ingest import load_book, save_book
from homerag.models import Block, Book, Section

BASELINE = Path("configs/experiments/baseline.yaml")


# --- index -------------------------------------------------------------------------

DIMENSIONS = 16


def fake_embed(texts: list[str]) -> Vectors:
    """Deterministic bag-of-words vectors: texts sharing words point in similar directions."""
    vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
    for row, text in enumerate(texts):
        for word in text.lower().split():
            vectors[row, sum(map(ord, word)) % DIMENSIONS] += 1.0
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def word_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def make_config(document: Path, **chunking: int) -> ExperimentConfig:
    cfg = load_experiment(BASELINE)
    sizes = {"size_tokens": 8, "overlap_tokens": 2, **chunking}
    return cfg.model_copy(
        update={"document": document, "chunking": ChunkingConfig(strategy="fixed", **sizes)}
    )


def write_book(path: Path, text: str) -> Path:
    blocks = (Block("paragraph", text, "ch.xhtml", page="1"),)
    section = Section("base", "Base", 1, ("Base",), "body", True, blocks)
    save_book(Book("My Book.epub", (section,)), path)
    return path


BOOK_TEXT = "the base period builds aerobic endurance with long steady rides and runs every week"


def test_index_key_ignores_settings_that_do_not_change_the_vectors(tmp_path: Path) -> None:
    cfg = make_config(tmp_path / "book.json")
    retrieval = cfg.retrieval.model_copy(update={"top_k": 10})
    embedding = cfg.embedding.model_copy(update={"device": "cpu", "batch_size": 4})

    assert index_key(cfg) == index_key(cfg.model_copy(update={"retrieval": retrieval}))
    assert index_key(cfg) == index_key(cfg.model_copy(update={"embedding": embedding}))


def test_index_key_changes_with_chunking_or_model(tmp_path: Path) -> None:
    cfg = make_config(tmp_path / "book.json")
    other_model = cfg.embedding.model_copy(update={"model": "other/model"})

    assert index_key(cfg) != index_key(make_config(tmp_path / "book.json", size_tokens=9))
    assert index_key(cfg) != index_key(cfg.model_copy(update={"embedding": other_model}))
    assert index_key(cfg).startswith("fixed-")


def test_ensure_index_builds_then_reuses(tmp_path: Path) -> None:
    cfg = make_config(write_book(tmp_path / "book.json", BOOK_TEXT))
    args = {"root": tmp_path / "index", "cache_dir": tmp_path / "cache", "spans": word_spans}

    first = ensure_index(cfg, load_embedder=lambda _: fake_embed, **args)
    second = ensure_index(cfg, load_embedder=lambda _: fake_embed, **args)

    assert first.built
    assert not second.built
    assert first.folder == second.folder
    assert first.folder.parent.name == "my-book"
    index = load_index(first.folder, fingerprint(cfg.document))
    assert len(index.chunks) == first.chunks == index.vectors.shape[0]
    assert np.allclose(np.linalg.norm(index.vectors, axis=1), 1.0)


def test_index_built_from_another_book_json_is_refused(tmp_path: Path) -> None:
    document = write_book(tmp_path / "book.json", BOOK_TEXT)
    cfg = make_config(document)
    args = {"root": tmp_path / "index", "cache_dir": tmp_path / "cache", "spans": word_spans}
    report = ensure_index(cfg, load_embedder=lambda _: fake_embed, **args)

    write_book(document, BOOK_TEXT + " and a new sentence after re-ingestion")

    with pytest.raises(StaleIndexError, match=r"different book\.json"):
        load_index(report.folder, fingerprint(document))
    assert ensure_index(cfg, load_embedder=lambda _: fake_embed, **args).built


def test_missing_index_is_reported_clearly(tmp_path: Path) -> None:
    with pytest.raises(StaleIndexError, match="no index here"):
        load_index(tmp_path / "nothing", "abc")


def test_saved_index_round_trips(tmp_path: Path) -> None:
    cfg = make_config(write_book(tmp_path / "book.json", BOOK_TEXT))
    built = build_index(load_book(cfg.document), cfg, fake_embed, word_spans)

    save_index(built, tmp_path / "idx", {"document_fingerprint": "f"})
    loaded = load_index(tmp_path / "idx", "f")

    assert loaded.chunks == built.chunks
    assert np.array_equal(loaded.vectors, built.vectors)

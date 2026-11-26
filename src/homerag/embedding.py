"""Embeddings: where the model runs, its tokenizer, and the function that embeds texts.

The pieces, in the order the pipeline uses them:
- `resolve_device`, `token_spans_for`: where the model runs, and its tokenizer for the chunker;
- `EMBEDDERS`: loaders that return an `Embed` function (texts -> normalized vectors), keeping
  the loaded model in a closure; `cached` wraps any of them with an on-disk cache;
- `load_embedder_for`: the configured embedder in its cache, the same for chunks and questions.

The only module that imports `sentence_transformers`, `transformers` and `torch`.
"""

import hashlib
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt

from homerag.chunking import TokenSpans
from homerag.config import EmbeddingConfig

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


def load_embedder_for(
    cfg: EmbeddingConfig,
    cache_dir: Path = CACHE_ROOT,
    load_embedder: Callable[[EmbeddingConfig], Embed] | None = None,
) -> Embed:
    """The configured embedder wrapped in the cache: the same one for chunks and questions."""
    loader = load_embedder or EMBEDDERS[cfg.strategy]
    return cached(loader(cfg), cfg.model, cache_dir)


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()

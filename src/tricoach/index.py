"""Embeddings and search indexes (Phase 3, in progress).

Computes chunk embeddings (`sentence-transformers` with `bge-m3`, cached on disk by text hash
and model), builds the in-memory `numpy` vector index and the BM25 lexical index, and saves and
loads them with a `schema_version`. One index per document and config.
"""

import logging
from collections.abc import Callable
from typing import Literal

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

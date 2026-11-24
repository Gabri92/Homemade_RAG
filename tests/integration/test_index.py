import numpy as np

from homerag.config import EmbeddingConfig
from homerag.index import load_local_embedder, token_spans_for


def test_bge_m3_offsets_point_into_the_original_text() -> None:
    text = "Zone 5b efforts: 3 x 4 min at LTHR,\n\nthen   recovery."

    spans = token_spans_for("BAAI/bge-m3")(text)

    assert spans == sorted(spans)
    assert all(0 <= start < end <= len(text) for start, end in spans)
    assert "".join(text[s:e] for s, e in spans) == "".join(text.split())


def test_bge_m3_puts_related_texts_closer() -> None:
    cfg = EmbeddingConfig(strategy="local", model="BAAI/bge-m3")
    embed = load_local_embedder(cfg)

    question, related, unrelated = embed(
        [
            "How long is the base period?",
            "The base period usually lasts about twelve weeks.",
            "Open-water swimming requires sighting and drafting skills.",
        ]
    )

    assert question.shape == (1024,)
    assert np.isclose(np.linalg.norm(question), 1.0, atol=1e-3)
    assert question @ related > question @ unrelated

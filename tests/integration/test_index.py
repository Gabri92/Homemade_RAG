from homerag.index import token_spans_for


def test_bge_m3_offsets_point_into_the_original_text() -> None:
    text = "Zone 5b efforts: 3 x 4 min at LTHR,\n\nthen   recovery."

    spans = token_spans_for("BAAI/bge-m3")(text)

    assert spans == sorted(spans)
    assert all(0 <= start < end <= len(text) for start, end in spans)
    assert "".join(text[s:e] for s, e in spans) == "".join(text.split())

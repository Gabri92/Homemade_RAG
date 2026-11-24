# ADR 0007 — The model cites source numbers; the code builds the citations

- **Date:** 2026-11-24
- **Status:** accepted

## Context
Every claim in an answer must point to where it comes from in the book (chapter, section, page), and the reader must be able to trust that the location exists. The generator receives the top-k retrieved chunks. Chunk ids (`<section id>#<n>`) are long, and a chunk may cover several sections (ADR 0005).

## Decision
- The prompt (`answer_v1`) gives the chunks as numbered sources, `[1]` for the best ranked, each with its section path and page. The model cites with numbers in square brackets (`[2]`, `[1][3]`, `[1, 3]`).
- `qa.cite` turns the numbers into `Citation`s from the chunks' metadata: one per section the chunk covers, with the chunk's page. A number without a source is ignored and logged. The model never writes a section name or page that the reader sees as a citation.
- Generation runs on the model in the config (`claude-sonnet-5-5` in the baseline, judge on `claude-opus-5-5`) through `llm.py`: answers cached on disk by the whole request, cost computed from a price table, and server-side refusal fallbacks (`fallbacks: "default"`) on the models that support them. A refusal that survives the fallback becomes a short notice without citations.

## Alternatives considered
- **Cite chunk ids**: long strings the model may copy wrongly, and they mean nothing to the model.
- **Let the model write chapter and page**: readable, but a citation could point to a section that does not exist.
- **The Claude API's native citations**: they return the cited text and its location inside the provided documents. Worth measuring against this format, which needs no extra feature; planned as an experiment in Phase 6.

## Consequences
- A citation always points to a real section and page. Whether the cited source really supports the claim is not guaranteed: the judge (Phase 3b, step 8) measures it.
- A chunk spanning two sections cites both, so a citation can be less precise than the claim.
- Prices in `llm.py` must be updated when they change; a model without a price is counted at 0 with a warning.

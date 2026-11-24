# ADR 0003 — The golden set references book sections, not chunks

- **Date:** 2026-11-18
- **Status:** accepted (relevance of chunks covering several sections: ADR 0005)

## Context
Each golden-set question must say where its answer is in the book, so that retrieval metrics (hit rate, recall@k, MRR) can be computed. The original plan in `architecture.md` §7.1 stored `relevant_chunk_ids` plus text spans used to remap them whenever the chunking changes. But chunks do not exist yet, they change with every chunking experiment, and spans would put book text in a committed file.

Phase 1 already gives every section a stable, path-based id (`Section.id` in `book.json`). The risk: an ingestion fix can still rename or drop a section and silently orphan a reference.

## Decision
- A golden question cites `relevant_section_ids`: `Section.id` values from `book.json`. No chunk ids, no spans.
- Retrieval metrics will map a retrieved chunk to its section (each chunk records the section it comes from).
- `check_references` (`eval/dataset.py`) lists cited ids that are missing from the book or excluded from the index. It runs:
  - in `tests/book/test_golden.py`, so the full suite (and the pre-commit hook) fails as soon as an ingestion change orphans a reference;
  - in `homerag eval check`, while the user writes questions.
- Follow-up questions point at the previous question with `previous_id` instead of copying its text.

## Alternatives considered
- **Chunk ids + spans** (the original plan): more precise, but it depends on the chunker, needs remapping code, and puts book text in the repository.
- **Section ids + spans**: finer recall, but more manual work and still book text in the repository. To reconsider in Phase 5 only if sections turn out too coarse for the metrics.

## Consequences
- Changing the chunking never touches the golden set.
- Retrieval metrics are at section granularity: a retrieved chunk counts as relevant when it comes from a cited section.
- Renaming a section in ingestion means updating `golden.jsonl` in the same change; the book test enforces it.

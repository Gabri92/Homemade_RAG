# ADR 0005 — A chunk may cover several sections

- **Date:** 2026-11-23
- **Status:** accepted

## Context
ADR 0003 makes the golden set cite sections, and says that a retrieved chunk is relevant when it comes from a cited section. That assumed one section per chunk.

The Phase 3 baseline must be the naive fixed-size chunker, so that Phase 5 measures the full value of using the book's structure. On the reference book, 192 of the 325 indexed sections are shorter than one 500-token chunk (median 311 words). Cutting only inside sections would turn most of them into a single chunk. The baseline would then already be close to structure-aware chunking (experiment 5.1), and 5.1 would underestimate its own effect.

## Decision
- The fixed-size chunker cuts the running text of the included sections, across section boundaries.
- `Chunk.sections` lists every section a chunk covers, in reading order (`SectionRef`: id and title path). The chunk id is `<first section id>#<n>`.
- For retrieval metrics, a chunk is relevant when **at least one** of its sections is cited by the question.
- Citations show every section the chunk covers; the page is the one where the chunk starts.

## Alternatives considered
- **Fixed-size windows inside each section**: one section per chunk and exact citations, but most sections become a single chunk, so the baseline is no longer naive. It can still be measured as its own experiment.
- **Assign a crossing chunk to the section where it starts (or where most of it lies)**: keeps one id per chunk, but makes retrieval metrics wrong. A chunk that does contain the answer would count as irrelevant whenever the answer sits in its second section.

## Consequences
- Strategies that respect boundaries (structure-aware, parent-child) simply produce chunks with one section: same type, no special case.
- "At least one cited section" is lenient for chunks covering several sections (on the reference book, 60% of baseline chunks cover two or more). This is a known bias of the baseline. Phase 5 compares strategies with the same rule, and the share of multi-section chunks is reported with each run.
- A citation built from a crossing chunk may name a section that does not support the claim. The judge's citation accuracy will show how often this happens.

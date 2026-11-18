# Practical roadmap — from the book to an evaluated Q&A

Guiding principle: **eval-driven development**. First build the way to measure, then optimize.
Each phase has a concrete deliverable and a learning goal.

---

## Phase 0 — Project setup ✅ (v0.1.0)

- Initialize the project with `uv`, folder layout as in `docs/steering/structure.md`.
- Tooling: `ruff` (lint + format), `mypy --strict`, `pytest`, `pre-commit`.
- `git init` + a `.gitignore` that excludes `data/` and `eval/runs/`.
- Environment variables in `.env` (never committed): `ANTHROPIC_API_KEY`.

**Deliverable:** `uv run pytest` passes on an empty test; lint and type check green.

---

## Phase 1 — Ingestion and inspection ✅ (v0.2.0)

> Status at closing: ePub Loader, Cleaner, Structurer → `book.json`, `dump`/`ingest`/`inspect`, tests on the real book. Problems found, rules and open issues in `docs/ingestion-findings.md`. Problems **#12–#14**, which surfaced when testing other ePubs (Standard Ebooks corpus), are closed in v0.2.1, with generalization tests in `tests/corpus/`.

1. Loader for the format you own (preferably ePub).
2. Cleaner + Structurer → `data/processed/book.json` (chapters, sections, tables, pages).
3. Inspection script: prints the chapter tree, counts words per section, lists the tables found.
4. **Check by hand** 5–10 sections and all key tables (zones, hours per period).

**Learning:** RAG quality is born here. Broken tables = wrong numeric answers.
**Deliverable:** a reliable `book.json` + Cleaner tests with real examples of artifacts.

---

## Phase 2 — Golden dataset (before retrieval!)

1. Write **30 initial questions** by hand covering every category (`factual`, `table`, `conceptual`, `multi_hop`, `out_of_scope`, `follow_up`).
2. For each one: a reference answer + the book section/span that supports it.
2b. All questions in English, plus ~10 `non_english` messages (including short questions and edge cases) to test the language gate.
3. Later: extend to 80–100, also with **reviewed** synthetic questions.

**Learning:** writing the questions forces you to understand what a "correct answer" means.
**Deliverable:** `eval/datasets/golden.jsonl` + a pydantic schema that validates it.

---

## Phase 3 — "Naive RAG" baseline + evaluation harness

1. Fixed-size chunker (e.g. 500 tokens, overlap 50).
2. `bge-m3` embedder, in-memory `numpy` index, dense top-5 retrieval.
3. Language gate with `lingua-py`: non-English message → notice, no query.
3b. Claude generator with a simple prompt + citations, answers in English.
4. **Eval runner**: runs the golden set, computes retrieval metrics (hit rate, recall@k, MRR) and generation metrics (judge), saves the run.
5. CLI: `ask "question"` and `eval run --config configs/experiments/baseline.yaml`.
6. Development tooling, once `eval run` exists: the `/experiment` skill and the `eval-analyst` subagent (see `docs/working-with-claude-code.md`, "Planned").

**Learning:** have a starting number. It will probably be mediocre: that's fine.
**Deliverable:** first run in `eval/runs/` with metrics per category.

---

## Phase 4 — Optimize retrieval (one experiment at a time)

Each row is an experiment with its own config; it is always compared with the previous best run.

| # | Experiment | Hypothesis |
|---|---|---|
| 4.1 | Structure-aware chunking (sections, intact tables) | Improves `table` and `factual` |
| 4.2 | Varying chunk size and k | Find the sweet spot |
| 4.3 | Hybrid dense + BM25 with RRF | Improves exact terms ("Build 2", "LTHR") |
| 4.4 | Query rewriting with an LLM (multi-query or HyDE) | Improves vague questions or questions phrased differently from the book |
| 4.5 | Cross-encoder reranker | Improves precision of the top 5 |
| 4.6 | Contextual chunking | Improves ambiguous chunks |
| 4.7 | Parent-child | Improves `multi_hop` / `conceptual` |
| 4.8 | **Generic pipeline baseline**: ingestion and chunking with a public tool versus our ingestion, with the same retrieval, LLM and golden set. **Tool to be evaluated** before the experiment (candidates: LlamaIndex, Unstructured, Docling, pandoc + a simple chunker), based on ePub support, output quality and dependencies | Measures how much the data work is worth (tables, glossary, repeated pull quotes, roles) and on which question categories. The baseline remains **only** a point of comparison (ADR 0001: no framework in the main pipeline) |

**Learning:** understand *which lever moves which metric* and in which question category.
**Deliverable:** comparison report between runs + a reasoned choice of the best config (recorded in an ADR).

---

## Phase 5 — Optimize generation

1. Prompt: strict grounding, citation format, answers in English keeping the book's terms.
2. Handling `out_of_scope`: explicit refusal.
3. Multi-turn: condensing the follow-up into a standalone question before retrieval.
3b. *Gate accuracy* metric (deterministic) on the `non_english` category.
4. **Judge calibration**: label ~30 answers by hand, measure judge/human agreement, fix the rubric.

**Deliverable:** faithfulness and refusal correctness measured and reliable.

---

## Phase 6 — Comparison with a long-context baseline

- A generator that receives the whole book in context with prompt caching.
- Same golden set: compare quality, cost and latency with the best RAG config.

**Learning:** understand concretely the RAG vs long-context trade-offs.
**Deliverable:** comparison table + conclusions in `docs/adr/`.

---

## Phase 7 — Minimal chat interface

- Streamlit or Gradio calling the same `qa.answer()` (no logic in the UI).
- Shows expandable citations (chapter/section + short excerpt).
- 👍/👎 button that saves the interaction: it becomes material for new golden set questions.

**Deliverable:** a usable local chat.

---

## Later (out of scope for now)

- **User-added sources** (NotebookLM style): the Loader and Cleaner rules are already generic (they work on HTML semantics and on `Block`), but thresholds and expected values are tuned on a single book. To generalize:
  1. **ingestion corpus**: a few copyright-free ePubs/PDFs from different publishers (e.g. Project Gutenberg, Standard Ebooks, open-access articles), each with its own expected values, run as regression tests;
  2. **automatic quality report** computed on every uploaded file, with no expected values: generic invariants (coverage of the source text, heading structure, untitled tables, figures without captions, duplicate rate, anomalous blocks) → warnings to the user when a document is extracted badly;
  3. **downstream evaluation**: a small golden set of questions for each corpus document, because ingestion quality is ultimately measured by the answers.

- **Figures with Claude's multimodality**: during ingestion, images (first tables published as images, then charts and illustrations) are passed to Claude, which transcribes tables to Markdown and describes figures. The generated text replaces the caption-only `figure` block and is cached, so each image is paid for once. Measured as an experiment: golden set questions that depend on figures, before and after.

- Multilingual: the language gate is replaced by an LLM query processor (answer language + query translated into English for retrieval) and the golden set is extended with the same questions in more languages.
- The book's rules as deterministic code (zone calculation, ATP) exposed as tools.
- Athlete profile and onboarding.
- Integration with real training data (Strava/Garmin).

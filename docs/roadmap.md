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

## Phase 2 — Golden dataset (before retrieval!) ✅ (v0.3.0)

> Status at closing: format, validation and `homerag eval check` done (ADR 0003: references are section ids). First golden set written by hand: 40 questions (multi_hop 4, conceptual 6, follow_up 3, factual 8, table 5, out_of_scope 4, non_english 10).

1. Write **30 initial questions** by hand covering every category (`factual`, `table`, `conceptual`, `multi_hop`, `out_of_scope`, `follow_up`).
2. For each one: a reference answer + the book section/span that supports it.
2b. All questions in English, plus ~10 `non_english` messages (including short questions and edge cases) to test the language gate.
3. Later: extend to 80–100, also with **reviewed** synthetic questions.

**Learning:** writing the questions forces you to understand what a "correct answer" means.
**Deliverable:** `eval/datasets/golden.jsonl` + a pydantic schema that validates it.

---

## Phase 3 — "Naive RAG" baseline + evaluation harness

The largest phase: it builds the whole pipeline end to end, plus the way to measure it. It is split in two, so that the first number arrives before any LLM cost and each half reaches `main` through its own pull request. Order of work: retrieval first, then its metrics on the golden set (deterministic and free), then the gate, the generator and the judge.

### Phase 3a — Retrieval baseline ✅ (v0.4.0)

> First baseline run (26 questions citing sections, top-5 dense retrieval, fixed 500/50 chunks): hit@5 0.77, recall@5 0.73, MRR 0.61. Weakest categories: `table` (hit@5 0.40) and `follow_up` (0.33, retrieved without rewriting); `multi_hop` always hits but finds 75% of the cited sections. 60% of the chunks cover two or more sections (ADR 0005). With 3–8 questions per category, one question moves a category by 0.12–0.33: differences are read per question, not only as means.

1. Dependencies, experiment config (YAML → pydantic), pipeline data types, device choice. ✅
2. Fixed-size chunker (500 tokens, overlap 50) over the running text of the book (ADR 0005). ✅
3. `bge-m3` embedder with an on-disk cache, in-memory `numpy` index per document and index key; `homerag index`. ✅
4. Dense top-5 retrieval; `homerag search` shows what retrieval returns for one question. ✅
5. **Retrieval metrics** (hit rate, recall@k, MRR) per question category on the golden set; `homerag eval run` saves a retrieval-only run. ✅

**Learning:** have a starting number, at zero API cost. It will probably be mediocre: that's fine.
**Deliverable:** first run in `eval/runs/` with retrieval metrics per category.

### Phase 3b — Generation and judge (v0.5.0)

> First full baseline run (30 answered questions, $1.14, about 3.6 s per answer): correct 0.77, faithful 0.97, paraphrase 1.00. Weakest: `table` (correct 0.30, declined 0.60) and `follow_up` (0.50). Most wrong answers are honest refusals when retrieval missed the cited section, so retrieval (Phase 5) comes before prompt work.

6. Language gate with `lingua-py`: non-English message → notice, no query. Gate accuracy (deterministic) scored by `eval run` on every golden question. ✅
7. Claude generator: `llm.py` (retries, cache, cost), prompt `answer_v1` with citations, answers in English, `qa.answer`; `homerag ask "question"` (ADR 0007). ✅
8. **LLM judge** (correctness, faithfulness, refusal on `out_of_scope`) + code-based answer checks + the full `eval run` (retrieval + generation, cost and latency per question) + `eval compare` (ADR 0008). ✅
9. Development tooling, once `eval run` exists: the `/experiment` skill and the `eval-analyst` subagent, with `docs/reading-a-run.md` as the guide they follow (see `docs/working-with-claude-code.md`). ✅

**Learning:** what a complete RAG answer costs, and how far a simple prompt gets.
**Deliverable:** first full run in `eval/runs/` with judged answers per category.

---

## Phase 4 — Shared demo: web chat over documents

Right after the first complete pipeline, before the optimizations: a web page reachable through a link, with no installation and no sign-in, where a visitor picks a document and chats with it. The build-in-public posts can then show the product working and people can try it; Phases 5–6 improve a product that is already online. Product rules: `docs/steering/product.md`, "Shared demo".

It is split in two. Most of the risk of a public demo comes from files sent by strangers: malicious files, other people's copyright and personal data, session isolation, indexing while the visitor waits. 4a avoids all of it by serving only documents chosen and prepared by the author, so the link can be public early, with the cost of questions as the main remaining risk. 4b adds uploads, planned in detail along the way.

### Phase 4a — Public demo on curated documents

1. **Curated documents**: 2–3 sports or technical documents in English whose license allows showing excerpts to the public (public domain or an open license such as Creative Commons); never the reference book. Each one is ingested and checked by hand like the reference book, with a small golden set, so the quality of the demo is measured.
2. **Indexes built offline**: on the author's machine (GPU), published with the demo as read-only files shared by all visitors. The server only embeds the question, so it needs no GPU.
3. **Web chat** (Streamlit or Gradio, chosen at the start of the phase): pick a document, ask, read the answer with expandable citations (chapter/section + short excerpt). It calls the same `qa.answer()`: no logic in the UI. First on this machine, on the reference book.
4. **Cost and abuse limits**: a spending limit on the API key in the Anthropic console (the final safety net, independent of the code); a global daily budget in the app (the real ceiling: without accounts, per-visitor limits can be bypassed); per-visitor limits on questions; a clear message when one is reached. Questions are not stored beyond what answering needs, and the page says so.
5. **Hosting** on a public URL (platform chosen at the start of the phase): secrets only in the platform's secret store; the deployed files are checked so that the reference book and its derivatives are never included.

In local use (the author, on the reference book) a 👍/👎 button saves the interaction as material for new golden set questions.

Decisions recorded as ADRs at the start of the phase: UI framework, hosting platform, curated documents and their licenses, limit values. Screenshots and videos for posts show short paraphrased answers, never long excerpts of the book.

**Learning:** what it takes to put a RAG in front of other people: hosting, cost control, cost per question measured with real use.
**Deliverable:** a public link where anyone can chat with the curated documents, within a daily budget.

### Phase 4b — Document upload (planned along the way)

Visitors upload their own documents, as in NotebookLM. It brings back the risks that 4a avoids, so it is planned in detail with the numbers from 4a (cost per question, traffic) and may come after the optimizations. Starting point:
- **Upload and indexing**: ingestion and indexing while the page shows progress; indexing time measured first (the host's CPU, a GPU, or an embedding API; changing the embedding model is an experiment on the golden set).
- **Checks on uploaded documents, with clear messages** that say what happened and what to do next: DRM-protected, corrupt or unsupported file → rejected (DRM detection does not exist yet in the loader); not in English → rejected (same detection as the language gate, on a sample of the text); too large, or too large once decompressed (an ePub is a zip) → rejected, with a time limit on processing; extraction problems found by the generic quality report → a warning in plain words. Every check is tested with synthetic files, messages included.
- **Security on untrusted files**: zip bombs, XML external entities in the ePub parser.
- **Isolation and deletion**: a document and its index belong to the visitor's session only and are deleted after a time limit or on request; tested so that one session never reads another's files, also under concurrent use.
- **Terms of use and privacy notice** before the first upload: upload only documents you have the right to use; uploads serve only to answer their owner and are deleted afterwards; how long data is kept.
- Per-visitor limits on uploads; hosting resized for indexing.

**Deliverable:** visitors can upload an English ePub and chat with it, with a clear message for every rejected or badly extracted document.

---

## Phase 5 — Optimize retrieval (one experiment at a time)

Each row is an experiment with its own config; it is always compared with the previous best run.

| # | Experiment | Hypothesis |
|---|---|---|
| 5.1 | Structure-aware chunking (sections, intact tables) | Improves `table` and `factual` |
| 5.2 | Varying chunk size and k | Find the sweet spot |
| 5.3 | Hybrid dense + BM25 with RRF | Improves exact terms ("Build 2", "LTHR") |
| 5.4 | Query rewriting with an LLM (multi-query or HyDE) | Improves vague questions or questions phrased differently from the book |
| 5.5 | Cross-encoder reranker | Improves precision of the top 5 |
| 5.6 | Contextual chunking | Improves ambiguous chunks |
| 5.7 | Parent-child | Improves `multi_hop` / `conceptual` |
| 5.8 | **Generic pipeline baseline**: ingestion and chunking with a public tool versus our ingestion, with the same retrieval, LLM and golden set. **Tool to be evaluated** before the experiment (candidates: LlamaIndex, Unstructured, Docling, pandoc + a simple chunker), based on ePub support, output quality and dependencies | Measures how much the data work is worth (tables, glossary, repeated pull quotes, roles) and on which question categories. The baseline remains **only** a point of comparison (ADR 0001: no framework in the main pipeline) |
| 5.9 | Semantic chunking (cut where consecutive sentences stop being similar) | Helps documents with little structure; probably no gain on the reference book, so it is also measured on the corpus |

How to run them:
- **Before starting**, review this list as a cost/complexity versus expected-gain trade-off, using the baseline run: implementation effort, cost per run (LLM calls for contextual chunking and query rewriting), latency, and which question categories the baseline fails. The order of the experiments follows from that review, not from the numbering.
- **One lever at a time**, always against the previous best run; a lever is kept only if it improves the metric and the question category it was meant for.
- The chunking levers lie on three axes (`architecture.md` §5): where to cut, what to add to a chunk, what to give the LLM. Combinations across axes are tried last, starting from the levers that won.

**Learning:** understand *which lever moves which metric* and in which question category.
**Deliverable:** comparison report between runs + a reasoned choice of the best config, including its cost and complexity (recorded in an ADR).

---

## Phase 6 — Optimize generation

1. Prompt: strict grounding, citation format, answers in English keeping the book's terms.
2. Handling `out_of_scope`: explicit refusal.
3. Multi-turn: condensing the follow-up into a standalone question before retrieval.
4. **Judge calibration**: label ~30 answers by hand, measure judge/human agreement, fix the rubric.
4b. **Numeric match check** (code-based, free): the numbers in the reference answer must appear in the answer; aimed at `table` and `factual`, and a cross-check on the judge (architecture §7.3).
5. **Experiment: our citations vs the Claude API's native citations.** Pass the retrieved chunks as document/content blocks with citations enabled, so the API returns the cited text and its location; we keep our own metadata (chapter, section, printed page) to show the reader. Same golden set and judge: compare citation accuracy, faithfulness and prompt complexity against our prompt-based citation format. Answers whether citation handling is worth building ourselves.

**Deliverable:** faithfulness and refusal correctness measured and reliable.

---

## Phase 7 — Comparison with external baselines

Both baselines answer the same build-versus-buy question: how much does our own pipeline add over an approach that needs little or no pipeline at all?

1. **Long context**: a generator that receives the whole book in context with prompt caching.
2. **Managed "all-in-one" RAG**: the book uploaded to a hosted retrieval service (candidates to evaluate before the experiment: an LLM provider's file search, Bedrock Knowledge Bases, Vertex AI RAG Engine, Azure AI Search), with default settings. Like experiment 5.8, it stays **only** a point of comparison (ADR 0001). Copyright check first: uploading the book to a third-party service must be allowed for personal use and the data must not be shared or retained beyond the experiment.

Same golden set and judge for both: compare quality per question category, citation precision, cost and latency with the best RAG config.

**Learning:** understand concretely the trade-offs of RAG vs long context, and of a custom pipeline vs a managed one.
**Deliverable:** comparison table + conclusions in `docs/adr/`.

---

## Phase 8 — UI improvements (optional)

Only if the build-in-public phase asks for it; the RAG pipeline and its evaluation come first.

- Streaming answers, so the first words arrive while the rest is generated.
- Multi-turn conversation in the UI, using the follow-up condensing from Phase 6.
- Citations you can open: the cited section, with the cited passage highlighted.
- A page to review the 👍/👎 feedback and turn it into golden set questions.
- Cost and latency per answer, visible during development.

**Deliverable:** a chat that is pleasant to use and to show; every change keeps the logic in `qa`, not in the UI.

---

## Later (out of scope for now)

- **User-added sources, generalized** (the uploads of Phase 4b serve them): the Loader and Cleaner rules are already generic (they work on HTML semantics and on `Block`), but thresholds and expected values are tuned on a single book. To generalize:
  1. **ingestion corpus**: a few copyright-free ePubs/PDFs from different publishers (e.g. Project Gutenberg, Standard Ebooks, open-access articles), each with its own expected values, run as regression tests;
  2. **automatic quality report** computed on every uploaded file, with no expected values: generic invariants (coverage of the source text, heading structure, untitled tables, figures without captions, duplicate rate, anomalous blocks) → warnings to the user when a document is extracted badly (first shown to visitors in Phase 4b, then refined);
  3. **downstream evaluation**: a small golden set of questions for each corpus document (the curated documents of Phase 4a are the first ones), because ingestion quality is ultimately measured by the answers. The corpus favours sports and technical documents (manuals, guides, papers): the kind of document the product is evaluated on.

- **Figures with Claude's multimodality**: during ingestion, images (first tables published as images, then charts and illustrations) are passed to Claude, which transcribes tables to Markdown and describes figures. The generated text replaces the caption-only `figure` block and is cached, so each image is paid for once. Measured as an experiment: golden set questions that depend on figures, before and after.

- Multilingual: the language gate is replaced by an LLM query processor (answer language + query translated into English for retrieval) and the golden set is extended with the same questions in more languages.

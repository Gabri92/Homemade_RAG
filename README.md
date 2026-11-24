# Homemade RAG

A homemade clone of NotebookLM (now Gemini Notebook), specialized on sports documents: an assistant that answers questions about the documents you give it and cites its sources. Built from scratch to learn **retrieval-augmented generation (RAG)** component by component and to **measure** every choice with a golden dataset (eval-driven development).

The reference document used to build and evaluate it is Joe Friel's *The Triathlete's Training Bible*. The assistant answers in English and cites the chapter and section behind every claim.

> **Unofficial project.** Not affiliated with, endorsed by or connected to the author or the publisher of the book.

## The book is not included

The book is copyrighted and is **not** part of this repository, nor is anything derived from it (extracted text, `book.json`, indexes, evaluation runs). To run the pipeline you need your own legally obtained copy, placed in `data/raw/`. Only **ePub** input is supported for now; a PDF loader is planned. The whole `data/` folder is gitignored, and a pre-commit hook refuses book files even when they are added with `git add -f`.

The hand-written **golden dataset** (`eval/datasets/golden.jsonl`) is kept local too: its answers paraphrase the book. `eval/datasets/example.jsonl` shows the format with synthetic questions about an invented training plan.

## Why build it by hand

- **Learning first:** readable functions for each step (loader, cleaner, structurer, chunker, retriever, generator) instead of a batteries-included framework that would hide them.
- **Measurability:** every pipeline change is an experiment, scored on the same golden set (retrieval metrics plus an LLM judge), with the delta reported.
- **Answer quality:** grounded in the book, with verifiable citations; when the book does not cover a question, the assistant says so.

## Architecture in one picture

Three pipelines, linked by two artifacts on disk:

| Pipeline | Steps | Produces |
|---|---|---|
| Ingestion | Loader → Cleaner → Structurer | `book.json`: sections with stable ids |
| Indexing | Chunker → Enricher → Embedder → Index | vector + BM25 index |
| Query | Language gate → Retriever → Reranker → Generator | answer with citations |

An evaluation harness sends the golden questions through the query pipeline and scores what it retrieved and what it answered. Details: [`docs/architecture.md`](docs/architecture.md).

## Status

| Phase | What | State |
|---|---|---|
| 0 | Project setup | ✅ v0.1.0 |
| 1 | Ingestion and inspection | ✅ v0.2.0 |
| 2 | Golden dataset format and validation | ✅ v0.3.0 |
| 3a | Naive RAG baseline: retrieval + its metrics | ✅ v0.4.0 |
| 3b | Naive RAG baseline: generation + judge | ✅ v0.5.0 |
| 4a | Public demo: web chat over curated documents | next |
| 4b | Document upload in the demo (planned along the way) | planned |
| 5–8 | Retrieval and generation experiments, external baselines, UI improvements (optional) | planned |

Full plan: [`docs/roadmap.md`](docs/roadmap.md).

## What you need

- Python 3.12+ and [uv](https://docs.astral.sh/uv/).
- Your own copy of the document, as an **ePub in English**, in `data/raw/`.
- Your own **Anthropic API key**. Answers and evaluations call the Claude API and are billed to your account: about one cent per question, and about $1 for a full `eval run` (a repeated run is served from the on-disk cache and costs nothing). A key from a workspace dedicated to this project, with a spending limit, keeps the cost bounded. Ingestion, indexing, search and `eval run --retrieval-only` are local and free.
- About 9 GB of disk: most of it is PyTorch and the `BAAI/bge-m3` embedding model, downloaded on the first `index`. A CUDA GPU makes indexing faster; without one it runs on the CPU.

## Quick start

```bash
uv sync
uv run pre-commit install
cp .env.example .env                           # then put your key in .env: ANTHROPIC_API_KEY=...
uv run homerag ingest data/raw/<book>.epub     # -> data/processed/book.json
uv run homerag inspect data/raw/<book>.epub    # quality report, numbers only
uv run homerag index                           # chunk + embed -> data/index/
uv run homerag search "How long is the base period?"   # retrieval only, free
uv run homerag ask "How long is the base period?"      # answer with citations (Claude API)
```

`.env` is gitignored and refused by a pre-commit hook: the key never reaches the repository.

To evaluate, write your golden set (format in [`docs/architecture.md`](docs/architecture.md) §7.1, example in `eval/datasets/example.jsonl`), then:

```bash
uv run homerag sections                        # section ids to cite in the golden set
uv run homerag eval check                      # validate eval/datasets/golden.jsonl
uv run homerag eval run --retrieval-only       # gate + retrieval metrics, free
uv run homerag eval run                        # + answers graded by an LLM judge (about $1)
uv run homerag eval compare <run_a> <run_b>    # what changed between two runs
```

How to read the numbers: [`docs/reading-a-run.md`](docs/reading-a-run.md).

## Limits (for now)

- **English only.** Ask questions in English: a message in another language gets a short notice and starts no search and no API call. Very short messages ("LTHR?") always pass.
- **English documents only**, in **ePub**: retrieval compares the question with the document's text, so a document in another language could not be queried. A PDF loader is planned.
- **Answers come only from the document.** When the retrieved passages do not cover a question, the assistant says so instead of using general knowledge. It gives no medical advice.
- **Personal use.** Use a document you have the right to use; nothing derived from it should be published.

All commands: [`docs/commands.md`](docs/commands.md). Definition of done:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

Tests on the real book are skipped automatically when the book is not in `data/raw/`; CI runs every other check on each pull request.

## Documentation

- [`docs/commands.md`](docs/commands.md): every command, grouped by task.
- [`docs/reading-a-run.md`](docs/reading-a-run.md): how to read an evaluation run and turn it into the next change.
- [`docs/architecture.md`](docs/architecture.md): pipelines, chunking strategies, evaluation.
- [`docs/roadmap.md`](docs/roadmap.md): phases and planned experiments.
- [`docs/adr/`](docs/adr/): architecture decision records.
- [`docs/steering/`](docs/steering/): product, tech, structure and conventions.
- [`docs/ingestion-findings.md`](docs/ingestion-findings.md): ingestion problems found and how they were fixed.
- [`docs/working-with-claude-code.md`](docs/working-with-claude-code.md): how the repo is set up for development with Claude Code.

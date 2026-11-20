# Homemade RAG

[![CI](https://github.com/Gabri92/Homemade_RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/Gabri92/Homemade_RAG/actions/workflows/ci.yml)

A question-answering assistant over a triathlon training book, built from scratch to learn **retrieval-augmented generation (RAG)** component by component and to **measure** every choice with a golden dataset (eval-driven development).

The reference book is Joe Friel's *The Triathlete's Training Bible*. The assistant answers in English and cites the chapter and section behind every claim.

> **Unofficial project.** Not affiliated with, endorsed by or connected to the author or the publisher of the book.

## The book is not included

The book is copyrighted and is **not** part of this repository, nor is anything derived from it (extracted text, `book.json`, indexes, evaluation runs). To run the pipeline you need your own legally obtained copy, placed in `data/raw/`. The whole `data/` folder is gitignored, and a pre-commit hook refuses book files even when they are added with `git add -f`.

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
| 3 | Naive RAG baseline + evaluation harness | next |
| 4–7 | Retrieval and generation experiments, external baselines, minimal chat | planned |

Full plan: [`docs/roadmap.md`](docs/roadmap.md).

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pre-commit install
uv run tricoach ingest data/raw/<book>.epub     # -> data/processed/book.json
uv run tricoach inspect data/raw/<book>.epub    # quality report, numbers only
uv run tricoach sections                        # section ids to cite in the golden set
uv run tricoach eval check                      # validate eval/datasets/golden.jsonl
```

All commands: [`docs/commands.md`](docs/commands.md). Definition of done:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest
```

Tests on the real book are skipped automatically when the book is not in `data/raw/`; CI runs every other check on each pull request.

## Documentation

- [`docs/architecture.md`](docs/architecture.md): pipelines, chunking strategies, evaluation.
- [`docs/roadmap.md`](docs/roadmap.md): phases and planned experiments.
- [`docs/adr/`](docs/adr/): architecture decision records.
- [`docs/steering/`](docs/steering/): product, tech, structure and conventions.
- [`docs/ingestion-findings.md`](docs/ingestion-findings.md): ingestion problems found and how they were fixed.
- [`docs/working-with-claude-code.md`](docs/working-with-claude-code.md): how the repo is set up for development with Claude Code.

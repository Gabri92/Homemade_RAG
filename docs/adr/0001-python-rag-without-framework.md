# ADR 0001 — RAG pipeline in Python without a RAG framework

- **Date:** 2026-11-16
- **Status:** accepted

## Context
The project's primary goal is to understand RAG in practice and to be able to evaluate it. The corpus is a single book (~1–3k chunks).

## Decision
Python 3.12 with hand-written components in a few flat modules; the variants to compare are functions picked by name from the config (KISS). In-memory vector index with `numpy`, BM25 with `rank-bm25`, local `bge-m3` embeddings and reranker, generation and judge with Claude. Evaluation implemented in-house.

## Alternatives considered
- **LangChain / LlamaIndex** — they speed things up, but hide chunking, retrieval and prompts: at odds with the learning goal.
- **Dedicated vector DB (Qdrant, pgvector)** — pointless for a few thousand vectors; it stays replaceable behind the `VectorIndex` interface.
- **Ragas for eval** — useful as a comparison later, but first the metrics are implemented by hand to understand them.

## Consequences
- More code to write, but every component is readable and testable.
- Changing a technology touches a single module, because every external library is imported in one place only.
- If the flat structure becomes too tight, it grows module by module (a module becomes a package) only when needed.

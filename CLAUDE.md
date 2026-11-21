# CLAUDE.md

Homemade clone of NotebookLM (now Gemini Notebook), specialized on sports documents: Q&A with citations over source documents. Reference document: *The Triathlete's Training Bible* (Joe Friel). A learning project: RAG in practice plus rigorous evaluation. The public repository describes only this clone, never other products built on it (see `docs/steering/product.md`).

Read and follow the steering files:

@docs/steering/product.md
@docs/steering/tech.md
@docs/steering/structure.md
@docs/steering/conventions.md

References (read them when you touch the related area): `docs/architecture.md`, `docs/roadmap.md`, `docs/adr/`, `docs/ingestion-findings.md` (book defects and their status: update it when you fix or find an ingestion problem), `docs/working-with-claude-code.md` (how this repo is set up for Claude Code), `docs/commands.md` (command cheat sheet: update it when commands change). The user's personal notes live in `notes/` (gitignored): never commit them or quote them in repository docs.

## Rules that always apply

1. **Never commit the book or anything derived from it** (`data/`, `eval/runs/`, `eval/datasets/golden.jsonl`). Do not print long verbatim excerpts of the book in output, logs or tests: use synthetic fixtures.
2. **Every change to the RAG pipeline is an experiment**: new config in `configs/experiments/`, eval before and after, delta reported.
3. **KISS now, modularity when needed.** No new modules, classes or abstractions if a function will do. Structure grows only in response to the concrete signals listed in `structure.md` ("When to grow the structure"), one step at a time. If a change seems to need more structure, propose it before making it.
4. **New dependencies**: justify them and ask before adding them.
5. **Definition of done**: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest` all green.
6. **Architectural decisions** (new component, technology change, winning config) → a new ADR in `docs/adr/`.
7. **Keep the docs aligned**: if you change structure, commands or conventions, update the matching steering file in the same change.
8. **Language**: everything in the repository (code, docs, comments, commits) is in **English**, because the project is built in public. Chat replies to the user are in **Italian**.

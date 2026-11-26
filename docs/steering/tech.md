# Tech

## Stack
| Area | Choice |
|---|---|
| Language | Python 3.12+ |
| Packages/env | `uv` (never a direct `pip install`) |
| Data and config validation | `pydantic` v2, `pydantic-settings`, YAML config |
| LLM | `anthropic` SDK; generation `claude-sonnet-5-5`, judge `claude-opus-5-5` (configurable) |
| Embedding / reranker | `sentence-transformers` with `BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3` |
| Torch | CUDA 12.6 build on Windows (local GPU), CPU build on Linux (CI), set in `[tool.uv.sources]`; the device is chosen at runtime from the experiment config |
| Index | in-memory `numpy` (persisted to file); `rank-bm25` for lexical search |
| Language detection | `lingua-py` (language gate: English only) |
| Extraction | `ebooklib` + `beautifulsoup4` (ePub), `pymupdf` (PDF) |
| CLI | `typer` |
| Web chat | `gradio` (local; ADR 0011) |
| Tests | `pytest` |
| Quality | `ruff` (lint + format), `mypy --strict`, `pre-commit` |

## Commands
```bash
uv sync                                   # install dependencies
uv run ruff check . --fix                 # lint
uv run ruff format .                      # format
uv run mypy src                           # type check
uv run pytest                             # all tests (unit + real book when present)
uv run pytest tests/unit                  # unit only: the fast loop during development
uv run pytest -m integration              # tests that call real APIs/models
uv run pytest -m book                     # only the real-book checks (they also run with `pytest`, skipped if the book is missing)
uv run pytest -m corpus                   # only the generalization on data/corpus/ (sources in tests/corpus/expectations.py)
uv run homerag dump data/raw/<book>.epub          # loader output -> data/processed/blocks_raw.txt
uv run homerag dump data/raw/<book>.epub --clean  # after the Cleaner -> data/processed/blocks_clean.txt
git diff --no-index data/processed/blocks_raw.txt data/processed/blocks_clean.txt  # what the Cleaner changed
uv run homerag ingest data/raw/<book>.epub  # load + clean + structure -> data/processed/book.json
uv run homerag inspect data/raw/<book>.epub # quality report (numbers only); exit code 1 on warnings
uv run homerag sections                  # section ids, pages, excluded flags -> data/processed/sections.txt
uv run homerag eval check                # validate eval/datasets/golden.jsonl against data/processed/book.json
uv run homerag index [--config configs/experiments/<name>.yaml]  # chunk + embed -> data/index/ (reused if up to date)
uv run homerag search "question" [--text]  # retrieval only: ranked chunks, no LLM
uv run homerag ask "question"            # single Q&A
uv run homerag chat                      # web chat on http://127.0.0.1:7860 (documents in configs/documents.yaml)
uv run homerag eval run --config configs/experiments/<name>.yaml
uv run homerag eval compare <run_a> <run_b>
```
> Available now: `dump`, `ingest`, `inspect`, `sections`, `eval check`, `index`, `search`, `ask`, `chat`, `eval run` (gate, retrieval, answers graded by the judge; `--retrieval-only` for the free loop), `eval compare`. `uv run homerag --help` lists the existing commands. Task-oriented cheat sheet of what is available now: `docs/commands.md` (keep it aligned when commands change).

## Secrets and configuration
- `ANTHROPIC_API_KEY` and the like only in `.env` (gitignored; `.env.example` lists the variables), read through `pydantic-settings` as `SecretStr`, never logged. Use a key from a Console workspace dedicated to this project, with a spending limit; the shared demo gets its own key. `.claude/settings.json` denies Claude Code reading `.env`.
- No magic values in code: models, k, chunk sizes and prompts live in the experiment config.

## Dependency policy
- Prefer the standard library and a few targeted dependencies.
- Every new dependency must be justified (what it solves, which alternative was rejected).
- Every external library is imported in a single module (see `structure.md`).

## Cost and reproducibility
- The Claude API no longer accepts `temperature`: a fixed `effort` per config and the on-disk caches make runs repeatable.
- On-disk cache for embeddings (key = text hash + model) and for LLM answers (`data/cache/llm/`, key = the whole request: model, effort, max_tokens, prompt, message), so identical calls are never paid twice.
- Cost per call is computed in `llm.py` from the response's tokens and a price table (`PRICES`), and logged.
- Every eval run saves the full config and the version of the prompts it used.

## Claude Code
How the repo is set up for development with Claude Code (steering files, the definition-of-done hooks, the pre-commit guard on book files, planned skills and subagents): see `docs/working-with-claude-code.md`.

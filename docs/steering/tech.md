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
uv run homerag eval run --config configs/experiments/<name>.yaml
uv run homerag eval compare <run_a> <run_b>
```
> Available now: `dump`, `ingest`, `inspect`, `sections`, `eval check`, `index`, `search`. `eval run` arrives in Phase 3a (retrieval only), `ask` and `eval compare` in Phase 3b. `uv run homerag --help` lists the existing commands. Task-oriented cheat sheet of what is available now: `docs/commands.md` (keep it aligned when commands change).

## Secrets and configuration
- `ANTHROPIC_API_KEY` and the like only in `.env` (gitignored), read through `pydantic-settings`.
- No magic values in code: models, k, chunk sizes and prompts live in the experiment config.

## Dependency policy
- Prefer the standard library and a few targeted dependencies.
- Every new dependency must be justified (what it solves, which alternative was rejected).
- Every external library is imported in a single module (see `structure.md`).

## Cost and reproducibility
- Temperature 0 for the judge and for experiments.
- On-disk cache for embeddings (key = text hash + model) and judge answers, so identical calls are never paid twice.
- Every eval run saves the full config and the version of the prompts it used.

## Claude Code
How the repo is set up for development with Claude Code (steering files, the definition-of-done hooks, the pre-commit guard on book files, planned skills and subagents): see `docs/working-with-claude-code.md`.

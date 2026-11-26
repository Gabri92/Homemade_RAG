# ADR 0012 — Interfaces apart from the RAG core, and structure rules checked by a test

- **Date:** 2026-11-26
- **Status:** accepted

## Context
After the web chat (ADR 0011) the package had two interfaces next to the core: `cli.py` (typer) and `chat.py` (Gradio). A third is coming with the hosting of Phase 4a, step 5. A review of the code against `docs/steering/` found:
- **the boundary between interfaces and core existed only by convention.** Nothing stopped a core module from importing the chat. The rule "`cli` → `qa`/`eval` → the rest" also did not say what the CLI may call: it already called `ingest`, `index` and `retrieval` directly, which is right for commands like `ingest` and `index`;
- **`index.py` had 304 lines and two reasons to change:** the embedding model (device, tokenizer, loader, on-disk cache) and the vector index (build, save, load, reuse). Both are signals for a split in `structure.md`;
- **`FakeLLM` was defined four times in the tests**, and `test_chat.py` imported fixtures from `test_qa.py`. That breaks DRY at the third repetition and "test fixtures only in `tests/conftest.py`";
- **smaller points:** `Any` without a comment justifying it, two functions over ~40 lines (`run_experiment`, `anthropic_llm`).

## Decision
- **`src/homerag/interfaces/`** holds what talks to a person: `cli.py` and `chat.py`, later the hosted demo.
  - An interface reads input, calls the core's public functions (`qa`, `eval`, `ingest`, `index`, `retrieval`) and lays out the result, with no RAG logic.
  - The core never imports `interfaces/`.
  - The `homerag` command points at `homerag.interfaces.cli:app`.
  - The tests follow: `tests/unit/interfaces/`.
- **The rules are checked on the code.** `tests/unit/test_architecture.py` reads every module's imports with `ast`, also the imports inside functions, and fails if:
  - a core module imports `interfaces/`;
  - an external library is imported outside its module (`OWNERS`: `anthropic` → `llm`, `torch`/`transformers`/`sentence_transformers` → `embedding`, `lingua` → `language`, `ebooklib`/`bs4` → `ingest/epub`, `gradio` → `interfaces/chat`, `typer` → `interfaces/cli`);
  - `models.py` imports another project module.

  Tried by adding a forbidden import to `qa.py`: two tests fail.
- **`index.py` → `embedding.py` + `index.py`,** 161 lines each, with the code moved unchanged.
  - They are two concepts with their own reasons to change, so they become two modules named after them, not an `index/` package. `structure.md` now allows that form of split.
  - `embedding.py` is the only module importing `torch`, `transformers` and `sentence_transformers`.
- **One `FakeLLM`, `embed_on_first_axis` and `fake_resources` in `tests/conftest.py`.**

## Alternatives considered
- **`gradio` as an optional dependency** (`uv sync --extra chat`), so a CLI-only install skips its ~143 MB. Rejected for now:
  - `uv sync` removes what it was not asked for, so after a plain `uv sync` the definition of done would fail (`mypy src` and the chat tests need `gradio`);
  - CI and every documented command would need the extra;
  - the only user of the repository runs the chat anyway.

  To be reconsidered at hosting time (step 5), when the deployed files are chosen.
- **Separate packages in a uv workspace** (`homerag-core`, `homerag-chat`): a real boundary at install time, but a second `pyproject.toml`, versions to keep aligned, and no user who installs the core alone. The import test gives the same guarantee at a fraction of the cost.
- **An import-linter tool:** a new dependency for three rules that 60 lines of `ast` check.
- **`index/` as a package with the same public functions:** it would hide that callers use two different things. `qa` and `retrieval` need the embedder, `cli` needs the index.

## Consequences
- A new interface (the hosted demo) is a new module in `interfaces/`, with no change to the core.
- A new external library needs a line in `OWNERS`, or the test fails. That is on purpose: it makes the choice of where the library lives explicit.
- Imports change for whoever used `homerag.cli`, `homerag.chat`, or the embedding names from `homerag.index`. All callers are in this repository and were updated.

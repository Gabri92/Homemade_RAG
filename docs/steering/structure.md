# Structure

Principle: **KISS**. One module per concept, functions before classes, no extra layer until it is needed.

## Layout
Modules marked *(placeholder)* contain only a docstring describing their purpose: they are filled in from Phase 3 onwards.
```
src/tricoach/
  models.py      # dataclasses: Block, Section, Book (then Chunk, RetrievedChunk, Answer, Citation)
  config.py      # settings (.env) + experiment config (YAML -> pydantic)
  ingest/        # source -> blocks -> cleaning -> sections -> data/processed/book.json (ADR 0002)
    __init__.py  #   public API: from outside, import only from `tricoach.ingest`
    epub.py      #   ePub Loader (one file per format: pdf.py tomorrow)
    cleaning.py  #   Cleaner: structural rules on list[Block]
    structure.py #   Structurer: list[Block] -> Book (sections, ids, roles, inclusion, pages)
    book_file.py #   save_book / load_book for book.json, with SCHEMA_VERSION
    quality.py   #   generic quality report (no expected values): `tricoach inspect`
    dump.py      #   format_blocks, format_sections for inspection
  chunking.py    # (placeholder) chunking strategies (functions) + CHUNKERS registry
  index.py       # (placeholder) embeddings, numpy index, BM25, save/load
  retrieval.py   # (placeholder) dense, bm25, RRF fusion, rerank
  language.py    # (placeholder) language gate: is_english(text)
  llm.py         # (placeholder) the single access point to the Anthropic API
  qa.py          # (placeholder) answer(question) -> Answer: gate -> retrieve -> generate
  prompts/       # (placeholder) prompts as versioned .md files
  eval/          # evaluation harness
    dataset.py   #   golden set: GoldenQuestion schema, load_golden, check_references
    metrics.py   #   (placeholder) metrics (pure functions)
    judge.py     #   (placeholder) LLM-as-judge
    run.py       #   (placeholder) runs an experiment, saves and compares runs
  cli.py         # typer commands: dump, ingest, inspect, sections, eval check (then ask, eval run/compare)
.claude/               # Claude Code project settings: settings.json (hooks) + hooks/ scripts
configs/experiments/   # one YAML per experiment (from Phase 3)
eval/datasets/         # golden.jsonl (hand-written, gitignored: kept local, ADR 0004) + example.jsonl (synthetic, committed)
eval/runs/             # run outputs (gitignored)
data/                  # raw/, processed/, index/ (gitignored)
notes/                 # personal notes: prompting, building in public (gitignored)
tests/                 # one kind of test = one folder (see conventions.md, "Tests")
  conftest.py          #   shared fixtures (make_epub: synthetic mini-ePub)
  unit/                #   fast, offline; mirrors src/tricoach/ (unit/ingest/test_cleaning.py, unit/eval/test_dataset.py, ...)
  book/                #   on the real book: `book` marker and automatic skip in book/conftest.py
    expectations.py    #     expected values for the book (numbers and short titles only)
    test_golden.py     #     golden-set section ids exist in the current ingestion (skipped until golden.jsonl exists)
  corpus/              #   generalization on ePubs from other publishers in data/corpus/ (`corpus` marker)
    expectations.py    #     expected values and where to download each ePub
  integration/         #   (from Phase 3) real APIs and models, `integration` marker
  e2e/                 #   (from Phase 3) question -> cited answer on the real book
```

## Rules
- **Dependencies flow one way:** `cli` → `qa` / `eval` → the rest. `models.py` imports no other project module.
- **One external library, one module:** `anthropic` only in `llm.py`, `sentence_transformers` only in `index.py` / `retrieval.py`, `lingua` only in `language.py`. Replacing a technology then touches one file.
- **Interchangeable strategies = functions with the same signature in a dictionary.** Example:
  ```python
  CHUNKERS: dict[str, Callable[[list[Section], ChunkingConfig], list[Chunk]]] = {
      "fixed": fixed_size_chunks,
      "sections": section_chunks,
  }
  ```
  The config picks the key. No classes, no factories.
- **Split a module only when needed:** beyond ~300 lines, or when it holds two things that change for different reasons. At that point it becomes a package (`chunking/`) with the same name.
- **No logic in `cli.py`:** it reads arguments, calls `qa` or `eval`, prints.

## When to grow the structure

Simplicity and modularity are a **trade-off that changes over time**: start flat and add structure only when a concrete signal justifies it. Never "for the future", never on principle.

| Concrete signal | Next step (the smallest possible) |
|---|---|
| A module exceeds ~300 lines or mixes two reasons to change | It becomes a package with the same name (`chunking.py` → `chunking/`), same public functions |
| The variants in a registry need different signatures | Unify the signature with a config object; if that is not enough, a small class per variant |
| There is a **second real stateful implementation** (e.g. a second vector index, a second LLM provider) | Introduce a `Protocol` for that one component |
| The same group of parameters travels through many functions | Group them in a dataclass (e.g. `Resources(index, llm)`) |
| A test needs `monkeypatch` or complicated setup | The dependency must be passed as a parameter |
| The same knowledge appears in three places | Extract it into a single place (DRY) |
| A new product area arrives (e.g. multilingual support) | A new dedicated module/package, without touching the existing structure |

Rules for the step:
- one signal → one step; do not anticipate the next ones;
- a structural change is a separate refactoring (`refactor:` commit) with tests green before and after;
- if the change touches several modules or introduces a new concept (Protocol, package, layer), propose it first and record it in an ADR.

## Exploration notebooks (reminder: from Phase 3)

To be introduced at the start of chunking, not before (YAGNI). They are for **experimenting and learning** (how chunkers cut, what retrieval returns, BM25 vs dense), not for building the product.
- `notebooks/` folder; `jupyter`/`ipykernel` dependencies in the dev group only.
- Notebooks **import** `tricoach` functions, they do not rewrite them (DRY). Whatever works moves into the package, with its tests.
- They are committed **without outputs** (outputs contain book text): automatic stripping before commit.

## Where to put what
| I want to add… | It goes in… |
|---|---|
| A new chunking / retrieval strategy | a function in `chunking.py` / `retrieval.py` + an entry in the registry |
| A new source format | a file in `ingest/` (e.g. `pdf.py`) that produces `list[Block]` |
| A new cleaning rule | a function in `ingest/cleaning.py` + an entry in the `CLEANING_STEPS` sequence |
| A new metric | a pure function in `eval/metrics.py` |
| A new prompt or prompt version | a new file in `prompts/` |
| A new command | `cli.py` |
| A new data type | `models.py` |

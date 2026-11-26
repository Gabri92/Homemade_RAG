# Structure

Principle: **KISS**. One module per concept, functions before classes, no extra layer until it is needed.

## Layout
Modules marked *(placeholder)* contain only a docstring describing their purpose: they are filled in from Phase 3 onwards.
```
src/homerag/
  models.py      # dataclasses: Block, Section, Book, SectionRef, Chunk, RetrievedChunk, Citation, Passage, Usage, Answer
  config.py      # settings (.env) + experiment config (YAML -> pydantic, frozen, unknown fields rejected)
  ingest/        # source -> blocks -> cleaning -> sections -> data/processed/book.json (ADR 0002)
    __init__.py  #   public API: from outside, import only from `homerag.ingest`
    epub/        #   ePub Loader (one file or package per format: pdf.py tomorrow), ADR 0009
      loader.py  #     container: spine, navigation, page carry-over -> load_epub, epub_text
      html.py    #     one document -> blocks (headings, lists, figures, notes, pages)
      tables.py  #     tables -> Markdown (rowspan/colspan)
      roles.py   #     what each file is: landmarks, epub:type
      pressbooks.py #   one tool's conventions, used only where EPUB semantics are missing
    cleaning.py  #   Cleaner: structural rules on list[Block]
    structure.py #   Structurer: list[Block] -> Book (sections, ids, roles, inclusion, pages)
    book_file.py #   save_book / load_book for book.json, with SCHEMA_VERSION
    quality.py   #   generic quality report (no expected values): `homerag inspect`
    dump.py      #   format_blocks, format_sections for inspection
  chunking.py    # chunking strategies (functions) + CHUNKERS registry: fixed
  embedding.py   # device choice, tokenizer offsets, EMBEDDERS + on-disk cache, load_embedder_for
  index.py       # vector index: build, save, load, ensure_index, open_index (BM25 with 5.3)
  retrieval.py   # RETRIEVERS: dense (then bm25, RRF fusion, rerank in Phase 5); search, format_results
  language.py    # language gate: build_detector, is_english(text, detector, cfg), NOTICE
  llm.py         # the single access point to the Anthropic API: LLMRequest -> Completion, cache, cost, prompts
  qa.py          # answer(question, resources, cfg) -> Answer: gate -> retrieve -> generate -> citations;
                 #   passages(answer, book): each cited section with the chunk the model read marked
  prompts/       # prompts as versioned .md files (answer_v1.md, judge_v1.md)
  eval/          # evaluation harness
    dataset.py   #   golden set: GoldenQuestion schema, load_golden, check_references
    metrics.py   #   retrieval metrics (hit@k, recall@k, reciprocal rank), gate metrics, code-based answer checks, aggregate per category
    judge.py     #   LLM-as-judge: Verdict (structured outputs), judge, verdict_scores
    parts.py     #   the parts of a run, each scored on its own: run_gate, run_retrieval, run_generation
    run.py       #   run_experiment: the parts on the golden set, metrics per category, cost, provenance (`retrieval_only` skips answers)
    report.py    #   run files: result_rows, save_run, load_run, format_*, compare_runs (RUN_FORMAT)
  interfaces/    # what talks to a person (ADR 0012); the core never imports it
    cli.py       #   typer commands: dump, ingest, inspect, sections, index, search, ask, chat, eval check, eval run, eval compare
    chat.py      #   local web chat (Gradio, ADR 0011): document menu, chat, source panel
.claude/               # Claude Code project settings: settings.json (hooks, deny reading .env), hooks/, agents/eval-analyst.md, skills/experiment/
configs/experiments/   # one YAML per experiment: baseline.yaml is the Phase 3 starting point
configs/documents.yaml # documents offered in the web chat: title, author, license, URL, experiment config
eval/datasets/         # golden.jsonl (hand-written, gitignored: kept local, ADR 0004) + example.jsonl (synthetic, committed)
                       # + one set per curated document of the demo, committed (open license): exercise-science*.jsonl + .md (method)
eval/runs/             # run outputs (gitignored)
data/                  # raw/, processed/, index/, cache/ (gitignored)
notes/                 # personal notes: prompting, building in public (gitignored)
tests/                 # one kind of test = one folder (see conventions.md, "Tests")
  conftest.py          #   shared fixtures and fakes (make_epub, blocks_of, page_marker; FakeLLM, fake_resources; a synthetic golden set)
  unit/                #   fast, offline; mirrors src/homerag/ (unit/ingest/test_cleaning.py, unit/interfaces/test_cli.py, ...)
    test_architecture.py #   the rules below, checked on the imports: core vs interfaces, one library per module
  book/                #   on the real book: `book` marker and automatic skip in book/conftest.py
    expectations.py    #     expected values for the book (numbers and short titles only)
    test_golden.py     #     golden-set section ids exist in the current ingestion (skipped until golden.jsonl exists)
  corpus/              #   generalization on ePubs from other publishers in data/corpus/ (`corpus` marker)
    expectations.py    #     expected values and where to download each ePub
  integration/         #   real APIs and models (bge-m3 tokenizer, one Claude call): `integration` marker set in integration/conftest.py
  e2e/                 #   (from Phase 3b) question -> cited answer on the real book
```

## Rules
- **Interfaces apart from the core (ADR 0012):** everything that talks to a person lives in `interfaces/` (the CLI, the web chat, later the hosted demo). An interface reads input, calls the core's public functions (`qa`, `eval`, `ingest`, `index`, `retrieval`) and lays out what comes back, with no RAG logic of its own. The core never imports `interfaces/`.
- **Dependencies flow one way:** `interfaces` → `qa` / `eval` → the rest. `models.py` imports no other project module.
- **One external library, one module:** `anthropic` only in `llm.py`, `sentence_transformers`, `transformers` and `torch` only in `embedding.py`, `lingua` only in `language.py`, `ebooklib` and `bs4` only in `ingest/epub/`, `gradio` only in `interfaces/chat.py`, `typer` only in `interfaces/cli.py`. Replacing a technology then touches one file.
- These rules are checked by `tests/unit/test_architecture.py`: a new external library gets its line in `OWNERS` there.
- **Interchangeable strategies = functions with the same signature in a dictionary.** Example:
  ```python
  CHUNKERS: dict[str, Callable[[Book, ChunkingConfig, TokenSpans], list[Chunk]]] = {
      "fixed": fixed_size_chunks,
      "sections": section_chunks,
  }
  ```
  The config picks the key. No classes, no factories.
- **Split a module only when needed:** beyond ~300 lines, or when it holds two things that change for different reasons. At that point it becomes a package (`chunking/`) with the same name, or, when the two things are separate concepts, two modules named after them (`index.py` → `embedding.py` + `index.py`, ADR 0012).
- **No logic in the interfaces:** `cli.py` reads arguments, calls the core, prints; `chat.py` reads the page, calls the core, lays out.

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
- Notebooks **import** `homerag` functions, they do not rewrite them (DRY). Whatever works moves into the package, with its tests.
- They are committed **without outputs** (outputs contain book text): automatic stripping before commit.

## Where to put what
| I want to add… | It goes in… |
|---|---|
| A new chunking / retrieval strategy | a function in `chunking.py` / `retrieval.py` + an entry in the registry |
| A new source format | a file in `ingest/` (e.g. `pdf.py`) that produces `list[Block]` |
| A publishing tool's conventions (e.g. Pressbooks) | a file in `ingest/epub/` named after the tool, called only where the EPUB semantics are missing (ADR 0009) |
| A new cleaning rule | a function in `ingest/cleaning.py` + an entry in the `CLEANING_STEPS` sequence |
| A new metric | a pure function in `eval/metrics.py` |
| A new prompt or prompt version | a new file in `prompts/` |
| A new command | `interfaces/cli.py` |
| A new way to reach the pipeline (web page, hosted demo, API) | a module in `interfaces/` |
| A new data type | `models.py` |

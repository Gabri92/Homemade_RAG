# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/) (0.x while in development).

## [Unreleased]

### Added
- First curated document of the Phase 4a demo, *Introduction to Exercise Science for Fitness Professionals* (CC BY 4.0): experiment config `exercise-science-baseline.yaml` and two committed golden sets. `exercise-science.jsonl` has 27 questions written by Claude Haiku from seeded, sampled sections, checked for overlap with the passage and verified against it. `exercise-science-human.jsonl` has 10 hand-written questions, kept apart to measure the generator's bias. The method and prompt are in `eval/datasets/exercise-science.md`.
- ADR 0010: how a curated document is chosen (license checked in the document; NC and ND excluded), attribution wherever its material appears, and why the files stay out of git. Attribution for the first document next to its golden set and in the README. A corpus test checks the SHA-256 of the edition the golden set cites.

### Fixed
- Ingestion (findings #20, #21): an untitled table whose first row spans every column takes it as its title (new Cleaner step `title_from_spanning_row`, after the intro rule); multiple-choice quiz sections, recognised from their content, get the role `quiz` and are not searched. Only the Pressbooks book changes: untitled tables 8 → 2, 4 quiz sections excluded.

## [0.5.1] - 2026-11-26

Fixes on `main` after Phase 3b: ingestion of Pressbooks open textbooks, the first candidate document for the Phase 4a shared demo.

### Changed
- The ePub loader is now the package `ingest/epub/` (`loader`, `html`, `tables`, `roles`, `pressbooks`), with the same public functions and no change in behaviour (ADR 0009). A publishing tool's conventions are used only where the EPUB semantics are missing.
- README: what you need to run the project, and its limits.

### Fixed
- Ingestion of Pressbooks ePubs (open textbooks, findings #17–#19): roles from the first `<div>` when a file has no `epub:type`, so cover, title page, copyright and table of contents are no longer searchable; chapter titles no longer doubled (note numbers in headings, chapter number and authors dropped; new Cleaner step `remove_repeated_headings`); figure captions inside `<figure>` and text in `<div>`s without `<p>` are kept (coverage 96.0% → 99.6%). The reference book's ingestion is unchanged. The Pressbooks book joins the corpus regression tests.
- `/experiment` skill: the run cost is written in words, because `$1` in a skill is replaced by the first argument.

## [0.5.0] - 2026-11-24

Phase 3b: generation and judge. The first complete pipeline, measured end to end: correct 0.77, faithful 0.97, gate 40/40, about $1 per full run.

### Added
- `forbid-secrets` pre-commit hook: refuses `.env` and its variants, `CLAUDE.local.md`, `notes/` and `.claude/settings.local.json` even after `git add -f`; `.gitignore` now covers `.env.*` (except `.env.example`) and `.claude/settings.local.json`.
- `docs/reading-a-run.md`: how to read a run, column by column, and from symptoms to causes and levers. The `/experiment` skill (`.claude/skills/experiment/`) runs an experiment end to end; the `eval-analyst` subagent (`.claude/agents/`) reports on one or two runs following the guide.
- LLM judge (`eval/judge.py`, prompt `judge_v1`, ADR 0008): one structured-output call per answer to `claude-opus-5-5` returning reasoning, correctness (correct / partial / incorrect), faithfulness and whether the answer declines. Code-based answer checks in `eval/metrics.py`: cites a source, cites only real sources, English, longest run copied from a source (`evaluation.max_copied_words`).
- Full `homerag eval run`: gate, retrieval, answers and judge, with cost and latency per question; `--retrieval-only` for the free loop. Run files moved to `eval/report.py` (`RUN_FORMAT` 2: one `results.jsonl` row per question, `metrics.json` by part, no `gate.json`). `homerag eval compare <run_a> <run_b>`: changes per category and the questions that got worse or better. First full baseline: correct 0.77, faithful 0.97, $1.14.
- Structured outputs and per-call latency in `llm.py`; `judge.max_tokens` in the experiment config.
- Claude generator: `llm.py` (the only module importing `anthropic`: `LLMRequest` -> `Completion`, on-disk answer cache in `data/cache/llm/`, cost from a price table, server-side refusal fallbacks), prompt `answer_v1`, `qa.answer` (gate -> retrieval -> generation -> citations built from chunk metadata, ADR 0007) and `homerag ask "question"`. `Usage` and `Citation.source` in the data types; `generation.max_tokens` 4096 in the baseline.
- `.env.example`; `.claude/settings.json` denies Claude Code reading `.env`.
- Language gate (`language.is_english`, `build_detector`, `NOTICE`; ADR 0006): local, deterministic detection with `lingua-py` among the configured languages; a message is blocked only when a non-English language reaches `min_confidence`, and messages under `min_words` always pass. New `language_gate` section in the experiment config.
- Gate accuracy in `homerag eval run`: every golden question goes through the gate (`eval/metrics.gate_metrics`: accuracy, English blocked, non-English passed); saved in `gate.json` and printed with the misjudged ids. Baseline: 40/40 correct.

### Changed
- Roadmap: Phase 4 becomes the shared web demo, before the optimizations: 4a a public demo on curated, openly licensed documents (indexes built offline, cost limits); 4b document upload, planned along the way. Product, architecture and the risk notes follow.
- Uploaded documents must be in English, like questions (product.md, architecture §4.1).
- Reproducibility no longer relies on `temperature` (the API rejects it): fixed `effort` per config plus on-disk caches (`tech.md`).
- Run files: `RUN_FORMAT` 2 (one `results.jsonl` row per question, `metrics.json` by part, no `gate.json`). Runs saved by 0.4.0 must be run again to be compared.

## [0.4.0] - 2026-11-24

Phase 3a: retrieval baseline. First measured number at zero API cost.

### Fixed
- Section ids are always unique: the suffix for repeated title paths no longer collides with a title ending in a number (ingestion finding #16).

### Added
- Retrieval evaluation: `eval/metrics.py` (hit@k, recall@k, reciprocal rank, means per category), `homerag eval run` saving `config.yaml`, `results.jsonl`, `metrics.json`, `meta.json` to `eval/runs/`; `evaluation.ks` in the experiment config. First baseline: hit@5 0.77, recall@5 0.73, MRR 0.61 over 26 questions.
- Dense retrieval (`retrieval.dense_search`, registry `RETRIEVERS`): cosine similarity on normalized vectors, stable ranking on ties, refuses a question vector from another model; `homerag search "question" [--text]` prints the ranking.
- `homerag index`: chunk + embed a document into `data/index/<document>/<strategy>-<hash>/`; the folder key hashes only the chunking and embedding settings, so experiments that change retrieval or generation share one index. An index built from another `book.json` (fingerprint in `meta.json`) or in another format is refused and rebuilt.
- Embedders registry `EMBEDDERS` (`local`: sentence-transformers, fp16 on GPU) and an on-disk embedding cache (one `.npy` per model + text, atomic writes).
- Fixed-size chunker (`chunking.fixed_size_chunks`, registry `CHUNKERS`): token windows with overlap over the running text, counted with the bge-m3 tokenizer (`index.token_spans_for`).
- ADR 0005: a chunk may cover several sections; it is relevant when at least one of them is cited.
- `tests/integration/` with the `integration` marker applied per folder.
- Experiment configs: `configs/experiments/baseline.yaml`, validated by `load_experiment` (frozen, unknown fields and invalid values rejected with the file name).
- Data types `SectionRef`, `Chunk`, `RetrievedChunk`, `Citation`, `Answer`.
- `resolve_device`: `device: auto` uses CUDA only if a test computation succeeds, otherwise CPU with a warning.
- Phase 3 dependencies: `anthropic`, `numpy`, `sentence-transformers` + `torch` (CUDA build on Windows, CPU build on Linux CI), `lingua-language-detector`, `pyyaml`; `types-pyyaml` for mypy.
- `README.md`: project overview, unofficial-project notice, how the book and the golden set stay out of the repository.
- ADR 0004: the golden set is kept local.
- CI on GitHub Actions: every pull request and push to `main` runs all pre-commit hooks on all files.
- Pull request template with the definition-of-done, experiment, docs and copyright checklist.

### Changed
- Roadmap: Phase 3 split into 3a (retrieval baseline) and 3b (generation and judge); the minimal chat moves to Phase 4, right after the first complete pipeline; optimization and comparison phases become 5–8.
- Changes reach `main` through pull requests merged with a merge commit (`docs/steering/conventions.md`, "Git").
- `eval/datasets/golden.jsonl` is gitignored and refused by the `forbid-book-files` hook; `example.jsonl` stays the committed format example.
- The pull-quote test fixture is fully synthetic.
- Package and CLI renamed to `homerag` (`uv run homerag ...`), matching the repository; `book.json` schema 2 (field `homerag_version`): regenerate it with `homerag ingest`.

## [0.3.0] - 2026-11-19

Phase 2 — golden dataset: format, validation against the book and the first 40 hand-written questions.

### Added
- Golden dataset format: `GoldenQuestion` schema and `load_golden` (`eval/dataset.py`), with per-category rules; synthetic `eval/datasets/example.jsonl`.
- `check_references`: golden-set section ids must exist in the book and be indexed; enforced by `tests/book/test_golden.py` (ADR 0003).
- `homerag eval check`: validates the golden set against `book.json`.
- First golden set (`eval/datasets/golden.jsonl`): 40 hand-written questions covering every category, with paraphrased reference answers and section references.
- `homerag sections`: lists section ids, pages and excluded flags (no book text) in `data/processed/sections.txt`, to find the ids the golden set cites.
- The pre-commit `pytest` hook also runs on changes to `eval/datasets/*.jsonl`, so golden-set references are checked before every commit.
- Pre-commit hook `forbid-book-files`: refuses `data/`, `eval/runs/`, `*.epub` and `*.pdf` even after `git add -f`.
- Pre-commit hook `pytest`: the full test suite runs on every commit that touches Python files, `pyproject.toml` or `uv.lock`.
- Claude Code `Stop` hook (`.claude/hooks/check_done.py`): lint, types and unit tests before Claude ends a turn with code changes.
- Placeholder modules for Phase 3 (`chunking`, `index`, `retrieval`, `language`, `llm`, `qa`, `eval/`, `prompts/`), docstring only.
- `docs/working-with-claude-code.md`: Claude Code setup, planned skills and subagents.

### Changed
- All documentation translated to English (the project is built in public); answers are English only, as in the rest of the docs.

## [0.2.1] - 2026-11-18

### Added
- `inspect` check "words glued to numbers" (leftover note references).
- Generalization tests on public-domain ePubs from Standard Ebooks (`tests/corpus/`, marker `corpus`).

### Fixed
- A headingless section (e.g. a title page) became the parent of every following chapter (#12).
- File roles now also come from each file's own `epub:type`, most specific type first; imprint, colophon and lists of illustrations are excluded, notes and appendices included (#13).
- Note references and backlinks are stripped from the text instead of sticking to words (#14).

## [0.2.0] - 2026-11-18

Phase 1 — ingestion and inspection. Known open issues (#12–#14 in `docs/ingestion-findings.md`) affect other ePubs, not the reference book.

### Added
- `Block`: format-independent intermediate representation for ingestion.
- ePub loader (`load_epub`): reads documents in spine order and converts headings, paragraphs, list items and tables (as Markdown) into blocks.
- `homerag` CLI (typer) with the `dump` command: writes the raw loader output to `data/processed/blocks_dump.txt`.
- `figure` blocks: each image becomes a block carrying the caption of its container.
- Real-book regression tests (`tests/test_book_quality.py`, marker `book`), skipped when the book is absent.
- `docs/ingestion-findings.md`: findings from the book inspection, with rules and regression tests.
- Cleaner (`ingest/cleaning.py`): `merge_continued_tables` joins tables split across `<table>` elements; `attach_intro_to_untitled_tables` titles untitled tables with their intro paragraph.
- Cleaner rule `remove_pull_quotes`: drops pull quotes that repeat a sentence of a longer nearby block (157 removed on the book, 0 body paragraphs).
- `homerag dump --clean`: dumps the cleaned blocks to `blocks_clean.txt` (raw dump renamed `blocks_raw.txt`).

- `Block.role` (landmark type of the block's file, default `body`) and `Block.page` (printed-page label where the block starts, from EPUB page markers); both shown in the dump.

- Structurer (`ingest/structure.py`): sections from headings across files, stable path-based ids, roles with front-matter inference (#11), `include` policy, page ranges; `Book`/`Section` models.
- Generic quality report (`ingest/quality.py`) and the `homerag inspect` command: text coverage, headings, untitled tables, duplicates within a section, pages; exit code 1 on warnings.
- `book.json` with `schema_version` (`save_book`/`load_book`) and the `homerag ingest` command.

### Fixed
- Glossary definitions (`<dl>`/`<dt>`/`<dd>`) were dropped: each term is now a "term: definition" paragraph.
- Table titles in `<caption>` were dropped: they are now the first line of the table block.
- Merged cells (`rowspan`/`colspan`) shifted values into the wrong columns: the grid is now expanded.
- Figure captions were emitted as loose paragraphs.

## [0.1.0] - 2026-11-16

### Added
- Project bootstrap: architecture, roadmap, steering docs, ADR 0001.
- Tooling: uv, ruff, mypy --strict, pytest, pre-commit.
- `Settings` loading `ANTHROPIC_API_KEY` from `.env`.

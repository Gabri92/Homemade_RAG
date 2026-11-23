# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/) (0.x while in development).

## [Unreleased]

### Added
- Phase 3 dependencies: `anthropic`, `numpy`, `sentence-transformers` + `torch` (CUDA build on Windows, CPU build on Linux CI), `lingua-language-detector`, `pyyaml`; `types-pyyaml` for mypy.
- `README.md`: project overview, unofficial-project notice, how the book and the golden set stay out of the repository.
- ADR 0004: the golden set is kept local.
- CI on GitHub Actions: every pull request and push to `main` runs all pre-commit hooks on all files.
- Pull request template with the definition-of-done, experiment, docs and copyright checklist.

### Changed
- Changes reach `main` through pull requests merged with a merge commit (`docs/steering/conventions.md`, "Git").
- `eval/datasets/golden.jsonl` is gitignored and refused by the `forbid-book-files` hook; `example.jsonl` stays the committed format example.
- The pull-quote test fixture is fully synthetic.

## [0.3.0] - 2026-11-19

Phase 2 — golden dataset: format, validation against the book and the first 40 hand-written questions.

### Added
- Golden dataset format: `GoldenQuestion` schema and `load_golden` (`eval/dataset.py`), with per-category rules; synthetic `eval/datasets/example.jsonl`.
- `check_references`: golden-set section ids must exist in the book and be indexed; enforced by `tests/book/test_golden.py` (ADR 0003).
- `tricoach eval check`: validates the golden set against `book.json`.
- First golden set (`eval/datasets/golden.jsonl`): 40 hand-written questions covering every category, with paraphrased reference answers and section references.
- `tricoach sections`: lists section ids, pages and excluded flags (no book text) in `data/processed/sections.txt`, to find the ids the golden set cites.
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
- `tricoach` CLI (typer) with the `dump` command: writes the raw loader output to `data/processed/blocks_dump.txt`.
- `figure` blocks: each image becomes a block carrying the caption of its container.
- Real-book regression tests (`tests/test_book_quality.py`, marker `book`), skipped when the book is absent.
- `docs/ingestion-findings.md`: findings from the book inspection, with rules and regression tests.
- Cleaner (`ingest/cleaning.py`): `merge_continued_tables` joins tables split across `<table>` elements; `attach_intro_to_untitled_tables` titles untitled tables with their intro paragraph.
- Cleaner rule `remove_pull_quotes`: drops pull quotes that repeat a sentence of a longer nearby block (157 removed on the book, 0 body paragraphs).
- `tricoach dump --clean`: dumps the cleaned blocks to `blocks_clean.txt` (raw dump renamed `blocks_raw.txt`).

- `Block.role` (landmark type of the block's file, default `body`) and `Block.page` (printed-page label where the block starts, from EPUB page markers); both shown in the dump.

- Structurer (`ingest/structure.py`): sections from headings across files, stable path-based ids, roles with front-matter inference (#11), `include` policy, page ranges; `Book`/`Section` models.
- Generic quality report (`ingest/quality.py`) and the `tricoach inspect` command: text coverage, headings, untitled tables, duplicates within a section, pages; exit code 1 on warnings.
- `book.json` with `schema_version` (`save_book`/`load_book`) and the `tricoach ingest` command.

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

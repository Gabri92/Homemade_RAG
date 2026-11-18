# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/) (0.x while in development).

## [Unreleased]

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

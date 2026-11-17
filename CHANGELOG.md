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

### Fixed
- Table titles in `<caption>` were dropped: they are now the first line of the table block.
- Merged cells (`rowspan`/`colspan`) shifted values into the wrong columns: the grid is now expanded.
- Figure captions were emitted as loose paragraphs.

## [0.1.0] - 2026-11-16

### Added
- Project bootstrap: architecture, roadmap, steering docs, ADR 0001.
- Tooling: uv, ruff, mypy --strict, pytest, pre-commit.
- `Settings` loading `ANTHROPIC_API_KEY` from `.env`.

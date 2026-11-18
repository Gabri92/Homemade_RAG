# ADR 0002 — `ingest.py` becomes the `ingest/` package

- **Date:** 2026-11-17
- **Status:** accepted

## Context
`ingest.py` had reached 196 lines and was about to receive the Cleaner (roughly +100). Above all, it would have held code that changes for different reasons: the Loader changes with the file **format** (ePub today, probably PDF tomorrow), the Cleaner with the **defects in the data**, the dump with **inspection** needs. These are two of the growth signals listed in `structure.md`.

## Decision
Refactoring with no change in behaviour:
```
ingest/
  __init__.py   # public API: load_epub, html_to_blocks, format_blocks (then clean, ...)
  epub.py       # ePub Loader
  dump.py       # format_blocks
```
The Cleaner will arrive as `ingest/cleaning.py`, a PDF loader (if any) as `ingest/pdf.py`. Callers import only from `tricoach.ingest`: the existing tests pass unchanged, which proves the refactoring does not change behaviour.

## Alternatives considered
- **Stay in a single file** — simple for a little longer, but it mixes three reasons to change.
- **Separate flat modules** (`loader.py`, `cleaning.py` next to `ingest.py`) — scatters at the top of the package concepts that belong to a single pipeline stage.

## Consequences
- Adding a format or a cleaning rule touches a single file.
- The internal modules must not be imported directly from outside the package.

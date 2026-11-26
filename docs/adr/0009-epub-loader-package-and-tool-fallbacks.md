# ADR 0009 — The ePub loader is a package; a publishing tool's conventions are only fallbacks

- **Date:** 2026-11-26
- **Status:** accepted

## Context
The first ePub from Pressbooks, the open-textbook platform and a candidate document for the Phase 4a demo, brought three loader fixes (findings #17–#19). After them `ingest/epub.py` had 416 lines and five reasons to change: the ePub container, HTML-to-block conversion, tables, file roles, and one tool's conventions. Both of the signals in `structure.md` were there: more than ~300 lines, and several reasons to change in one module.

Pressbooks writes no `epub:type`, so the role of each file (title page, table of contents, chapter) has to be read from its own ids and classes. A first version of that rule read the classes of any first `<div>` and excluded 274 sections of the reference book (`div.sidenote`). Rules written for one tool can damage books made with another.

## Decision
- `ingest/epub.py` becomes the package `ingest/epub/`, with the same public functions (`load_epub`, `epub_text`, `html_to_blocks`, `landmark_types`, `role_from_types`). Each module has one reason to change:
  - `loader.py`: the container (spine, navigation, page carry-over between files);
  - `html.py`: one document to blocks;
  - `tables.py`: tables to Markdown;
  - `roles.py`: what each file is, from landmarks and `epub:type`;
  - `pressbooks.py`: Pressbooks conventions.
- **A tool's conventions are fallbacks only.** They apply where the EPUB semantics are missing, never on top of them. `roles.py` asks `pressbooks.py` only when a file declares no `epub:type`, and Pressbooks rules match only Pressbooks' own ids and classes. A book that declares its semantics is never touched by a tool's rules.
- Rules that hold for any HTML stay generic, in `html.py` or `cleaning.py`, even when one tool revealed them: note numbers in headings, a heading repeated right after itself, captions inside `<figure>`, text in `<div>`s without `<p>`.
- No registry of tools and no detection of the tool yet. There is one tool, and the ePubs in the corpus do not declare which tool produced them (no `generator` metadata), so detection would itself be a guess. The registry comes with the second real tool, one step at a time.
- Tests mirror the package (`tests/unit/ingest/epub/test_<module>.py`). The helpers that several of those files use (`blocks_of`, `page_marker`) live in `tests/conftest.py`.

The refactor moved code without changing behaviour. The ingestion of the reference book and of the four corpus books (sections and raw blocks) is byte-identical before and after.

## Alternatives considered
- **Keep one module**: about 420 lines and growing with every new tool or HTML pattern. It is the module most likely to change with Phase 4b uploads.
- **A `producers/` package with a registry now**: structure for tools that do not exist yet (YAGNI). It also needs a way to tell which tool made a book, and the files do not say.
- **Apply a tool's rules to every book**: simpler, but it already broke the reference book once.
- **A generic `pdf`/`epub` loader abstraction**: a PDF loader would share only `Block` and the steps after it, not the HTML or role code. It stays a separate file (`ingest/pdf.py`) when PDFs enter a roadmap phase.

## Consequences
- A new tool's conventions go in `ingest/epub/<tool>.py`, are called from the one place where semantics are missing, and come with a corpus book in `tests/corpus/`.
- An unknown tool degrades gracefully: its files come out as `body` and are included, and `homerag inspect` reports what looks wrong. For Phase 4b uploads, a tool-independent fallback based on content (a file made of links to other files is a table of contents) is still to be designed and measured on the corpus.
- `tables.py` repeats the one-line whitespace rule of `html.py` rather than importing it, to keep the import graph one-way (`loader` → `html` → `roles`/`tables`/`pressbooks`).

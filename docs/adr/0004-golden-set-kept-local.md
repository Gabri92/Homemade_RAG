# ADR 0004 — The golden set is kept local

- **Date:** 2026-11-20
- **Status:** accepted

## Context
The repository is about to get a remote (private for now, possibly public later). The golden set (`eval/datasets/golden.jsonl`) holds hand-written answers that paraphrase the book and section ids that mirror its structure: it is the part of the project closest to the copyrighted content. It is also useless without the book, which nobody else can get from the repository.

## Decision
- `eval/datasets/golden.jsonl` is gitignored and refused by the `forbid-book-files` pre-commit hook, like the other book derivatives.
- It was removed from the whole git history before the first push, so no version of it ever reaches the remote.
- `eval/datasets/example.jsonl` (synthetic, about an invented plan) stays committed as the format reference, and the schema in `eval/dataset.py` keeps it valid.
- The author keeps a backup of the file outside the repository.

## Alternatives considered
- **Commit it** (the original plan in `structure.md`): simpler, and the set would be versioned with the code. Rejected: it publishes book-derived content and the author's work.
- **A separate private repository** for the golden set: versioned and backed up, but one more thing to keep in sync. Possible later if the set grows.

## Consequences
- Evaluation runs only where the book and the golden set are present; elsewhere `tests/book/` is skipped as before.
- Changes to the golden set are not versioned by git: backups are the author's responsibility.

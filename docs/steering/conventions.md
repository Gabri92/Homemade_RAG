# Conventions

## Principles, in priority order
1. **KISS** — the simplest solution that works. Functions before classes; a class only if it holds state (e.g. an index loaded in memory).
2. **YAGNI** — no abstractions "for the future" (multilingual, coach, tools, athlete profile) until they are in the current roadmap phase.
3. **DRY** — a single source of truth for everything:
   - LLM calls only through `llm.py` (retries, cache, cost logging in one place);
   - parameters (models, k, chunk sizes) only in the config, never repeated in code;
   - prompts only in `prompts/`;
   - test fixtures only in `tests/conftest.py`.
   DRY applies to *knowledge*, not to code that happens to look alike: two repeated lines are better than the wrong abstraction. Extract on the **third** repetition.
4. **SOLID, pragmatically** — not as structure imposed up front, but as a criterion as the code grows:
   - *Single responsibility*: a function does one thing (a chunker does not compute embeddings);
   - *Open/closed*: a new strategy is a new function in the registry, not one more `if` in existing code;
   - *"Light" dependency inversion*: functions receive what they use as parameters (e.g. `answer(question, index, llm)`) instead of creating it inside. This is what makes tests easy.
   - `Protocol` and abstract classes only when there **really** are two stateful implementations.

## Python style
- Type hints everywhere; `mypy --strict` must pass. No `Any` without a comment justifying it.
- Data: `@dataclass(frozen=True, slots=True)`; `pydantic` only for what comes from outside (config, golden set, LLM JSON output).
- Descriptive names: `snake_case` for functions/modules, `PascalCase` for classes, `UPPER_CASE` for constants.
- Short functions (roughly < 40 lines); if a block needs a comment to be understood, extract it into a well-named function.
- Comments only for the *why*. Docstrings on the public functions of each module.
- No `print` outside `cli.py`: use `logging`.

## Errors
- Fail early with clear messages. Never `except Exception: pass`.
- A custom exception only when the caller must handle it differently.

## Tests
- **One kind of test, one folder:**

  | Folder | What | When it runs |
  |---|---|---|
  | `tests/unit/` | One function with synthetic data; mirrors `src/tricoach/` (`src/tricoach/ingest/cleaning.py` → `tests/unit/ingest/test_cleaning.py`) | Always; `uv run pytest tests/unit` during development (< 1 s) |
  | `tests/book/` | Ingestion on the real book against the values in `expectations.py` | With `uv run pytest`; skipped if the book is missing |
  | `tests/corpus/` | Generalization: the same ingestion on ePubs from other publishers (`data/corpus/`) | With `uv run pytest`; each missing book is skipped |
  | `tests/integration/` | (Phase 3) components with real APIs/models | Only with `-m integration` |
  | `tests/e2e/` | (Phase 3) question → cited answer | To be decided in Phase 3 |

  Markers and skips are applied **per folder** in its `conftest.py`, not file by file. The `integration/` and `e2e/` folders are created when their first test arrives.
- One `test_<module>.py` file per module; tests of pure functions without mocks.
- Tests are a package (`tests/__init__.py`): import explicitly, e.g. `from tests.conftest import MakeEpub`.
- External dependencies (LLM, embedding model) are replaced by passing a fake as a parameter, not with scattered `monkeypatch`.
- The strategies in a registry are tested with a single test parametrized over all entries.
- `cli.py`: one smoke test per command with typer's `CliRunner` (startup, error on invalid input, expected output). Logic is tested in the modules, not through the CLI.
- Standard tests are deterministic and offline; those calling real APIs or models are `@pytest.mark.integration`.
- Fixtures: a **synthetic mini-book** written by us, never text from the real book.
- Bug found → first a test that reproduces it, then the fix.

## Prompts
- One file per prompt in `src/tricoach/prompts/`, with the version in the name (`answer_v2.md`).
- A prompt used in an eval run is never modified: create a new version instead.

## Git
- Small commits, messages in English in Conventional Commits style (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `exp:` for experiments).
- One experiment = one commit with the config + a summary of the metrics in the message.
- **Branches:** `main` holds only finished work (definition of done green). Work happens on a branch per roadmap phase (`feat/phase-1-ingestion`) or per experiment (`exp/<name>`), with one commit per module or step. At the end of a phase: merge into `main` with `--no-ff`, so the phase stays visible in the history.
- Pre-commit hooks: ruff, mypy, the **full test suite** (on commits touching Python, `pyproject.toml`, `uv.lock` or the golden-set files in `eval/datasets/`), and `forbid-book-files`, which refuses book files (`data/`, `eval/runs/`, `*.epub`, `*.pdf`) even when they were added with `git add -f`. Never skip them with `--no-verify`.
- While Claude Code works, a `Stop` hook runs the fast part of the definition of done (lint, types, unit tests) before each turn ends (see `docs/working-with-claude-code.md`).

## Versioning
- **SemVer during 0.x**: the version lives only in `pyproject.toml` (single source).
  - *minor* (`0.2.0`) for every roadmap phase completed and merged into `main`;
  - *patch* (`0.2.1`) for fixes on `main`.
- **Annotated tag** `vX.Y.Z` on the merge commit into `main`.
- **`CHANGELOG.md`** (Keep a Changelog format): every `feat:`/`fix:` commit adds a line under `[Unreleased]`; at release time the section gets a number and a date.
- **Data artifacts:** `book.json` (constant `SCHEMA_VERSION` in `ingest/book_file.py`) and the indexes carry a `schema_version` (integer, bumped on every format change) and the `tricoach` version that produced them. An artifact with a schema other than the expected one must be regenerated, not read.

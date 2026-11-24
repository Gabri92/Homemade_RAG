# Working with Claude Code

This project is developed with [Claude Code](https://claude.com/claude-code) as a pair programmer. This page explains how the repository is set up for it and what is planned.

## How the repo is set up

| Piece | Where | Loaded | Purpose |
|---|---|---|---|
| Project instructions | `CLAUDE.md` | Every session | The always-valid rules (copyright, experiments, KISS, definition of done, language) and links to everything else |
| Steering files | `docs/steering/*.md` | Every session (imported by `CLAUDE.md` with `@`) | Product, tech, structure and conventions: the *principles* Claude should apply without being told |
| Reference docs | `docs/architecture.md`, `docs/roadmap.md`, `docs/adr/`, `docs/ingestion-findings.md` | On demand, when the related area is touched | Detail that would waste context if it were always loaded |
| Book-file guard | `.pre-commit-config.yaml`, hook `forbid-book-files` | On every commit | Refuses `data/`, `eval/runs/`, `eval/datasets/golden.jsonl`, `*.epub`, `*.pdf` even after `git add -f`: copyright protection that does not depend on anyone remembering a rule |
| Fast definition of done | `.claude/settings.json` (`Stop` hook) → `.claude/hooks/check_done.py` | When Claude is about to end a turn, if `.py` files have uncommitted changes | Ruff, format, mypy and unit tests (~3 s). On failure the error goes back to Claude, which keeps working instead of declaring the task done. One retry only, so it never loops |
| Full test suite | `.pre-commit-config.yaml`, hook `pytest` | On every commit that touches Python files, `pyproject.toml`, `uv.lock` or `eval/datasets/*.jsonl` | Unit + real book + corpus (~15 s): nothing enters the history with broken tests, whoever makes the commit |
| CI | `.github/workflows/ci.yml` | Every pull request and push to `main`, on GitHub | `pre-commit run --all-files`: the same hooks on the server, for commits that skipped the local ones. Real-book tests are skipped there (the book is never uploaded) |

### Three levels of checks

The definition of done is enforced at three moments, each with the right cost:

| Moment | What runs | Cost | Why there |
|---|---|---|---|
| End of each Claude turn with code changes | fast checks + `pytest tests/unit` | ~3 s | Immediate feedback while working, without slowing every answer |
| Every commit | `pytest` (full suite) | ~15 s | Commits are much rarer than turns, and that is where the guarantee matters |
| Every pull request and push to `main` | all hooks on all files, on GitHub (no book) | ~1–2 min | Independent of anyone's local setup: the last line before `main` |

### Each rule in the right mechanism

A rule written in a prompt is a *request*: the model usually follows it, but nothing guarantees it. The more a rule matters, the more it should move towards a mechanism that enforces it.

| Kind of rule | Best mechanism | Example here |
|---|---|---|
| Must *never* happen | A hard check (pre-commit hook, permission `deny` rule) | Never commit the book → `forbid-book-files` |
| Must *always* happen at a given moment | A Claude Code hook (`.claude/settings.json`) or a pre-commit hook | Definition of done before ending a turn and before every commit |
| A multi-step procedure | A skill (slash command) | `/experiment` (planned) |
| A focused job that benefits from its own context | A subagent | `eval-analyst`, `conventions-reviewer` (planned) |
| Context for one area of the code | Reference doc read on demand, or a nested `CLAUDE.md` in that folder | `docs/ingestion-findings.md` for ingestion work |
| Principles and taste | Steering files | KISS, "When to grow the structure" |

## Planned

Introduced only when they have something to work on (YAGNI): both depend on `homerag eval`, which arrives in Phase 3 (step 9 of Phase 3b in the roadmap).

### Skill: `/experiment`

A **skill** is a Markdown file (`.claude/skills/experiment/SKILL.md`) that describes a procedure step by step. It is run by typing `/experiment <name>`, and Claude can also pick it up on its own when a request matches its description. It turns a rule that today must be *remembered* (CLAUDE.md rule 2: "every change to the RAG pipeline is an experiment") into a procedure that is *executed* the same way every time:

1. create `configs/experiments/<name>.yaml` starting from the current best config, changing only the variable under test;
2. run `homerag eval run` on the baseline and on the new config (or reuse the cached baseline run);
3. run `homerag eval compare` and summarize the deltas per metric and per question category, plus the questions that got worse;
4. propose the `exp:` commit message with the metric summary;
5. if the config wins, draft the ADR.

### Subagents: `eval-analyst` and `conventions-reviewer`

A **subagent** is a Markdown file in `.claude/agents/` that defines a specialised assistant: its own instructions, a restricted set of tools, optionally a cheaper model. The main session delegates a task to it; the subagent works in a **separate context** and returns only its conclusion. This is the useful form of a "role": not a persona in the prompt ("you are a senior engineer"), but isolation of context and permissions.

- **`eval-analyst`** — reads two runs in `eval/runs/`, compares metrics and per-question outputs, and returns a short report: what improved, what regressed, in which categories, with examples. Read-only. It keeps hundreds of lines of run output out of the main conversation.
- **`conventions-reviewer`** — reviews a diff against `docs/steering/conventions.md` and `structure.md` only (KISS, one library per module, tests in the right folder, no logic in `cli.py`). Read-only. A narrow brief makes it stricter than a general review.

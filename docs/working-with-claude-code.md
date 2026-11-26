# Working with Claude Code

This project is developed with [Claude Code](https://claude.com/claude-code) as a pair programmer. This page explains how the repository is set up for it and what is planned.

## How the repo is set up

| Piece | Where | Loaded | Purpose |
|---|---|---|---|
| Project instructions | `CLAUDE.md` | Every session | The always-valid rules (copyright, experiments, KISS, definition of done, language) and links to everything else |
| Personal instructions | `CLAUDE.local.md` (gitignored) | Every session, on your machine only | Your own preferences, such as the chat language; never committed |
| Steering files | `docs/steering/*.md` | Every session (imported by `CLAUDE.md` with `@`) | Product, tech, structure and conventions: the *principles* Claude should apply without being told |
| Reference docs | `docs/architecture.md`, `docs/roadmap.md`, `docs/adr/`, `docs/ingestion-findings.md` | On demand, when the related area is touched | Detail that would waste context if it were always loaded |
| Book-file guard | `.pre-commit-config.yaml`, hook `forbid-book-files` | On every commit | Refuses `data/`, `eval/runs/`, `eval/datasets/golden.jsonl`, `*.epub`, `*.pdf` even after `git add -f`: copyright protection that does not depend on anyone remembering a rule |
| Secrets guard (commits) | `.pre-commit-config.yaml`, hook `forbid-secrets` | On every commit | Refuses `.env` and its variants (`.env.example` excepted), `CLAUDE.local.md`, `notes/` and `.claude/settings.local.json` even after `git add -f`: the repository is public, and `.gitignore` alone can be bypassed |
| Secrets guard | `.claude/settings.json` (`permissions.deny`: `Read(./.env)`, `Read(./.env.*)`) | Every session | Claude Code's file reading tool cannot open `.env`, so the API key never enters a conversation by mistake. The code still reads it; a shell command could too, so the rule is a guard against accidents, not a sandbox |
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
| Must *never* happen | A hard check (pre-commit hook, permission `deny` rule) | Never commit the book → `forbid-book-files`; never commit secrets or personal files → `forbid-secrets` |
| Must *always* happen at a given moment | A Claude Code hook (`.claude/settings.json`) or a pre-commit hook | Definition of done before ending a turn and before every commit |
| A multi-step procedure | A skill (slash command) | `/experiment` |
| A focused job that benefits from its own context | A subagent | `eval-analyst`; `conventions-reviewer` (planned) |
| Context for one area of the code | Reference doc read on demand, or a nested `CLAUDE.md` in that folder | `docs/ingestion-findings.md` for ingestion work |
| Principles and taste | Steering files | KISS, "When to grow the structure" |

## Experiments: the `/experiment` skill and the `eval-analyst` subagent

Added in v0.5.0, once `homerag eval run` and `eval compare` existed.

### Skill: `/experiment`

A **skill** is a Markdown file (`.claude/skills/experiment/SKILL.md`) that describes a procedure step by step. It runs when you type `/experiment <name> [what to change]`, and Claude can also pick it up on its own when a request matches its description. It turns a rule that must be *remembered* (CLAUDE.md rule 2: "every change to the RAG pipeline is an experiment") into a procedure that is *executed* the same way every time:

1. plan: base config, one variable, hypothesis, expected cost; wait for a yes before any paid run;
2. branch `exp/<name>` and `configs/experiments/<name>.yaml`, changing only the variable under test;
3. run `homerag eval run` on the new config, reusing the base run when it is comparable;
4. delegate the comparison to `eval-analyst`, check its numbers, decide (kept only if it improves the metric and category it was meant for);
5. `exp:` commit with the metric summary; if it wins, an ADR draft and a CHANGELOG line.

### Subagent: `eval-analyst`

A **subagent** is a Markdown file in `.claude/agents/` that defines a specialised assistant: its own instructions, a restricted set of tools, optionally a cheaper model. The main session delegates a task to it; the subagent works in a **separate context** and returns only its conclusion. This is the useful form of a "role": not a persona in the prompt ("you are a senior engineer"), but isolation of context and permissions.

`eval-analyst` (`.claude/agents/eval-analyst.md`, Sonnet, read-only) reads one or two runs in `eval/runs/`, interprets them with `docs/reading-a-run.md`, and returns a short report: verdict, per-part and per-category numbers, the questions to look at with their failure class, the next lever, and the cautions. It keeps run files out of the main conversation and never quotes the book. A new subagent is available from the next session after it is added.

## Planned

- **`conventions-reviewer`** (subagent): reviews a diff against `docs/steering/conventions.md` and `structure.md` only (KISS, one library per module, tests in the right folder, no logic in `interfaces/`). Read-only. Part of these rules is already checked by `tests/unit/test_architecture.py` (ADR 0012). A narrow brief makes it stricter than a general review. Added when reviews start to repeat the same remarks.

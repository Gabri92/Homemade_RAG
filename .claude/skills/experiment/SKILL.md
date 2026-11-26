---
name: experiment
description: Run one RAG pipeline experiment end to end - new config changing one variable, eval run, comparison with the base run, analysis, exp commit and, if it wins, an ADR draft. Use for /experiment <name>, or whenever a change to chunking, embedding, retrieval, prompt, generation or judge settings is about to be tried (CLAUDE.md rule 2).
argument-hint: <name> [what to change]
---

# /experiment

Every change to the RAG pipeline is a measured experiment (CLAUDE.md rule 2). This procedure runs one, always the same way. `$ARGUMENTS` holds the experiment name and, optionally, what to change; ask for what is missing. Chat with the user in their language (English unless `CLAUDE.local.md` says otherwise); everything written to the repository is in English.

## 1. Plan (confirm before spending)

- **Base**: the current best config. It is `configs/experiments/baseline.yaml` until an ADR names a winning config; check `docs/adr/` for the latest "winning config" decision.
- **One variable**: state the hypothesis ("structure-aware chunking improves `table`") and the single setting that changes. Two settings at once means two experiments.
- **Code first, if needed**: a new strategy is a function in its registry (`CHUNKERS`, `RETRIEVERS`, ...) with tests, following `docs/steering/structure.md`. It is committed before the experiment, as its own `feat:` commit.
- **Cost**: a full run costs about one US dollar the first time (answers + judge); only the answers whose prompt changes are paid again. A change to chunking or to the embedding model changes the chunks, so every answer is paid again. A retrieval-only run is free (`--retrieval-only`): use it when the change cannot affect answers beyond retrieval and the user agrees.
- Tell the user the plan and the expected cost in a few lines, and wait for a yes before any paid run.

## 2. Branch and config

- Branch `exp/<name>` from the branch the work is on (`git switch -c exp/<name>`).
- Copy the base config to `configs/experiments/<name>.yaml`, set `name: <name>`, change only the variable under test, and add a comment on the changed line saying what it was.

## 3. Run

- Base run: reuse the latest run of the base config in `eval/runs/` if its `meta.json` has `run_format` 2 and the same `golden_fingerprint` and `document_fingerprint` as a new run would; otherwise run it again (cached answers make it cheap).
- `uv run homerag eval run --config configs/experiments/<name>.yaml` (with `--retrieval-only` if agreed). Long runs go in the background.
- If the index must be rebuilt (chunking or embedding changed), `eval run` does it; say that the first run takes longer.

## 4. Compare and analyse

- Delegate the analysis to the `eval-analyst` subagent with the two run folders (base first). It runs `homerag eval compare` and returns the report.
- Check its numbers against `metrics.json` before relaying them. Relay the verdict, the per-part changes, the questions that got worse, and the cautions (small categories, judge not calibrated).
- **Decide**: the change wins only if it improves the metric and the category it was meant for, without making others clearly worse (roadmap, Phase 5, "One lever at a time"). Say the decision and why.

## 5. Record

- Commit on `exp/<name>`: the config (and nothing from `eval/runs/`, which is gitignored), with a message like:

  ```
  exp: <name> - <hypothesis in a few words>

  Base <base run>, candidate <new run>.
  retrieval: hit@5 0.77 -> 0.85, mrr 0.61 -> 0.70
  generation: correct 0.77 -> 0.80, faithful 0.97 -> 0.97; table correct 0.30 -> 0.60
  Decision: kept / not kept, because ...
  ```

- If it wins: draft an ADR in `docs/adr/` (template `0000-template.md`) recording the winning config and the numbers, and add a line to `CHANGELOG.md` under `[Unreleased]`. If it loses, the commit message is the record.
- Keep `docs/commands.md` and the steering files aligned if the experiment added a command or a strategy.
- Never push or merge: tell the user the branch is ready.

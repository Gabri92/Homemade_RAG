# ADR 0008 — Answers are graded by an LLM judge and by code-based checks, kept apart

- **Date:** 2026-11-24
- **Status:** accepted

## Context
From Phase 3b the pipeline writes answers, and every change must be measured on them, not only on retrieval. Reading every answer by hand does not scale to one run per experiment. The prompt-evaluation workflow (draft a prompt, a test set, run, grade, change, compare) needs a grader; some properties need judgement (does the answer agree with the reference?), others are mechanical (is there a citation?).

## Decision
- **LLM judge** (`eval/judge.py`, prompt `judge_v1`): one call per answer to a stronger model than the generator (`claude-opus-5-5`, effort `medium`). It receives the question, the hand-written reference answer, the sources the generator received and the answer, and returns a `Verdict` through structured outputs (JSON valid against the schema; assistant prefill is no longer accepted by current models): `reasoning` first, then `correctness` (correct 1 / partial 0.5 / incorrect 0), `faithful` (every claim supported by the sources) and `declined` (says the book does not cover it: right on `out_of_scope`, a false refusal elsewhere). Small scales are easier to calibrate against human labels than 1–10.
- **Code-based checks** (`eval/metrics.answer_checks`, free and deterministic): cites a real source, cites only real sources, answer in English (the gate's detector), and the longest run of words copied from one source, with `paraphrase` = at most `evaluation.max_copied_words` (20).
- The two kinds of score stay **separate metrics**, never averaged into one number: each points at a different fix.
- `eval run` runs gate, retrieval and generation, each scored on its own, with cost and latency per question; `--retrieval-only` keeps the free loop. `eval compare` shows changes per category and the questions that got worse. Judgements are cached like answers, so a repeated run costs nothing.
- Follow-ups are answered as written; condensing them is a Phase 6 experiment.

First full run (baseline, 30 answered questions, $1.14): correct 0.77, faithful 0.97, paraphrase 1.00, cites 0.93 (the missing ones are `out_of_scope` refusals), about 3.6 s per answer. Weakest: `table` correct 0.30 with declined 0.60, and `follow_up` 0.50. The wrong answers are mostly honest refusals when retrieval missed the section (hit@5 = 0), or answers that miss one key point: retrieval, not the prompt, is the first lever.

## Alternatives considered
- **Only an LLM judge**: it would also grade mechanical properties, at a cost and with noise, where code is exact.
- **One combined score** (mean of judge and code scores): one number to rank runs, but it hides which part failed.
- **A 1–10 scale**: the judge tends to drift to middling scores, and it is harder to compare with human labels.
- **One judge call per criterion**: about three times the cost, for criteria that share the same reading of the answer.

## Consequences
- The judge's numbers are indicative until it is calibrated against ~30 hand-labelled answers (Phase 6). Odd results are read per question in `results.jsonl`, where the judge's reasoning is saved.
- A run costs about $1 the first time; experiments that change only retrieval re-pay only the answers that change.
- Answer relevance and citation accuracy (does the cited source support *that* sentence) are not measured yet.
- Run files changed format (`RUN_FORMAT` 2): runs saved before v0.5.0 cannot be compared and must be run again.

# ADR 0006 — The language gate blocks only confident non-English messages

- **Date:** 2026-11-24
- **Status:** accepted

## Context
Questions and answers are English only for now (`docs/architecture.md` §4.1). A message in another language should get a fixed notice and stop before retrieval or any LLM call, so it costs nothing. The gate can make two errors with very different costs:
- **blocking an English question**: the user is told to write in English while writing in English. This is the worst error;
- **letting a non-English message through**: at worst a mediocre answer.

Detection on short text is unreliable. On synthetic messages, "LTHR?" comes out as German (0.45) ahead of English (0.40).

## Decision
- `language.is_english(text, detector, cfg)` with `lingua-py`, restricted to the configured languages (EN, IT, ES, FR, DE). It is local, deterministic and has no API cost. `language.py` is the only module that imports `lingua`.
- The gate **fails open**: a message is blocked only when it has at least `min_words` words **and** its most likely language is not English with confidence ≥ `min_confidence`. Everything else passes.
- The thresholds live in the experiment config (`language_gate`): `min_words: 3`, `min_confidence: 0.5` in the baseline.
- `homerag eval run` scores the gate on every golden question, separately from retrieval: accuracy, English questions blocked and non-English messages passed, plus the misjudged ids (`gate.json`). Retrieval metrics do not depend on the gate, so changing a gate threshold never moves them.

First measurement (baseline, 40 questions): 40/40 correct. The 10 non-English messages reach a confidence of 0.98–1.00. One English question has Italian as its most likely language (0.41) and passes only because it is below the 0.5 threshold.

## Alternatives considered
- **Pass only confident English** (fail closed): it blocks short and doubtful English questions, the costly error.
- **Ask an LLM to detect the language**: it adds cost and latency to every message, and it is not deterministic. It is the planned path for multilingual support (query processor), not for a yes/no gate.
- **Detection among every language lingua knows**: more candidates make short texts even less reliable, and the product only needs "English or not".
- **Raise `min_confidence` to fit the golden set** (non-English messages are at 0.98+): with 10 messages it would fit this set, not the problem. The threshold stays at 0.5 until more cases show it is wrong.

## Consequences
- The golden set has no short non-English messages: all 10 have 7 or more words. Short ones pass by design, so adding some would measure how often the gate lets them through.
- Uploaded documents follow the same rule (product.md, "Shared demo"). The upload check can reuse the detection on a sample of the text.
- Multilingual support replaces `is_english` with a query processor at the start of `qa.answer()`. Both rules (English questions, English documents) go away together.

# Golden set: Introduction to Exercise Science for Fitness Professionals

The first curated document of the Phase 4a shared demo: Amanda Shelton (ed.), *Introduction to Exercise Science for Fitness Professionals*, MHCC Library Press, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Download: https://mhcc.pressbooks.pub/hpe172 (EPUB export), into `data/corpus/exercise-science/`. Ingested with `homerag ingest ... --output data/processed/exercise-science/book.json`; the experiment config is `configs/experiments/exercise-science-baseline.yaml`.

Unlike the reference book's golden set (ADR 0004), this one is committed: the book's license allows it. Reference answers are still paraphrased key points, for evaluation reasons: the judge compares content, and a copied reference would reward answers that copy the book.

## How the questions are made

The book's author did not write this set, and neither did the project's author, who has not read the book. Most questions are written by an LLM and checked by a person against the passage. The method limits the bias this brings:

1. **Sections sampled by code, not chosen by the LLM.** Seed `20261126`. Included sections only. Sections of 120–1500 words, plus every section with a table; glossaries, chapter reviews, objectives, terminology, references and quizzes are skipped. Ten sections for `factual`/`conceptual`, one per chapter plus one more; three sections with a table; two pairs of sections of the same chapter for `multi_hop`.
2. **Written by a model that neither answers nor judges.** Generation uses `claude-sonnet-5-5` and the judge `claude-opus-5-5`, so the candidates were written by **Claude Haiku**. It ran as a Claude Code subagent that saw only the sampled sections, not the code or the pipeline's prompts. The prompt is below.
3. **Automatic checks** on every candidate:
   - **lexical overlap**: the share of the question's content words found in its passage. Above 60% the question is too easy for retrieval, and it goes back to the generator to be rewritten;
   - **copied run**: the longest run of words a key point copies from the passage. Above 8 it is flagged.
4. **Verification against the passage**, by Claude (Opus, in the Claude Code session), not by a person. Each candidate was checked for three things: is the reference answer in the passage, with nothing added or wrong? Does the question have one correct answer? Is it clear without the passage? Every section that also holds the answer was added to `relevant_section_ids`, so that retrieval is not penalised for finding it. People will review only the questions the pipeline gets wrong, because that is where an error in the set does harm.
5. **Human-written questions, kept apart** in `exercise-science-human.jsonl`: five questions written by hand without reading the book (translated to English), plus the `out_of_scope` and `follow_up` ones. If the pipeline scores much better on the generated questions than on the hand-written ones, the gap measures the generator's bias.

### Sampled sections

| Category | Section ids |
|---|---|
| factual, conceptual | `the-pelvic-girdle/the-lower-limb`, `nervous-system-control-of-muscle-tension/motor-units`, `metabolic-reactions/catabolic-reactions`, `creating-a-successful-fitness-plan/follow-through`, `creating-an-effective-stretching-program/applying-the-fitt-principle`, `the-heart`, `progressional-training`, `speed`, `types-of-resistance-training/4-isokinetic-training`, `measuring-intensity/the-karvonen-formula-or-heart-rate-reserve-method` |
| table | `planes-of-motion/axis-of-rotation`, `metabolic-reactions/hormonal-regulation-of-metabolism`, `modifications-to-breathing/high-altitude-effects` |
| multi_hop | `improving-range-of-motion/neuromuscular-system` + `improving-flexibility/proprioceptive-neuromuscular-facilitation-pnf-stretching`; `what-is-force/mechanical-energy` + `leverage` |

### Generation prompt (Claude Haiku)

```text
You write candidate questions for an evaluation set of a question-answering assistant over an
open textbook (Introduction to Exercise Science for Fitness Professionals, CC BY 4.0).

Input: a JSON file with three lists, each item with `id` (the section id) and `text`:
- `single`: for EACH section write exactly 2 candidates: one `factual` (a specific fact: a
  number, a definition, a named structure or method) and one `conceptual` (why / how / what is
  the difference / when to use).
- `table`: for EACH section write 2 `table` candidates whose answer needs the table in the
  section (its rows and columns), not only the prose.
- `multi_hop`: a list of PAIRS of sections. For EACH pair write 2 `multi_hop` candidates that
  can only be answered by combining information from BOTH sections.

Rules for every question:
1. Write it the way a fitness student or a gym-goer would ask it: natural, sometimes informal,
   one sentence. Never "according to the text/section/chapter/table".
2. Do not reuse the section's technical key terms when an everyday word exists, and do not copy
   any phrase of 4+ words from the section. The question must still be answerable from the
   section.
3. Self-contained: no "this", "the table above", "the figure".
4. Its answer must be fully supported by the given section(s), nothing else.

Rules for the reference answer, `key_points`: 1 to 4 short points, in your own words, that a
correct answer must contain. Keep specific values exactly (numbers, units, names of muscles or
methods). Never copy more than 8 consecutive words from the section.

Output: one JSON object per line:
{"category": "...", "question": "...", "key_points": ["..."], "relevant_section_ids": ["..."]}
```

Rewrite request for questions over the overlap threshold: *"rewrite only the question; keep category, key points and sections; describe the thing in everyday words or by its effect or use, instead of naming it with the section's terms, while keeping it answerable from the section"*.

### Results

The generator wrote 30 candidates: 10 factual, 10 conceptual, 6 table, 4 multi_hop. All section ids exist, and no key point copies more than 7 words in a row. 8 questions were over the overlap threshold. After the rewrite, 2 factual questions remain at 70%. They were kept, because a question about a precise fact sometimes needs its term.

The verification kept 21 candidates as they were, fixed 6 and dropped 3. The final `exercise-science.jsonl` has **27 questions**: 11 factual, 8 conceptual, 6 table, 2 multi_hop.
- **Fixed:**
  - two questions reworded so much that they no longer sounded like a person ("pieces of hard tissue" for bones, "birthday count" for age);
  - a key point that attributed a fact to the wrong example;
  - a question that asked two things, one of them overstated;
  - two questions whose answer also appears in other sections, now listed;
  - a key point that repeated a defect of the book (below).
- **Dropped:**
  - a question too vague to have one correct answer;
  - the two questions of the second `multi_hop` pair, which glued two unrelated questions together. The sampled pair was weak: one of its sections is a short story about nurses lifting patients.

The hand-written set has 10 questions: 3 factual, 1 conceptual, 1 table, 3 out_of_scope, 2 follow_up.

**Defects of the book itself**, kept out of the reference answers so the set measures faithfulness without rewarding errors:
- the table of planes of motion and axes of rotation pairs the planes with axes differently from standard anatomy;
- the table of anabolic hormones says insulin stores glucose "as glucagon" instead of glycogen.

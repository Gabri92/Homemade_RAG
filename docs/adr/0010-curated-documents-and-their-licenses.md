# ADR 0010 — Curated documents: license checks, attribution, and the files stay out of git

- **Date:** 2026-11-26
- **Status:** accepted

## Context
Phase 4a serves a few documents chosen by the author to the public. The roadmap asks for openly licensed documents in English, each with a small golden set, and an ADR on the documents and their licenses. The first one is *Introduction to Exercise Science for Fitness Professionals* (Amanda Shelton, MHCC Library Press), a Pressbooks open textbook.

What its license allows, checked on the ePub downloaded on 2026-11-26:
- The **text** is under **CC BY 4.0** ("except where otherwise noted"). The book is a remix of other open textbooks (*Health and Fitness for Life*, *OU Human Physiology*, *Body Physics*, *Human Anatomy*, OpenStax material), credited in its attribution statement.
- Some **images** carry other terms: a few Wikimedia Commons images under CC BY-SA 3.0, some in the public domain, and micrographs "provided by the Regents of University of Michigan Medical School © 2012" with no open license stated in the book.
- CC BY 4.0 lets anyone copy, redistribute and adapt the material, also commercially. In return each copy or adaptation must give the title, the author, the source, the license (with a link), and a note on changes, and must not suggest that the authors endorse the use.

## Decision
- **A curated document qualifies** if its text is under a license that allows public display and adaptation: public domain, CC BY or CC BY-SA, checked in the document itself. Documents under a non-commercial (NC) or no-derivatives (ND) license are not used: the project may be reused commercially, and the golden set adapts the text.
- **Only the text is used.** Images are not shown or indexed, so the exceptions on images do not reach the repository or the demo.
- **Attribution wherever the material appears:**
  - next to every committed file derived from the book (`eval/datasets/<document>.md`): title, author, source, license link, what was changed, and a no-endorsement note;
  - in the README, a section on third-party content;
  - in the demo, on the page of each document, with the same elements, from Phase 4a step 3.
- **The ePub is not committed**, even though its license would allow redistributing it:
  - it weighs 64 MB, and once committed it stays in every clone's history;
  - it contains the images under other terms;
  - the `forbid-book-files` hook refuses any `*.epub`, a guard for the copyrighted reference book that should have no exceptions.

  Instead, `tests/corpus/expectations.py` gives the download URL and the **SHA-256 of the edition** the golden set was written on. A corpus test fails if a different edition is in `data/corpus/`: the section ids the golden set cites change when the publisher updates the book.
- **Derived data is committed**: the golden sets, which are questions and paraphrased reference answers, with attribution. Extracted text, `book.json` and indexes stay in `data/` (gitignored), the same for every book.

## Alternatives considered
- **Commit the ePub** (or store it with Git LFS): it is allowed for the text, but it means 64 MB in the history, images under other terms, and an exception in the copyright guard.
- **Attach the ePub to a GitHub release**: it keeps git light and gives an archived copy if the publisher's URL disappears. It is still redistribution of the images. Kept as a fallback if the source goes away.
- **Accept NC documents**: there are more of them (several exercise physiology textbooks are CC BY-NC), but they close future reuse.

## Consequences
- Anyone can rebuild the evaluation: download the ePub, check its hash, ingest it, run `eval check` and `eval run`.
- If the publisher updates the book, the hash test fails. The golden set's section ids must then be checked against the new edition, or the old edition found again.
- Every new curated document repeats the check: the license in the document, the exceptions, the attribution file next to its golden set, and its hash in `expectations.py`.
- The repository itself still has no license file: the project's own code and docs are not yet licensed to others. That is a separate decision for the author.

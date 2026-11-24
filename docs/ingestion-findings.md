# Ingestion — problems found and fixes

Development document: it collects the defects found by inspecting the pipeline output (`homerag dump`, `homerag inspect`) and the ePubs' HTML, with the rule chosen for each and the test that keeps it from coming back.

- **Reference book:** *The Triathlete's Training Bible*, 5th ed., ePub (54 XHTML documents).
- **Generalization corpus:** three Standard Ebooks ePubs (see "Generalization tests").

> No text from the books here: only structure, counts and short titles.

## Fixes

| # | Problem | Rule | Where | Priority | Status | Regression test |
|---|---|---|---|---|---|---|
| 1 | Table titles lost (29 tables out of 37): the title is in the `<caption>`, the Loader only read the cells | `<caption>` text as the first line of the table block | Loader | High | ✅ | `test_table_caption_*`, `test_book_tables_keep_their_titles` |
| 2 | Merged cells (`rowspan`/`colspan`, 4 tables) shifted values across columns (e.g. Table 9.2) | Expand the grid by repeating the value in every covered cell: each row stays self-contained | Loader | High | ✅ | `test_table_rowspan_*`, `test_table_colspan_*`, `test_book_table_9_2_rows_keep_their_period` |
| 3 | Figures present only as caption paragraphs (39 figures + 5 tables published as images) | Each image becomes a `figure` block with the caption of its container; the caption is no longer a separate paragraph | Loader | Medium | ✅ | `test_figure_*`, `test_book_figures_are_kept` |
| 4 | Repeated pull quotes: 157 of the 214 `div.sidenote` repeat a sentence of the text, sometimes reworded | A paragraph is removed if it is a **complete sentence** of at least 5 words, if at least **50%** of its word trigrams appear in a block of the **same file**, and if it is at most **60%** as long as that block. Recognition by content, valid for any format (evaluation below) | Cleaner | High | ✅ | `test_pull_quote_*`, `test_book_pull_quotes_are_removed_and_nothing_else` |
| 5 | Front and back matter mixed with the content | Role per file from the **landmarks** in `nav.xhtml` (later extended by #13); glossary and appendices included, index and bibliography excluded | Loader (role in `Block.role`) + Structurer (`Section.include` from `INCLUDED_ROLES`: when in doubt include, never the index) | High | ✅ | `test_landmark_types_*`, `test_inclusion_depends_on_the_role`, `test_book_excludes_only_non_content_parts` |
| 6 | Print page numbers available (360 `epub:type="pagebreak"` markers; text labels: A, B, i–xix, 1–342; 168 in the middle of a paragraph) | `Block.page` = page of the last marker **before the first text** of the block (a mid-paragraph marker applies to the following blocks); the page carries over from one file to the next. When the Cleaner merges blocks, the page of the first block is kept | Loader | High | ✅ | `test_block_takes_the_page_*`, `test_book_every_body_block_has_a_page`, `test_book_table_11_1_is_on_its_printed_page` (p. 172, checked by hand in the XHTML: the marker sits at the start of the `<caption>`) |
| 7 | Image content not visible to a text RAG | Transcription/description with Claude's multimodality | Future (`roadmap.md`, "Later") | To be measured | 💤 | — |
| 8 | Split tables: Tables 9.3 and 9.4 are a 3-week plan published as 3 `<table>`s, only the first with a title (4 continuation tables) | An untitled table that **immediately** follows another table is its continuation: they are merged into a single block under the first one's title. Valid for any format (in PDFs tables break at every page change) | Cleaner | High | ✅ | `test_untitled_tables_right_after_*`, `test_book_split_weekly_plans_are_one_table` |
| 9 | Untitled tables (4 questionnaire scoring tables, ch. 5–6): the only context is the preceding paragraph; if chunking separates them they become meaningless numbers | If a table has no title and the **immediately preceding** block is a **paragraph** in the **same file**, that paragraph becomes the first line of the table block (like a `<caption>`) and is no longer a separate paragraph | Cleaner | High | ✅ | `test_paragraph_before_untitled_table_*`, `test_book_no_table_is_left_without_a_title` |
| 10 | **Glossary lost**: the 123 definitions are a definition list (`<dl>`/`<dt>`/`<dd>`), an element the Loader did not read (only the heading was left) | Each `<dt>` becomes a "term: definition" paragraph with all its `<dd>`s | Loader | High | ✅ | `test_definition_list_*`, `test_book_glossary_keeps_every_definition` |
| 11 | `praise.xhtml` (33 blocks of promotional reviews) is not in the landmarks, so it comes out as `body`. The landmarks also contain an error: "bodymatter" points to the cover | An **algorithmic** rule, valid for other books: (A) a file without a landmark **enclosed between two front-matter files** becomes `frontmatter`; (B) confirmation: if it has Arabic-numbered pages, a warning in the log. The first version ("before the last front landmark") was wrong: here the acknowledgments (p. xv) sit at the end of the ePub. Manual per-source override only if it ever becomes necessary | Structurer | Medium | ✅ | `test_unlisted_file_between_front_matter_files_*`, `test_book_excludes_only_non_content_parts` |
| 12 | **Structurer bug** (corpus): a file without headings and with a new role opens a fake level-1 section that becomes the **ancestor of every following chapter** (IDs like `frontmatter/xv`) | The fake section does not enter the hierarchy: after it, the heading stack starts empty again | Structurer | High | ✅ | `test_section_without_heading_is_not_an_ancestor_*`, `test_headingless_sections_are_never_ancestors` |
| 13 | **Incomplete roles** (corpus): in Standard Ebooks ePubs the landmarks list only 3–4 files; each file, however, declares its division and type with `epub:type` on `<body>`/`<section>` (`frontmatter`, `backmatter`, `dedication`, `colophon`, `appendix`…). Imprint, dedication, colophon and "uncopyright" came out as `body` and were included; multiple types like "backmatter endnotes" were not recognized | `role_from_types`: landmark types + the file's types (`<section>` then `<body>`); the **first specific type** wins (`chapter`/`part` = body), otherwise the division, otherwise body; vocabulary prefixes (`z3998:`) and genres ignored. Notes (`endnotes`, `translator-note`) included; imprint, colophon, list of illustrations excluded | Loader + Structurer | High | ✅ | `test_role_comes_from_the_most_specific_declared_type`, `test_load_epub_reads_the_type_each_file_declares`, `test_non_content_parts_are_excluded_*` |
| 14 | **Note references glued to words** (corpus): 8 / 142 / 439 `epub:type="noteref"` references in Slocum / Engels / Whymper turned into "summit12" → dirty tokens for BM25 | The Loader strips references (`noteref`/`doc-noteref`) and the return links in the notes (`backlink`); the note text stays in its section. `inspect` check "words glued to numbers" (lowercase word + number, with or without punctuation; codes like "AE1" excluded): 0 on Friel, 90 / 3 / 277 on the corpus before, 0 after | Loader + `inspect` | High | ✅ | `test_note_references_are_removed_*`, `test_numbers_glued_to_words_*`, `test_only_missing_page_markers_are_reported` |
| 15 | No page markers in the corpus ePubs | Correct behaviour: citations by section only, `inspect` warns | — | — | ✅ (expected) | `test_missing_page_markers_*` |
| 16 | **Duplicate section ids** (found while designing chunk ids, Phase 3): the numeric suffix for repeated paths could collide with a title that already ends in a number ("Workout", "Workout", "Workout 2" → `workout-2` twice). Not present in the reference book (its ids are unchanged), but possible in any uploaded document; chunk ids and golden-set references rely on unique section ids | The suffix keeps increasing until the id is unused in the book | Structurer | High | ✅ | `test_suffix_never_collides_with_a_title_that_ends_in_a_number` |

Legend: ✅ done · 🔶 partly · ⏳ to do · 💤 postponed.

## Structure of the reference ePub (for whoever touches the Loader)

- **Semantics:** inside chapters, `epub:type` appears only as `pagebreak`. The file roles (cover, dedication, preface, acknowledgments, epilogue, glossary, bibliography, index, copyright, about the author) are in the **landmarks** of the navigation page.
- **Tables:** 37 `<table>` elements; title in `<caption>` (29), merged cells in 4.
- **Images:** 64 `<img>`, alt text almost always generic (`alt="Image"`). Captions are paragraphs in the same container as the image (`div.inline_group`).
- **Boxes:** 214 `div.sidenote`, some of them pull quotes.

## Structurer: edge cases measured on the book

Measured on the blocks after the Cleaner (headings: 19 L1, 86 L2, 142 L3, 101 L4, 20 L5).

| Case | In the book | How it is handled |
|---|---|---|
| Skipped levels (e.g. L2 → L4) | **None** | The heading attaches to the last ancestor of a lower level ✅ `test_skipped_levels_*` |
| The hierarchy crosses files | The `ch13_sub*` files (workouts) start at L3/L4: they continue the chapter of the previous file | Hierarchy over the whole sequence of blocks, not per file ✅ `test_hierarchy_continues_across_files` |
| Duplicate headings | Mostly in the workouts: "AE1: Recovery" ×3, "Aerobic Capacity Workouts" ×4, "Swim/Bike/Run" ×2 | ID = path of headings (e.g. `appendix-c-bike-workouts/aerobic-endurance-workouts/ae1-recovery`), `-2` suffix if the path repeats ✅ `test_same_title_*`, `test_book_section_ids_are_unique` |
| Content before a file's first heading | 1 case (`ch13_sub08`, 1 block) | Belongs to the previously open section ✅ `test_hierarchy_continues_across_files` |
| Files without headings | `cover`, `title`, `dedication`, `copyright` | Section titled with the role (e.g. `copyright-page`), excluded from the index and never an ancestor of other sections (#12) ✅ `test_content_without_heading_*` |

Result on the book: **372 sections, 325 included**, 14 chapters, all IDs unique, every included section with pages (e.g. `…/11-rest-and-recovery/morning-warnings`, pp. 171–172). 24 sections are headings only (e.g. "PART I …") with no content of their own.

Effect of duplicate headings on RAG: the three "AE1: Recovery" sections can be told apart **only** by their path (the sport). The path will therefore have to travel with the chunks, otherwise retrieval cannot know which sport a workout is for.

## Generic quality report (`homerag inspect`)

Checks without expected values, so valid for any source (the basis for future automatic checks on user sources). On the reference book: no warnings.

| Check | Warns if | On the book |
|---|---|---|
| Text coverage (letters and digits of the blocks / of the source) | < 98% | 100.0% |
| Headings per level | no headings | L1 19 · L2 86 · L3 142 · L4 101 · L5 20 |
| Untitled tables (included sections) | > 0 | 0 |
| Duplicate paragraphs | repeated **within the same section** | 0 within a section, 1 across sections (identical note under two workouts in appendix E: intentional) |
| Words glued to numbers | > 0.2 per 10,000 words | 0 |
| Blocks with a page | < 95% | 100% |
| Informational | — | 325/372 sections included; 15/60 figures without a caption; 4 sections > 2000 words (the longest: glossary); 24 empty sections |

**Known, measured limitation:** text coverage sees **large** losses, not small scattered ones. Simulating the fixed bugs: without the glossary (#10) it drops to **97.0%** → warning; without table titles (#1) to **99.81%** → no warning. Small losses need targeted checks (like the tests on the real book).

Lesson from the first round: the duplicate check flagged every repetition; the only one found was intentional (same note under two workouts). It now warns only for repetitions within the same section, where they indicate a defect.

## Evaluation of rule #4 (pull quotes)

The rule was treated as a classifier: the 214 `div.sidenote` in the HTML act as labels, the remaining 1375 paragraphs are normal text that must **never** be removed.

| Variant | Pull quotes removed | Normal paragraphs removed |
|---|---|---|
| Overlap ≥ 0.5 only | 157 | 6 |
| + at least 5 words, ≤ 60% of the original's length, complete sentence | **157** | **0** |

The 6 errors of the first variant were of two kinds: very short texts quoted by a paragraph ("SIDEBAR x.y" headings, ISBN) and nearly identical paragraphs of equal length (workout variants in the appendix). Removing them would have lost content: hence the extra conditions.

Distribution useful for the future: a pull quote has 5–23 words (median 13), is in median 11% as long as the original paragraph and sits in median 3 blocks away from it.

**Boxes not removed (57): original content, rightly kept.** Verified in two ways:
- manual review of a sample at both ends of the score (0 and ~0.45): none has a second occurrence in the book;
- measurement: even the most similar ones share at most **7 consecutive words** with the closest paragraph (typically 4–6), i.e. common phrases on the same topic, not repeated sentences. None of the 57 texts appears twice in the book, with a single exception: the ch. 8 box identical to the "caption" of the second image of FIGURE 8.1 (isolated case, left as is).

Conclusion: threshold 0.5 confirmed, do not lower it. Final estimate on the book: precision 100%, recall ~100% (157 pull quotes out of 157). Review list: `data/processed/pull_quote_review.txt` (local).

## Generalization tests (corpus)

Three **Standard Ebooks** ePubs in `data/corpus/` (local; where to download them: `tests/corpus/expectations.py`):

- Whymper, *Scrambles Amongst the Alps* (59.7 MB, 145 figures, appendices, 439 note references);
- Slocum, *Sailing Alone Around the World* (2.5 MB);
- Engels, *The Condition of the Working Class in England* (0.7 MB, 142 note references).

**First run** (`homerag inspect` only, no code changes):

| Check | Engels | Slocum | Whymper | Reading |
|---|---|---|---|---|
| Text coverage | 100.0% | 100.0% | 99.9% | The Loader loses no text |
| Headings | L2: 20 | L2: 28 | L2: 39 | Chapters as `<h2>`: handled |
| Pages | 0% ⚠ | 0% ⚠ | 0% ⚠ | Expected (#15) |
| Sections > 2000 words | 11 (max 19,444) | 22 | 24 (max 15,778) | Chapters without subheadings: the chunker will have to split them |

The report did **not** see problems #12–#14: they surfaced by looking at section IDs and the HTML. `inspect` covers losses and coarse structure, not the correctness of roles and hierarchy.

**After the fixes** (#12–#14, v0.2.1): top-level chapters (`i`, `ii`… instead of `frontmatter/i`), only non-content parts excluded, appendices and notes included, the only warning is pages.

| | Engels | Slocum | Whymper |
|---|---|---|---|
| Included sections | 15 / 21 | 23 / 30 | 34 / 42 |
| Excluded | titlepage, halftitlepage, imprint, dedication, colophon, copyright-page | as Engels + loi | as Engels + epigraph, frontispiece, loi |
| Appendices included | — | — | 9 |
| Words glued to numbers | 0 | 0 | 0 |

## Regression tests

- **Reference book:** `tests/book/test_ingestion.py` (`book` marker), expected values in `tests/book/expectations.py`.
- **Corpus:** `tests/corpus/test_generalization.py` (`corpus` marker), expected values in `tests/corpus/expectations.py`.

Both run with the normal `uv run pytest`; a missing book is skipped automatically.

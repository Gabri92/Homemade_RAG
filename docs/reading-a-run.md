# Reading a run

How to read what `homerag eval run` prints and saves, and how to turn the numbers into the next change. The metrics are defined in `docs/architecture.md` §7 and ADR 0008; this page is about **interpreting** them. The `eval-analyst` subagent follows it when it reports on a run.

## The three parts

A run scores three parts of the pipeline, each on its own, so a change to one never moves the numbers of another:

| Part | Questions | Graded by | Cost |
|---|---|---|---|
| **Language gate** | all | code (expected language vs outcome) | free |
| **Retrieval** | those citing sections (not `out_of_scope`, `non_english`) | code (cited sections vs ranking) | free |
| **Generation** | all but `non_english` | LLM judge + code-based checks | about $1 per run, $0 when cached |

Read them in pipeline order: if the gate blocks a question, nothing else runs; if retrieval misses the section, the answer cannot be right. **Optimize upstream first.**

## The columns

Every number is a mean over the questions of a category (`n` is how many), then over all of them (`all`).

### Retrieval (higher is better)

| Column | Per question | Read it as |
|---|---|---|
| `hit@k` | 1 if one of the first k chunks covers a cited section | "did the answer have a chance?" `hit@5` is what the generator sees with `top_k: 5` |
| `recall@k` | share of the cited sections covered by the first k chunks | below `hit@k` when a question needs several sections (`multi_hop`) and only some came back |
| `mrr` | 1 / position of the first relevant chunk | how high the right chunk sits: 1.0 first, 0.5 second, 0.33 third |

### Generation: the judge

| Column | Per question | Better | Read it as |
|---|---|---|---|
| `correct` | 1 correct, 0.5 partial, 0 incorrect, against the hand-written reference | higher | the headline: is the answer right? |
| `faithful` | 1 if every claim is supported by the sources | higher | below 1 = the model added something the sources do not say (hallucination, or general knowledge) |
| `declined` | 1 if the answer says the book does not cover it | **depends** | on `out_of_scope` it should be 1.0 (refusal correctness); anywhere else it is a refusal, usually because retrieval missed the section |

### Generation: code-based checks (exact, free)

| Column | Per question | Better | Read it as |
|---|---|---|---|
| `cites` | 1 if the answer cites a real source | higher | below 1 outside `out_of_scope` = uncited claims; on `out_of_scope` a refusal needs no citation |
| `cites_ok` | 1 if every cited number has a source | higher | below 1 = the model cites sources that do not exist |
| `english` | 1 if the answer is in English | higher | should always be 1 |
| `copied` | longest run of words copied from one source | lower | how close to the text the answer stays; a mean around 10 is normal phrasing of terms and short phrases |
| `paraphrase` | 1 if `copied` ≤ `evaluation.max_copied_words` | higher | below 1 = an answer copies a long passage (copyright and "paraphrase" rule) |
| `cost_usd` | answer + judge cost of the question | lower | what one question costs to answer and grade, even when served from the cache |
| `latency_s` | seconds for the answer call when it was made | lower | what a user waits for the model, without retrieval |

### Language gate

`accuracy`, plus the two errors counted apart: **English blocked** (the worst error: a legitimate question refused) and **non-English passed** (mild: a mediocre answer). The misjudged ids are printed.

## From symptoms to causes

| Symptom | Likely cause | Where to look | Lever |
|---|---|---|---|
| `correct` low, `declined` high, `hit@5` low | retrieval missed the section; the model honestly refused | `retrieval.retrieved` in `results.jsonl` vs `cited` | retrieval (Phase 5: chunking, hybrid search, reranker) |
| `correct` low, `declined` high, `hit@5` high | the section came back but not the part with the answer (e.g. a table split across chunks) | the cited section's chunks (`homerag search "<question>" --text`, local only) | structure-aware chunking, chunk size |
| `correct` 0.5 (partial) with `faithful` 1 | the answer misses a key point the sources may hold | judge `reasoning` | prompt (completeness), or `top_k` if the missing point is in a chunk ranked 6th+ |
| `faithful` below 1 | the model added claims not in the sources | judge `reasoning`, the answer | prompt (grounding rules) |
| `declined` below 1 on `out_of_scope` | the model answered from general knowledge | the answer | prompt (refusal rule) |
| `follow_up` low across the board | follow-ups are retrieved and answered without the earlier question | `follow_up` rows | condensing follow-ups (Phase 6) |
| `cites_ok` below 1 | citations to missing sources | the answer's `[n]` | prompt (citation format) |
| `paraphrase` below 1 | an answer copies a long passage | `copied` per question | prompt (paraphrase rule); check before sharing any output |
| `correct` high but `faithful` low | right answers from general knowledge, not from the book | judge `reasoning` | prompt (grounding); retrieval if the book's answer was not retrieved |

## Cautions

- **Small categories move in big steps.** With 3–8 questions per category, one question changes a category mean by 0.12–0.33. Read changes per question (`eval compare` lists them), not only as means.
- **The judge is not calibrated yet** (Phase 6). Its grades are indicative: when a result looks odd, read its `reasoning` in `results.jsonl` before trusting the number.
- **Cached runs.** `cost_usd` and `latency_s` are what the call cost and took when it was made, even when this run read it from the cache. `cost: ... (paid in this run ...)` says what was actually spent.
- **Comparable runs** share the golden set (`golden_fingerprint` in `meta.json`) and the book (`document_fingerprint`). Otherwise differences may come from the data, not from the change.

## Where the details are

A run folder `eval/runs/<date-time>-<name>/` (gitignored: answers paraphrase the book) holds:

- `metrics.json`: the tables above (`retrieval`, `generation`, `gate`), per category;
- `results.jsonl`: one row per golden question with `gate` (`passed`, `correct`), `retrieval` (`cited`, `retrieved` with chunk ids, sections and pages, `metrics`) and `generation` (`answer`, `citations`, `usage`, `verdict` with the judge's `reasoning`, `judge_usage`, `metrics`);
- `meta.json`: versions, fingerprints, costs, `retrieval_only`;
- `config.yaml`: the exact config of the run.

`homerag eval compare <run_a> <run_b>` prints the changes per category and the questions that got worse or better. Never paste answers, judge reasoning or chunk text into issues, posts or commits: they paraphrase or quote the book.

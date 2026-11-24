# Architecture — Homemade RAG

> A NotebookLM-style Q&A assistant over source documents. Reference document: *The Triathlete's Training Bible* (called "the book" below).
> Primary goal: understand RAG in practice and **measure its quality**.
> Language: **English only** for questions and answers.
> Out of scope (for now): multilingual, and anything beyond answering questions about the source documents.

---

## 1. Knowledge model: why the book is not "just text"

The book holds several kinds of content, which behave very differently in a RAG system:

| Kind | Examples | Problem in RAG | Strategy |
|---|---|---|---|
| **Narrative prose** | training philosophy, limiters, recovery, tapering | Few problems: the ideal case | Chunking by section, semantic retrieval |
| **Tables and numeric rules** | zone percentages of LTHR, weekly hours by period/annual hours, mesocycle length | A naive chunker **splits tables**; embeddings capture numbers poorly; the LLM tends to "interpolate" invented values | Extract tables as **atomic units** (never split), in Markdown, with a textual caption describing what they contain |
| **Workout descriptions** | workout codes and descriptions by ability | Very similar to each other → retrieval confuses neighbouring workouts | One chunk per workout + metadata (sport, ability, period) |
| **Figures and image tables** | charts, illustrations, some tables published as images | They are pixels: a text RAG cannot see their content. Image tables are the most critical (numbers) | **Now:** a `figure` block with just the caption, so we know a figure was there. **Future:** transcription/description with Claude's multimodality (see roadmap, "Later") |

**Golden rule:** when an answer depends on a number, that number must come *literally* from a retrieved, cited chunk.
Handling these contents well during chunking is what makes Q&A reliable — and it is an excellent test bed for evaluation.

---

## 2. Overview

Three pipelines, connected only by two artifacts on disk: `book.json` and the index.

| Pipeline | Steps | Produces | Re-run when | Phase |
|---|---|---|---|---|
| **Ingestion** (offline) | Loader → Cleaner → Structurer | `data/processed/book.json` | a book defect is fixed (rarely) | 1 ✅ |
| **Indexing** (offline) | Chunker → Enricher → Embedder → Index | `data/index/` | every experiment that changes chunking or embeddings | 3–4 |
| **Query** (online) | Language gate → Retriever → Reranker → Generator | answer + citations | every question | 3–5 |

The split follows how often each part changes: experiments start from the same `book.json` and never re-run ingestion. The golden set cites section ids from `book.json`, not chunks, so it survives every indexing experiment (ADR 0003).

```mermaid
flowchart LR
  subgraph Ingestion [Ingestion - offline]
    A[PDF / ePub] --> B[Loader]
    B --> C[Cleaner]
    C --> D[Structurer<br/>chapters, sections, tables]
  end

  BJ[(book.json<br/>sections with stable ids)]

  subgraph Indexing [Indexing - offline, per experiment]
    E[Chunker] --> F[Enricher<br/>metadata, context]
    F --> G[Embedder]
    G --> H[(Index<br/>vector + BM25)]
  end

  subgraph Query [Query - online]
    Q[User question] --> S[Retriever<br/>dense + BM25]
    S --> T[Reranker]
    T --> U[Context builder]
    U --> V[Generator LLM]
    V --> W[Answer + citations]
  end

  subgraph Eval [Evaluation - offline, per experiment]
    X[(Golden dataset)] --> Y[Runner<br/>asks each question]
    Y --> M[Scoring<br/>retrieval + answers]
    M --> Z[Report<br/>per category]
  end

  %% Links between pipelines, kept outside the subgraphs so each node stays in its own box.
  D --> BJ
  BJ --> E
  H --> S
  Y -- question --> Q
  S -. retrieved sections .-> Y
  W -. answer .-> Y
  X -. expected sections + answers .-> M
  BJ -. section ids checked .-> X
```

The evaluation pipeline acts as a fake user: the runner sends each golden question into the query pipeline, which runs unchanged, and collects what it retrieved and what it answered. Retrieval is scored against `relevant_section_ids` without any model; the answer is scored by the judge against `reference_answer`. Real users never go through evaluation: it runs only when an experiment is launched.

---

## 3. Ingestion and indexing pipelines

### 3.1 Ingestion (`homerag.ingest`, `homerag ingest`)

| Step | Responsibility | Practical notes |
|---|---|---|
| **Loader** | Extracts raw text from PDF/ePub | ePub is much cleaner than PDF (the HTML structure is already there). For PDF: `pymupdf`. |
| **Cleaner** | Removes headers/footers, page numbers, hyphenation, artifacts | Always inspect the output by hand: this is where half of the quality problems start. |
| **Structurer** | Rebuilds the hierarchy: part → chapter → section; isolates tables and sidebars | Produces a structured `Book`, saved as `data/processed/book.json` (with `schema_version`). |

### 3.2 Indexing (`chunking.py`, `index.py`; from Phase 3)

Starts from `book.json` and is re-run for every experiment config.

| Step | Responsibility | Practical notes |
|---|---|---|
| **Chunker** | Splits the included sections into `Chunk`s; each chunk keeps the ids of the sections it covers | Interchangeable strategies (see §5). The section ids link retrieval metrics to the golden set: a chunk is relevant when it covers a cited section (ADR 0005). |
| **Enricher** | Adds metadata and, optionally, generated context | `chapter`, `section`, `page`, `content_type` (prose/table/workout), `sport`. |
| **Embedder** | Computes vectors | Interchangeable model (see §6). |
| **Index** | Persists vectors + lexical index | For one book (~1–3k chunks) an in-memory / on-file index is enough. |

Each pipeline ends in an artifact on disk (`book.json`, the index) → it can be inspected, versioned (locally) and only the changed pipeline re-run.

---

## 4. Query pipeline

1. **Language gate** — a local, deterministic check: if the message is not in English, it returns a notice and **the pipeline stops** (no retrieval, no LLM calls). See §4.1.
2. **Retriever** — hybrid:
   - *dense* (cosine similarity between embeddings) → captures meaning;
   - *BM25* (lexical) → captures exact terms ("Build 2", "LTHR", "Zone 5b").
   - Fusion with **Reciprocal Rank Fusion (RRF)**. Retrieves a wide top-k (e.g. 20–30).
3. **Reranker** — a cross-encoder reorders the candidates and keeps the best (e.g. 5). Usually the biggest single improvement.
4. **Context builder** — formats the chunks with ID and reference (chapter/section/page), deduplicates, respects a token budget.
5. **Generator** — the LLM answers **only** from the context, cites chunk IDs, and says "not in the book" when needed. It always answers in English.

### 4.1 Language: English only (for now)

Questions and answers are **English only**, the same language as the book. This way retrieval has no cross-language issues (BM25 and embeddings compare English text with English text) and the pipeline stays simple.

**Language gate** — the first step of the pipeline, before any cost:
- **local, deterministic** detection with `lingua-py`, restricted to a small set of languages (EN, IT, ES, FR, DE) to be more accurate;
- non-English message → the pipeline returns a fixed notice and **does not run the query**:
  > *"I can only answer questions in English for now. Please rephrase your question in English."*
- **very short messages** (e.g. fewer than 3 words: "LTHR?", "Build 2") or low confidence → **let through**. Detection on short texts is unreliable, and blocking a legitimate question is worse than letting a doubtful case through;
- the method's terms (Build, LTHR, Zone 5b) are already English, so they cause no problems.

**Documents too:** the same rule applies to the source documents. Uploaded documents (shared demo) must be in English: at upload time a sample of the extracted text goes through the same detection, and a non-English document is rejected with a clear message. On long texts detection is far more reliable than on short questions.

The gate is a single function (`is_english` in `language.py`), called at the start of `answer()`: when multilingual support arrives, it is replaced there.

### Conversation design (Q&A)

- **Language:** English only; messages in other languages get the language gate notice.
- **Persona:** an expert, concise assistant who cites sources ("Friel, ch. 7 — Base period").
- **Grounding:** no claim without a citation; if the context is not enough it says so explicitly instead of using general knowledge.
- **Guardrails:** no medical diagnoses; on pain/injuries it refers to a professional.
- **Copyright:** summarizes and paraphrases, does not reproduce long passages verbatim.
- **Multi-turn:** a follow-up question is rewritten as a standalone question (*condensation*) before retrieval: "and how long does it last?" → "How long does the Build period last?".

---

## 5. Chunking strategies (to compare)

| Strategy | Description | When it wins |
|---|---|---|
| **Fixed-size + overlap** | N tokens with overlap over the running text of the book, ignoring section boundaries (a chunk may cover several sections) | Baseline: simple, gives a reference point |
| **Structure-aware** | One chunk per section/subsection, split only if too long; tables intact | Well-structured books like this one |
| **Semantic** | Split where the meaning changes: consecutive sentences with low embedding similarity mark a boundary, with a maximum size | Documents with little structure (e.g. uploaded files without useful headings) |
| **Contextual chunking** | Each chunk is prefixed with 1–2 LLM-generated sentences that place it in the book ("This passage, from the chapter on the Base period, describes…") | Chunks that are ambiguous on their own (pronouns, "this period") |
| **Parent-child** | Small chunks are indexed, but the wider "parent" section is passed to the LLM | Questions that need wide context |

The strategies answer three different questions, so they combine across axes and are alternatives within one axis:

| Axis | Question | Strategies |
|---|---|---|
| **Where to cut** | How is the text divided? | fixed-size, structure-aware, semantic (they can be nested: e.g. semantic splits inside sections that are too long) |
| **What to add to a chunk** | Is the chunk understandable on its own? | contextual chunking |
| **What to give the LLM** | The retrieved piece, or something larger? | parent-child |

Chunk size and k are parameters of all of them. When a second axis arrives, it becomes its own step (an enricher after the chunker, a parent lookup after retrieval), so any splitter can be combined with it without one function per combination.

---

## 6. Initial technology choices

Every external library lives in a single module (see §8): changing it touches one file.

| Component | Initial choice | Alternative to try |
|---|---|---|
| Language | Python 3.12+, managed with `uv` | — |
| Extraction | `ebooklib` + `beautifulsoup4` (ePub) / `pymupdf` (PDF) | — |
| Embedding | local `BAAI/bge-m3` (free; multilingual, so already ready for the future) | Voyage AI (API) |
| Vector index | in memory with `numpy` (brute force: with few chunks it is instant and instructive) | LanceDB / Qdrant |
| Lexical | `rank-bm25` | — |
| Reranker | local `BAAI/bge-reranker-v2-m3` | Rerank via API |
| Language gate | local `lingua-py` (no LLM call) | — |
| Generation LLM | Claude (`claude-sonnet-5-5`) via the `anthropic` SDK | — |
| Judge LLM (eval) | Claude (`claude-opus-5-5`) | — |
| Config | YAML + `pydantic` | — |
| UI (later) | CLI → Streamlit/Gradio | — |

**Long-context baseline:** besides RAG, we implement a `Generator` that receives **the whole book** in context (with prompt caching), if it fits in the model's window. Comparing it with RAG in the eval is the most instructive way to understand when RAG is really needed.

---

## 7. Evaluation

Evaluation is the heart of the project: **every change to the pipeline is a measured experiment**.

### 7.1 Golden dataset

File `eval/datasets/golden.jsonl`, one line per question (format: `GoldenQuestion` in `eval/dataset.py`; synthetic examples in `eval/datasets/example.jsonl`):

```json
{
  "id": "q-042",
  "question": "How long does the Base period typically last and how is it divided?",
  "category": "factual",
  "reference_answer": "…hand-written paraphrase…",
  "relevant_section_ids": ["<Section.id from book.json>"],
  "language": "en"
}
```

| Field | Rule |
|---|---|
| `id` | `q-` + at least 3 digits, unique in the file |
| `reference_answer` | Hand-written **paraphrase**, never a quote. The file is gitignored and kept local (ADR 0004), but written as if it could be shared. Required, except for `non_english` where it is absent |
| `relevant_section_ids` | `Section.id` values from `book.json` (ADR 0003). At least 1; at least 2 for `multi_hop`; none for `out_of_scope` and `non_english` |
| `previous_id` | Only and always for `follow_up`: the id of an earlier question in the file |
| `language` | ISO 639-1, default `en`. It is the expected gate outcome: `en` passes, anything else is blocked. Only `non_english` has a language other than `en` |

`uv run homerag eval check` validates the file and checks that every cited section exists in `book.json` and is indexed; `tests/book/test_golden.py` runs the same check on every full test run.

- **50–100 questions** written by hand (time well spent: you read them and understand the book).
- **Categories** (to see *where* the pipeline fails):
  - `factual` — a fact in one precise place;
  - `table` — the answer is in a table (numbers);
  - `conceptual` — explanation of a concept;
  - `multi_hop` — needs several sections;
  - `out_of_scope` — not in the book → the correct answer is to say so;
  - `follow_up` — second question of a conversation;
  - `non_english` — a message the language gate must block.
- **Synthetic** questions generated by the LLM from the chunks help increase volume, but must be **reviewed by hand**.
- All questions in **English**, plus a `non_english` category (~10 messages in IT/ES/FR) to test the language gate. For these the expected answer is the notice, with zero chunks retrieved. Edge cases that must **pass** the gate (short messages, English with a foreign term) are ordinary questions with `language: "en"`.
- References are **section ids**, not chunk ids, so they do not depend on the chunking strategy: a retrieved chunk is relevant when it comes from a cited section (ADR 0003).

### 7.2 Retrieval metrics (deterministic, cheap)

| Metric | Question it answers |
|---|---|
| **Hit rate@k** | Is at least one relevant chunk in the top k? |
| **Recall@k** | What fraction of the relevant chunks is in the top k? |
| **MRR** | How high does the first relevant chunk appear? |
| **nDCG@k** | Overall quality of the ranking |

If retrieval is poor, no prompt will save generation: optimize retrieval **first**.

### 7.3 Generation metrics (LLM-as-judge)

| Metric | What it measures |
|---|---|
| **Faithfulness / groundedness** | Is every claim supported by the retrieved context? (anti-hallucination) |
| **Answer correctness** | Does the answer agree with the `reference_answer`? |
| **Answer relevance** | Does it really answer the question? |
| **Citation accuracy** | Do the cited chunks really support the sentences they are attached to? |
| **Refusal correctness** | On `out_of_scope`, does it say "not in the book" instead of inventing? |
| **Gate accuracy** | Does the language gate block non-English messages and let English ones through? *Deterministic*: precision/recall on blocking, no judge. A false block on an English question is the most serious error. |

Good practices for the judge:
- **Explicit rubric** with a small scale (e.g. 1–3 or pass/fail) and reasoning before the score.
- **Calibration:** label ~30 answers by hand and measure agreement with the judge before trusting the numbers.
- A judge from a different/stronger model than the generator, temperature 0.

### 7.4 Experiments

- Each experiment = a `configs/experiments/<name>.yaml` file (chunker, embedder, k, reranker, prompt, model).
- The runner saves to `eval/runs/<timestamp>-<name>/`: the config used, per-question output, aggregate metrics **per category**.
- A report compares two runs side by side (metric deltas + questions that got worse).
- **Cost and latency** per question are tracked too.

---

## 8. Code design

Simple: functions in a few modules (see `docs/steering/structure.md`). The variants to compare in experiments are **functions with the same signature in a dictionary**, picked by name from the config:

```python
# chunking.py
CHUNKERS = {"fixed": fixed_size_chunks, "sections": section_chunks}

# retrieval.py
RETRIEVERS = {"dense": dense_search, "bm25": bm25_search, "hybrid": hybrid_search}


# qa.py
def answer(question: str, index: Index, llm: LLM, cfg: QAConfig) -> Answer:
    if not is_english(question):
        return Answer.not_english()
    candidates = RETRIEVERS[cfg.retriever](question, index, cfg.top_k)
    context = (
        rerank(question, candidates, cfg.rerank_k) if cfg.rerank else candidates[: cfg.rerank_k]
    )
    return generate(question, context, llm, cfg.prompt)
```

An experiment = a new config, not a code change. `index` and `llm` are passed as parameters, so tests replace them with fakes.

---

## 9. Data and copyright

- The book (`data/raw/`) and all its derivatives (`data/processed/`, `data/index/`) **must never be committed** (they are in `.gitignore`, and a pre-commit hook refuses them).
- Strictly personal use with a legally owned copy. The book is never distributed: the planned shared demo (`docs/steering/product.md`, "Shared demo") serves only the documents each visitor uploads, not the reference book.
- Uploaded documents are third-party data: they stay in the visitor's session, are never shared between visitors and are deleted with their indexes. Terms of use and deletion must be settled before the demo link goes out.
- DRM-protected files are not supported: the loader rejects them with a clear message, and the project never removes DRM.
- Indexes are kept per document (`data/index/<document>/...`), with no global state in the query pipeline: the same code serves the reference book locally and one uploaded document per visitor.

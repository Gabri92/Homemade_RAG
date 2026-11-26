# ADR 0011 — Web chat with Gradio, and a source panel to check every answer

- **Date:** 2026-11-26
- **Status:** accepted

## Context
Phase 4a, step 3 needs a web chat over the existing pipeline: pick a document, ask a question, read the answer with its citations. It runs on this machine first; later the same page is hosted for the public demo (steps 4 and 5). The roadmap left the choice between Streamlit and Gradio to the start of the phase.

Requirements from the steering files:
- **no logic in the UI.** The page calls `qa` and lays out what comes back, as `cli.py` does;
- **one external library, one module;**
- **tests without a browser or an API call.**

The reader is often someone who does not know the document. A two-line excerpt next to a citation does not let them check anything. They need the text the model actually read, and its context.

Both libraries were measured on the current lockfile (Python 3.12, Windows, 2026-11-26). The table counts only the packages each one adds on top of what the project already installs:

| | Gradio 6.32 | Streamlit 1.67 |
|---|---|---|
| New packages | 22 (fastapi, uvicorn, starlette, httpx, pandas, pillow, …) | 24 (pyarrow, pandas, altair, pydeck, protobuf, tornado, …) |
| Size on disk | about 143 MB (gradio 78, pandas 40) | about 236 MB (pyarrow 87, pandas 40, streamlit 33) |
| Chat with collapsible items | `Chatbot` messages with a `metadata` title open and close in place | `st.chat_message` plus `st.expander` |
| Execution model | event handlers (plain functions) bound to components | the whole script reruns on every interaction |
| Hugging Face Spaces | built-in SDK | the built-in SDK is deprecated since April 2025: Docker template |
| Concurrency | a request queue with limits, built in | one thread per session |
| Tests | the handlers are plain functions; `build_app` builds the page without serving it | `AppTest` runs the script headless |
| Import time | about 6 s | not measured |

## Decision
- **Gradio**, imported only in `src/homerag/chat.py`. It is the lighter of the two, hosts natively on Hugging Face Spaces, and has a request queue that the cost limits of step 4 can build on. Its chat messages can be collapsed, which gives citations that open in place with no extra code.
- **Two depths to check a citation:**
  1. *In the chat:* each cited chunk is a collapsed message under the answer, titled `[n] Chapter > Section, p. 12`. Opened, it shows the whole chunk: exactly the text the model read as source `[n]`.
  2. *In the source panel:* next to the chat, the whole cited section, with the chunk's part highlighted, its pages, and the document's title, author, license and a link to read it online. It gives the passage its context, and it is where the attribution of ADR 0010 lives.
- **What the UI calls:** `qa.load_resources`, `qa.answer` and `qa.passages`, plus `ingest.load_book` to read the book the panel shows. The same rule as `cli.py`: the page only calls and lays out.
  - `qa.passages(answer, book)` returns, for each citation, its section split around the cited chunk (`models.Passage`).
  - `qa.read_span` finds the chunk in the section. Both come from the same running text (`chunking.section_text`), so this is plain string matching on block boundaries, without fuzzy search.
- **Documents offered** are listed in `configs/documents.yaml`, each pointing at its experiment config, with title, author, license and URL. For now the list holds only the openly licensed document: the reference book stays on the CLI. Adding a document needs one more entry in that file and no code.
- **Local only:**
  - `homerag chat` serves on `127.0.0.1`, with no public link and Gradio's analytics off;
  - no cost limits, no hosting, no 👍/👎 yet.
  - `gradio` is imported inside the `chat` command, so every other command stays fast.

## Alternatives considered
- **Streamlit:** its linear script and expanders read well, and `AppTest` is a good test tool. But it adds about 100 MB more (pyarrow), reruns the whole page on every click, and would need a Docker template on Hugging Face Spaces.
- **A short excerpt only** (the roadmap's first idea): not enough for a reader who does not know the document.
- **Highlighting the exact sentence** behind each claim: useful, but it needs a matching method that must itself be measured. Left for later.
- **A hand-written page** (FastAPI and HTML): full control, but every chat behaviour (streaming states, the queue, collapsible messages) would have to be written by hand. That is not where this project's learning is.

## Consequences
- The chat answers each question on its own, like `homerag ask`: follow-up questions are not rewritten yet (architecture §4.3).
- The panel shows whole sections of the document. That is allowed for openly licensed documents with attribution (ADR 0010). The reference book can be shown that way only locally, for personal use: the public demo never serves it.
- Gradio's own HTTP API is reachable next to the page. That is harmless locally, but step 4 must cover it with the same limits as the page, or turn it off.
- `qa` grows by three small functions (`passages`, `read_span`, `format_citation`). If the panel's needs grow, they become a module of their own.

# Product

## What we are building
A homemade clone of NotebookLM (now Gemini Notebook), specialized on sports documents: a conversational assistant that answers questions about its source documents, always citing where each answer comes from. The reference document, used to build and evaluate every component, is Joe Friel's *The Triathlete's Training Bible*. Like NotebookLM, the product is meant to work on the documents its users upload (see "Shared demo"). Evaluation stays focused on sports and technical documents.

## Goals (in priority order)
1. **Learning**: understand RAG component by component, with readable implementations instead of opaque frameworks.
2. **Measurability**: every choice is backed by metrics on the golden dataset.
3. **Answer quality**: correct, grounded in the book, with verifiable citations, in English.

## User
The project's author, who uses sports books as a reference. The book is in English and, for now, questions and answers are English only.

From Phase 4, during the build-in-public phase, other people can try the product on their own documents from a web page (see "Shared demo").

## Current scope
- Q&A about the book (single question and follow-ups).
- Ingestion, retrieval, generation and evaluation pipelines.
- CLI interface for development; a shared web demo (Phase 4) where visitors upload a document and chat with it.

## Non-goals (for now)
- Multilingual support (questions or answers in languages other than English).
- Anything beyond question answering over the source documents: the project is a homemade, NotebookLM-style RAG.
- Products built on top of it: if the clone is reused, that happens in a separate project and is not described in this repository.
- Accounts and authentication: the shared demo is reached through a link, with no sign-in.
- Using "batteries-included" RAG frameworks (LangChain, LlamaIndex) for the main pipeline: they would hide exactly what we want to learn.

## Assistant behaviour principles
- Answers only from retrieved content; if that is not enough, it says so.
- Cites chapter/section for every claim.
- Accepts and answers English only: a message in another language gets a notice and does not start the query (see `docs/architecture.md` §4.1).
- No medical advice; paraphrases instead of reproducing long passages.

## Shared demo (Phase 4, build in public)
Right after the first complete pipeline, and before the optimizations, the product opens to other people through a link: a web page, with nothing to install, where they upload a document and chat with it while the project is built in public.
- **Visitors upload their own documents** in the supported formats (ePub for now) and ask questions about them, as in NotebookLM. The demo does not serve the reference book: it stays a local document for development and evaluation.
- **Documents in English only (for now):** questions are English only (language gate), and retrieval compares the question with the document text, so a document in another language could not be queried. The loader checks the language of an uploaded document and rejects a non-English one with a clear message (`docs/architecture.md` §4.1). Both rules go away together when multilingual support arrives.
- **No accounts or authentication:** whoever has the link can use it. An uploaded document and its index belong to the visitor's session only and are never shared with other visitors.
- **Open before the link goes out — uploaded documents:** the service processes and stores files that belong to others, so it needs terms of use (upload only documents you have the right to use), deletion of documents and indexes, and no use of uploads beyond answering their owner. DRM-protected files are not supported: the loader rejects them with a clear message and the project never strips DRM. See `docs/architecture.md` §9.
- **Ingestion with nobody checking:** uploaded documents are not inspected by hand, so the generic quality report warns the visitor in plain words when a document was extracted badly (roadmap, Phase 4a).
- **Indexing time:** a document is indexed while the visitor waits, so embedding speed becomes a product constraint (a local model on CPU takes minutes for a book; an embedding API or a GPU takes seconds). Measured at the start of Phase 4.
- **Cost and abuse:** every query is paid by the author, so the demo needs a usage limit (per visitor and a global daily budget).

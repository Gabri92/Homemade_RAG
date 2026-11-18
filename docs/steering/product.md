# Product

## What we are building
A conversational assistant that answers questions about the training method described in Joe Friel's *The Triathlete's Training Bible*, always citing its sources in the book.

## Goals (in priority order)
1. **Learning**: understand RAG component by component, with readable implementations instead of opaque frameworks.
2. **Measurability**: every choice is backed by metrics on the golden dataset.
3. **Answer quality**: correct, grounded in the book, with verifiable citations, in English.

## User
The project's author: a triathlete who uses the book as a reference. The book is in English and, for now, questions and answers are English only.

Later, during a build-in-public phase, other people can try part of the product (see "Shared demo").

## Current scope
- Q&A about the book (single question and follow-ups).
- Ingestion, retrieval, generation and evaluation pipelines.
- CLI interface; a minimal chat (Streamlit/Gradio) at the end of the roadmap.

## Non-goals (for now)
- Multilingual support (questions or answers in languages other than English).
- Generating training plans, computing zones, athlete profile.
- Integration with Strava/Garmin or other activity data.
- Accounts, authentication, per-user data: the shared demo is reached through a link, with no sign-in.
- Using "batteries-included" RAG frameworks (LangChain, LlamaIndex) for the main pipeline: they would hide exactly what we want to learn.

## Assistant behaviour principles
- Answers only from retrieved content; if that is not enough, it says so.
- Cites chapter/section for every claim.
- Accepts and answers English only: a message in another language gets a notice and does not start the query (see `docs/architecture.md` §4.1).
- No medical advice; paraphrases instead of reproducing long passages.

## Shared demo (planned, build in public)
A later phase opens part of the product to other people through a link, so they can try it while the project is built in public. Their questions are also raw material for the golden set (rewritten and answered by hand).
- **No accounts or authentication:** whoever has the link can use it.
- **Which part of the product** is exposed is decided when the phase starts.
- **Open before the link goes out — copyright:** the book is copyrighted and the project so far is personal use (`docs/architecture.md` §9). Sharing answers built on it with other people is distribution: what the demo may serve (e.g. short paraphrased answers with citations, or a public-domain source instead of the book) must be settled first, ideally with the publisher or author.
- **Cost and abuse:** every query is paid by the author, so the demo needs a usage limit.

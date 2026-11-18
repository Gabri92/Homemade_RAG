# Product

## What we are building
A conversational assistant that answers questions about the training method described in Joe Friel's *The Triathlete's Training Bible*, always citing its sources in the book.

## Goals (in priority order)
1. **Learning**: understand RAG component by component, with readable implementations instead of opaque frameworks.
2. **Measurability**: every choice is backed by metrics on the golden dataset.
3. **Answer quality**: correct, grounded in the book, with verifiable citations, in English.

## User
The project's author: a triathlete who uses the book as a reference. The book is in English and, for now, questions and answers are English only.

## Current scope
- Q&A about the book (single question and follow-ups).
- Ingestion, retrieval, generation and evaluation pipelines.
- CLI interface; a minimal chat (Streamlit/Gradio) at the end of the roadmap.

## Non-goals (for now)
- Multilingual support (questions or answers in languages other than English).
- Generating training plans, computing zones, athlete profile.
- Integration with Strava/Garmin or other activity data.
- Public distribution, multiple users, authentication.
- Using "batteries-included" RAG frameworks (LangChain, LlamaIndex) for the main pipeline: they would hide exactly what we want to learn.

## Assistant behaviour principles
- Answers only from retrieved content; if that is not enough, it says so.
- Cites chapter/section for every claim.
- Accepts and answers English only: a message in another language gets a notice and does not start the query (see `docs/architecture.md` §4.1).
- No medical advice; paraphrases instead of reproducing long passages.

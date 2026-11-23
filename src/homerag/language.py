"""Language gate (placeholder, Phase 3).

`is_english(text)`: local, deterministic language detection with `lingua-py`. Non-English
messages get a notice and never reach retrieval or the LLM; very short or low-confidence
messages are let through. The only module that imports `lingua`.
"""

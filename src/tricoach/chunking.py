"""Chunking strategies (placeholder, Phase 3).

Splits the sections of a `Book` into `Chunk`s. Each strategy is a function with the same
signature, registered by name in `CHUNKERS` so an experiment config can pick it
(fixed-size with overlap, structure-aware, contextual, parent-child). Tables are never split.
"""

"""Embeddings and search indexes (placeholder, Phase 3).

Computes chunk embeddings (`sentence-transformers` with `bge-m3`, cached on disk by text hash
and model), builds the in-memory `numpy` vector index and the BM25 lexical index, and saves and
loads them with a `schema_version`.
"""

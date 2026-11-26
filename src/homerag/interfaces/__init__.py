"""What talks to a person: the command line (`cli.py`) and the web chat (`chat.py`).

No RAG logic here: interfaces read input, call the core (`qa`, `eval`, `ingest`, `index`,
`retrieval`), and lay out what comes back. The core never imports this package
(ADR 0012, enforced by tests/unit/test_architecture.py).
"""

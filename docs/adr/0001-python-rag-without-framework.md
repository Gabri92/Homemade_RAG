# ADR 0001 — Pipeline RAG in Python senza framework RAG

- **Data:** 2026-11-16
- **Stato:** accettata

## Contesto
L'obiettivo primario del progetto è capire il RAG in pratica e saperlo valutare. Il corpus è un solo libro (~1–3k chunk).

## Decisione
Python 3.12 con componenti scritti a mano in pochi moduli piatti; le varianti da confrontare sono funzioni scelte per nome dalla config (KISS). Indice vettoriale in memoria con `numpy`, BM25 con `rank-bm25`, embedding e reranker locali `bge-m3`, generazione e judge con Claude. Valutazione implementata in casa.

## Alternative considerate
- **LangChain / LlamaIndex** — accelerano, ma nascondono chunking, retrieval e prompt: in contrasto con l'obiettivo didattico.
- **Vector DB dedicato (Qdrant, pgvector)** — inutile per poche migliaia di vettori; resta sostituibile dietro l'interfaccia `VectorIndex`.
- **Ragas per l'eval** — utile come confronto in seguito, ma prima si implementano le metriche a mano per capirle.

## Conseguenze
- Più codice da scrivere, ma ogni componente è leggibile e testabile.
- Cambiare tecnologia tocca un solo modulo, perché ogni libreria esterna è importata in un posto solo.
- Se la struttura piatta diventa stretta, la si fa crescere modulo per modulo (un modulo diventa un package) solo quando serve.

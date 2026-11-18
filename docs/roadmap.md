# Roadmap pratica — dal libro al Q&A valutato

Principio guida: **eval-driven development**. Prima si costruisce il modo di misurare, poi si ottimizza.
Ogni fase ha un deliverable concreto e un obiettivo di apprendimento.

---

## Fase 0 — Setup progetto ✅ (v0.1.0)

- Inizializza il progetto con `uv`, struttura cartelle come in `docs/steering/structure.md`.
- Tooling: `ruff` (lint + format), `mypy --strict`, `pytest`, `pre-commit`.
- `git init` + `.gitignore` che esclude `data/` ed `eval/runs/`.
- Variabili d'ambiente in `.env` (mai committato): `ANTHROPIC_API_KEY`.

**Deliverable:** `uv run pytest` passa su un test vuoto; lint e type-check verdi.

---

## Fase 1 — Ingestion e ispezione ✅ (v0.2.0)

> Stato a chiusura: Loader ePub, Cleaner, Structurer → `book.json`, `dump`/`ingest`/`inspect`, test sul libro reale. Problemi trovati, regole e aperti in `docs/ingestion-findings.md`. Restano aperti **#12–#14**, emersi dal test su altri ePub (corpus Standard Ebooks): non toccano il libro di Friel e vanno chiusi prima di usare altre sorgenti.

1. Loader per il formato che possiedi (preferibilmente ePub).
2. Cleaner + Structurer → `data/processed/book.json` (capitoli, sezioni, tabelle, pagine).
3. Script di ispezione: stampa l'albero dei capitoli, conta parole per sezione, elenca le tabelle trovate.
4. **Controlla a mano** 5–10 sezioni e tutte le tabelle chiave (zone, ore per periodo).

**Apprendimento:** la qualità del RAG nasce qui. Tabelle rotte = risposte numeriche sbagliate.
**Deliverable:** `book.json` affidabile + test sul Cleaner con esempi reali di artefatti.

---

## Fase 2 — Golden dataset (prima del retrieval!)

1. Scrivi a mano **30 domande** iniziali coprendo tutte le categorie (`factual`, `table`, `conceptual`, `multi_hop`, `out_of_scope`, `follow_up`).
2. Per ognuna: risposta di riferimento + sezione/span del libro che la supporta.
2b. Tutte le domande in inglese, più ~10 messaggi `non_english` (incluse domande brevi e casi limite) per testare il language gate.
3. Più avanti: estendi a 80–100, anche con domande sintetiche **revisionate**.

**Apprendimento:** scrivere le domande ti obbliga a capire cosa significa "risposta corretta".
**Deliverable:** `eval/datasets/golden.jsonl` + schema pydantic che lo valida.

---

## Fase 3 — Baseline "naive RAG" + harness di valutazione

1. Chunker fixed-size (es. 500 token, overlap 50).
2. Embedder `bge-m3`, indice in memoria con `numpy`, retrieval top-5 dense.
3. Language gate con `lingua-py`: messaggio non inglese → avviso, nessuna query.
3b. Generator Claude con prompt semplice + citazioni, risposte in inglese.
4. **Eval runner**: esegue il golden set, calcola metriche di retrieval (hit rate, recall@k, MRR) e di generazione (judge), salva il run.
5. CLI: `ask "domanda"` ed `eval run --config configs/experiments/baseline.yaml`.

**Apprendimento:** avere un numero di partenza. Sarà probabilmente mediocre: va bene.
**Deliverable:** primo run in `eval/runs/` con metriche per categoria.

---

## Fase 4 — Ottimizzare il retrieval (un esperimento alla volta)

Ogni riga è un esperimento con la sua config; si confronta sempre con il run migliore precedente.

| # | Esperimento | Ipotesi |
|---|---|---|
| 4.1 | Chunking structure-aware (sezioni, tabelle intatte) | Migliora `table` e `factual` |
| 4.2 | Variazione di dimensione chunk e k | Trovare il punto ottimale |
| 4.3 | Ibrido dense + BM25 con RRF | Migliora termini esatti ("Build 2", "LTHR") |
| 4.4 | Query rewriting con LLM (multi-query o HyDE) | Migliora domande vaghe o formulate diversamente dal libro |
| 4.5 | Reranker cross-encoder | Migliora la precisione dei primi 5 |
| 4.6 | Contextual chunking | Migliora chunk ambigui |
| 4.7 | Parent-child | Migliora `multi_hop` / `conceptual` |
| 4.8 | **Baseline di pipeline generica**: ingestion e chunking con uno strumento pubblico contro la nostra ingestion, a parità di retrieval, LLM e golden set. **Strumento da valutare** prima dell'esperimento (candidati: LlamaIndex, Unstructured, Docling, pandoc + chunker semplice), in base a supporto ePub, qualità dell'output e dipendenze | Misura quanto vale il lavoro fatto sui dati (tabelle, glossario, citazioni ripetute, ruoli) e su quali categorie di domande. La baseline resta **solo** un termine di confronto (ADR 0001: niente framework nella pipeline principale) |

**Apprendimento:** capire *quale leva sposta quale metrica* e in quale categoria di domande.
**Deliverable:** report di confronto tra run + scelta motivata della config migliore (registrata in un ADR).

---

## Fase 5 — Ottimizzare la generazione

1. Prompt: grounding rigoroso, formato citazioni, risposta in italiano con termini originali.
2. Gestione `out_of_scope`: rifiuto esplicito.
3. Multi-turn: condensation della domanda di follow-up in una domanda autonoma prima del retrieval.
3b. Metrica *gate accuracy* (deterministica) sulla categoria `non_english`.
4. **Calibrazione del judge**: etichetta a mano ~30 risposte, misura accordo judge/umano, correggi la rubrica.

**Deliverable:** faithfulness e refusal correctness misurati e affidabili.

---

## Fase 6 — Confronto con baseline long-context

- Generator che riceve l'intero libro in contesto con prompt caching.
- Stesso golden set: confronta qualità, costo e latenza con la miglior config RAG.

**Apprendimento:** capire concretamente i trade-off RAG vs long-context.
**Deliverable:** tabella comparativa + conclusioni in `docs/adr/`.

---

## Fase 7 — Interfaccia chat minima

- Streamlit o Gradio che chiama la stessa `qa.answer()` (nessuna logica nella UI).
- Mostra le citazioni espandibili (capitolo/sezione + estratto breve).
- Pulsante 👍/👎 che salva l'interazione: diventa materiale per nuove domande del golden set.

**Deliverable:** chat locale utilizzabile.

---

## Dopo (fuori scope ora)

- **Sorgenti aggiunte dall'utente** (stile NotebookLM): le regole di Loader e Cleaner sono già generiche (lavorano su semantica HTML e su `Block`), ma soglie e valori attesi sono tarati su un solo libro. Per generalizzare:
  1. **corpus di ingestion**: alcuni ePub/PDF di editori diversi e liberi da copyright (es. Project Gutenberg, Standard Ebooks, articoli open access), ognuno con i suoi valori attesi, eseguiti come test di regressione;
  2. **report di qualità automatico** calcolato su ogni file caricato, senza valori attesi: invarianti generiche (copertura del testo sorgente, struttura dei titoli, tabelle senza titolo, figure senza didascalia, tasso di duplicati, blocchi anomali) → avvisi all'utente quando un documento è estratto male;
  3. **valutazione a valle**: un piccolo golden set di domande per ogni documento del corpus, perché la qualità dell'ingestion si misura alla fine dalle risposte.

- **Figure con la multimodalità di Claude**: in ingestion, le immagini (prima le tabelle pubblicate come immagine, poi grafici e illustrazioni) vengono passate a Claude, che trascrive le tabelle in Markdown e descrive le figure. Il testo generato sostituisce il blocco `figure` con la sola didascalia ed è salvato in cache, così ogni immagine si paga una volta sola. Si misura come esperimento: domande del golden set che dipendono da figure, prima e dopo.

- Multilingua: il language gate viene sostituito da un query processor LLM (lingua di risposta + query tradotta in inglese per il retrieval) e il golden set si estende con le stesse domande in più lingue.
- Regole del libro come codice deterministico (calcolo zone, ATP) esposte come tool.
- Profilo atleta e onboarding.
- Integrazione con dati di allenamento reali (Strava/Garmin).

# CLAUDE.md

Assistente Q&A basato su *The Triathlete's Training Bible* (Joe Friel). Progetto di apprendimento: RAG in pratica + valutazione rigorosa.

Leggi e rispetta i file di steering:

@docs/steering/product.md
@docs/steering/tech.md
@docs/steering/structure.md
@docs/steering/conventions.md

Riferimenti (leggili quando tocchi l'area relativa): `docs/architecture.md`, `docs/roadmap.md`, `docs/adr/`.

## Regole sempre valide

1. **Mai committare il libro o derivati** (`data/`, `eval/runs/`). Non stampare lunghi estratti verbatim del libro in output, log o test: usa fixture sintetiche.
2. **Ogni modifica alla pipeline RAG è un esperimento**: nuova config in `configs/experiments/`, eval prima/dopo, delta riportato.
3. **KISS ora, modularità quando serve.** Niente nuovi moduli, classi o astrazioni se una funzione basta. La struttura cresce solo davanti ai segnali concreti elencati in `structure.md` ("Quando far crescere la struttura"), un passo alla volta. Se una modifica sembra richiedere più struttura, proponila prima di farla.
4. **Nuove dipendenze**: giustificale e chiedi prima di aggiungerle.
5. **Definition of done**: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest` tutti verdi.
6. **Decisioni architetturali** (nuovo componente, cambio tecnologia, scelta di config vincente) → nuovo ADR in `docs/adr/`.
7. **Mantieni allineati i docs**: se cambi struttura, comandi o convenzioni, aggiorna lo steering file corrispondente nella stessa modifica.
8. Lingua: codice, identificatori, docstring e commit in **inglese**; documentazione in `docs/` e risposte all'utente in **italiano**.

# Tech

## Stack
| Area | Scelta |
|---|---|
| Linguaggio | Python 3.12+ |
| Package/env | `uv` (mai `pip install` diretto) |
| Validazione dati e config | `pydantic` v2, `pydantic-settings`, config YAML |
| LLM | SDK `anthropic`; generazione `claude-sonnet-5-5`, judge `claude-opus-5-5` (configurabili) |
| Embedding / reranker | `sentence-transformers` con `BAAI/bge-m3` e `BAAI/bge-reranker-v2-m3` |
| Indice | `numpy` in memoria (persistito su file); `rank-bm25` per il lessicale |
| Rilevamento lingua | `lingua-py` (language gate: solo inglese) |
| Estrazione | `ebooklib` + `beautifulsoup4` (ePub), `pymupdf` (PDF) |
| CLI | `typer` |
| Test | `pytest` |
| Qualità | `ruff` (lint + format), `mypy --strict`, `pre-commit` |

## Comandi
```bash
uv sync                                   # installa dipendenze
uv run ruff check . --fix                 # lint
uv run ruff format .                      # format
uv run mypy src                           # type check
uv run pytest                             # test (veloci, offline)
uv run pytest -m integration              # test che chiamano API/modelli reali
uv run pytest -m book                     # solo i controlli sul libro reale (girano anche con `pytest`, saltati se il libro manca)
uv run tricoach dump data/raw/<libro>.epub          # output del loader -> data/processed/blocks_raw.txt
uv run tricoach dump data/raw/<libro>.epub --clean  # dopo il Cleaner -> data/processed/blocks_clean.txt
git diff --no-index data/processed/blocks_raw.txt data/processed/blocks_clean.txt  # cosa ha cambiato il Cleaner
uv run tricoach ingest                    # libro -> data/processed -> data/index
uv run tricoach ask "domanda"             # Q&A singolo
uv run tricoach eval run --config configs/experiments/<nome>.yaml
uv run tricoach eval compare <run_a> <run_b>
```
> Disponibile ora: `dump`. `ingest` e `inspect` arrivano nella Fase 1, `ask` ed `eval` nella Fase 3. `uv run tricoach --help` elenca i comandi esistenti.

## Segreti e configurazione
- `ANTHROPIC_API_KEY` e simili solo in `.env` (gitignored), letti tramite `pydantic-settings`.
- Nessun valore magico nel codice: modelli, k, dimensioni chunk, prompt vivono nella config dell'esperimento.

## Politica dipendenze
- Preferire la libreria standard e poche dipendenze mirate.
- Ogni nuova dipendenza va motivata (cosa risolve, alternativa scartata).
- Ogni libreria esterna è importata in un solo modulo (vedi `structure.md`).

## Costi e riproducibilità
- Temperatura 0 per judge ed esperimenti.
- Cache su disco degli embedding (chiave = hash testo + modello) e delle risposte del judge per non ripagare chiamate identiche.
- Ogni run di eval salva la config completa e la versione dei prompt usati.

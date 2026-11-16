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
uv run tricoach ingest                    # libro -> data/processed -> data/index
uv run tricoach ask "domanda"             # Q&A singolo
uv run tricoach eval run --config configs/experiments/<nome>.yaml
uv run tricoach eval compare <run_a> <run_b>
```
> I comandi `tricoach` saranno disponibili dalla Fase 3 della roadmap.

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

# ADR 0002 — `ingest.py` diventa il package `ingest/`

- **Data:** 2026-11-17
- **Stato:** accettata

## Contesto
`ingest.py` era a 196 righe e stava per ricevere il Cleaner (circa +100). Soprattutto avrebbe contenuto codice che cambia per motivi diversi: il Loader cambia con il **formato** del file (ePub oggi, PDF probabile domani), il Cleaner con i **difetti dei dati**, il dump con le esigenze di **ispezione**. Sono due dei segnali di crescita previsti in `structure.md`.

## Decisione
Refactoring senza cambi di comportamento:
```
ingest/
  __init__.py   # API pubblica: load_epub, html_to_blocks, format_blocks (poi clean, ...)
  epub.py       # Loader ePub
  dump.py       # format_blocks
```
Il Cleaner arriverà come `ingest/cleaning.py`, un eventuale loader PDF come `ingest/pdf.py`. Chi usa l'ingestion importa solo da `tricoach.ingest`: i test esistenti passano senza modifiche, ed è la prova che il refactoring non cambia il comportamento.

## Alternative considerate
- **Restare in un solo file** — semplice ancora per poco, ma mescola tre motivi di cambiamento.
- **Moduli piatti separati** (`loader.py`, `cleaning.py` accanto a `ingest.py`) — disperde in cima al package concetti che appartengono a un'unica fase della pipeline.

## Conseguenze
- Aggiungere un formato o una regola di pulizia tocca un solo file.
- I moduli interni non vanno importati direttamente da fuori del package.

# Structure

Principio: **KISS**. Un modulo per concetto, funzioni prima di classi, nessuno strato in più finché non serve.

## Layout
```
src/tricoach/
  models.py      # dataclass: Block, Section, Book, Chunk, RetrievedChunk, Answer, Citation
  config.py      # settings (.env) + config esperimento (YAML -> pydantic)
  ingest/        # sorgente -> blocchi -> pulizia -> sezioni -> data/processed/book.json (ADR 0002)
    __init__.py  #   API pubblica: da fuori si importa solo da `tricoach.ingest`
    epub.py      #   Loader ePub (un file per formato: domani pdf.py)
    cleaning.py  #   Cleaner: regole strutturali su list[Block]
    structure.py #   Structurer: list[Block] -> Book (sezioni, id, ruoli, inclusione, pagine)
    book_file.py #   save_book / load_book di book.json, con SCHEMA_VERSION
    quality.py   #   report di qualità generico (nessun valore atteso): `tricoach inspect`
    dump.py      #   format_blocks per l'ispezione
  chunking.py    # strategie di chunking (funzioni) + registro CHUNKERS
  index.py       # embedding, indice numpy, BM25, salvataggio/caricamento
  retrieval.py   # dense, bm25, fusione RRF, rerank
  language.py    # language gate: is_english(text)
  llm.py         # unico punto di accesso all'API Anthropic
  qa.py          # answer(question) -> Answer: gate -> retrieve -> generate
  prompts/       # prompt come file .md versionati
  eval/
    dataset.py   # carica e valida golden.jsonl
    metrics.py   # metriche (funzioni pure)
    judge.py     # LLM-as-judge
    run.py       # esegue un esperimento, salva e confronta run
  cli.py         # comandi typer: ingest, ask, eval
configs/experiments/   # una YAML per esperimento
eval/datasets/         # golden.jsonl (committato)
eval/runs/             # output dei run (gitignored)
data/                  # raw/, processed/, index/ (gitignored)
tests/                 # un tipo di test = una cartella (vedi conventions.md, "Test")
  conftest.py          #   fixture condivise (make_epub: mini-ePub sintetico)
  unit/                #   veloci, offline; rispecchia src/tricoach/ (unit/ingest/test_cleaning.py, ...)
  book/                #   sul libro reale: marker `book` e salto automatico in book/conftest.py
    expectations.py    #     valori attesi del libro (solo numeri e titoli brevi)
  integration/         #   (dalla Fase 3) API e modelli reali, marker `integration`
  e2e/                 #   (dalla Fase 3) domanda -> risposta citata sul libro reale
```

## Regole
- **Dipendenze in una sola direzione:** `cli` → `qa` / `eval` → resto. `models.py` non importa nessun altro modulo del progetto.
- **Una libreria esterna, un modulo:** `anthropic` solo in `llm.py`, `sentence_transformers` solo in `index.py` / `retrieval.py`, `lingua` solo in `language.py`. Così si sostituisce una tecnologia toccando un file.
- **Strategie intercambiabili = funzioni con la stessa firma in un dizionario.** Esempio:
  ```python
  CHUNKERS: dict[str, Callable[[list[Section], ChunkingConfig], list[Chunk]]] = {
      "fixed": fixed_size_chunks,
      "sections": section_chunks,
  }
  ```
  La config sceglie la chiave. Niente classi, niente factory.
- **Si divide un modulo solo quando serve:** oltre ~300 righe, oppure quando contiene due cose che cambiano per motivi diversi. A quel punto diventa un package (`chunking/`) con lo stesso nome.
- **Niente logica in `cli.py`:** legge gli argomenti, chiama `qa` o `eval`, stampa.

## Quando far crescere la struttura

Semplicità e modularità sono un **compromesso che cambia nel tempo**: si parte piatti e si aggiunge struttura solo quando un segnale concreto lo giustifica. Mai "per il futuro", mai per principio.

| Segnale concreto | Passo successivo (il più piccolo possibile) |
|---|---|
| Un modulo supera ~300 righe o mescola due motivi di cambiamento | Diventa un package con lo stesso nome (`chunking.py` → `chunking/`), stesse funzioni pubbliche |
| Le varianti in un registro hanno bisogno di firme diverse | Uniformare la firma con un oggetto di config; se non basta, una piccola classe per variante |
| Esiste una **seconda implementazione reale con stato** (es. un secondo indice vettoriale, un secondo provider LLM) | Introdurre un `Protocol` per quel solo componente |
| Lo stesso gruppo di parametri passa attraverso molte funzioni | Raggrupparli in un dataclass (es. `Resources(index, llm)`) |
| Un test richiede `monkeypatch` o setup complicato | La dipendenza va passata come parametro |
| La stessa conoscenza compare in tre punti | Estrarla in un posto solo (DRY) |
| Arriva una nuova area di prodotto (es. coach, tool, multilingua) | Un nuovo modulo/package dedicato, senza toccare la struttura esistente |

Regole del passaggio:
- un segnale → un passo; non anticipare i passi successivi;
- il cambio di struttura è un refactoring separato (commit `refactor:`) con i test verdi prima e dopo;
- se il cambio tocca più moduli o introduce un nuovo concetto (Protocol, package, livello), va proposto prima e registrato in un ADR.

## Notebook di esplorazione (promemoria: dalla Fase 3)

Da introdurre all'inizio del chunking, non prima (YAGNI). Servono a **sperimentare e imparare** (come tagliano i chunker, cosa restituisce il retrieval, BM25 vs dense), non a costruire il prodotto.
- Cartella `notebooks/`; dipendenze `jupyter`/`ipykernel` solo nel gruppo dev.
- I notebook **importano** le funzioni di `tricoach`, non le riscrivono (DRY). Ciò che funziona si sposta nel package, con i suoi test.
- Si committano **senza output** (contengono testo del libro): pulizia automatica prima del commit.

## Dove mettere cosa
| Voglio aggiungere… | Va in… |
|---|---|
| Una nuova strategia di chunking / retrieval | una funzione in `chunking.py` / `retrieval.py` + una voce nel registro |
| Un nuovo formato di sorgente | un file in `ingest/` (es. `pdf.py`) che produce `list[Block]` |
| Una nuova regola di pulizia | una funzione in `ingest/cleaning.py` + una voce nella sequenza `CLEANING_STEPS` |
| Una nuova metrica | una funzione pura in `eval/metrics.py` |
| Un nuovo prompt o versione | un nuovo file in `prompts/` |
| Un nuovo comando | `cli.py` |
| Un nuovo tipo di dato | `models.py` |

# Structure

Principio: **KISS**. Un modulo per concetto, funzioni prima di classi, nessuno strato in più finché non serve.

## Layout
```
src/tricoach/
  models.py      # dataclass: Block, Section, Chunk, RetrievedChunk, Answer, Citation
  config.py      # settings (.env) + config esperimento (YAML -> pydantic)
  ingest.py      # ePub/PDF -> testo pulito -> sezioni -> data/processed/book.json
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
tests/                 # test_<modulo>.py, conftest.py con fixture condivise e mini-libro sintetico
                       # test_book_quality.py + book_expectations.py: controlli sul libro reale (marker `book`)
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

## Dove mettere cosa
| Voglio aggiungere… | Va in… |
|---|---|
| Una nuova strategia di chunking / retrieval | una funzione in `chunking.py` / `retrieval.py` + una voce nel registro |
| Una nuova metrica | una funzione pura in `eval/metrics.py` |
| Un nuovo prompt o versione | un nuovo file in `prompts/` |
| Un nuovo comando | `cli.py` |
| Un nuovo tipo di dato | `models.py` |

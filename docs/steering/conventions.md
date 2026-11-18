# Conventions

## Principi, in ordine di priorità
1. **KISS** — la soluzione più semplice che funziona. Funzioni prima di classi; una classe solo se tiene stato (es. un indice caricato in memoria).
2. **YAGNI** — niente astrazioni "per il futuro" (multilingua, coach, tool, profilo atleta) finché non sono nella fase corrente della roadmap.
3. **DRY** — una sola fonte di verità per ogni cosa:
   - chiamate all'LLM solo tramite `llm.py` (retry, cache, logging dei costi in un posto solo);
   - parametri (modelli, k, dimensioni chunk) solo nella config, mai ripetuti nel codice;
   - prompt solo in `prompts/`;
   - fixture di test solo in `tests/conftest.py`.
   DRY vale per la *conoscenza*, non per il codice che si somiglia per caso: meglio due righe ripetute che un'astrazione sbagliata. Si estrae alla **terza** ripetizione.
4. **SOLID, in modo pragmatico** — non come struttura imposta a priori, ma come criterio quando il codice cresce:
   - *Single responsibility*: una funzione fa una cosa (un chunker non calcola embedding);
   - *Open/closed*: una nuova strategia è una nuova funzione nel registro, non un `if` in più nel codice esistente;
   - *Dependency inversion "leggera"*: le funzioni ricevono ciò che usano come parametro (es. `answer(question, index, llm)`) invece di crearlo al loro interno. È ciò che rende i test facili.
   - `Protocol` e classi astratte solo quando ci sono **davvero** due implementazioni con stato.

## Stile Python
- Type hints ovunque; `mypy --strict` deve passare. Niente `Any` senza commento che lo giustifichi.
- Dati: `@dataclass(frozen=True, slots=True)`; `pydantic` solo per ciò che arriva dall'esterno (config, golden set, output JSON dell'LLM).
- Nomi descrittivi: `snake_case` funzioni/moduli, `PascalCase` classi, `UPPER_CASE` costanti.
- Funzioni brevi (indicativamente < 40 righe); se un blocco richiede un commento per essere capito, estrailo in una funzione con un buon nome.
- Commenti solo per il *perché*. Docstring sulle funzioni pubbliche dei moduli.
- Niente `print` fuori da `cli.py`: usa `logging`.

## Errori
- Fallire presto con messaggi chiari. Mai `except Exception: pass`.
- Un'eccezione personalizzata solo quando il chiamante deve gestirla in modo diverso.

## Test
- **Un tipo di test, una cartella:**

  | Cartella | Cosa | Quando gira |
  |---|---|---|
  | `tests/unit/` | Una funzione con dati sintetici; rispecchia `src/tricoach/` (`src/tricoach/ingest/cleaning.py` → `tests/unit/ingest/test_cleaning.py`) | Sempre; `uv run pytest tests/unit` durante lo sviluppo (< 1 s) |
  | `tests/book/` | L'ingestion sul libro reale contro i valori di `expectations.py` | Con `uv run pytest`; saltati se il libro manca |
  | `tests/integration/` | (Fase 3) componenti con API/modelli reali | Solo con `-m integration` |
  | `tests/e2e/` | (Fase 3) domanda → risposta citata | Da decidere con la Fase 3 |

  Marker e salti si applicano **per cartella** nel suo `conftest.py`, non file per file. Le cartelle `integration/` ed `e2e/` si creano quando arriva il primo test.
- Un file `test_<modulo>.py` per modulo; test di funzioni pure senza mock.
- I test sono un package (`tests/__init__.py`): si importa in modo esplicito, es. `from tests.conftest import MakeEpub`.
- Le dipendenze esterne (LLM, modello di embedding) si sostituiscono passando un fake come parametro, non con `monkeypatch` sparsi.
- Le strategie di un registro si testano con un unico test parametrizzato su tutte le voci.
- `cli.py`: un test di fumo per comando con il `CliRunner` di typer (avvio, errore su input non valido, output atteso). La logica si testa nei moduli, non attraverso la CLI.
- I test standard sono deterministici e offline; quelli che chiamano API o modelli reali sono `@pytest.mark.integration`.
- Fixture: un **mini-libro sintetico** scritto da noi, mai testo del libro reale.
- Bug trovato → prima un test che lo riproduce, poi la correzione.

## Prompt
- Un file per prompt in `src/tricoach/prompts/`, con versione nel nome (`answer_v2.md`).
- Un prompt usato in un run di eval non si modifica: se ne crea una nuova versione.

## Git
- Commit piccoli, messaggi in inglese in stile Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `exp:` per esperimenti).
- Un esperimento = commit con config + riepilogo delle metriche nel messaggio.
- **Branch:** `main` contiene solo lavoro finito (definition of done verde). Si lavora su un branch per fase della roadmap (`feat/phase-1-ingestion`) o per esperimento (`exp/<nome>`), con un commit per modulo o step. A fine fase: merge in `main` con `--no-ff`, così la fase resta visibile nella storia.

## Versioning
- **SemVer in fase 0.x**: la versione vive solo in `pyproject.toml` (unica fonte).
  - *minor* (`0.2.0`) a ogni fase della roadmap completata e mergiata in `main`;
  - *patch* (`0.2.1`) per correzioni su `main`.
- **Tag annotato** `vX.Y.Z` sul commit di merge in `main`.
- **`CHANGELOG.md`** (formato Keep a Changelog): ogni commit `feat:`/`fix:` aggiunge una riga in `[Unreleased]`; al rilascio la sezione prende numero e data.
- **Artefatti dati:** `book.json` e gli indici contengono un `schema_version` (intero, incrementato a ogni cambio di formato) e la versione di `tricoach` che li ha prodotti. Un artefatto con schema diverso da quello atteso va rigenerato, non letto.

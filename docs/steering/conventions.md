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
- Un file `tests/test_<modulo>.py` per modulo; test di funzioni pure senza mock.
- Le dipendenze esterne (LLM, modello di embedding) si sostituiscono passando un fake come parametro, non con `monkeypatch` sparsi.
- Le strategie di un registro si testano con un unico test parametrizzato su tutte le voci.
- I test standard sono deterministici e offline; quelli che chiamano API o modelli reali sono `@pytest.mark.integration`.
- Fixture: un **mini-libro sintetico** scritto da noi, mai testo del libro reale.
- Bug trovato → prima un test che lo riproduce, poi la correzione.

## Prompt
- Un file per prompt in `src/tricoach/prompts/`, con versione nel nome (`answer_v2.md`).
- Un prompt usato in un run di eval non si modifica: se ne crea una nuova versione.

## Git
- Commit piccoli, messaggi in inglese in stile Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `exp:` per esperimenti).
- Un esperimento = commit con config + riepilogo delle metriche nel messaggio.

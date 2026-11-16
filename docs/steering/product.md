# Product

## Cosa stiamo costruendo
Un assistente conversazionale che risponde a domande sul metodo di allenamento descritto in *The Triathlete's Training Bible* di Joe Friel, citando sempre le fonti nel libro.

## Obiettivi (in ordine di priorità)
1. **Apprendimento**: capire il RAG componente per componente, con implementazioni leggibili anziché framework opachi.
2. **Misurabilità**: ogni scelta è supportata da metriche sul golden dataset.
3. **Qualità delle risposte**: corrette, ancorate al libro, con citazioni verificabili, in italiano.

## Utente
L'autore del progetto: triatleta che usa il libro come riferimento. Il libro è in inglese e, per ora, anche domande e risposte sono solo in inglese.

## Scope attuale
- Q&A sul libro (singola domanda e follow-up).
- Pipeline di ingestion, retrieval, generazione, valutazione.
- Interfaccia CLI; chat minima (Streamlit/Gradio) a fine roadmap.

## Non-goals (per ora)
- Multilingua (domande o risposte in lingue diverse dall'inglese).
- Generazione di piani di allenamento, calcolo zone, profilo atleta.
- Integrazione con Strava/Garmin o altri dati di attività.
- Distribuzione pubblica, multi-utente, autenticazione.
- Uso di framework RAG "tutto incluso" (LangChain, LlamaIndex) per la pipeline principale: nasconderebbero proprio ciò che vogliamo imparare.

## Principi di comportamento dell'assistente
- Risponde solo da contenuto recuperato; se non basta, lo dice.
- Cita capitolo/sezione per ogni affermazione.
- Accetta e risponde solo in inglese: un messaggio in un'altra lingua riceve un avviso e non avvia la query (vedi `docs/architecture.md` §4.1).
- Nessun consiglio medico; parafrasa invece di riprodurre lunghi passaggi.

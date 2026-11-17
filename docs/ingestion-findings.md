# Ingestion — problemi trovati nel libro e correzioni

Documento di sviluppo: raccoglie i difetti trovati ispezionando il dump del Loader (`tricoach dump`) e l'HTML dell'ePub, con la regola scelta per ciascuno e il test che ne impedisce il ritorno.
Sorgente analizzata: *The Triathlete's Training Bible*, 5ª ed., ePub (54 documenti XHTML).

> Nessun testo del libro qui: solo struttura, conteggi e titoli brevi.

## Correzioni

| # | Problema | Regola | Dove | Priorità | Stato | Test di regressione |
|---|---|---|---|---|---|---|
| 1 | Titoli delle tabelle persi (29 tabelle su 37): il titolo sta nel `<caption>`, il Loader leggeva solo le celle | Testo del `<caption>` come prima riga del blocco tabella | Loader | Alta | ✅ | `test_table_caption_*`, `test_book_tables_keep_their_titles` |
| 2 | Celle unite (`rowspan`/`colspan`, 4 tabelle) spostavano i valori di colonna (es. Table 9.2) | Srotolare la griglia ripetendo il valore in ogni cella coperta: ogni riga resta autosufficiente | Loader | Alta | ✅ | `test_table_rowspan_*`, `test_table_colspan_*`, `test_book_table_9_2_rows_keep_their_period` |
| 3 | Figure presenti solo come paragrafi-didascalia (39 figure + 5 tabelle pubblicate come immagine) | Ogni immagine diventa un blocco `figure` con la didascalia del suo contenitore; la didascalia non è più un paragrafo separato | Loader | Media | ✅ | `test_figure_*`, `test_book_figures_are_kept` |
| 4 | Citazioni in evidenza (*pull quote*) ripetute: ≥80 dei 214 `div.sidenote` ripetono una frase del testo, a volte riformulata | Rimuovere un blocco molto simile a un blocco vicino (somiglianza, non uguaglianza); poi decidere sugli altri riquadri | Cleaner | Alta | ⏳ | — |
| 5 | Front e back matter mescolati al contenuto | Ruolo per file dai **landmarks** della `nav.xhtml`; glossario e appendici inclusi, indice analitico e bibliografia esclusi | Structurer | Alta | ⏳ | — |
| 6 | Numeri di pagina del cartaceo disponibili (360 marcatori `epub:type="pagebreak"`) | Pagina dai marcatori, da usare nelle citazioni | Structurer | Da valutare | ⏳ | — |
| 7 | Contenuto delle immagini non visibile a un RAG testuale | Trascrizione/descrizione con la multimodalità di Claude | Futuro (`roadmap.md`, "Dopo") | Da misurare | 💤 | — |
| 8 | Tabelle spezzate: Table 9.3 e 9.4 sono un piano di 3 settimane pubblicato come 3 `<table>`, solo la prima con titolo (4 tabelle di continuazione) | Una tabella senza titolo che segue **immediatamente** un'altra tabella ne è la continuazione: si uniscono in un unico blocco sotto il titolo della prima. Vale per ogni formato (nei PDF le tabelle si spezzano a ogni cambio pagina) | Cleaner | Alta | ✅ | `test_untitled_tables_right_after_*`, `test_book_split_weekly_plans_are_one_table` |
| 9 | Tabelle senza titolo (4 tabelle di punteggio dei questionari, cap. 5–6): il contesto è solo nel paragrafo che le precede; se il chunking le separa restano numeri senza significato | Se una tabella non ha titolo e il blocco **immediatamente precedente** è un **paragrafo** dello **stesso file**, quel paragrafo diventa la prima riga del blocco tabella (come un `<caption>`) e non resta come paragrafo separato. Si applica **dopo** la #8 | Cleaner | Alta | ✅ | `test_paragraph_before_untitled_table_*`, `test_book_no_table_is_left_without_a_title` |

Legenda: ✅ fatto · ⏳ da fare · 💤 rimandato.

## Struttura dell'ePub (per chi tocca il Loader)

- **Semantica:** `epub:type` nei capitoli c'è solo come `pagebreak`. I ruoli dei file (cover, dedication, preface, acknowledgments, epilogue, glossary, bibliography, index, copyright, about the author) sono nei **landmarks** della pagina di navigazione.
- **Tabelle:** 37 elementi `<table>`; titolo in `<caption>` (29), celle unite in 4.
- **Immagini:** 64 `<img>`, testo alternativo quasi sempre generico (`alt="Image"`). Le didascalie sono paragrafi nello stesso contenitore dell'immagine (`div.inline_group`).
- **Riquadri:** 214 `div.sidenote`, in parte citazioni in evidenza.

## Test sul libro reale

`tests/test_book_quality.py` (marker `book`) verifica sul libro vero che i problemi chiusi non ritornino. Gira con il normale `uv run pytest` ed è saltato automaticamente se il libro non è in `data/raw/`. I valori attesi sono in `tests/book_expectations.py`.

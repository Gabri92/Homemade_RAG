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
| 4 | Citazioni in evidenza (*pull quote*) ripetute: 157 dei 214 `div.sidenote` ripetono una frase del testo, a volte riformulata | Si rimuove un paragrafo se: è una **frase completa** di almeno 5 parole, almeno il **50%** dei suoi trigrammi di parole compare in un blocco dello **stesso file** almeno **1/0,6 volte più lungo**. Riconoscimento dal contenuto, valido per ogni formato. Restano da esaminare a mano i 57 riquadri non rimossi (vedi sotto) | Cleaner | Alta | ✅ | `test_pull_quote_*`, `test_book_pull_quotes_are_removed_and_nothing_else` |
| 5 | Front e back matter mescolati al contenuto | Ruolo per file dai **landmarks** della `nav.xhtml`; glossario e appendici inclusi, indice analitico e bibliografia esclusi | Loader (ruolo in `Block.role`) + Structurer (cosa includere) | Alta | 🔶 ruoli assegnati; inclusione da fare | `test_landmark_roles_*`, `test_book_landmark_roles_are_assigned` |
| 6 | Numeri di pagina del cartaceo disponibili (360 marcatori `epub:type="pagebreak"`; etichette testuali: A, B, i–xix, 1–342; 168 a metà paragrafo) | `Block.page` = pagina dell'ultimo marcatore **prima del primo testo** del blocco (un marcatore a metà paragrafo vale per i blocchi successivi); la pagina prosegue da un file all'altro. Nelle unioni del Cleaner si tiene la pagina del primo blocco | Loader | Alta | ✅ | `test_block_takes_the_page_*`, `test_book_every_body_block_has_a_page`, `test_book_table_11_1_is_on_its_printed_page` (p. 172, verificata a mano nell'XHTML: il marcatore sta all'inizio del `<caption>`) |
| 7 | Contenuto delle immagini non visibile a un RAG testuale | Trascrizione/descrizione con la multimodalità di Claude | Futuro (`roadmap.md`, "Dopo") | Da misurare | 💤 | — |
| 8 | Tabelle spezzate: Table 9.3 e 9.4 sono un piano di 3 settimane pubblicato come 3 `<table>`, solo la prima con titolo (4 tabelle di continuazione) | Una tabella senza titolo che segue **immediatamente** un'altra tabella ne è la continuazione: si uniscono in un unico blocco sotto il titolo della prima. Vale per ogni formato (nei PDF le tabelle si spezzano a ogni cambio pagina) | Cleaner | Alta | ✅ | `test_untitled_tables_right_after_*`, `test_book_split_weekly_plans_are_one_table` |
| 9 | Tabelle senza titolo (4 tabelle di punteggio dei questionari, cap. 5–6): il contesto è solo nel paragrafo che le precede; se il chunking le separa restano numeri senza significato | Se una tabella non ha titolo e il blocco **immediatamente precedente** è un **paragrafo** dello **stesso file**, quel paragrafo diventa la prima riga del blocco tabella (come un `<caption>`) e non resta come paragrafo separato. Si applica **dopo** la #8 | Cleaner | Alta | ✅ | `test_paragraph_before_untitled_table_*`, `test_book_no_table_is_left_without_a_title` |

| 10 | **Glossario perso**: le 123 definizioni sono una lista di definizioni (`<dl>`/`<dt>`/`<dd>`), elemento che il Loader non leggeva (restava solo il titolo) | Ogni `<dt>` diventa un paragrafo "termine: definizione" con tutti i suoi `<dd>` | Loader | Alta | ✅ | `test_definition_list_*`, `test_book_glossary_keeps_every_definition` |
| 11 | `praise.xhtml` (33 blocchi di recensioni promozionali) non è nei landmarks, quindi risulta `body`. I landmarks hanno anche un errore: "bodymatter" punta alla copertina | Regola **algoritmica**, valida per altri libri: (A) un file senza landmark che compare **prima dell'ultimo landmark di front matter** è `front`; (B) conferma: pagine con lettere/numeri romani = parte iniziale (se A e B non concordano, si segnala nel log). Override manuale per sorgente solo come rete di sicurezza | Structurer | Media | ⏳ | — |

Legenda: ✅ fatto · 🔶 in parte · ⏳ da fare · 💤 rimandato.

## Struttura dell'ePub (per chi tocca il Loader)

- **Semantica:** `epub:type` nei capitoli c'è solo come `pagebreak`. I ruoli dei file (cover, dedication, preface, acknowledgments, epilogue, glossary, bibliography, index, copyright, about the author) sono nei **landmarks** della pagina di navigazione.
- **Tabelle:** 37 elementi `<table>`; titolo in `<caption>` (29), celle unite in 4.
- **Immagini:** 64 `<img>`, testo alternativo quasi sempre generico (`alt="Image"`). Le didascalie sono paragrafi nello stesso contenitore dell'immagine (`div.inline_group`).
- **Riquadri:** 214 `div.sidenote`, in parte citazioni in evidenza.

## Structurer: casi limite misurati sul libro

Misurati sui blocchi dopo il Cleaner (titoli: 19 L1, 86 L2, 142 L3, 101 L4, 20 L5).

| Caso | Sul libro | Come va gestito |
|---|---|---|
| Livelli saltati (es. L2 → L4) | **Nessuno** | Gestirli comunque senza errori (altri libri li avranno): il titolo si aggancia all'ultimo antenato di livello inferiore |
| La gerarchia attraversa i file | I file `ch13_sub*` (workout) iniziano a L3/L4: continuano il capitolo del file precedente | Costruire la gerarchia sull'intera sequenza di blocchi, **non** ripartire da zero a ogni file |
| Titoli duplicati | Soprattutto nei workout: "AE1: Recovery" ×3, "Aerobic Capacity Workouts" ×4, "Swim/Bike/Run" ×2 (stesso workout per sport diversi) | ID costruito dal **percorso** (es. `…-bike-ae1-recovery`), non dal solo titolo; garanzia di unicità |
| Contenuto prima del primo titolo di un file | 1 caso (`ch13_sub08`, 1 blocco) | Appartiene alla sezione aperta in precedenza |
| File senza titoli | `cover`, `title`, `dedication`, `copyright` | Sezione con titolo dal landmark; ruolo `front`, esclusa dall'indice |

Effetto sul RAG dei titoli duplicati: tre sezioni "AE1: Recovery" sono distinguibili **solo** dal percorso (lo sport). Il percorso dovrà quindi accompagnare i chunk, altrimenti il retrieval non sa per quale sport è un workout.

## Valutazione della regola #4 (citazioni in evidenza)

La regola è stata trattata come un classificatore: i 214 `div.sidenote` dell'HTML fanno da etichette, i 1375 paragrafi restanti sono il testo normale che **non** va mai rimosso.

| Variante | Citazioni rimosse | Paragrafi normali rimossi |
|---|---|---|
| Solo sovrapposizione ≥ 0,5 | 157 | 6 |
| + almeno 5 parole, ≤ 60% della lunghezza dell'originale, frase completa | **157** | **0** |

I 6 errori della prima variante erano di due tipi: testi brevissimi citati da un paragrafo (titoli "SIDEBAR x.y", ISBN) e paragrafi quasi uguali ma di pari lunghezza (varianti di workout in appendice). Rimuoverli avrebbe fatto perdere contenuto: per questo le due condizioni in più.

Distribuzione utile per il futuro: una citazione ha 5–23 parole (mediana 13), è lunga in mediana l'11% del paragrafo originale e sta in mediana a 3 blocchi da esso.

**Riquadri non rimossi (57): contenuto originale, giusto tenerli.** Verificato in due modi:
- revisione manuale di un campione ai due estremi del punteggio (0 e ~0,45): nessuno ha una seconda occorrenza nel libro;
- misura: anche i più simili condividono con il paragrafo più vicino al massimo **7 parole consecutive** (tipicamente 4–6), cioè espressioni comuni sullo stesso tema, non frasi ripetute. Nessuno dei 57 testi compare due volte nel libro, con un'unica eccezione: il riquadro del cap. 8 identico alla "didascalia" della seconda immagine di FIGURE 8.1 (caso isolato, lasciato com'è).

Conclusione: soglia 0,5 confermata, non abbassarla. Stima finale sul libro: precisione 100%, richiamo ~100% (157 citazioni su 157). Elenco per la revisione: `data/processed/pull_quote_review.txt` (locale).

## Test sul libro reale

`tests/book/test_ingestion.py` (marker `book`) verifica sul libro vero che i problemi chiusi non ritornino. Gira con il normale `uv run pytest` ed è saltato automaticamente se il libro non è in `data/raw/`. I valori attesi sono in `tests/book/expectations.py`.

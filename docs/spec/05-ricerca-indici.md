# O3 — Ricerca: indici, range e search/sort list

Trovare e ordinare i record come Alpha Four: indici dinamici, range con
prima/ultima chiave, liste di ricerca salvate o one-time, Find, Locate,
sostituzione e cancellazione dei duplicati.

## 1. Espressioni

Tutto ciò che l'utente scrive in un indice, in un filtro o in una ricerca è
un'espressione valutata dal modulo `data/expressions.py`.

- Operatori: `+ - * /`, `= == <> != < > <= >=`, `.AND. .OR. .NOT.` (anche
  senza punti), parentesi, `-` unario.
- Valori: testo fra virgolette doppie o singole, numeri, date `{MM/DD/YY}`,
  `.T.`/`.F.`, campi del database.
- Precedenza: `NOT` > `AND` > `OR`; con le parentesi si cambia.
- Funzioni principali: `UPPER LOWER TRIM LTRIM RTRIM LEFT RIGHT SUBSTR LEN AT
  OCCURS REPLICATE SPACE STUFF WORD W_COUNT VAL STR CHR ASC LIKE ISBLANK
  ISALPHA ISLOWER ISUPPER SOUNDEX DIFFERENCE ABS INT ROUND MOD MAX MIN SIGN
  FLOOR CEILING SQRT EXP LOG DATE CTOD DTOS CDATE YEAR MONTH DAY DOW CDOW
  CMONTH ADDMONTHS ADDYEARS IF IIF DELETED RECNO RECCOUNT BOF EOF` e le
  wildcard `*ANY *FIRST *LEADING *WORD`.
- Le date sono `datetime.date`; i numerici `Decimal`; i logici `bool`; il
  vuoto è `None`. Un errore di sintassi è riportato nella status line e non
  salva nulla.

### Pattern matching

Il confronto fra stringhe segue l'impostazione globale
`pattern_matching` (`adbx_settings`), come al prompt *Pattern matching*
delle Default Settings:

| Modo | `"Janelle" = "Jan"` | `"Smith" = "smith"` |
|---|---|---|
| `Exact` (predefinito) | falso | falso |
| `Case` | vero (prefisso, case-sensitive) | falso |
| `insensitive` | vero | vero |

Si cambia da `Other → Pattern matching`, che cicla i tre modi; il valore è
globale per il workspace.

`Exact` rimuove gli spazi finali prima del confronto; `==` confronta sempre
carattere per carattere, maiuscole comprese, indipendentemente dal modo.
La **Table mode** delle ricerche è sempre case-insensitive ed esatta, come
da manuale, anche con Pattern matching su `Case`.

## 2. Indici

Un indice è una definizione persistente in `adbx_indexes`:

| Campo | Significato |
|---|---|
| `name` | nome DOS 1–8 caratteri |
| `expression` | espressione di ordinamento (max 100 caratteri di chiave) |
| `levels` | livelli Field/Direction della Table mode |
| `description` | etichetta mostrata al posto dell'espressione |
| `filter` | espressione logica: solo i record veri entrano nell'indice |
| `allow` | `All`, `Unique`, `Unique with exceptions` |
| `case_sensitive` | ordine e duplicati distinti per maiuscole |
| `attached` | se è disponibile come primary index |

- **Table mode**: livelli `Field` + `Ascending/Descending`; l'espressione
  generata è `FIELD1+FIELD2+…`.
- **Expression mode**: l'espressione si scrive direttamente; può contenere
  funzioni e campi. Un indice con soli livelli usa il confronto multi-chiave,
  così le direzioni miste funzionano.
- La chiave usa i campi **imbottiti alla loro lunghezza**, come Alpha Four:
  `LASTNAME+FIRSTNAME` conserva gli spazi interni e Find richiede la stessa
  chiave. Il limite è 100 caratteri.
- Il filtro dell'indice è **sempre attivo**; i record esclusi non compaiono
  né nell'ordine né nei valori di chiave.
- Massimo 15 indici attached; il sedicesimo viene rifiutato.
- `Unique` blocca il salvataggio di un record con chiave già presente (il
  record stesso è escluso); `Unique with exceptions` lo consente ma lo
  segnala nella status line.
- **Update indexes** riapre l'indice nello stesso editor e lo ricostruisce.
- **Attach/detach** cambia solo il flag: un indice staccato non è
  manutenuto e non è offerto come primary.

Deviazione dichiarata: gli indici vivono in SQLite e non vengono scritti in
file `.NDX`/`.IDN`. Il `.DBF` resta la sorgente dei dati; un indice creato da
adbx non è leggibile da dBASE. La scelta evita di reimplementare un formato
binario morto e mantiene il file dati interoperabile.

## 3. Primary index e range

Il range corrente (`adbx_database_state.range_json`) contiene:

| Impostazione | Valori |
|---|---|
| Primary index | Record Number, un indice attached, Search/Sort List |
| Order | Ascending, Descending |
| Show | All, Deleted, Not deleted |
| First/Last record | chiave o `<First>`/`<Last>` |
| Unique keys | No, Yes |
| Filter | espressione |
| Filter status | Active, Inactive |

- Cambiare primary index resetta First/Last e Unique keys, e aggiorna il
  range: è il comportamento del manuale.
- L'ordine Discendente inverte l'ordine dell'indice (o dei record).
- First/Last confrontano la chiave; un valore parziale funziona da prefisso
  (`B` come Last include i record che iniziano per B).
- `Unique keys` tiene il primo record per ogni chiave dell'indice.
- Il filtro è dinamico e si può disattivare senza cancellare l'espressione.
- Il `Default Range` riporta tutto ai valori iniziali.
- Si salvano fino a 26 range (A–Z) con descrizione; `F7` li recupera.

Deviazione: il range predefinito di adbx mostra i record **non cancellati**
(`Show = Not deleted`), mentre il manuale parte da `All` con i cancellati
marcati. La scelta conserva il comportamento di O2 (F7 per mostrarli) ed è
reversibile dal Range Settings.

## 4. Search/sort list

Una search/sort list è un elenco di numeri di record in `adbx_search_lists`.
Non è un database: come l'indice, mostra i valori correnti dei record.

### Criteri

- **Table mode**: righe `Field`, `Op.`, `Search for What?`, `And/Or`.
  Operatori: `= > < >= <= <> ? *A *F *L *W`. I campi speciali `*CHAR *NUM
  *DATE *LOGIC *MEMO` cercano in tutti i campi del tipo.
- `And/Or` sulla riga unisce la riga con la successiva; `AND` ha precedenza
  su `OR`.
- **Expression mode**: espressione libera, con distinzione maiuscole
  secondo Pattern matching; `F9` passa da una modalità all'altra.
- **Sort**: Table mode (`Field` + `Ascending/Descending`) o espressione.
  Se c'è un ordinamento, il Range Settings non compare: il sort basta.
- `Show` della lista: `All`, `Deleted`, `Not deleted`; `Case sensitive`
  per l'ordinamento.
- Si possono salvare 26 criteri (A–Z) con descrizione; le ricerche one-time
  non salvano i criteri ma producono una lista.
- `F7 (Use last)` copia i criteri dell'ultima ricerca.

### Esecuzione e storia

- La lista prodotta diventa subito primary index; finché è attiva si vedono
  solo i suoi record.
- Una ricerca successiva con la lista attiva e senza ordinamento cerca solo
  fra i record della lista (intersezione). Se la lista nuova non ha sort,
  compare il Range Settings.
- La storia conserva le ultime **10** liste, salvate e one-time.
- Una lista diventa **out of date** quando la revisione del database cambia
  (append/update/delete/pack/alter) o quando cambiano i criteri salvati. È
  marcata con `♦` nella status line, nel popup degli indici e nella storia.
- `F5 (Refresh)` ricostruisce la lista con gli stessi criteri e il range
  memorizzato; `F4` la cancella.

Deviazione: non esistono i file `.SLx`/`.SL0-9`; le liste e i loro criteri
stanno in SQLite. La storia è di 10 elementi, non 36 file.

## 5. Find, Locate, Replace

### Find

`F` in View/Browse (e Change). Usa l'indice primario o il sort della lista:

- chiede la chiave con l'etichetta dell'indice (`Which 'Alphabetically by
  Title'`);
- trova il primo record con chiave **uguale o successiva** (il più vicino);
  una stringa parziale funziona da prefisso;
- con primary `Record Number` chiede un numero di record;
- il confronto è case-insensitive salvo indice case-sensitive.

Deviazioni: non sono implementati `F2 (Use alternate index)` e la storia
delle stringhe con `UP` al prompt; la cronologia resta nella sessione
(`find_history`) e non è ancora esposta.

### Locate

`L` in View/Browse. Cerca il testo **ovunque** nei campi selezionati:

- Field Selection con `ENTER`/`SPACE` per selezionare, `F3` tutti i campi
  non memo, `F4` tutti (memo compresi), `F10` avvia;
- la ricerca parte dall'inizio del range corrente ed è case-insensitive;
- ogni corrispondenza imposta il record; la status line dice `Locate: FIELD`
  e `(Memo)` se il match è in un memo;
- `F3` = Next locate, `ESC` = esci dal Locate (non chiude la modalità).

Deviazioni: durante il Locate non ci sono i comandi `Change`/`Options` del
menu originale; si esce e si usa la modalità record normale.

### Search and replace

Solo in View (`S`). Chiede *Search for*, *Replace with*, i campi (i memo sono
esclusi, come da manuale) e conferma. Sostituisce **tutte** le occorrenze,
case-insensitive, e riscrive il `.DBF` una volta sola.

Deviazione: manca la conferma per ogni sostituzione (`Replace/Bypass/Quit/
Change`); l'operazione è tutto-o-niente dopo la conferma.

### Delete duplicate records

`Global update/delete → Delete duplicate records`. Richiede un indice
primario (non Record Number, non una search list) e marca cancellati tutti i
record con chiave duplicata tranne il primo nell'ordine dell'indice. Il
`PACK` li elimina fisicamente.

## 6. Tasti

| Contesto | Tasto | Azione |
|---|---|---|
| View/Browse | `F` | Find |
| View/Browse | `L` | Locate |
| View/Browse | `I` | scegli primary index |
| View/Browse | `R` | Range Settings |
| View | `S` | Search and replace |
| Indice (tabella) | `F2` | elenco campi |
| Indice (tabella) | `F5`/`F6` | elimina/inserisci livello |
| Indice (opzioni) | `TAB`/`ENTER` | cambia Allow/Case |
| Range | `F2`/`F3`/`F7` | indice / key values / retrieve |
| Range | `F10` | Save box, poi Save o Exit |
| Range | `ALT-E` | esci e applica senza salvare |
| Search table | `F2`/`F3` | campi / operatori |
| Search table | `F4` | Sort Table |
| Search table | `F7`/`F8`/`F9` | use last / descrizione / espressione |
| Storia | `F5`/`F4` | refresh / delete |

## 7. Accettazione

`tests/test_index_ui.py` — lezione 7: creazione in Table mode, indice a due
livelli, primary index, Expression mode.
`tests/test_find_locate_ui.py` — lezione 8: Find sull'indice, Locate su campo
e memo, search and replace, delete duplicate.
`tests/test_range_ui.py` — lezione 9: ordine discendente, Show deleted,
unique keys, key values G–PG, range salvato e Default Range.
`tests/test_search_ui.py` — lezione 15: ricerca one-time con Range Settings,
criteri salvati con sort, storia, out-of-date e refresh, run/erase.

Test di supporto: `tests/test_expressions.py` (pattern matching nei tre modi,
precedenza AND/OR, funzioni, wildcard, tabella), `tests/test_indexing.py`
(indici, filtri, range, liste, revisione, unique).

Screenshot: `docs/render/10-index-table.png`, `11-range-settings.png`,
`12-search-table.png`, `13-search-history.png`.

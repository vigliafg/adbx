# O4 — Regole di campo

La logica dichiarativa del capitolo 10 del Reference Manual: valori calcolati,
default, incrementi, maschere, validazioni, doppia immissione, skip, post data
e lookup. Le regole vivono nel workspace SQLite e vengono valutate dalla
sessione record a ogni passaggio di campo e a ogni salvataggio.

## 1. Dove stanno le regole

Nel manuale le regole sono in `database.RLN`. adbx le conserva nella tabella
`adbx_field_rules(owner, field, rules)` con `rules` in JSON. `owner` è il nome
del database; in O5 potrà essere anche il nome di un set.

**Risoluzione database/set.** Per ogni campo Alpha Four usa *o* le regole di
set *o* quelle di database, mai un mix. Se il set definisce una qualunque
regola per un campo, tutte le regole di quel campo vengono dal set. La regola
è implementata in `resolve_rule`/`resolve_rules` e verificata da
`test_set_level_rule_replaces_database_rule_entirely`. I set arriveranno con
O5: oggi esiste solo il livello database.

Il comando è `Database/set design → Field rules`, con tre voci:
`Create/edit field rules`, `Re-evaluate field rules`, `Erase field rules`.
La schermata ha in alto l'elenco dei campi e in basso le regole del campo
attivo, su tre pagine.

## 2. Pagina 1 — valore e formato

| Regola | Valori | Note |
|---|---|---|
| `Value` | `User-entered`, `Calculated` | `Summary` è solo per i set (O5) |
| `Expression` | espressione | visibile solo per un campo calcolato |
| `Case Convert` | `None Caps Lower First Word X` | solo campi carattere |
| `Template` | caratteri fissi | `\|` = spazio fisso; gli spazi sono le posizioni libere |
| `Mask` | `9 A a` e spazi | `9` cifra, `A` maiuscola, `a` lettera, spazio qualsiasi |
| `Allow Exceptions` | `No/Yes` | una violazione di maschera viene segnalata ma salvata |
| `Default Mode` | `None Value Expression` | valore costante o espressione |
| `Increment` | `None Records Updates` | numeri, date e testo alfanumerico |
| `Auto-advance` | `No/Yes` | passa al campo successivo a riempimento completato |
| `Prompt` | testo | messaggio sulla status line mentre il campo è attivo |

### Campi calcolati

L'espressione deve restituire un valore del tipo del campo; il valore viene
scritto nel record come gli altri. Il campo non è editabile, viene saltato
dalla navigazione e ricalcolato dopo ogni campo confermato. Il ricalcolo
ripete fino a quattro passaggi per catene come
`SUBTOTAL → INVTOTAL`. Un errore di espressione lascia il valore precedente;
il salvataggio non viene bloccato.

### Template e maschere

Il template è una stringa della stessa lunghezza del campo. I caratteri
diversi da spazio sono fissi; `|` diventa uno spazio fisso. Il cursore salta i
caratteri fissi, backspace non li cancella e il valore salvato contiene i
caratteri fissi. Se non si digita nulla il campo resta vuoto: il template non
viene salvato.

La maschera si applica alle sole posizioni libere del template. Senza
template si applica posizione per posizione al valore. `Allow Exceptions`
consente di salvare un valore non conforme, con un avviso.

### Increment

- `Records`: il valore è proposto per ogni nuovo record partendo **dall'ultimo
  record fisico** (record number più alto, cancellati inclusi); un valore
  inserito a mano diventa la base per il successivo.
- `Updates`: +1 a ogni salvataggio, anche senza modifiche.
- Numeri: +1 con i decimali del campo. Date: +1 giorno.
- Testo: base 36 dalla destra (`12→13`, `A9→B0`, `13Z→14A`, `ZZ→AAA`), con i
  template rispettati.

## 3. Pagina 2 — controllo dell'immissione

| Regola | Valori | Comportamento |
|---|---|---|
| `Required` | `No Yes Expression` | impedisce di lasciare il campo vuoto e di salvare |
| `Required Expn` | espressione | la condizione vale solo se `Required=Expression` |
| `Validation Expn` | espressione logica | falsa ⇒ messaggio e campo non confermato |
| `Validation Msg` | testo | mostrato quando la validazione fallisce |
| `Double Entry` | `No Yes Expression` | chiede due volte lo stesso valore |
| `Dbl Entry Expn` | espressione | condizione della doppia immissione |
| `Skip Expression` | espressione logica | vera ⇒ il campo viene saltato |
| `Post data` | `No Yes` | abilita le regole di post (F8) |

La doppia immissione confronta i valori canonici dopo il parsing. Al primo
invio il campo si svuota e chiede conferma; un valore diverso azzera il ciclo
e chiede di ricominciare. Il salvataggio è bloccato finché la coppia non
coincide.

Le validazioni vengono rieseguite su tutti i campi al salvataggio, non solo
sull'ultimo campo confermato. Un campo obbligatorio blocca anche il passaggio
al campo successivo (non quello all'indietro), come da manuale.

## 4. Post data

La regola `Post data` contiene una o più righe (`PostingRule`):

| Campo | Significato |
|---|---|
| `Database` | database di destinazione (nome nel workspace o file `.DBF`) |
| `Field to post to` | campo da aggiornare |
| `Mode` | `Add`, `Subtract`, `Replace` |
| `Condition` | espressione logica opzionale |
| `Expression` | valore da postare; vuoto = campo sorgente |
| `Link index` | indice del database di destinazione |
| `Common` | campo/espressione comune nel database corrente |

Il post avviene dopo la scrittura del record. Su un record nuovo si posta il
valore; su una modifica si posta la **differenza** fra nuovo e vecchio valore
sorgente per `Add`/`Subtract`, mentre `Replace` scrive il valore assoluto. Il
record di destinazione è il primo con chiave uguale a `Common`; senza indice
di collegamento si usa il primo record. Errori e destinazioni mancanti
diventano avvisi nella status line e non annullano il salvataggio.

## 5. Pagina 3 — lookup

`Lookup=Yes` abilita:

| Regola | Valori |
|---|---|
| `Lookup Validation` | `None`, `Exists`, `Doesn't Exist` |
| `Allow Exceptions` | `No/Yes` per Exists/Doesn't Exist |
| `Location` | `1`–`9` (tastierino) o `Hidden` |
| `Rows in Window` | `1`–`15` |
| `Auto Pop-up` | `No`, `Yes`, `Expression` (Entry/Exit) |
| `Lookup Source` | `Table`, `Database`, `Advanced` |

In data entry `F3 (Choices)` apre la finestra sul campo corrente. `UP/DOWN`,
`PGUP/PGDN` scorrono, digitare cerca per prefisso, `ENTER` sceglie, `ESC`
annulla. `Location` decide l'angolo della finestra; `Hidden` impedisce di
mostrarla.

### Lookup table

Fino a 6 colonne e 255 righe. La prima colonna è la scelta per il campo; le
altre 5 riempiono campi omonimi del record corrente alla selezione. `F2` in
`F7 (Lookup table)` aggiunge una colonna, `F5/F6` cancellano/inseriscono righe.

### Lookup database

F7 apre il **Lookup Mapping**: righe `Choice Field`, `Filled Field`,
`Condition`, `Expression`, `Display`. Almeno una riga deve riempire il campo
corrente. Il campo scelto nel database di lookup determina la chiave; il
`Linking Index` accelera e il `Display Index` ordina la finestra. `Condition`
e `Expression` permettono di riempire campi diversi per riga; `Display`
decide se la colonna compare nella finestra.

### Cascading table

F7 apre un outline: `TAB` demota, `SHIFT-TAB` promuove. Le foglie sono
endpoint; `~` separa il testo mostrato dal valore da salvare; `^` fa
restituire il percorso completo (`Fiction. Thriller`). La finestra mostra un
livello alla volta e `LEFT`/`BACKSPACE` risalgono.

### Conditional table / conditional database

`Advanced` sceglie fra `Cascading table`, `Conditional table` e
`Conditional database`. Nei due modi condizionali si definiscono gruppi
`Expression` (+ `Filter` per le tabelle) e un gruppo di fall-through. Il primo
gruppo vero viene usato; il fall-through è la tabella o il database della
pagina 3. Nei filtri delle tabelle `LOOKUP->FIELD` indica una colonna della
tabella, gli altri nomi vengono dal database corrente.

## 6. Tasti

| Contesto | Tasto | Azione |
|---|---|---|
| Elenco campi | `ENTER`/`F9` | apri le regole del campo |
| Elenco campi | `F5` | cancella tutte le regole del campo |
| Regole | `ENTER` | modifica un testo o cambia una scelta |
| Regole | `PGUP`/`PGDN` | pagina 1/2/3 |
| Regole | `F2` | elenco campi nell'espressione |
| Regole | `F7` | tabella, mapping, cascata o condizioni |
| Regole | `F8` | regole di post data |
| Regole | `F9` | torna all'elenco campi |
| Regole | `F10` | salva tutte le regole |
| Data entry | `F3` | apre la finestra di lookup |
| Lookup | `LEFT`/`BACKSPACE` | risale di un livello nella cascata |

## 7. Accettazione

`tests/test_rules.py` — motore: maiuscole, template/maschere, default,
incrementi, required, validation, double entry, skip, calcolati, lookup
table/database, cascata, condizionali, post data (Add/Subtract/Replace e
differenza), risoluzione set/database, persistenza e rinomina dei campi,
re-evaluate.

`tests/test_field_rules_ui.py` — lezioni 11, 12 e 13 dall'interfaccia:
creazione delle regole dal menu, tabella di lookup con scelta e validazione,
lookup database con mapping, re-evaluate ed erase.

`tests/test_field_rules_entry.py` — integrazione in data entry: obbligatorietà,
validazione, doppia immissione, skip, auto-advance, calcolati, default,
lookup e post data al salvataggio.

Screenshot: `docs/render/14-field-rules.png`, `15-lookup-table.png`,
`16-lookup-choices.png`, `17-posting-rules.png`.

## 8. Deviazioni dichiarate

- Niente file `.RLN`: le regole sono nel workspace SQLite. Il `.DBF` resta
  interoperabile; le regole no.
- `Summary` è riservato ai set e non è ancora calcolato (O5).
- L'`Exit expression` dell'auto popup non apre la finestra al momento
  dell'uscita dal campo; sono implementate la modalità `Yes` e l'`Entry
  expression`.
- I filtri delle conditional table usano `LOOKUP->`; le lookup database
  filtrano con i campi del database di lookup.
- Il post data verso un database esterno aggiorna il primo record trovato;
  il post verso un figlio 1:N arriverà con i set (O5).
- Le regole di un campo memo si limitano al `Prompt`, come da manuale.
- Un campo `Calculated` mostra le altre regole nell'editor ma il motore usa
  solo calcolo e post data; la UI non le nasconde.

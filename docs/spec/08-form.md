# O6 — Form designer

Un form è una schermata a celle composta da testi, campi, riquadri e regioni.
Fino a 26 form per database o set (A–Z), fino a 10 pagine ciascuno. La
definizione vive nel workspace SQLite (`adbx_forms`), non in file `.INx`.

## 1. Form e parametri

`Layouts → Forms` offre:

- `Create/edit a form`: lettera A–Z, descrizione e parametri; se la lettera
  esiste il form viene riaperto nel layout.
- `Select active form`: sceglie il form usato da View/Enter/Change.
- `Erase a form`: cancellazione con conferma.

Il form salvato diventa subito attivo (`active = 1` per proprietario).

| Parametro | Uso |
|---|---|
| `Description` | etichetta nella lista (`A - Alpha Video`) |
| `Custom menu bar` | testo del menu personalizzato (memorizzato) |
| `Restrict access` | comandi limitati (memorizzato) |
| `Printable` | se il form può essere stampato |
| `Print width` | 40–240 colonne |
| `Margins` | margini di stampa |

Per un set il proprietario è il nome del set; i campi possono appartenere a
qualsiasi database del set e le regioni ai link 1:N.

## 2. Layout

La griglia usa le stesse coordinate dello schermo (righe 1–40, colonne
1–128). `PgUp`/`PgDn` cambiano pagina; le pagine usate vengono calcolate al
salvataggio. Le etichette sono testo; i campi hanno `length`, `window`,
giustificazione, formato e titolo opzionale.

| Tasto | Azione |
|---|---|
| `F2` | elenco campi (con `DB.FIELD` nei set); inserisce il campo al cursore |
| `F4` | campo calcolato o summary |
| `F5` | cancella l'elemento sotto il cursore |
| `F6` | aggiunge una regione 1:N (solo set) |
| `F7` | parametri del form |
| `F8` | disegna un riquadro |
| `F9` | opzioni di formattazione |
| `F10` | salva |
| `PgUp/PgDn` | pagina precedente/successiva |
| `Alt-O`-equivalente | `F9` |

### Campi

- Un campo reale è un riferimento `database.field`; il valore è preso dal
  record corrente.
- Un campo calcolato ha un'espressione valutata sui valori del record e non
  viene salvato.
- Un campo summary aggrega i figli 1:N: `Count`, `Total`, `Average`,
  `Biggest`, `Smallest`, `First`, `Last` su un campo del figlio. La regione
  serve a mostrare le righe; il summary può stare anche fuori dalla regione.
- I campi memo con formato `!X` mostrano il testo su più righe; `length` è
  il numero di caratteri e `window` la larghezza.

### Formattazione

`F9` mostra le colonne `Field`, `Page`, `Len`, `Window`, `Just`, `Fmt`,
`Title`. `Len` e `Window` ammettono testo; `Just` cicla `L`/`R`/`C`; `Fmt`
accetta `!X` per i memo e `Title` imposta il titolo mostrato sopra il campo.
Il form designer semplifica il manuale: non ci sono blocchi/move/copy e i
colori sono memorizzati ma non ancora resi.

## 3. Regioni

Una regione è un riquadro che mostra i record figli del link 1:N corrente.
La regione contiene `Database`, `Title`, altezza/larghezza, `Maximum`
(default 100), `Filter` e `Show Mode` (nel modello). Nel form del set:

- la regione viene disegnata nella pagina e scorre con `UP/DOWN` quando il
  focus è sulla regione (`F6`);
- `Alt-Z` apre il figlio selezionato in Browse;
- il summary può usare la stessa regione o una regione nascosta (il modello
  non richiede che il summary stia dentro la regione);
- una regione non rende il form non stampabile di per sé: `Printable`
  controlla la stampa; il report engine di O7 userà il flag.

## 4. Uso nei record

`View/enter records` carica il form attivo del database o del set:

- **database**: `RecordSession` disegna campi, testi, riquadri e memo
  multilinea; la navigazione segue l'ordine dei campi del form; i campi
  esclusi dal form non vengono visitati; i calcolati sono di sola lettura.
- **set**: `SetSession` combina i campi del primario e dei figli 1:1 del
  form, disegna le regioni e i summary; Enter/Change modificano i campi reali,
  mentre le regioni si modificano con lo zoom.
- Le regole di campo e i lookup restano quelli del database; il form cambia
  solo la presentazione e l'ordine.

Senza form attivo resta il form automatico di O2/O5.

## 5. Accettazione

`tests/test_forms.py` — persistenza e active form, pagine, validazione dei
campi, calcolati, summary, form di set con regione e flag di stampa.

`tests/test_forms_ui.py` — creazione dal menu, campi e caselle, parametri,
formattazione, View/Enter con form personalizzato, form di set con regione e
summary, select/erase.

Screenshot: `docs/render/21-form-designer.png`, `22-custom-form.png`,
`23-set-form.png`, `24-formatting.png`.

## 6. Deviazioni dichiarate

- Niente file `.INx`: i form sono nel workspace SQLite.
- Colori, `Restrict access` e `Custom menu bar` sono memorizzati ma non
  ancora applicati alla UI; la stampa arriva con O7.
- Non ci sono Borrow form, Block/Move/Copy, editor di regione completo né
  auto-expand `@` nella stampa.
- Un titolo di campo è disegnato sopra il campo con larghezza minima; il
  manuale permette di posizionare il titolo separatamente.
- I summary calcolano sui figli del link 1:N del set, non su più livelli.
- I form dei database non usano regioni (sono riservate ai set).

# adbx — piano di realizzazione

Clone funzionale moderno di **Alpha Four versione 3** (Alpha Software, 1993):
database relazionale a finestre di caratteri, senza programmazione, con
regole di campo, set, report, script e applicazioni.

- Licenza: MIT
- Piattaforme: Linux, Windows, macOS
- Interfaccia: finestra con griglia di celle 132×43, font TrueType (DejaVu Sans Mono)
- Motore: SQLite
- Lingua di sviluppo: Python 3.11+

La specifica di riferimento è la documentazione originale di Alpha Four v3
(`Reference Manual`, 25 capitoli + 8 appendici; `Tutorial Manual`, 25 lezioni),
letta e inventariata in `docs/reference/`.

---

## 1. Principi

1. **Fedeltà funzionale, non emulazione del DOS.** Si replicano comportamenti,
   comandi, tasti, semantica e forma delle schermate. Non si emula l'hardware:
   niente EMS/XMS, niente driver ESC/P, niente `.PIF`.
2. **Fedeltà della griglia.** Lo schermo è una matrice di celle (carattere +
   colore + blink). Non esistono widget: esistono box, placeholder, popup,
   regioni, righe. Questo non è un vezzo: report, script e designer di Alpha
   Four *sono* operazioni su celle, e solo su celle restano economici.
3. **Semantica record-based.** Alpha Four ragiona per numero di record, con
   cancellazione logica, `PACK`, ordine da indice primario. Lo strato dati lo
   riproduce, non lo aggira.
4. **Una sola tastiera.** Il gestore di tastiera è unico; il motore di script
   inietta tasti in quel gestore. Se il playback non passa dal vero key
   handler, il keystroke scripting non è fedele.
5. **Determinismo.** Ogni scelta con più esiti ammessi (arrotondamenti,
   ordinamenti, precedenze) è fissata da un test di conformità, non dal caso.
6. **La documentazione è la specifica.** Ogni ondata cita i capitoli o le
   lezioni che implementa; ogni comportamento non documentato va segnalato,
   non inventato.

---

## 2. Non-obiettivi e deviazioni dichiarate

Fuori scope, per scelta esplicita:

| Elemento originale | Perché è escluso | Conseguenza |
|---|---|---|
| Runtime cifrato, `A4ENC`, `A4EXEMKR` | modello commerciale DOS | le applicazioni si distribuiscono come progetto |
| `SETUP.DTA`, installer DOS | sostituito dal packaging Python | — |
| Multiuser, `A4.NET`, bump licenze, locking DOS | desktop moderno single-user | opzioni `Shared`/`Exclusive` presenti ma inattive |
| Novell, NetBIOS, Banyan, Lantastic | reti scomparse | — |
| Dialer Hayes, `MODEM.CFG` | modem scomparsi | comando `Dial Telephone` assente |
| Swap EMS/XMS, `CONFIG.SYS`, `FILES=`, `BUFFERS=` | non applicabili | — |
| `.NDX` in scrittura | formato indice proprietario | `.NDX` in sola lettura; indice interno proprio |
| `A4LIB`, `SCRIPTED` | tool di distribuzione | sostituiti da file `.SCP` leggibili |
| `PFS:File`, DBMII, Multiplan | formati morti | import solo se a costo trascurabile |

Deviazioni consapevoli dalla documentazione:

1. **Form fino a 25 schermate.** Il manuale stampato (cap. 13) dichiara 10;
   il `README.DOC` della 3.0 dichiara 25. Si adotta 25 e si documenta il
   conflitto.
2. **Colori di campo 0–255** mappati su una palette a 16 colori + attributi;
   la mappatura è fissata in O0 e verificata con rendering golden.
3. **Support files come JSON su disco**, non dentro SQLite: `Borrow`,
   `Duplicate`, `Inherit support files`, `Prevent/allow file alterations`
   sono operazioni su file e restano tali.
4. **Numeri memorizzati come testo canonico** (non `REAL`): 19 cifre con 14
   decimali, arrotondamenti e conversione in lettere richiedono esattezza.
5. **`Pattern Matching`** ha tre valori (`Exact`, `Case`, `Case-insensitive`);
   il default della v3 è `Exact`, quello della v2 era `Case`.

---

## 3. Architettura

### 3.1 Strati

```
config/      A4.DFL equivalente (JSON), driver stampanti, palette
cell/        buffer di celle, colori, mapping CP437, renderer, mouse mapping
screen/      scene, popup, dialog, menu line, status line, help line, keymap
data/        SQLite, DDL, strato record, indici, range, liste, memo, lock logico
expr/        valutatore di espressioni e funzioni (semantica Alpha Four)
rules/       field rules, lookup, post data, trigger
sets/        modelli di set, link, integrità referenziale, regioni
design/      builder di tabelle, form, browse, report, etichette, lettere, set
report/      motore a sezioni, multipass, formattazioni, anteprima, PDF
letters/     parser del markup delle lettere
script/      keystroke engine, dialog, menu bar, variabili, debugger, trigger
app/         applicazioni, banner, macro, simulate
util/        copy/append/summarize/pack/zap/crosstab/post/join/intersect/subtract
io/          import/export formati legacy e moderni
docs/        generatore di documentazione (equivalente A4DOC)
```

### 3.2 Motore a celle

- Griglia logica **132×43** fissa; font **TrueType** incorporato (DejaVu Sans
  Mono regular/bold, licenza Bitstream Vera); corpo scelto automaticamente per
  riempire la finestra, senza mai stirare i glifi (vedi
  `docs/spec/01-scalabilita.md`).
- Cella = `(char, fg, bg, blink, bold)`. Attributi ereditabili.
- Righe convenzionali: **23** status line, **24** help line, **25** menu line.
- Canvas separato per la stampa: fino a **240 colonne** (report), righe per
  pagina configurabili (default 66, 60 per laser).
- Backend: `QPainter` su `QWidget` (primario). Il renderer non conosce la
  semantica: riceve solo celle. Questo rende possibile, in futuro, un backend
  terminale senza toccare il resto.
- Anteprime e screenshot: dump testuale della griglia (formato `golden`).

### 3.3 Dati: SQLite con strato record

| Alpha Four | adbx |
|---|---|
| `.DBF` | tabella `t_<db>`: una colonna per campo + `__seq`, `__deleted` |
| `.DBT` memo | tabella `m_<db>(seq, field, body)` |
| numero di record | posizione in ordine di `__seq` |
| `PACK` | delete fisico + rinumerazione di `__seq` |
| `.NDX` | tabella `i_<idx>(key, seq)` + definizione in `index_defs` |
| `.IDN` | tabella `index_attach` |
| `.SET` | `sets` (JSON) |
| range, search/sort, layout, rules, app, script | file JSON in `objects/` |

Regole:

- **Numeric** in testo canonico con segno, punto e decimali fissi; aritmetica
  in `Decimal`, arrotondamento half-up come da manuale.
- **Date** come `YYYYMMDD` intero; `Logical` come `0/1` con blank ammesso;
  `Memo` in tabella separata (nessun puntatore, semantica equivalente).
- **Cancellazione logica**: `__deleted`; `Show` = `All`/`Deleted`/`Not Deleted`
  applicato dallo strato range, non da SQL.
- **Generazione database**: contatore incrementato a ogni scrittura; le liste
  search/sort lo registrano e diventano *out-of-date* quando cambia (◇).
- Tabella `t_<db>` senza `ROWID` impliciti nascosti: `__seq` è l'unica chiave.

### 3.4 Indici, range, liste

- Indice = definizione (`expression`, `filter`, `case_sensitive`, `unique`,
  `descending`, `description`) + tabella chiavi materializzata, mantenuta in
  scrittura.
- Chiave normalizzata per collation: maiuscolo se `case_sensitive = No`.
- Ordinamento `BINARY` sul testo normalizzato; `INVERT()` per i discendenti.
- `Key Values` popup, `Find` per prefisso e `First/Last record` leggono la
  tabella chiavi, non i dati.
- `Unique only` / `Unique with Exceptions` applicati in scrittura; duplicato =
  stessa chiave, anche con altri campi diversi.
- Range = struttura di impostazioni (primary index, order, show, first, last,
  unique keys, link mode, filter, filter status) applicata dallo strato
  lettura.
- Search/Sort list = tabella `(pos, seq)` + criteri; history a 10; 26 salvate
  + 10 one-time.

### 3.5 Espressioni

Valutatore unico, usato da indici, filtri, range, calcolati, validazioni,
report, script. Semantica:

- `=` dipende da `Pattern Matching`; `==` sempre esatto (solo character);
  `-` concatena con trim; `$` substring case-sensitive.
- `AND` più forte di `OR`; `.AND.`/`.OR.`/`.NOT.`; parentesi.
- Data letterale `{11/25/91}`; `+`/`-` su date con giorni.
- ~75 funzioni (elenco completo in `docs/reference/00-inventario.md`).
- Limiti: espressione 254 caratteri (512 per search/sort), filtro 254.

### 3.6 Field rules

Pipeline per campo, ordine fissato:

```
mask/template → case convert → default → increment → skip
→ required → validation → double entry → lookup → post data
→ calculated / summary → trigger enter/validate/exit
```

- Risoluzione **database vs set tutto-o-niente**: se esiste una qualunque
  regola a livello set per un campo, *tutte* le regole di quel campo vengono
  lette a livello set.
- `Calculated` ammette come unica altra regola `Post data`.
- `Summary` solo a livello set e solo sul database primario.
- `Re-evaluate field rules` con marcatura dei record non conformi.
- Lookup: tabella (max 6 colonne, 255 righe), database, condizionale,
  cascading; 4 forme di validazione; popup con `Location` 1–9 o `Hidden`.

### 3.7 Set e regioni

- Max 10 database per set; un solo link 1:N per livello; set annidati
  (sottoset non può essere parent).
- `Link to`: `All` (1:N), `First`/`Last` (1:1), `Closest` (1:1 inesatto,
  primo figlio con chiave ≥).
- Integrità referenziale con cascading update/delete, `Integrity Rule` per il
  riempimento dei campi figli, `Include Parent If`.
- Regione = sotto-forma nella griglia: bordo, colori, ombra, titoli, griglia,
  riga record number, `Maximum Number of Records` (default 100), filtro,
  `Display Region`, read-only, `REG_RECNUM`.
- Un form con regioni **non è stampabile**: la stampa passa da un report.

### 3.8 Designer

Tutti i designer operano sulla stessa griglia con gli stessi comandi
(`F2` campi, `F3` colore, `F4` blocco, `F5/F6` insert/delete, `F7` goto,
`F8` box, `F9` linea, `F10` continue). Un solo motore di editing.

### 3.9 Report

- Sezioni: Report Header, Page Header, Titles, Group 1–9 Header, Detail,
  Group 1–9 Footer, Page Footer, Summary.
- Larghezza 40–240 colonne; 128 campi calcolati; 9 livelli di gruppo.
- `Summary`: 7 tipi × 3 livelli × 4 ignore × 2 modi (`Running`,
  `Pre-processed` = multipass).
- Codici di formattazione carattere/numerici/data/memo; attributi di stampa
  `!b !i !n !u !o`; riga non sopprimibile `CHR(127)`.
- Opzioni: widow/orphan, split lines, page breaks, form pre-stampati, pagina
  separata per il summary, reset numerazione per gruppo.
- Anteprima a schermo (fino a 10 pagine indietro, scroll orizzontale, split),
  stampa PDF.

### 3.10 Script

- Tre tipi: **keystroke**, **dialog box**, **menu bar**.
- Keystroke: registrazione reale dei tasti (`F3 Learn`, `F4 Append`),
  iniezione nel key handler, `Screen Test` per validare il contesto.
- 40 comandi, argomenti `#`/`$`/`%`, blocchi, label `:A`–`:Z`, commenti.
- Variabili `%NAME` (24 char, valore character ≤254, indirezione `@`,
  `VSAVE`/`VRESTORE`), variabili di sistema `%SYS_*`.
- 17 eventi di trigger, attivati assegnando `%SYS_TRIG_<EVENT>`.
- Limiti: 3.000 char per script, 1.000 per comando, 400 script per
  directory, 10 livelli di annidamento, debugger con single step.

### 3.11 Applicazioni

- Editor a due finestre (outline + parametri), voci `Sub-Menu`/`Macro`/
  `Call-App`/`GotO-App`, password per voce, help file ASCII, `Simulate`.
- Banner painter (box, colori, template, link testo/colore).
- Macro ≤3.000 char; `Call-App` fino a 10 livelli; `%SYS_APP_PATH`,
  `%SYS_APP_DESKTOP` per la portabilità dei path.
- `Prevent/allow file alterations`.

### 3.12 Utility e I/O

Copy, Append (4 modalità), Summarize, Pack, Zap, Cross Tabulation,
Post, Join, Intersect, Subtract. Import/export: dBASE II/III/IV, ASCII
carattere-separato, ASCII tabellare, DIF, SYLK, Lotus, WordPerfect merge,
Multimate; CSV come alias moderno dell'ASCII separato.

### 3.13 Configurazione e stampa

- `A4.DFL` → `config.json`: ultimo database, default settings, colori,
  valuta, stampante, script path, data path.
- 26 driver stampante con `Lines per page`, `Page advance`
  (formfeed/sheetfeeder/linefeed), codici setup/close-out/normal/bold/italic/
  underline/compressed, margini.
- `Set screen colors` per database/set con palette e alternative.
- `Default settings`: separatore data, formato americano/europeo, auto flush,
  pattern matching, prevent change/enter, single step enters, lock utility.

---

## 4. Mappa dei moduli

```
adbx/
  README.md  LICENSE  PLAN.md  DIARIO.md  pyproject.toml
  docs/
    reference/00-inventario.md      # limiti, funzioni, comandi, tasti, estensioni
    spec/                           # specifiche per ondata (si aggiungono in O0+)
  src/adbx/
    __init__.py  __main__.py
    config/  cell/  screen/  data/  expr/  rules/  sets/
    design/  report/  letters/  script/  app/  util/  io/  docs/
  tests/
    conformance/                    # un file per capitolo del manuale
    tutorial/                       # una prova per lezione
    golden/                         # dump di celle attesi
  tools/
    capture_ui.py                   # screenshot/dump canonici
```

---

## 5. Invarianti di UI

1. Schermo 132×43: riga 41 status, 42 help, 43 menu; area di lavoro 40 righe.
2. Ogni comando è raggiungibile in tre modi: highlight+`ENTER`, **hot key**
   (la maiuscola del nome: `V`, `P`, `S`, `I`, `G`, `C`, `D`, `L`, `A`, `U`,
   `O`, `Q`), mouse. I nomi dei comandi sono quindi API della tastiera.
   `W` è la scorciatoia per Choose database/set → sWitch databases.
3. `F10` = Continue ovunque; box `Save` standard (`Save`, `save As`,
   `save and Continue editing`, `save and Preview`); `ALT-S` = Save.
4. `ALT-F10` torna al main menu da ogni punto; `ESC`/tasto destro annullano un
   livello.
5. Fino a 26 oggetti per tipo, identificati da lettera A–Z; database, set,
   indici, script, lettere usano nomi DOS 8.3.
6. Ogni schermata mostra il contesto: status line, aiuto contestuale, comandi
   disponibili.
7. Modalità: View, Browse, Enter, Change, Simulation, Region[x]; il passaggio
   cambia menu line, status e gestione tasti.

---

## 6. Ondate

Regola: una ondata alla volta, test verdi prima della successiva, diario
aggiornato, commit atomici. Checkpoint a fine O3, O6, O9, O12.

### O0 — Fondamenta
- **Obiettivo:** repository, motore a celle, input, harness.
- **Scope:** buffer di celle, font TrueType, renderer `QPainter` scalabile,
  mapping mouse→cella, scene/popup, keymap con Alt/F/Ctrl, dump golden,
  packaging, CI.
- **Accettazione:** griglia 132×43 con 16 colori + blink; griglia scalata alla
  finestra senza stirare i glifi; box e popup disegnabili; ogni tasto della
  tabella comandi arriva al gestore; `pytest` verde; dump golden stabile su
  tutte le piattaforme.

### O1 — Shell
- **Obiettivo:** l'ambiente che si vede all'avvio.
- **Scope:** main menu a 12 comandi, status box, status/help/menu line,
  browser di directory (drive, wildcard, `<Parent>`, history, refresh),
  help `F1` con topic navigabili, `Quit`, temi/colori.
- **Accettazione:** lezioni 1 e 3 del Tutorial; help contestuale su ogni
  comando; directory navigabile da tastiera e mouse.

### O2 — Dati e immissione
- **Obiettivo:** database veri e record veri.
- **Scope:** strato SQLite+record, table designer (128 campi, tipi, lunghezze,
  riconfigurazione con tabella di conversione), View/Browse/Enter/Change,
  memo editor, clipboard, delete logico, pack, password.
- **Accettazione:** lezioni 2, 4, 5, 6; tabella di conversione dei tipi
  verificata caso per caso.

### O3 — Ricerca
- **Obiettivo:** trovare e ordinare come Alpha Four.
- **Scope:** indici (creazione, attach/detach, filtro, unique, case sensitive,
  key values), primary index, range (26), search/sort (table + expression,
  history, out-of-date), Find, Locate, Search and replace, delete duplicate.
- **Accettazione:** lezioni 7, 8, 9, 15; precedenza `AND`/`OR`; pattern
  matching nei tre modi; liste out-of-date marcate.

### O4 — Field rules
- **Obiettivo:** logica dichiarativa senza codice.
- **Scope:** tutte le regole del cap. 10, lookup table/database, cascading,
  conditional, post data, re-evaluate, risoluzione database vs set.
- **Accettazione:** lezioni 11, 12, 13; ogni regola ha un test dedicato;
  conflitto set/database verificato.

### O5 — Set e regioni
- **Scope:** set editor, link, integrity rule, referential integrity,
  cascading, zoom, regioni scorrevoli, include parent if.
- **Accettazione:** lezioni 20 e 22 (parte set); `Closest` verificato;
  limite 10 database e un 1:N per livello.

### O6 — Form designer
- **Scope:** layout a celle, 25 schermate, regioni, calcolati, summary,
  prompt order, colori, restrict access, menu bar custom, print parameters.
- **Accettazione:** lezioni 10 e 22 (form completo); form con regioni non
  stampabile.

### O7 — Report engine
- **Scope:** sezioni, gruppi, summary (7×3×4×2), formattazioni, multipass,
  widow/orphan, check writing, anteprima, PDF.
- **Accettazione:** lezione 19; report 1 e 2 del Tutorial identici al
  riferimento; numeri-in-lettere e `$*` verificati.

### O8 — Etichette e lettere
- **Scope:** label designer con giustificazioni avanzate (`Suppress`, `Float`,
  `Trim`, `Join`, `Before`, `After`), envelope, parser lettere
  (`[.IF]`, `[.ELSEIF]`, `[.INCLUDE]`, `[.EJECT]`, `[.WIDTH]`, `[@codici]`).
- **Accettazione:** lezioni 17 e 18.

### O9 — Utility e I/O
- **Scope:** copy, append (4 modalità), summarize, crosstab, post, join,
  intersect, subtract; import/export.
- **Accettazione:** cap. 19–21; ogni formato ha una fixture di andata e
  ritorno.

### O10 — Script
- **Scope:** keystroke engine con registrazione e `Screen Test`, dialog box
  designer, menu bar script, 40 comandi, variabili, `%SYS_*`, 17 trigger,
  debugger, `AUTOEXEC`, `nomeDB!`, `CTRL-F1..10`, `Tools`.
- **Accettazione:** lezioni 24 e 25; ogni comando ha un test; trigger
  verificati uno per uno.

### O11 — Applicazioni
- **Scope:** application editor, parametri, banner, macro, simulate,
  call-app/goto-app, password, prevent/allow.
- **Accettazione:** lezione 21; simulazione identica all'esecuzione.

### O12 — Configurazione e stampa
- **Scope:** 26 driver, codici, page advance, colori per database, default
  settings, documentation generator.
- **Accettazione:** cap. 22 e App. 6; stampa PDF con margini e formfeed
  verificate.

### O13 — Conformità 1.0
- **Scope:** suite completa delle 25 lezioni, armonizzazione dei messaggi,
  prestazioni, packaging, documentazione utente.
- **Accettazione:** Tutorial al 100% in CI; nessun test saltato; release 1.0.

---

## 7. Strategia di test

1. **Unità** — espressioni, arrotondamenti, conversioni, chiavi, parser.
2. **Conformità** — un file per capitolo del manuale; ogni prompt, default e
   caso limite diventa un test.
3. **Tutorial end-to-end** — 25 lezioni eseguite come scenari: creazione dei
   database `AV*`, immissione, indici, report, set, applicazione. È la prova
   d'accettazione del clone.
4. **Golden screens** — dump testuali delle celle, confronto byte a byte.
5. **Fixture** — dataset `AVMOVIES`, `AVPATRON`, `AVSALES`, `AVHEADER`,
   `AVITEMS` ricostruiti dagli esempi del Tutorial.

Comandi: `pytest`, `python -m adbx --smoke`, `python tools/capture_ui.py`.

---

## 8. Prestazioni

- Apertura database 10.000 record: < 300 ms.
- Scorrimento View/Browse: 60 fps percepiti, nessuna query per cella.
- `Find` su indice: < 20 ms.
- Report 1.000 righe con 2 gruppi: < 1 s in anteprima.
- Memoria: nessuna copia integrale del database in RAM.

---

## 9. Rischi

| Rischio | Impatto | Mitigazione |
|---|---|---|
| Report engine sottostimato | alto | O7 isolata, con dataset di riferimento e PDF golden |
| Fedeltà tastiera (Alt/F/Ctrl, repeat, tastierino) | alto | keymap come tabella dati, testata in O0 |
| Semantica `Pattern Matching` | medio | test dedicati nei tre modi, prima di O3 |
| Numerici a 14 decimali e lettere | medio | `Decimal` + test di arrotondamento |
| Script engine che dipende dalla UI | alto | key handler unico fin da O0, playback come iniezione |
| Scope creep su formati morti | basso | tabella delle deviazioni, import opzionali |
| Divergenza dal manuale | medio | ogni scostamento va nel diario, non nel codice |

---

## 10. Regole di lavoro

- `DIARIO.md` append-only: una voce per ondata, con stato, file toccati,
  scelte, test, problemi aperti, prossimo passo.
- Checkpoint a fine O3, O6, O9, O12: test completi, screenshot, blocco
  `RIPRESA`, stop.
- Commit atomici in italiano, imperativo (`O0: introdurre motore a celle`).
- Nessuna modifica al motore per accomodare la UI: si adatta la UI al motore.
- Ogni comportamento non documentato va segnalato nel diario.

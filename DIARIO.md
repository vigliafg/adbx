# Diario di implementazione — adbx

Append-only: le voci precedenti non si riscrivono e non si cancellano.
Una voce per ondata; più voci solo per sotto-attività rilevanti.

Formato:

```
### AAAA-MM-GG — Ondata N — Titolo
- Stato: in corso | completata | bloccata
- Branch/commit: ...
- Obiettivo: ...
- File toccati: ...
- Scelte/deviazioni: ...
- Test: ...
- Screenshot: ...
- Problemi aperti: ...
- Prossimo passo: ...
```

---

### 2026-11-23 — Avvio progetto — Repository e piano
- Stato: completata
- Branch/commit: `main`; commit iniziale.
- Obiettivo: creare il repository pubblico `adbx` e depositare il piano di
  realizzazione di un clone funzionale di Alpha Four v3, dopo la lettura
  completa della documentazione originale.
- File toccati: `README.md`, `LICENSE`, `PLAN.md`, `DIARIO.md`,
  `docs/reference/00-inventario.md`, `pyproject.toml`, `src/adbx/__init__.py`,
  `.gitignore`.
- Scelte:
  - Licenza MIT, nome `adbx`.
  - Interfaccia a **finestra con griglia di celle** 80×25, font CP437 8×16
    incorporato; motore **SQLite** con strato di emulazione record-based;
    multipiattaforma.
  - Il piano è organizzato in 14 ondate (O0–O13) con criteri di accettazione
    legati ai capitoli del `Reference Manual` e alle lezioni del `Tutorial`.
  - Inventario funzionale consolidato in `docs/reference/00-inventario.md`
    (limiti, funzioni, comandi di script, trigger, tasti, estensioni), per non
    perdere contatto con le funzionalità durante l'implementazione.
  - Deviazioni dichiarate: niente runtime cifrato, installer DOS, multiuser,
    modem, swap EMS/XMS; `.NDX` in sola lettura; form fino a 25 schermate
    (README 3.0) contro le 10 del manuale stampato.
- Test: nessuno (solo struttura).
- Screenshot: nessuno.
- Problemi aperti: i nomi esatti di alcune variabili `%SYS_TRIG_*` sono
  illeggibili nell'OCR del manuale e vanno verificati sull'help in linea
  durante O10; mappatura dei colori di campo 0–255 da fissare in O0.
- Prossimo passo: O0 — motore a celle, font CP437, input, harness di
  rendering.

---

### 2026-11-23 — Ondata O0 — Motore a celle
- Stato: completata
- Branch/commit: `main`; commit `O0: introdurre motore a celle, font e tastiera`.
- Obiettivo: fondamenta del clone: griglia 80×25, font CP437, renderer Qt,
  scene a strati, tastiera canonica, dump golden, CI.
- File toccati: `src/adbx/cell/{buffer,attrs,cp437,font}.py`,
  `src/adbx/screen/{keys,scene,demo,qt_input}.py`,
  `src/adbx/render/qt_renderer.py`, `src/adbx/{app,__main__}.py`,
  `src/adbx/data/cp437_8x16.bin`, `src/adbx/data/LICENSE-font.txt`,
  `tools/build_font.py`, `tools/capture_ui.py`,
  `tests/{conftest,test_cp437,test_buffer,test_font,test_keys,test_scene,test_render,test_shell,test_cli}.py`,
  `tests/golden/main-menu.txt`, `docs/spec/00-motore-celle.md`,
  `docs/render/*.png`, `.github/workflows/ci.yml`, `pyproject.toml`, `DIARIO.md`.
- Scelte:
  - **Font**: tabella bitmap 8×16 generata da DejaVu Sans Mono; i caratteri
    grafici (cornici, blocchi, retinature) sono **disegnati proceduralmente**
    perché il font tipografico lascia un pixel di vuoto ai bordi della cella e
    le linee risultavano tratteggiate. Verticale singola a `x=3`, orizzontale
    a `y=7`; doppia a `x=2,4` e `y=6,8`.
  - **Colori**: 16 VGA + bold/blink; i valori 0–255 dei form sono ridotti con
    `indice % 16` (regola provvisoria, da sostituire con la palette `A4.PAL`).
  - **Strati**: una schermata è una pila di `CellBuffer` con origine; il popup
    include la propria ombra nel buffer (`width+1 × height+1`), così
    l'ombra non viene tagliata e il compositore resta banale.
  - **Tastiera**: `Key(name, ctrl, alt, shift)` con notazione `alt-f`, `f10`,
    `{ENTER}` — la stessa che userà il motore di script per digitare.
  - **Dump golden**: riga di caratteri + run-length degli attributi
    (`count@fg,bg,bold,blink`), leggibile in diff.
- Test: `69 passed` (buffer, CP437, font, tasti, scene, rendering offscreen,
  CLI, golden screen). `python -m adbx --smoke` verde; `tools/capture_ui.py`
  produce `01-main-menu.png` e `02-popup.png` a 1280×800.
- Screenshot: `docs/render/01-main-menu.png`, `docs/render/02-popup.png`,
  `docs/render/font-cp437.png`.
- Problemi aperti:
  - La mappatura 0–255 → 16 colori è provvisoria; va chiusa con la palette
    originale prima di O6 (colori per campo nei form).
  - Il font tipografico ha il glifo un pixel più in basso del centro cella:
    accettabile, da valutare quando arriveranno i form veri.
  - La schermata dimostrativa è provvisoria: in O1 diventa il main menu reale.
- Prossimo passo: O1 — shell: main menu a 12 comandi con hot key, status box,
  browser di directory, help `F1` contestuale, `Quit`.

### 2026-11-23 — O0 — Avvio rapido (start.sh)
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: lanciare l'app senza attivare a mano un ambiente virtuale.
- File toccati: `start.sh`, `README.md`, `DIARIO.md`.
- Scelte: il launcher sceglie l'interprete in ordine `$ADBX_PYTHON`,
  `.venv/bin/python`, `python3`, `python`; se manca PyQt6 crea `.venv` e vi
  installa il pacchetto con `pip install -e .` alla prima esecuzione, poi
  riusa l'ambiente. Passa gli argomenti (`--smoke`, `--version`) e imposta
  `PYTHONPATH=src`, quindi funziona anche da altre directory. Nessuna
  attivazione manuale.
- Test: `./start.sh --smoke` e `./start.sh --version` verdi, anche da `/tmp`;
  `69 passed`.
- Problemi aperti: nessuno.
- Prossimo passo: O1 — shell.

---

### 2026-11-23 — Ondata O0 — Griglia SVGA, font TrueType, fit-to-window
- Stato: completata (sostituisce le scelte di font e dimensioni della voce O0
  precedente; la storia resta per tracciabilità).
- Branch/commit: `main`.
- Obiettivo: l'interfaccia era troppo grande e sgranata su schermi moderni.
  Passare a una griglia SVGA, a un font TrueType antialiasato e alla scalatura
  automatica della finestra, sul modello della console DOS di Windows XP.
- File toccati: `src/adbx/cell/buffer.py` (132×43, `STATUS_ROW`/`HELP_ROW`/
  `MENU_ROW`), `src/adbx/render/{qt_renderer,fonts,glyphs}.py`,
  `src/adbx/app.py`, `src/adbx/screen/demo.py`, `src/adbx/data/fonts/*.ttf`,
  `src/adbx/data/LICENSE-font.txt`, `tools/capture_ui.py`, test aggiornati,
  `docs/spec/00-motore-celle.md`, nuovo `docs/spec/01-scalabilita.md`,
  `PLAN.md`, `README.md`, `pyproject.toml`.
- Scelte:
  - **Griglia 132×43**: 132 colonne è la larghezza dei modi testo SVGA
    classici; 43 righe stanno comodamente in una finestra 16:9. Chrome
    ancorato in fondo: status 41, help 42, menu 43; area di lavoro 40 righe.
  - **Font TrueType incorporato**: DejaVu Sans Mono regular e bold
    (licenza Bitstream Vera); fallback al monospace di sistema. Nessun font
    di sistema obbligatorio.
  - **Cella = metriche del font** (avanzamento × ascent+descent), mai glifi
    stirati, come nella console XP. Il corpo è scelto automaticamente fra 7 e
    72 px di dispositivo: è il più grande che fa entrare la griglia nella
    finestra; ridimensionando la finestra l'interfaccia si riscala, `F11`
    porta in full screen. I margini residui sono pochi e usano il colore di
    fondo dell'interfaccia, non il nero.
  - **Caratteri grafici disegnati geometricamente** (`render/glyphs.py`):
    cornici singole e doppie, blocchi e retinature non vengono dal font, così
    le linee sono continue a ogni corpo (DejaVu lascia un pixel di vuoto ai
    bordi della cella).
  - **Atlante per colore e grassetto**, costruito in pixel di dispositivo:
    testo nitido anche su HiDPI, nessuna conversione per frame.
  - Rimossi il font bitmap CP437 8×16, `cell/font.py`, `tools/build_font.py`
    e `tests/test_font.py`: non sono più la verità estetica.
- Test: `68 passed` (aggiornati dump golden, dimensioni, fit, continuità
  delle linee, smoke 132×43); lint pulito.
- Screenshot: `docs/render/01-main-menu.png` e `02-popup.png` (1452×903,
  corpo 18 px, cella 11×21). `font-cp437.png` rimosso.
- Problemi aperti:
  - Su finestre molto larghe (16:9) restano margini orizzontali, perché la
    griglia 132×43 ha un rapporto d'aspetto diverso: si potrebbe riempire
    allargando le celle, ma i glifi verrebbero stirati. Decisione rimandata.
  - La mappatura colori 0–255 → 16 resta provvisoria (palette `A4.PAL`).
- Prossimo passo: O1 — shell.

### 2026-11-23 — O0 — Materiale originale Alpha Four v3
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: verificare l'archivio fornito dall'utente (`DRIVEC TERZA
  VERSIONE.zip`, 112 MB) e censire i riferimenti originali.
- Contenuto trovato: `drivec/ALPHA4V3/` con `A4.EXE` (12/11/1993), `A4.PAL`,
  `A4.DFL`, `A4HELP.HLP`, `A4DOC.EXE`, `README.DOC`, `PRINTER.DTA`; le cartelle
  `TUTOR/`, `SAMPLE/`, `INVOICE/`. L'archivio è integro (`unzip -t`).
- Dati del Tutorial disponibili: `AVMOVIES.DBF` (50 record, 11 campi),
  `AVPATRON.DBF` (28, 17), `AVSALES.DBF` (109, 24), `AVSALES2.DBF` (16, 9),
  più indici `.NDX`, script `.SCP`, set `ALPHAVID.SET`.
- `A4.PAL`: 9.077 byte, intestazione `A4 10 0C`, palette con nome
  (`ARIZONA`, `BERMUDA`, `CAPE COD`, …): sostituirà la mappatura provvisoria
  `indice % 16` in O12.
- `A4HELP.HLP`: intestazione `A4H 1A` seguita da una tabella di offset:
  estraibile, servirà per i nomi esatti di aiuti e trigger.
- Scelte: i file originali **non** entrano nel repository (licenza
  proprietaria, repo MIT). Sono estratti in `/tmp/opencode/alpha4v3/` come
  riferimento di lettura; nel repo finiranno solo specifiche e valori
  derivati. `.gitignore` esclude gli archivi `/DRIVEC*.zip`.
- Test: nessuno (solo ricognizione).
- Problemi aperti: i dati reali hanno conteggi diversi da quelli inventati
  nella schermata demo (`AVMOVIES` 50 record, non 44); si allineeranno quando
  ci sarà il motore dati (O4).
- Prossimo passo: O1 — shell.

---

### 2026-11-23 — Ondata O1 — Shell
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: l'ambiente che si vede all'avvio, con accettazione sulle lezioni
  1 e 3 del Tutorial.
- File toccati: nuovo pacchetto `src/adbx/shell/` (`controller.py`,
  `screens.py`, `widgets.py`, `theme.py`, `help.py`, `files.py`, `state.py`),
  `src/adbx/data/{__init__,dbf}.py`, `src/adbx/app.py`,
  `src/adbx/__main__.py`, `src/adbx/cell/buffer.py` (attributo `underline`),
  `src/adbx/render/qt_renderer.py` (sottolineatura), `src/adbx/screen/keys.py`
  (`character`), rimossi `screen/demo.py` e `tests/test_shell.py`, nuovi test
  (`test_dbf`, `test_directory`, `test_help`, `test_shell_menu`,
  `test_shell_directory`, `test_lesson`, `test_golden`, `support.py`),
  `tools/capture_ui.py`, `docs/spec/02-shell.md`, `README.md`, `PLAN.md`.
- Scelte:
  - **Controller senza Qt**: `ShellController.handle(Key)` e
    `click(row, col)` producono un `View` (buffer + zone cliccabili). È la
    stessa porta d'ingresso che userà il motore di script in O10.
  - **Database Directory fedele**: path/filtro, `<Parent>`,
    sottodirectory, `.SET`/`.DBF`, colonne Name/Type/Date, F3 Import (in O9),
    F4 History, F6 Refresh, F8 Detail (Records/Fields dal DBF), F9 DOS
    dichiarato non disponibile. Il campo nome si modifica carattere per
    carattere, con cursore lampeggiante sottolineato.
  - **Main menu** con i 12 comandi, hot key = lettera maiuscola
    (`V P S I G C D L A U O Q`), status box a due righe, help line e menu
    line. Finestra chiara con barra del titolo scura, come il riferimento.
    Corretto l'elenco degli hot key nel PLAN: non sono W/L/R/V/… ma le
    iniziali; `W` resta la scorciatoia per sWitch databases.
  - **Aiuto contestuale** con topic nostri (non copiati dal manuale), rimandi
    in blu, barra di selezione, ENTER per seguire, BACKSPACE per tornare,
    ESC per chiudere, PgUp/PgDn per scorrere. Un test verifica che ogni
    rimando punti a un topic esistente.
  - **F2/F3** (struttura e stato) implementati perché la lezione 3 li usa:
    15 campi per pagina, stato con file/record/campi/indice.
  - **Database Directory legge il filesystem**: data dall'mtime (come il DIR
    di DOS), record e campi dall'intestazione DBF. Il reader DBF è minimo e
    tollerante: in O2 diventa la base dello strato dati.
  - **Comandi non ancora pronti**: un avviso dice l'ondata (View/Print/
    Search/ecc.); non si finge che funzionino. Niente banner iniziale.
  - **Mouse**: clic seleziona, doppio clic esegue, tasto destro = ESC, clic
    sulle voci della menu line esegue il tasto.
  - Aggiunto `underline` alle celle, usato per i campi di immissione; il dump
    golden ha ora un quinto attributo.
- Test: `124 passed`; lint pulito. Accettazione lezioni 1 e 3 in
  `tests/test_lesson.py`; help su ogni comando; directory da tastiera e mouse.
  Verificata anche sui file reali del Tutorial in
  `/tmp/opencode/alpha4v3/drivec/ALPHA4V3/TUTOR` (AVSALES: 109 record,
  24 campi, struttura su due pagine).
- Screenshot: `docs/render/01-main-menu.png`, `02-directory.png`,
  `03-help.png`, `04-structure.png`, `05-status.png`.
- Problemi aperti:
  - Set, desktop, import, creazione database: avvisi con l'ondata prevista.
  - Il main menu occupa 72 colonne su 132: il software originale era 80×25,
    la proporzione non è replicabile senza deformare il carattere.
  - Palette colori ancora provvisoria (O12); tema unico `newport`.
- Prossimo passo: O2 — Dati e immissione.

---

### 2026-11-23 — Riferimenti — Manuali originali e ambiente DOSBox-X
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: avere i manuali originali nel repository per la consultazione e
  poter eseguire Alpha Four v3 vero per confrontare schermate e tasti.
- File toccati: `docs/reference/manuals/` (tre PDF e `README.md`),
  `docs/spec/03-ambiente-dos-riferimento.md`,
  `docs/render/06-alpha-four-dosbox.png`, `tools/run_alpha4_dosbox.sh`,
  `README.md`, `DIARIO.md`.
- Scelte:
  - I PDF sono copiati dall'archivio di famiglia con nomi parlanti e hash
    SHA-256; restano documentazione proprietaria, non MIT, e il repository
    contiene un avviso esplicito. I file del programma (`A4.EXE`, dati) non
    entrano in git.
  - DOSBox-X installato da Ubuntu (`2026.01.02+dfsg-2`). Lo script cerca
    l'archivio `DRIVEC TERZA VERSIONE.zip`, estrae `drivec/` nella cache
    utente (`$XDG_CACHE_HOME/adbx/alpha4-dos`), genera la configurazione e
    monta la cartella come `C:`.
  - Configurazione verificata: `svga_s3`, 16 MB, EMS/XMS attivi, cicli
    automatici. `A4.EXE` parte e arriva al main menu con `AVMOVIES`
    (50 record, 12 nella lista); nessun errore di memoria.
- Test: avvio sotto Xvfb con cattura `scrot`; screenshot nel repository.
- Problemi aperti: il DOSBox mostra il main menu 80×25, mentre adbx usa
  132×43; il confronto è funzionale, non pixel a pixel.
- Prossimo passo: completare O2 (dati e immissione) e usare DOSBox-X per
  verificare le lezioni 2, 4, 5 e 6.

---

### 2026-11-23 — Ondata O2 — Dati e immissione
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: database veri, record veri, table designer e modalità
  View/Browse/Enter/Change, con memo, clipboard, cancellazione logica,
  PACK e password.
- File toccati: nuovi `src/adbx/data/{fields,workspace}.py`,
  `src/adbx/shell/{records,record_screens,designer}.py`, `src/adbx/data/dbf.py`
  (lettura record, memo, scrittura DBF/DBT), `src/adbx/shell/controller.py`,
  `screens.py`, `help.py`, `state.py`, `README.md`, `PLAN` implicito,
  `docs/spec/04-dati-immissione.md`, `tools/capture_ui.py`,
  `docs/render/07-view-records.png`, `08-browse-records.png`,
  `09-designer.png`, test nuovi (`test_fields`, `test_workspace`,
  `test_records`) e aggiornati (`test_shell_directory`, `support`).
- Scelte:
  - **SQLite di workspace** (`.adbx.sqlite`) con `t_<db>` e `m_<db>`, come
    da PLAN §3.3. Il `.DBF` viene importato al primo accesso e riscritto a
    ogni salvataggio: il file resta il formato di scambio e i dati non
    restano prigionieri del motore.
  - **Valori canonici** in testo: numerici `Decimal` half-up con decimali
    fissi, date `YYYYMMDD`, logici `1/0/vuoto`. La tabella di conversione è
    implementata caso per caso e verificata da `tests/test_fields.py`.
  - **Table designer** a celle con F5/F6/F10: creazione da F5 del Directory,
    modifica da `Database/set design`. I campi hanno un'identità stabile
    (`original`) così rinomina/conversione conservano i dati; l'eliminazione
    li perde, l'aggiunta li lascia vuoti.
  - **Form di default** etichetta/valore, una o più colonne, in attesa del
    form designer (O6); Browse di default a colonne larghe quanto i campi.
    Deviazione dichiarata: l'originale usa layout progettati.
  - **Tasti fedeli**: TAB ±10 record, CTRL-HOME/END, ALT-D/U, ALT-M,
    ALT-F5/F6, INSERT, CTRL-BACKSPACE. `RecordSession` è indipendente da Qt,
    quindi il playback di O10 userà gli stessi tasti.
  - **Password** PBKDF2-SHA256, richiesta all'apertura; protegge l'accesso,
    non cifra i file.
  - `Erase database` elimina i file solo per i database creati da adbx; per
    gli importati il `.DBF` resta (scelta prudente, documentata).
- Test: `154 passed`; lint non disponibile nell'ambiente (`ruff` assente),
  import e compilazione verificati. Accettazione lezioni 2, 4, 5 e 6 in
  `tests/test_records.py`; conversione caso per caso in `test_fields.py`;
  import/export DBF e memo in `test_workspace.py`. Verificato anche sui file
  reali del Tutorial: `AVMOVIES.DBF` importa 50 record e i memo `.DBT`.
- Screenshot: `docs/render/07-view-records.png`,
  `08-browse-records.png`, `09-designer.png`.
- Problemi aperti:
  - La form generata non è un layout Alpha Four: arriverà con O6.
  - La browse non ha ancora larghezze/ordine definiti dall'utente (O6).
  - Il DBF viene riscritto integralmente: su database molto grandi servirà
    una strategia incrementale (O3/O13).
  - Il nome database è limitato a 8 caratteri DOS; il percorso può essere
    lungo.
- Prossimo passo: O3 — ricerca, indici, range, search/sort list.

---

### 2026-11-23 — Ondata O3 — Ricerca: indici, range, search/sort list
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: trovare e ordinare i record come Alpha Four, con indici
  dinamici, range, liste di ricerca, Find/Locate, sostituzione e
  cancellazione dei duplicati.
- File toccati: nuovi `src/adbx/data/{expressions,indexing}.py`,
  `src/adbx/shell/{indexes,searching,dialogs}.py`,
  `docs/spec/05-ricerca-indici.md`, screenshot
  `docs/render/10-index-table.png`, `11-range-settings.png`,
  `12-search-table.png`, `13-search-history.png`; aggiornati
  `src/adbx/data/workspace.py`, `src/adbx/shell/{controller,records,
  record_screens,screens,state,help}.py`, `src/adbx/screen/keys.py`,
  `tools/capture_ui.py`, test nuovi (`test_expressions`, `test_indexing`,
  `test_index_ui`, `test_find_locate_ui`, `test_range_ui`,
  `test_search_ui`) e aggiornati (golden, shell menu, directory, support).
- Scelte:
  - **Linguaggio di espressioni proprietario** (`data/expressions.py`) con
    tipi Python (`Decimal`, `date`, `bool`) e Pattern matching nei tre modi
    del manuale; Table mode sempre case-insensitive ed esatta.
  - **Indici in SQLite**, non file `.NDX`/`.IDN`: definizione con
    espressione/livelli, filtro sempre attivo, Allow All/Unique/Unique with
    exceptions, case sensitive, attached (max 15). La chiave conserva gli
    spazi dei campi, quindi Find si comporta come l'originale.
  - **Range persistito** (`range_json`): primary index, order, show,
    first/last key, unique keys, filtro attivo/inattivo, 26 range salvati.
    Cambiare primary index resetta First/Last/Unique, come da manuale.
    Show predefinito = Not deleted (deviazione da All, per conservare O2).
  - **Search/sort list**: Table/Expression mode, sort table/espressione,
    una-time o salvata A–Z, storia di 10, combinazione con la lista attiva.
    Out-of-date confrontando la revisione del database e la versione dei
    criteri; `Refresh` li ricostruisce. Non esistono file `.SLx`.
  - **Find** con chiave uguale o successiva (closest match), **Locate** con
    Field Selection (memo inclusi), **Search and replace** tutto-o-niente,
    **Delete duplicate** sull'indice primario con cancellazione logica.
  - Tasti: `F` Find, `L` Locate, `I` Index, `R` Range, `S` Replace in View;
    Range `F2/F3/F7/F10/ALT-E`; Search `F2/F3/F4/F7/F8/F9/F10`.
- Test: **197 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi. Accettazione lezioni 7, 8, 9 e
  15 in quattro file UI; pattern matching nei tre modi, AND/OR e tabella in
  `test_expressions`; indici/range/liste in `test_indexing`. Verificato sui
  file reali del Tutorial: `AVMOVIES.DBF` (50 record), indice su titolo,
  indice a due livelli e ricerca per rating.
- Problemi aperti / deviazioni dichiarate:
  - Non ci sono file `.NDX`/`.IDN`/`.SLx`: indici e liste restano nel
    workspace SQLite. Il `.DBF` è interoperabile, gli indici no.
  - Find non ha `F2 (use alternate index)` né la storia delle stringhe con
    `UP`; Locate non offre `Change`/`Options` durante la ricerca.
  - Search and replace non verifica ogni singola sostituzione.
  - La storia delle liste non permette di modificare i criteri (solo
    selezionare, aggiornare, cancellare).
  - Il range predefinito mostra i non cancellati invece di All.
- Prossimo passo: O4 — Field rules (lookup, cascading, conditional, post).

---

### 2026-11-23 — Ondata O4 — Regole di campo
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: rendere il database dichiarativo con le regole del capitolo 10:
  valori calcolati, default, incrementi, maschere, validazioni, doppia
  immissione, skip, post data e lookup (tabella, database, cascata,
  condizioni).
- File toccati: nuovo `src/adbx/data/rules.py` (motore puro),
  `src/adbx/shell/rules.py` (editor a due finestre e grid editor), specifica
  `docs/spec/06-regole-campo.md`, screenshot `14-field-rules.png`,
  `15-lookup-table.png`, `16-lookup-choices.png`, `17-posting-rules.png`;
  aggiornati `src/adbx/data/workspace.py` (tabella `adbx_field_rules`,
  migrazione alla rinomina dei campi), `src/adbx/shell/records.py`
  (default, calcolati, maschere, template, required, validation, double
  entry, skip, auto-advance, lookup F3, post al salvataggio),
  `record_screens.py` (popup lookup e prompt), `controller.py`
  (sottomenu Field rules, re-evaluate, erase), `help.py`, `README.md`,
  `tools/capture_ui.py`; test nuovi `test_rules`, `test_field_rules_ui`,
  `test_field_rules_entry` e aggiornato `test_records` per il nuovo indice
  del menu Password.
- Scelte:
  - **Regole in SQLite** (`adbx_field_rules`), non in `database.RLN`: il
    `.DBF` resta interoperabile, le regole no. La tabella usa `owner` per
    essere pronta al livello set di O5.
  - **Risoluzione set/database** del manuale: se il set definisce una regola
    per un campo, quella di database viene ignorata per intero, non fusa.
  - **Motore puro** in `data/rules.py`: default, incrementi base 36,
    template/maschere, required, validation, double entry, skip, calcolati
    con passaggi multipli, lookup table/database/cascata/condizionali, post
    data con differenza su modifica, re-evaluate.
  - **Editor** a due finestre con tre pagine; F7 apre l'editor giusto per
    tabella, mapping, cascata o condizioni; F8 le regole di post; F5 cancella
    le regole del campo; F10 salva.
  - **Data entry**: il cursore salta calcolati e campi con skip; i default e
    gli incrementi `Records` sono applicati alla nascita del record; F3 apre
    la lookup e riempie i campi collegati; il salvataggio esegue required,
    validation, maschere, lookup validation, incrementi `Updates` e post.
  - **Popup lookup** rispetta `Location`, `Rows in Window` e `Auto Pop-up`;
    le cascate mostrano un livello alla volta con `LEFT` per risalire.
- Test: **234 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi. Accettazione lezioni 11–13 in
  `test_field_rules_ui`; motore in `test_rules`; integrazione in
  `test_field_rules_entry`.
- Problemi aperti / deviazioni dichiarate:
  - `Summary` è solo per i set e non è calcolato (O5).
  - L'`Exit expression` dell'auto popup non è ancora usata; `Entry` sì.
  - Il post data esterno aggiorna il primo record; il post verso un figlio
    1:N arriverà con i set (O5).
  - Le regole non sono scritte in `.RLN`; vivono nel workspace SQLite.
  - Un campo calcolato mostra nell'editor anche regole che il motore non usa.
- Prossimo passo: O5 — Set e regioni.

---

### 2026-11-23 — Ondata O5 — Set e regioni
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: collegare più database in un set, definire link e integrità,
  consultare i dati combinati con una regione uno-a-molti e lo zoom.
- File toccati: nuovi `src/adbx/data/sets.py` (definizione, persistenza,
  risoluzione link, closest, integrità, cascading),
  `src/adbx/shell/sets.py` (Set Editor, integrity mapping, SetSession),
  specifica `docs/spec/07-set.md`, screenshot `18-set-editor.png`,
  `19-set-view.png`, `20-set-browse.png`; aggiornati
  `src/adbx/data/workspace.py` (tabelle `adbx_sets`/`adbx_set_links`,
  pulizia dei set alla cancellazione di un database), `controller.py`
  (Set commands, Open a set, switch/close, sessioni set), `state.py`,
  `screens.py`, `help.py`, `README.md`, `tools/capture_ui.py`; test nuovi
  `test_sets`, `test_sets_ui`.
- Scelte:
  - **Definizione in SQLite**, non file `.SET`: primario, descrizione,
    show/filter e link con indice, campo comune, modalità, integrità,
    include parent e opzioni di editing.
  - **Motore in memoria**: i link risolvono i record del figlio nell'ordine
    dell'indice; `First/Last/All` e `Closest` (prima chiave successiva).
    Nessuna copia dei dati.
  - **Referential integrity**: mappa di integrità di default sui campi
    omonimi (più il campo comune), personalizzabile con F7; cascading update
    e delete/undelete riscrivono i `.DBF` coinvolti.
  - **Set Editor** a due finestre, con F6 add link, F5 detach, F7 integrity,
    F9 switch e F10 save. Limiti verificati: 10 database, un solo `All` per
    genitore, endpoint raggiungibili, indici esistenti.
  - **SetSession** per View/Browse/Enter/Change: campi combinati primario +
    figli 1:1, regione 1:N con F6 e zoom Alt-Z, cascata su delete, salvataggio
    del genitore e dei figli modificabili, regole del primario.
- Test: **252 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi. Accettazione set in
  `test_sets_ui`; motore in `test_sets` (closest, cascading, filtri,
  include parent, limiti).
- Problemi aperti / deviazioni dichiarate:
  - I set non sono file `.SET` reali; vivono nel workspace SQLite.
  - Il form designer e le regioni personalizzate arrivano con O6; la regione
    figli usa un layout predefinito.
  - I figli 1:1 annidati non compaiono nel form combinato (solo zoom/O6).
  - `Prompt` sull'aggiunta di figli è trattato come `Yes`.
  - Enter/Change applica le regole del primario, non quelle dei figli.
- Prossimo passo: O6 — Form designer.

---

### 2026-11-23 — Ondata O6 — Form designer
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: disegnare form a celle per database e set, con campi, testi,
  riquadri, regioni 1:N, calcolati, summary, parametri e stampa.
- File toccati: nuovi `src/adbx/data/forms.py` (modello, pagine, validazione,
  calcolati/summary, persistenza), `src/adbx/shell/forms.py` (Form Designer,
  parametri, formatting, campi sintetici), specifica
  `docs/spec/08-form.md`, screenshot `21-form-designer.png`,
  `22-custom-form.png`, `23-set-form.png`, `24-formatting.png`; aggiornati
  `workspace.py` (tabella `adbx_forms`, active form, delete), `controller.py`
  (Layouts → Forms, select/erase, form attivo in View/Enter/Change),
  `records.py`/`record_screens.py` (navigazione e rendering custom form),
  `sets.py` (form dei set con regioni e summary), `help.py`, `README.md`,
  `tools/capture_ui.py`; test nuovi `test_forms`, `test_forms_ui`.
- Scelte:
  - **Form in SQLite**, non file `.INx`: proprietario, lettera, descrizione,
    pagine, campi, etichette, riquadri, regioni e parametri.
  - **Fino a 26 form e 10 pagine**; il form salvato diventa attivo
    automaticamente.
  - **Layout a celle**: F2 campo, F4 calcolato/summary, F5 delete, F6 regione
    1:N, F7 parametri, F8 riquadro, F9 formatting (Len/Window/Just/Fmt/Title),
    F10 save.
  - **RecordSession** usa il form attivo: ordine dei campi, memo multilinea
    `!X`, campi esclusi non visitati, calcolati in sola lettura.
  - **SetSession** usa il form del set: campi da più database, regioni con
    F6/zoom, summary su Count/Total/Average/Biggest/Smallest/First/Last.
- Test: **262 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi. Accettazione form in
  `test_forms_ui`; modello in `test_forms`.
- Problemi aperti / deviazioni dichiarate:
  - Colori, restrict access e custom menu bar sono memorizzati ma non
    applicati; la stampa arriva con O7.
  - Niente Borrow form, Block/Move/Copy, editor di regione completo,
    auto-expand `@`.
  - Il titolo del campo è sopra il campo, non posizionabile separatamente.
  - I form dei database non hanno regioni; i summary usano i link 1:N dei set.
- Prossimo passo: O7 — Report engine.

---

### 2026-11-23 — Ondata O7 — Report engine
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: stampare report a sezioni con gruppi, summary, formattazioni,
  multipass, impaginazione, anteprima, PDF e check writing.
- File toccati: nuovi `src/adbx/data/reports.py` (modello, sezioni, gruppi,
  calcoli, summary, validazione, persistenza), `src/adbx/data/report_engine.py`
  (raccolta record, multipass, formati, paginazione), `src/adbx/shell/reports.py`
  (designer, parametri, gruppi, layout, calcolati, summary, formatting,
  anteprima), `src/adbx/render/report_pdf.py` (PDF senza dipendenze),
  specifica `docs/spec/09-report.md`, screenshot `25-report-designer.png`,
  `26-report-preview.png`, `27-report-grouping.png`; aggiornati
  `workspace.py` (tabella `adbx_reports` e metodi), `controller.py`
  (Layouts → Reports, Print → Report, borrow/erase, sessioni), `help.py`,
  `README.md`, `tools/capture_ui.py`; test nuovi `test_reports`,
  `test_reports_ui`; aggiornato `test_shell_directory` per il menu Print.
- Scelte:
  - **Report in SQLite**, non file `.RPx`: proprietario, lettera, parametri,
    sezioni, testi, campi, calcolati, summary e gruppi.
  - **Sezioni del manuale**: report header sostituisce page header a pagina 1;
    titles ripetibili; group header/footer annidati; summary finale.
  - **Summary 7×3×4×2**: sette tipi, livelli Grand/Page/Group n, ignore
    None/Empty/Zero/Both, modi Running/Pre-processed.
  - **Multipass a punto fisso** (max quattro passate) per calcoli che usano
    summary e summary che aggregano calcoli; paginazione ricalcolata finché
    le pagine assegnate ai record non si stabilizzano.
  - **Formati**: caratteri N/C/L/F/W/X/Y/Z/-; memo X/@; numerici $, virgola,
    X, X$, con `*`, `B`, `-` e capitalizzazione; date 1–10.
  - **Impaginazione**: page length, margini, page breaks, max records, blank
    line dopo N record, split lines, widow/orphan, re-print group header,
    substitute header/footer, reset pagina dopo gruppo.
  - **Output**: anteprima a schermo e PDF Courier letter/landscape; Print →
    Report per i report salvati.
- Test: **283 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi. Accettazione report 1 e 2 del
  Tutorial in `test_reports`; designer e anteprima in `test_reports_ui`.
- Problemi aperti / deviazioni dichiarate:
  - Niente file `.RPx`/`.SET`; range e stampa non sono memorizzati nel report.
  - Separatore date `/` e valuta `Dollars` non configurabili fino a O12.
  - `Borrow` resta nello stesso proprietario; l'orphan control non ridisegna
    i record già stampati; substitute footer non emette form feed.
  - Niente stampante diretta, driver o caratteri compressi: solo anteprima e
    PDF.
- Prossimo passo: O8 — etichette e lettere.

---

### 2026-11-23 — Ondata O8 — Etichette e lettere
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: stampare etichette con griglia e giustificazioni avanzate, e
  lettere con campi, comandi, condizionali, include e prompt.
- File toccati: nuovi `src/adbx/data/labels.py` (modello, parametri, campi,
  calcolati, validazione), `src/adbx/data/labels_engine.py` (griglia, copie,
  soppressione righe, Suppress/Float/Trim/Join/Before/After),
  `src/adbx/data/letters.py` (modello, parser comandi e marker, condizionali,
  include, paginazione), `src/adbx/shell/labels.py` (Label Designer),
  `src/adbx/shell/letters.py` (editor), specifica
  `docs/spec/10-etichette-lettere.md`, screenshot `28-label-designer.png`,
  `29-label-preview.png`, `30-letter-editor.png`, `31-letter-preview.png`;
  aggiornati `workspace.py` (`adbx_labels`, `adbx_letters`), `controller.py`
  (Layouts → Mail labels/Letters, Print → Mail labels/Letters, preview),
  `help.py`, `README.md`, `tools/capture_ui.py`; test nuovi `test_labels`,
  `test_letters`, `test_output_ui`.
- Scelte:
  - **Etichette e lettere in SQLite**, non file `.LNx`/`.LTR`.
  - **Griglia etichette**: width 10–78, height 1–20, across 1–6, gap
    orizzontale/verticale, copie da numero/campo/espressione, margini,
    continuous feed o righe per pagina.
  - **Giustificazioni avanzate** implementate con un cursore di shift per
    riga: `Suppress`/`Before`/`After` sopprimono gli spazi finali e spostano
    il seguito, `Float` sposta il campo senza spostare il testo seguente,
    `Trim` ignora lo shift precedente, `Join` porta con sé il testo.
  - **Lettere**: marker `[FIELD]`, `[DB->FIELD]`, `[SYSTEM->DATE]`,
    `[{expr}]`, `[?prompt]`; opzioni S/L/R/C/N/D/X/$/`,` e
    `:lunghezza.decimali`; comandi WIDTH/LEFT/TOP/BOTTOM/FILL/EJECT/INCLUDE/
    `[@codici]`; condizionali IF/ELSEIF/ELSE/ENDIF annidati.
  - **Fill mode**: paragrafi di solo testo riscritti alla larghezza, righe con
    campi mantenute separate per indirizzi e righe strutturate.
  - **Anteprima e PDF** con lo stesso visualizzatore dei report; Print →
    Mail labels/Letters.
- Test: **301 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi. Accettazione lezione 17 in
  `test_labels` e lezione 18 in `test_letters`.
- Problemi aperti / deviazioni dichiarate:
  - Niente `.LNx`/`.LTR`, test pattern di allineamento o pausa fogli singoli.
  - Continuous feed produce una pagina continua; la stampante reale è O12.
  - I codici `[@...]` sono rimossi, non inviati alla stampante.
  - I prompt usano una mappa fornita dal chiamante; manca il dialogo
    interattivo per lettera.
  - L'editor non ha block copy/move né clipboard delle lettere.
- Prossimo passo: O9 — Utility e I/O.

---

### 2026-11-23 — Ondata O9 — Utility e I/O
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: copy, append nelle quattro modalità, summarize, cross
  tabulation, post, join/intersect/subtract, global update/delete e
  import/export nei formati del manuale.
- File toccati: nuovi `src/adbx/data/utilities.py` (operazioni sui record e
  relazionali), `src/adbx/io/` (common, delimited, fixed, dif, sylk, lotus,
  dbf2, wordperfect, formats), `src/adbx/shell/utilities.py` (copy, append,
  summarize, crosstab), `src/adbx/shell/relational.py` (post e comandi
  relazionali), `src/adbx/shell/transfer.py` (import/export con Field
  Adjust), `src/adbx/shell/global_update.py`, specifica
  `docs/spec/11-utility-io.md`, screenshot `32-copy-database.png` …
  `38-delete-range.png`; aggiornati `workspace.py` (descrizione database,
  copia support files, migrazione), `controller.py` (menu Utilities e
  Relational, sessioni, range temporaneo, Zap), `help.py`, `README.md`,
  `tools/capture_ui.py`; test nuovi `test_utilities`, `test_io`,
  `test_utilities_ui`; aggiornato `test_records` per il nuovo ordine del
  menu Utilities.
- Scelte:
  - **Nessun formato proprietario**: le utility lavorano sul workspace
    SQLite e creano database normali; il `.DBF` resta il formato di scambio.
  - **Copy** copia tutti o alcuni campi, anche da un set (primario e link
    uno-a-uno), in ordine di primary index; `Inherit support files` copia
    regole, form, report, etichette, lettere, range e search/sort, non gli
    indici.
  - **Append**: `All`, `Unique`, `Replace existing, add unique`, `Replace
    existing, mark unique`; filtro sul database esterno, mappatura campo per
    campo, chiave calcolata sui valori che il record avrà nel master.
  - **Summarize**: sette tipi del manuale più `Group` e `Null`; `Total` e
    `Average` allargano il campo di due caratteri; totale troppo grande
    diventa zero; Record Number e Search/Sort list non raggruppano.
  - **Crosstab**: colonne automatiche dai valori distinti o esplicite con
    espressioni; nomi normalizzati a 10 caratteri; names database
    `SHORT C10`/`FULL C60`.
  - **Post**: espressione comune, filtro, `Add`/`Subtract`/`Replace`,
    condizione per campo, status logico e marcatura degli unmatched; più
    record master con la stessa chiave vengono aggiornati tutti.
  - **Join/Intersect/Subtract**: left outer join, inner join, anti-join;
    indice secondario e normalizzazione della chiave; collisioni di nome
    risolte con suffisso.
  - **Global update/delete**: update one-time di massimo 20 campi, sei
    conversioni di maiuscole, delete/undelete del range.
  - **Import/export**: dieci formati con fixture di andata e ritorno;
    dBASE II con intestazione di 10 byte e 32 campi; Lotus WK1 in scrittura
    e WKS/WK1 in lettura, date seriali; WordPerfect con `{END FIELD}` e
    `{END RECORD}`; MultiMate come documento secondario testuale.
  - **Field Adjust** nell'import: nome, tipo, lunghezza e decimali
    modificabili prima della creazione; le impostazioni non si salvano in
    file `A4.I?x`.
- Test: **338 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi.
- Screenshot: `32-copy-database`, `33-crosstab`, `34-relational-join`,
  `35-import-options`, `36-export-fields`, `37-global-update`,
  `38-delete-range`.
- Problemi aperti / deviazioni dichiarate:
  - Copy/summarize da set usano primario e link uno-a-uno; i campi
    uno-a-molti non hanno un valore unico.
  - `Inherit support files` non copia indici; le definizioni update salvate
    e le import settings `A4.I?x` non sono implementate.
  - MultiMate non replica la codifica binaria originale; PFS:File e DBMII
    restano esclusi come da non-obiettivi.
  - Non c'è stampa diretta: export e PDF sono i canali di uscita.
- Prossimo passo: O10 — Script.

---

### 2026-11-23 — Ondata O10 — Script
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: motore keystroke, registrazione e `Screen Test`, dialog box,
  menu bar script, comandi del capitolo 18, variabili, `%SYS_*`, trigger,
  debugger, `AUTOEXEC`, script `nomeDB!`, `CTRL-F1..F10` e `Tools`.
- File toccati: nuovi `src/adbx/script/` (model, parser, variables, engine,
  triggers, store), `src/adbx/shell/scripts.py` (editor, dialog designer,
  menu bar designer, debugger, dialog runtime), `src/adbx/shell/script_host.py`,
  specifica `docs/spec/12-script.md`, screenshot `39`–`44`; aggiornati
  `controller.py` (menu ALT-F3, playback, registrazione, variabili, trigger,
  AUTOEXEC, script di apertura, hot key, Tools, menu bar personalizzato),
  `records.py` (hook trigger e menu personalizzato), `screens.py` (overlay
  variabili), `help.py`, `README.md`, `tools/capture_ui.py`; test nuovi
  `test_script_engine`, `test_scripts_ui`.
- Scelte:
  - **Un solo percorso di input**: il playback chiama
    `ShellController.handle`, come la tastiera reale.
  - **JSON leggibile** per gli script; `.SCP` è un export/import testuale.
  - **Tutti i comandi** del cap. 18 sono riconosciuti; `EXEC`, `EXECCLR` e
    `RPL` falliscono in modo gestibile da `ONERROR` perché adbx non esegue
    programmi DOS.
  - **22 trigger** del manuale, con alias per i nomi ambigui dell'OCR;
    agganci reali su record, field rules, lettere, search/sort e update.
  - **Dialog runtime** con Prompt/Button/Display; il Button chiude la finestra
    prima di eseguire l'azione, per evitare rientri nel key handler.
  - **Screen test** sulle righe visibili; F6 marca l'area corrente.
- Test: **394 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi.
- Screenshot: `39-scripts-menu`, `40-script-editor`, `41-dialog-designer`,
  `42-script-variables`, `43-script-debugger`, `44-menu-bar`.
- Problemi aperti / deviazioni dichiarate:
  - `EXEC`/`EXECCLR`, `RPL` e i programmi DOS esterni non sono eseguiti.
  - Le attese sono cooperative e non sospendono l'event loop Qt.
  - Lo screen test memorizza il rettangolo ma confronta il testo.
  - I file di script non sono il formato binario `.SCP` originale.
- Prossimo passo: O11 — Applicazioni.

---

### 2026-11-23 — Ondata O11 — Applicazioni
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: application editor, parametri, banner, macro, simulate,
  Call-App/GotO-App, password e prevent/allow file alterations.
- File toccati: nuovi `src/adbx/app/` (model, store, runtime, protection),
  `src/adbx/shell/applications.py` (editor, runtime, banner painter,
  macro editor, protezioni), specifica `docs/spec/13-applications.md`,
  screenshot `45`–`50`; aggiornati `controller.py` (menu Applications,
  sessione, startup, banner, password, protezioni), `app.py`/`__main__.py`
  (`--app`), `README.md`, `tools/capture_ui.py`; test nuovi
  `test_applications`, `test_applications_ui`.
- Scelte:
  - **Albero di menu** con titolo, flusso Return/Stay/Advance, colonne e
    spaziatura; outline piatto per l'editor e JSON annidato per il disco.
  - **Stesso runtime** per esecuzione e simulazione; la simulazione non
    esegue macro, Call-App o GotO-App.
  - **Call-App** fino a 10 livelli con stack e ritorno; **GotO-App** sostituisce
    l'applicazione e azzera lo stack.
  - **Password** hash SHA-256 case-insensitive per voci e per ESC.
  - **Banner** a celle con colori per cella solo dove differiscono dai
    default; avvio con attesa di un tasto.
  - **Protezioni** come impostazioni del workspace: bloccano l'apertura dei
    designer, non i file.
- Test: **425 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi.
- Screenshot: `45-applications-menu`, `46-app-parameters`, `47-app-editor`,
  `48-app-runtime`, `49-app-banner`, `50-file-protection`.
- Problemi aperti / deviazioni dichiarate:
  - Banner senza vero screen painter (linee e blocchi).
  - Password hash senza salt e protezioni solo nel guscio.
  - Menu di sfondo non implementati; il banner è l'unico sfondo.
- Prossimo passo: O12 — Configurazione e stampa.

---

### 2026-11-23 — Ondata O12 — Configurazione e stampa
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: `config.json`, default settings, 26 driver di stampa, codici,
  page advance, colori per database, documentazione.
- File toccati: nuovi `src/adbx/config/` (defaults, printers, colors),
  `src/adbx/docs/generator.py`, `src/adbx/shell/settings.py`, specifica
  `docs/spec/14-config-stampa.md`, screenshot `51`–`56`; aggiornati
  `controller.py` (menu Other, sessioni, applicazione config, temi, prevent),
  `fields.py` (date configurabili), `report_pdf.py` (margini driver),
  `README.md`, `tools/capture_ui.py`; test nuovi `test_config`,
  `test_config_ui`.
- Scelte:
  - **`config.json`** unico, atomico, con defaults e driver.
  - **Date** configurabili a runtime (separatore e ordine).
  - **Catalogo di 26 modelli** e 26 lettere; codici decimali e tre modalità
    di avanzamento; margini applicati al PDF.
  - **Colori** per owner con 18 token, ricostruiti all'apertura.
  - **Documentazione** come ReportOutput e PDF, per database, set, regole,
    applicazioni e script.
- Test: **444 passed**; `uvx ruff check src tests tools` pulito;
  `./start.sh --smoke` e `--version` verdi.
- Screenshot: `51-other-menu`, `52-default-settings`, `53-printer-config`,
  `54-printer-driver`, `55-screen-colors`, `56-documentation`.
- Problemi aperti / deviazioni dichiarate:
  - I driver non scrivono su porte DOS; alimentano PDF e stream testuali.
  - Auto flush è già il comportamento; lock/dBASE IV/monocromatico senza
    effetti single-user.
  - Palette a 16 colori, non 64.000.
  - Il documentation program è integrato, non un `A4DOC` separato.
- Prossimo passo: O13 — Conformità 1.0.

---

### 2026-11-23 — Ondata O13 — Conformità 1.0
- Stato: completata — release **1.0.0**
- Branch/commit: `main`.
- Obiettivo: suite delle 25 lezioni, messaggi armonizzati, prestazioni,
  packaging, documentazione utente.
- File toccati: nuovi `tests/test_tutorial_25.py` (25 lezioni),
  `tests/test_performance.py`, `tests/test_packaging.py`,
  `src/adbx/shell/messages.py`, `tools/benchmark.py`,
  `tools/build_release.sh`, `docs/manuale-utente.md`, `docs/CHANGELOG.md`;
  aggiornati `conftest.py` (nessuno skip), `pyproject.toml` e
  `src/adbx/__init__.py` (1.0.0), `.github/workflows/ci.yml`, `README.md`.
- Scelte:
  - **Una prova per lezione** (1–25) e controllo automatico che siano tutte
    presenti.
  - **Nessuno skip ammesso**: `pytest_collection_modifyitems` fallisce se
    compare un test saltato.
  - **Messaggi** normalizzati da `messages.check_style` (spazi e punto
    finale) e testi comuni in `messages.py`.
  - **Prestazioni** con soglie larghe (3.000 record, indice, search, report,
    update) e benchmark riproducibile.
  - **Packaging** 1.0.0, wheel/sdist con `build_release.sh`, CI su 3.11–3.13
    con benchmark.
  - **Manuale utente** completo e changelog.
- Test: **480 passed**, nessuno saltato; `uvx ruff check src tests tools`
  pulito; `./start.sh --smoke` e `--version` verdi; benchmark 200 record
  sotto 0,1 s per operazione.
- Problemi aperti / deviazioni dichiarate: restano quelle delle ondate
  precedenti, raccolte in `docs/manuale-utente.md` §13 e nelle specifiche.
- Prossimo passo: release 1.0 pubblicata e manutenzione.

---

### 2026-11-23 — Automazione DOSBox e conferma visiva end-to-end
- Stato: completata
- Branch/commit: `main`.
- Obiettivo: pilotare l'originale con la REST API di dosbox-automation e
  aggiungere test end-to-end con screenshot versionati.
- File toccati: nuovi `tools/dosbox_automation.py` (avvio headless via Xvfb,
  token, mount policy, testo/frame/tasti, download del binario),
  `tools/e2e_visual.py` (8 scenari adbx + 2 catture DOSBox),
  `tests/test_dosbox_automation.py`, `docs/e2e/` (immagini + manifest);
  aggiornati `README.md` e `.github/workflows/ci.yml` (step E2E visuale).
- Scelte:
  - **dosbox-automation** (GPL-2.0) resta fuori dal repository: lo script lo
    cerca in cache, lo scarica con `--download` e isola config/token.
  - **REST API**: `/video/text` per le attese, `/video/frame` per il PNG,
    `/input/type` e `/input/sequence` per l'interazione.
  - **Xvfb** quando manca `DISPLAY`, così l'automazione gira in CI/headless.
  - **8 scenari adbx** verificano testo atteso, dimensioni, colori campionati
    e hash; `--dosbox` aggiunge menu e View records dell'originale.
- Test: **485 passed**, nessuno saltato; ruff pulito; smoke e version verdi.
- Artefatti: `docs/e2e/README.md`, `docs/e2e/manifest.json`,
  `docs/e2e/adbx/*.png`, `docs/e2e/dosbox/*.png`.
- Nota: il test pytest non richiede il binario DOSBox; la cattura originale
  si esegue con `python tools/e2e_visual.py --dosbox` quando disponibile.

---

## RIPRESA — checkpoint automazione DOSBox

- Ultimo commit: automazione DOSBox ed E2E visivi.
- Test: 485 verdi, nessuno saltato; ruff pulito; smoke e version verdi.
- Specifiche: tutte in `docs/spec/`; manuale `docs/manuale-utente.md`.
- E2E: `docs/e2e/` con 8 schermate adbx e 2 catture dell'originale.
- CI: Python 3.11–3.13, lint, test, smoke, rendering, E2E, benchmark.


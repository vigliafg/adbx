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

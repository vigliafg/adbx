# Diario di implementazione — `adbx-legacy` (80×25)

Variante legacy: griglia logica originale **80×25**, font TrueType scalabile,
parità funzionale completa con `adbx` (132×43).

Regola di lavoro: ogni 3 step ci si ferma in attesa della compattazione del
contesto e del comando "continua". La verifica visiva è obbligatoria in ogni
fase di test.

Piano di riferimento: `PLAN-LEGACY.md`.

---

## Step 1 — 2026-11-24 — Worktree e baseline

- `git worktree add /home/vigliafg/Documenti/GitHub/adbx-legacy -b adbx-legacy HEAD`
  eseguito da `adbx` (HEAD `fa845f2`).
- Patch `git diff --binary` dello stato di lavoro applicata nel worktree.
- Copiati `tests/NEW1.DBF` e `PLAN-LEGACY.md`.
- Commit baseline `98bd13a legacy: baseline dallo stato di lavoro di adbx`.
- `adbx` verificato intatto: HEAD `fa845f2`, status hash
  `8b03e36d00712fab3474799d403a6b50237805cf19c07f8f034ff8461de0e908`.
- Baseline test nel worktree: 451 funzioni, tutte verdi.

## Step 2 — 2026-11-24 — Griglia core e identità

- `src/adbx/cell/buffer.py`: `SCREEN_WIDTH = 80`, `SCREEN_HEIGHT = 25`
  (chrome derivato: status 22, help 23, menu 24, work rows 22) e nuovo
  `CellBuffer.copy()` usato dagli strumenti di cattura.
- `src/adbx/__init__.py`: `VARIANT = "legacy"`, `GRID_WIDTH/GRID_HEIGHT`,
  `WINDOW_TITLE = "adbx — legacy (80×25)"`; `__version__` resta `1.0.0`.
- `src/adbx/app/window.py`: titolo legacy (anche con zoom), dimensione
  iniziale derivata dalla griglia 80×25 e non più 1452×903; minimi ridotti a
  560×360.
- `src/adbx/shell/forms.py`: `MAX_ROW = STATUS_ROW - 2`, `MAX_COL = SCREEN_WIDTH - 2`.
- `src/adbx/data/forms.py`: `MAX_FORM_ROW = 20`, `MAX_FORM_COL = 78`.
- `pyproject.toml`: descrizione aggiornata, nome/versione/entry point invariati.
- Verifica offscreen della finestra: titolo `adbx — legacy (80×25)`,
  dimensione 736×499, griglia 80×25.

## Step 3 — 2026-11-24 — Chrome, directory, overlay, menu line

- `shell/widgets.py`: nuovo `elide_left()` (taglia l'inizio, conserva la coda)
  e `prompt_line` che segue il cursore, così i percorsi lunghi mostrano il
  nome file.
- `shell/screens.py`:
  - status box responsivo: percorso e contatori non si sovrappongono più;
  - banner con percorso eliso a sinistra (`Default database/set`);
  - directory: percorso su una riga intera quando non entra accanto
    all'etichetta; riga selezionata a tutta larghezza;
  - help overlay: `max_body = STATUS_ROW - 7`, altezza clampata;
  - variabili script 90 → 76 colonne, cronologia search 82 → 78.
- Menu line compactate a ≤ 80 colonne: main, forms, indexes, labels, reports,
  rules, scripts editor, searching. I tasti secondari restano nella help line.
- Nuovo `tests/test_layout_legacy.py`: costanti 80/25, chrome 22/23/24,
  larghezza di **tutte** le `*_KEYS` ≤ 80, regioni delle viste shell dentro il
  buffer, indipendenza di `CellBuffer.copy()`, golden a 51 righe.
- Test aggiornati: `test_cli.py` (80x25, 51 righe, identità legacy),
  `test_render.py` (griglia da costanti, zoom limitato calcolato),
  `test_dosbox_automation.py` (800×475).
- Corretto `tools/capture_ui.py`: `--out` fuori dal repo non solleva più
  `ValueError`; gli overlay della cattura non mutano più la vista di base
  (prima `01-main-menu.png` mostrava tre finestre sovrapposte).
- Golden rigenerati e **rivisti**: `main-menu`, `directory`, `help` a 80×25.

### Verifica di questo step

- `pytest -q`: **511 test verdi** (501 funzioni al baseline, ora 459
  definizioni con parametrizzazioni che portano il totale a 511).
- `./start.sh --smoke`: `adbx 1.0.0: griglia 80x25, digest 9f8b632350151a12`.
- Cattura UI: 55 PNG 880×525 in `/tmp/opencode/render-legacy`, controllo
  visivo di main menu, form designer, formatting, script editor, dialog
  designer, debugger.
- E2E adbx: 8 PNG 800×475 in `/tmp/opencode/e2e-legacy`, controllo visivo di
  view records e browse.

### Problemi visivi già individuati (da affrontare negli step successivi)

- `view records` e `browse records`: la **help line** (riga 23) elenca tasti
  con etichette lunghe e viene troncata (`ALT-D de…`, `F7Show dele…`).
- Debugger script: pannello variabili a colonna 98 → invisibile; liste a 36
  righe.
- Dialog designer: pannello Controls a colonna 72, stretto ma leggibile;
  anteprima dialog da clampare.
- Da verificare visivamente gli altri designer (report, label, set, rules,
  applications, printer, documentazione).

## Step 4 — 2026-11-24 — Audit del clipping

Reti di sicurezza permanenti (solo lato test: in produzione il taglio resta
silenzioso come nel video originale).

- `src/adbx/cell/buffer.py`:
  - `ClipEvent` + `audit_clipping()`: con il contesto aperto ogni scrittura
    oltre i bordi finisce in un elenco con tipo, riga, colonna, testo e
    **punto di codice** del primo chiamante (`_caller()`), così il difetto si
    attribuisce senza debug manuale.
  - `allow_clipping()` / `clipping_allowed`: dichiarano voluto il taglio dei
    canvas più larghi della griglia (form e report salvati a 132 colonne),
    che devono continuare a funzionare nella variante legacy.
- `tests/conftest.py`: fixture autouse `no_silent_clipping`, attiva in **tutti**
  i test, con marker `allow_clipping` per i test che verificano il taglio di
  proposito (`test_buffer`, due casi di `test_clip_audit`).
- `tests/test_clip_audit.py`: le 56 viste canoniche (le stesse della cattura
  UI, overlay compresi) e le schermate del guscio non devono produrre alcun
  evento; più test unitari dell'audit (bordi esatti, offset negativi, annidamento).
- `tools/capture_ui.py`: il corpo di `main()` diventa `build_views()`, così la
  cattura e i test di layout condividono le stesse viste.

### Difetti trovati dall'audit e corretti

L'audit ha trovato 112 scritture fuori griglia in 15 punti:

- `records.MODE_KEYS`: righe di menu di view/browse/enter lunghe fino a 144
  colonne (la scansione dello step 3 copriva solo le liste `*_KEYS`, non i
  dizionari). Ora 78/68/66 colonne; F7, Tools, Delete, Undelete, Replace e
  Alt-F6 Paste passano alla help line, riscritta e accorciata.
- `record_screens._form_hint`: help line da 83 a ≤78 colonne.
- Dialog designer (`scripts.py`): impostazioni a sinistra (col 1-27),
  anteprima a destra (col 30, righe 1-10), tabella Controls a tutta larghezza
  (righe 11-20) con colonne calcolate; prima le colonne da 72 a 117 erano
  invisibili.
- Debugger (`scripts.py`): sorgente 48 colonne + separatrice a 50, variabili a
  colonna 53 (erano a 98, invisibili), righe derivate da `STATUS_ROW`.
- Posting rules: colonne da 98 a 76 totali, intestazioni accorciate.
- Field rules: `Type` spostato a colonna 68 con clip sul valore.
- Report designer: il canvas di stampa (fino a 240 colonne) è marcato
  `@clipping_allowed` — il taglio è voluto.
- Applications editor: outline 10 righe (era 14), dettaglio da riga 13, sette
  campi fino a riga 20; prima l'ultimo campo finiva a riga 25 (fuori schermo).
- Searching: help line da 84 a 75 colonne.
- Documentation: `Source: <path>` clippato; righe del report derivate dalla
  griglia (erano fino a 36 righe × 128 colonne).
- Form/set/record custom form: `@clipping_allowed` sui tre renderer; i form
  demo della cattura sono ora larghi 78 colonne.

### Verifica di questo step

- `pytest`: **517 test verdi** (511 + 6 nuovi).
- Audit: **0 eventi** sulle 56 viste canoniche e sulle schermate del guscio.
- `./start.sh --smoke`: `adbx 1.0.0: griglia 80x25, digest 9f8b632350151a12`.
- Visiva: 55 PNG 880×525 rigenerati e ispezionati (dialog designer, debugger,
  posting rules, field rules, app editor, documentation, view/browse records);
  8 E2E 800×475 rigenerati e ispezionati (view records, documentation).


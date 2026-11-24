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

- `pytest -q`: **461 test verdi** (era 451).
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

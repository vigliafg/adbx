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

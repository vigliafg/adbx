# Changelog

## 0.10.0 — 2026-11-25

- **Variante legacy 80×25.** Il worktree `adbx-legacy` riporta la griglia alle
  80×25 celle dell'originale: area di lavoro righe 1–22, status line 23, help
  line 24, menu line 25. Font TrueType scalabile, zoom 50–200% e fit-to-window
  invariati; valori di stampa e formati dati invariati; pacchetto `adbx`
  invariato. Il titolo della finestra è
  `adbx — legacy (80×25)`. Schermate, overlay, designer e menu line
  riadattati alla larghezza di 80 colonne; audit dei test che segnala ogni
  scrittura fuori griglia non dichiarata.
- **Release 0.10.0 multipiattaforma.** Artefatti firmati dal workflow
  `release.yml`: installer Windows NSIS e archivio portabile PyInstaller,
  `.dmg` macOS (Apple Silicon), `.deb` e `.AppImage` Linux x86_64, tarball
  portabile e checksum SHA-256. La numerazione della linea legacy riparte da
  `0.10.0`, distinta dalla `1.0.0` della variante 132×43.
- **Cartella utente nell'eseguibile.** Quando l'app gira pacchettizzata
  (PyInstaller), `config.json` e i dati di lavoro finiscono nella cartella
  utente della piattaforma (`%APPDATA%\adbx-legacy`,
  `~/Library/Application Support/adbx-legacy`,
  `$XDG_DATA_HOME/adbx-legacy`) invece che accanto all'eseguibile, che può
  essere in sola lettura. `ADBX_DATA` e `--data` restano prioritari.
- Zoom: `CTRL-+` ora ingrandisce davvero anche quando la finestra era già
  piena. Al 100% il corpo è il massimo che entra; `CTRL-+` allarga la finestra
  fino allo schermo per contenere il corpo maggiore, `CTRL--` torna indietro
  e `F11` usa tutto lo schermo. `(max)` appare solo oltre il massimo
  effettivo, senza mai tagliare la griglia.
- Enter records: `CTRL-ENTER` salva il record corrente e apre subito il
  successivo da qualunque campo; sull'ultimo campo la command line mostra
  `ENTER Next record`. `F10` resta Continue/Save ed esce dalla modalità,
  come nell'originale.
- Record: da View/Browse `E` entra in Enter; `F10`/`ESC` tornano alla
  modalità precedente (View/Browse sul record salvato o corrente). Nella
  form Enter le frecce spostano tra i campi, non tra i record; `F10` su un
  nuovo record vuoto esce senza crearlo.
- Avvio: schermata di apertura (banner) con l'**ultimo database/set** sulla
  riga di stato; `F10` (o una breve attesa) carica il database e mostra il
  main menu, `F9` apre il Database Directory. L'ultimo database è salvato in
  `config.json` (`last_database`), come l'`A4.DFL` originale. Allineato al
  Reference Manual («Select FIO (Continue) … using the most recently used
  database or set»).
- Finestra: tetto di leggibilità di 24 px logici con margini su schermi
  grandi, zoom `CTRL-+` / `CTRL--` / `CTRL-0` (50–200%) salvato in
  `config.json` (`screen_zoom`) e modificabile da Default settings.
- Avvio: spostato il modulo della finestra in `adbx/app/window.py`; il file
  `src/adbx/app.py` era ombreggiato dal pacchetto `adbx/app/` e la GUI non
  partiva più (`cannot import name 'run'`).

## 1.0.0 — 2026-11-23

Prima release di conformità.

- Database SQLite con `.DBF` interoperabile, table designer, memo, password.
- View/Enter/Change/Browse, cancellazione logica, Find, Locate, Replace.
- Indici, range, search/sort salvati e one-time, storia e out-of-date.
- Field rules complete: default, incrementi, template, maschere, required,
  validation, double entry, skip, calcolati, lookup table/database/cascading,
  post data, re-evaluate.
- Set con link First/Last/Closest/All, integrità, cascading, regioni 1:N, zoom.
- Form designer a celle, form attivi, browse table, formattazione.
- Report engine con 9 gruppi, summary 7×3×4×2, multipass, anteprima e PDF.
- Etichette e lettere con giustificazioni avanzate, condizionali e PDF.
- Utility e I/O: copy, append, summarize, pack, zap, crosstab, post, join,
  intersect, subtract, global update/delete, dieci formati di import/export.
- Script: keystroke, dialog box, menu bar, registrazione, Screen Test, tutti i
  comandi del capitolo 18, variabili, `%SYS_*`, 22 trigger, debugger,
  `AUTOEXEC`, `nomeDB!`, `CTRL-F1..F10`, Tools.
- Applicazioni: editor a outline, parametri, banner, macro, simulazione,
  Call-App/GotO-App, password, protezione dei supporting files.
- Configurazione: `config.json`, default settings, date europee/americane,
  26 driver di stampa, codici e page advance, colori per database,
  generatore di documentazione.
- Suite di conformità: 25 lezioni del Tutorial, nessun test saltato,
  benchmark e CI su Python 3.11–3.13.

# Changelog

## Non pubblicato

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

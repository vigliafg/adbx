# 14 — Configurazione e stampa (O12)

Specifica dell'ondata O12: `config.json`, default settings, 26 driver di
stampa, codici, avanzamento carta, colori per database, documentazione.
Fonti: Reference Manual cap. 22 e appendice 6.

---

## 1. File di configurazione

`config.json` nella cartella di avvio è l'equivalente di `A4.DFL`:

```json
{
  "defaults": {
    "date_separator": "/", "date_format": "American",
    "auto_flush": true, "pattern": "exact",
    "prevent_change": false, "prevent_enter": false,
    "single_step_enters": false, "utilities_lock": true,
    "dbase4": false, "monochrome": false,
    "script_path": "", "data_path": "", "last_database": "",
    "printer_default": ""
  },
  "printers": {"drivers": {}, "default": ""}
}
```

`ConfigStore` legge e scrive il file in modo atomico. Le vecchie funzioni
`load_printers`/`save_printers` restano per i file separati.

`last_database` è scritto automaticamente quando si apre un database o un set
e alimenta il banner di apertura (vedi `docs/spec/02-shell.md`).

Le impostazioni che incidono davvero sul motore:

- **Date separator** e **Date format**: `fields.configure_dates` cambia
  parsing e visualizzazione (`31/01/1990` in formato europeo,
  `01/31/1990` in americano).
- **Pattern matching**: allinea `workspace.pattern_mode` e il valutatore.
- **Prevent change/enter**: View e Browse restano disponibili, Enter e Change
  vengono rifiutati con un messaggio.
- **Auto flush**, **Single step enters**, **Utilities should lock**,
  **dBASE IV**, **Monochrome**: conservati e mostrati; in un desktop
  single-user non cambiano il comportamento (deviazione dichiarata).

## 2. Driver di stampa

Ci sono 26 modelli nel catalogo e 26 lettere A–Z installabili. Un driver
contiene:

- `Lines per page` (default 66, 60 per laser);
- `Page advance`: `Formfeed`, `Sheetfeeder`, `Linefeed`;
- codici decimali: setup, close-out, normal, bold, italic, underline on/off,
  compressed on/off, page 1, new page;
- margini sinistro/destro/alto/basso in colonne o righe;
- `Column offset`, `Port` (`LPT1`, `COM1`, ...) e descrizione.

`PrinterConfig` installa, seleziona ed elimina i driver e indica il default.
`render_text` applica setup, margini, righe e avanzamento: formfeed `\x0c`,
codici della carta per lo sheetfeeder, `lines_per_page` ritorni a capo per il
linefeed. Il generatore PDF usa margini e font del driver attivo; il PDF resta
un formato moderno, non un flusso ESC/P.

Il comando `Other → Printer configuration` mostra l'elenco, installa un
modello (`F2`), elimina (`F5`), sceglie il default (`F6`) e modifica i campi
(`ENTER`). `F10` salva `config.json` e attiva il driver.

## 3. Colori per database

`Set screen colors` salva nella tabella delle impostazioni del workspace una
mappa `colors:<OWNER>` con i 18 token del tema (sfondo, testo, etichette,
finestre, titolo, selezione, status, help, menu, accento). Il tema del
database viene ricostruito con `dataclasses.replace` quando si apre il
database o il set; `F4` ripristina Newport. La palette resta a 16 colori DOS.

## 4. Documentazione

`Other → Documentation` riproduce il programma A4DOC:

- **Database structure**: campi con tipo, lunghezza, decimali e lunghezza
  record.
- **Set structure**: database, link, indici comuni, integrità.
- **Field rules**: per campo o per tipo di regola.
- **Application**: parametri e outline con azioni, macro e password.
- **Script**: tipo, descrizione, screen test, sorgente e script figli
  richiamati con `PLAY`.

La larghezza pagina è 40–240 colonne; l'opzione *Graphic characters* è
conservata. `P` scrive `DOC-<NOME>.PDF` con il driver attivo; `F10` chiude.
Il generatore usa `ReportOutput`, quindi la stessa impaginazione e lo stesso
PDF degli altri report.

## 5. Test

`tests/test_config.py` copre defaults, date, store, catalogo e driver,
avanzamento, margini PDF, colori e documentazione.
`tests/test_config_ui.py` copre menu Other, default settings, prevent enter,
installazione/modifica driver, colori persistenti, documentazione e pattern
matching.

## 6. Deviazioni dichiarate

- I driver non inviano byte a una porta DOS: descrivono codici e geometrie e
  alimentano PDF/stream di testo.
- `Auto flush` è già il comportamento del motore; `Utilities should lock`,
  `dBASE IV` e `Monochrome` sono conservati ma senza effetti single-user.
- I colori sono 16, non i 64.000 della VGA originale.
- Il documentation program è integrato nel guscio, non un eseguibile
  separato `A4DOC`.
- Il PDF ignora i codici ESC/P; l'avanzamento carta è verificato sul flusso
  testuale e i margini sul layout PDF.

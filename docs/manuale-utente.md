# adbx 1.0 — manuale utente

adbx è un clone funzionale di **Alpha Four versione 3**: un database
relazionale a finestre di caratteri, senza programmazione, con regole di
campo, set, report, etichette, lettere, script e applicazioni. Non emula il
DOS: usa una griglia 80×25, un motore SQLite e file `.DBF` interoperabili.

- Licenza MIT.
- Linux, Windows, macOS; Python 3.11 o successivo.
- Interfaccia in inglese come l'originale; documentazione in italiano.

---

## 1. Installazione e avvio

```bash
git clone <repository> adbx
cd adbx
./start.sh                 # crea .venv e installa PyQt6 alla prima esecuzione
./start.sh --data ~/dati   # parte dalla cartella indicata
./start.sh --open ~/dati/AVMOVIES.DBF
./start.sh --app AVSYSTEM  # avvia un'applicazione
./start.sh --smoke         # verifica headless
./start.sh --version
```

In alternativa:

```bash
python -m pip install -e .
adbx --data ~/dati
```

All'avvio compare il **banner** con l'ultimo database/set usato in basso.
`F10` (Continue) — o una breve attesa — carica quel database e porta al
**main menu**; `F9` (Change Database/Set) apre subito il **Database
Directory**. Senza un database precedente, `F10` porta al Database Directory.

Nel Database Directory con le frecce si sceglie un `.DBF` o `.SET` e con
ENTER lo si apre. Il filtro accetta `*` e `?`. F3 importa, F4 mostra la
cronologia, F5 crea un database, F6 aggiorna, F8 mostra i dettagli, F9 è
riservato al DOS e non è disponibile. `ESC` torna al main menu.

## 2. Tastiera e schermo

- `F1` aiuto contestuale, `F2` struttura, `F3` stato, `F10` continua/salva.
- `ALT-F10` torna al main menu; `ESC` o tasto destro annullano un livello.
- `ALT-F3` menu degli script, `ALT-F4` suona uno script.
- `ALT-F1` registra `UNTITLED`, `ALT-F2` lo suona.
- `CTRL-F1`…`CTRL-F10` suonano `CTRLF1`…`CTRLF10`.
- `CTRL-+` / `CTRL--` cambiano lo zoom (50–200%), `CTRL-0` torna al 100%;
  se la finestra non basta allo zoom richiesto il titolo mostra `(max)`.
- Nel main menu la lettera maiuscola del comando è la hot key.
- Nei record: `F` Find, `L` Locate, `I` indice, `R` range, `S` replace,
  `ALT-M` memo, `ALT-D` cancella, `ALT-U` richiama, `T` Tools.
- In Enter: `ENTER` sull'ultimo campo o `CTRL-ENTER` salvano e aprono il
  record successivo; `F10` salva ed esce dalla modalità (torna a View se sei
  entrato da View con `E`, altrimenti al menu).
- Nella form Enter `UP`/`DOWN` spostano tra i **campi**, non tra i record.
  Per rivedere i record già inseriti usa View: `E` da View entra in Enter,
  `F10`/`ESC` tornano a View e le frecce scorrono i record.

I nomi dei file sono DOS 8.3. Database, set, indici, script, lettere e
applicazioni usano lettere A–Z o nomi brevi.

## 3. Database

### Creare e modificare

`Database/set design → Create database` apre il table designer: nome campo
(massimo 10 caratteri, inizia con una lettera), tipo `C N D L M`, lunghezza e
decimali. F5 cancella, F6 inserisce, F7 sposta, F10 salva. Un database ha fino
a 128 campi e 4.000 caratteri per record; un memo arriva a 5.000 caratteri.

`Modify database` riconfigura i campi e applica la matrice di conversione del
manuale. Un cambio di tipo può perdere valori: leggere l'avviso prima di
confermare. `Password` protegge l'apertura; `Erase database` elimina struttura
e dati.

### Record

- **View**: solo lettura, con ricerca e range.
- **Enter**: nuovo record, F10 salva, ESC annulla.
- **Change**: modifica il record corrente.
- **Browse**: tabella con molte righe.
- **Delete/recall**: cancellazione logica; `F7` mostra i cancellati e `ALT-U`
  li richiama.

`Pack` elimina fisicamente i cancellati e rinumera; `Zap` svuota il database
mantenendo la struttura.

## 4. Ricerca, indici e range

`Indexes/ranges → Create an index` definisce espressione, filtro, maiuscole,
duplicati e ordine. Il primary index determina l'ordine di lettura.
`Create/edit a range` salva fino a 26 range con primo/ultimo valore, filtro e
modalità di visualizzazione.

`Search/sort lists` crea una lista one-time o salvata A–Z, in Table o
Expression mode, con ricerca e ordinamento separati. La storia conserva le
ultime 10 liste; una lista diventa out-of-date (`♦`) quando il database cambia.

`Find` cerca per prefisso sull'indice primario; `Locate` cerca un testo in più
campi; `Replace` sostituisce in View.

## 5. Field rules

`Database/set design → Field rules` pagina per pagina:

- valore `User-entered`, `Calculated` o `Summary`;
- default, incremento, template e maschera;
- required, validation con messaggio, double entry, skip, prompt;
- case convert (`Caps`, `Lower`, `First`, `Word`, `X`);
- lookup table, database, cascading table, conditional table/database;
- post data verso un altro database;
- summary con livello, ignore e modo `Running`/`Pre-processed`.

Le regole a livello set hanno precedenza tutto-o-niente. `Re-evaluate field
rules` riapplica calcoli e conversioni ai record esistenti e segnala i record
non conformi.

## 6. Set e regioni

`Database/set design → Set commands` crea un set con fino a 10 database, un
solo link 1:N per livello e link `First`, `Last`, `Closest` o `All`.
Integrità referenziale, cascading update/delete, `Include Parent If` e
`Integrity Rule` gestiscono i figli.

Nelle regioni 1:N si entra con TAB, ci si sposta con le frecce, si zooma con
F8/F9 e si torna con ESC. Un form con regioni non è stampabile: per la carta
serve un report.

## 7. Form, report, etichette, lettere

- `Layouts → Forms`: designer a celle con campi, testi, riquadri, regioni,
  calcolati, summary, formattazione e parametri. Il form attivo è usato da
  View/Enter/Change/Browse.
- `Layouts → Reports`: sezioni, gruppi 0–9, summary, multipass, formati,
  anteprima e PDF. `Print → Report` stampa un report salvato.
- `Layouts → Mail labels`: fino a 26 layout, 10–78 colonne, 1–20 righe, sei
  etichette per riga, giustificazioni `Suppress`, `Float`, `Trim`, `Join`,
  `Before`, `After`.
- `Layouts → Letters`: editor con `[CAMPO]`, `[{espressione}]`, `[?prompt]`,
  comandi `[.WIDTH]`, `[.LEFT]`, `[.TOP]`, `[.EOL]`, `[.FILL+]`, `[.EJECT]`,
  `[.INCLUDE]`, `[@codici]` e condizionali `[.IF]`, `[.ELSEIF]`, `[.ELSE]`,
  `[.ENDIF]`.

Report, etichette e lettere producono PDF; non c'è invio diretto a una
stampante DOS.

## 8. Utility e scambio

`Utilities` comprende Copy, Append (All, Unique, Replace existing add/mark
unique), Summarize, Pack, Zap, Cross Tabulation, Post, Join, Intersect,
Subtract, Import ed Export.

L'import/export gestisce dBASE II, dBASE III/IV, ASCII separato, CSV, ASCII
tabellare a colonne fisse, DIF, SYLK, Lotus WKS/WK1, WordPerfect merge e
MultiMate. Field Adjust permette di correggere nome, tipo, lunghezza e
decimali prima di creare il database. Le impostazioni non vengono salvate in
file proprietari.

`Global update/delete` aggiorna fino a 20 campi con espressioni, cambia
maiuscole e cancella o richiama un range.

## 9. Script

`ALT-F3` apre il menu Scripts. Tre tipi:

- **Keystroke**: tasti e comandi; registrazione con F3/F4 nell'editor.
- **Dialog box**: finestra con Prompt, Button e Display.
- **Menu bar**: menu alternativo per un form o browse table.

Sintassi: caratteri comuni sono tasti, `{COMANDO}` è un comando, `{*testo*}`
un commento, `:A` una label. I blocchi si annidano e la forma canonica è
`{{COMANDO ...}}`.

Comandi principali: `IF`, `CASE`, `LOOP`, `GOTO`, `SET`, `CLEAR`, `PLAY`,
`PROMPT`, `READ`, `WRITE`, `WAITFOR`, `WAITKEY`, `WAITSCRN`, `WAITUNTIL`,
`XLOOKUP`, `XLOOKUPC`, `XLOOKUPR`, `TRIGKEYS`, `ONKEY`, `ONERROR`, `ONESCAPE`,
`ONMAIN`, `ALLOWKEYS`, `SCREENOFF`, `SCREENON`, `SCREENFREEZE`, `SHOW`,
`TONE`, `BEEP`, `MOUSE*`, `VSAVE`, `VRESTORE`, `DEBUGON`, `DEBUGOFF`,
`ABORT`, `CANCEL`, `ENDAPP`, `MAINMENU`, `TOOLEND`.

Variabili `%NOME` (24 caratteri, valore 254) e `%SYS_*`. I trigger si attivano
con `{SET %SYS_TRIG_<EVENTO>,"SCRIPT"}` e si disattivano con `""`.

Lo **Screen Test** impedisce il playback su una schermata sbagliata. Il
debugger (F10 un token, F5 fino alla fine, F4 debug, F3 variabili) mostra il
punto di esecuzione.

`AUTOEXEC` parte all'avvio. Un script `<primi 7 caratteri>!` parte quando si
apre il database o set. `Tools` in View/Browse elenca gli script suonabili;
`%SYS_TOOLS` può imporre un nome.

## 10. Applicazioni

`Applications` permette di eseguire, creare, modificare, cancellare
applicazioni e proteggere i supporting files.

L'editor mostra l'outline (le intestazioni hanno `=`) e i parametri della voce:
testo, help line, azione (`Sub-Menu`, `Macro`, `Call-App`, `GotO-App`),
target, macro, password e help file. F2 aggiunge, F5 cancella, F9 cambia
finestra, F3 registra la macro, F4 apre il Macro Editor, F6 dipinge il banner,
F8 simula, F10 salva.

Il `Menu flow` decide il ritorno: `Return`, `Stay`, `Advance`. `Call-App`
torna al chiamante (massimo 10 livelli), `GotO-App` no. Le password sono
case-insensitive; `Allow escape` può essere `Yes`, `No` o `Password`.

`Prevent/allow file alterations` blocca Forms, Browse tables, Reports, Mail
labels, Letters, Ranges, Search/Sort lists e Field rules per database o set.

## 11. Configurazione

`Other` contiene:

- **Pattern matching**: Exact, Case, Case-insensitive.
- **Default settings**: separatore e formato data, auto flush, prevent
  change/enter, single step enters, lock, dBASE IV, monocromatico, path.
- **Printer configuration**: fino a 26 driver A–Z da un catalogo di 26
  modelli, codici decimali, righe per pagina, avanzamento `Formfeed`,
  `Sheetfeeder` o `Linefeed`, margini e porta.
- **Set screen colors**: 18 token del tema per database o set.
- **Documentation**: struttura database/set, field rules, applicazioni e
  script, con anteprima e PDF.

Le impostazioni stanno in `config.json` nella cartella di avvio.

## 12. Backup e dati

Il workspace conserva `.adbx.sqlite` con catalogo, record, memo, indici,
regole, form, report, etichette, lettere e impostazioni. Il `.DBF` è la
sorgente di scambio e viene riscritto a ogni salvataggio esplicito.

Per il backup:

1. chiudere adbx;
2. copiare l'intera cartella dati, inclusi `.DBF`, `.DBT` e `.adbx.sqlite`;
3. conservare anche `config.json` e le cartelle `objects/`.

Non copiare solo il `.DBF` se si vogliono mantenere regole, form e report:
sono nel workspace.

## 13. Differenze dichiarate

- Nessun runtime DOS, `A4ENC`, `A4EXEMKR`, installazione DOS o multiuser.
- Nessuna stampa diretta su LPT/COM: PDF e stream testuali.
- Indici `.NDX` in sola lettura; il motore usa indici propri.
- Form fino a 25 schermate; il manuale stampato ne dichiara 10.
- Colori di campo 0–255 mappati su 16 colori DOS.
- Numeri in testo canonico, non `REAL`.
- Script in JSON leggibile, non nel formato binario `.SCP`.
- `EXEC`, `EXECCLR` e `RPL` non eseguono programmi DOS.
- I file MultiMate sono documenti testuali, non la codifica originale.

## 14. Problemi comuni

**Il database non si apre.** Controllare che il `.DBF` esista e non sia
bloccato; il workspace viene ricreato dal `.DBF`. Se il database ha password,
digitarla senza eco.

**Un campo non accetta valori.** Controllare field rules, maschera, template,
required, validation e lookup. `Re-evaluate` mostra i record non conformi.

**Un report esce largo o tagliato.** Ridurre la larghezza (40–240) o usare il
formato landscape; verificare i margini del driver.

**Uno script non parte.** Controllare lo Screen Test, il path script e che il
nome esista. Il debugger mostra il token che fallisce.

**Un'applicazione non torna al menu.** Verificare `Menu flow` e `Allow
escape`; una voce `GotO-App` non torna per definizione.

**Un designer è bloccato.** `Applications → Prevent/allow file alterations`
mostra i tipi protetti per il database o set.

## 15. Automazione e test visivi

Per gli sviluppatori e per i test di regressione:

```bash
python tools/e2e_visual.py              # 8 scenari adbx + PNG e manifest
python tools/dosbox_automation.py --probe
python tools/dosbox_automation.py --download --screenshot /tmp/alpha4.png
python tools/e2e_visual.py --dosbox     # richiede dosbox-automation
```

`dosbox-automation` pilota l'originale via REST API: monta il drive, avvia
`A4.EXE`, legge il testo dello schermo, invia tasti e cattura frame. Il
binario GPL-2.0 non è incluso nel repository; `--download` lo mette nella
cache utente. Senza display viene usato `xvfb-run`.

Le immagini di conferma sono in [`docs/e2e/`](e2e/README.md), con testo
atteso, dimensioni, colori campionati e SHA-256 in `manifest.json`.

## 16. Riferimenti

- `README.md`: panoramica e stato.
- `PLAN.md`: architettura e ondate.
- `DIARIO.md`: scelte e stato dell'implementazione.
- `docs/spec/`: specifiche tecniche.
- `docs/reference/00-inventario.md`: inventario funzionale.
- `docs/CHANGELOG.md`: note di release.

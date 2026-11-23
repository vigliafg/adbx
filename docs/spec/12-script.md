# 12 — Script (O10)

Specifica dell'ondata O10: motore di script, registrazione dei tasti, dialog
box, menu bar, variabili, trigger, debugger e punti di aggancio del guscio.
Fonti: Reference Manual cap. 18, Tutorial lezioni 24–25, inventario §4–§6.

---

## 1. Tipi di script

| Tipo | Contenuto | Esecuzione |
|---|---|---|
| Keystroke | caratteri, comandi `{...}`, label `:A`–`:Z` | ALT-F4, menu Scripts, `{PLAY}`, trigger, CTRL-F1..F10 |
| Dialog box | finestra con controlli Prompt, Button, Display | dal menu Scripts o da un'applicazione; i Button lanciano uno script |
| Menu bar | voci alternative per View/Browse | assegnato al parametro *Custom menu bar* di un form |

I nomi sono DOS 8.3 (`A–Z 0–9 _`); un nome può terminare con `!` per gli
script di apertura database/set. La directory predefinita è
`objects/scripts` sotto la cartella dati; *Set script path* la cambia e la
salva nelle impostazioni del workspace. Il limite è 400 script per directory;
uno script ha al massimo 3.000 caratteri e un comando 1.000.

Ogni script è un file JSON leggibile `<NOME>.JSON`, con nome, descrizione,
tipo, sorgente, screen test, definizione del dialog box o del menu bar.
L'export `.SCP` produce un file di testo con un'intestazione commentata e la
sola sequenza; l'import lo rilegge.

## 2. Sintassi

- I caratteri comuni sono tasti. Spazi e tabulazioni sono significativi: gli
  spazi vengono digitati, le tabulazioni sono ignorate.
- `{NOME}` è un tasto speciale (`{ENTER}`, `{F10}`, `{ALT-F3}`,
  `{CTRL-F1}`, `{UP}`, ...).
- `{COMANDO argomenti}` è un comando; gli argomenti sono separati da virgola.
- `{*testo*}` è un commento.
- `:A` è una label; `{GOTO :A}` e `{LOOP :A,%N}` vi trasferiscono il controllo.
- Un blocco è `{ ... }` e può contenere tasti e comandi annidati; la forma
  canonica di un comando dentro un blocco è `{{COMANDO ...}}`, come nei
  manuali.
- I riferimenti `%NOME` sono sostituiti prima della valutazione delle
  espressioni; `@%NOME` è l'indirezione.

## 3. Comandi implementati

Tutti i comandi del cap. 18:

| Gruppo | Comandi |
|---|---|
| Applicazione | `ABORT`, `CANCEL`, `ENDAPP`, `MAINMENU`, `TOOLEND` |
| Schermo | `NOCLEAR`, `SCREENFREEZE`, `SCREENOFF`, `SCREENON`, `WRITE` |
| Variabili | `CLEAR`, `SET`, `VSAVE`, `VRESTORE`, `XLOOKUP`, `XLOOKUPC`, `XLOOKUPR` |
| Dialogo | `PROMPT`, `READ` |
| Decisioni | `CASE`, `IF`, `GOTO`, `LOOP` |
| Errori | `ONERROR` |
| Generali | `ONMAIN`, `PLAY`, `SHOW`, `TRIGKEYS` |
| Mouse | `MOUSEDCLICK`, `MOUSEDOWN`, `MOUSEMOVE`, `MOUSEUP` |
| Tastiera | `ALLOWKEYS`, `ONESCAPE`, `ONKEY`, `PAUSE`, `WAITKEY` |
| Esecuzione esterna | `EXEC`, `EXECCLR`, `RPL` |
| Suono | `BEEP`, `TONE` |
| Attese | `WAITFOR`, `WAITSCRN`, `WAITUNTIL` |
| Debug | `DEBUGON`, `DEBUGOFF` |

Note di semantica:

- `IF` valuta un'espressione con il valutatore unico; `CASE` prova i rami in
  ordine e accetta fino a 15 coppie.
- `LOOP` decrementa la variabile a ogni ritorno alla label; con valore ≤ 1
  esegue il corpo una volta.
- `SET` converte il risultato in testo character (data `MM/DD/YYYY`, logico
  `T`/`F`, numerico canonico). `SET@VARNAME` risolve il nome dal valore di
  `%VARNAME`.
- `PLAY` annida fino a 10 livelli; `CANCEL` ferma il figlio, `ABORT` ferma
  tutto e torna al main menu.
- `XLOOKUP*` imposta `%DB_CAMPO` per ogni campo del record trovato e la
  variabile di stato (`0` successo, `218` chiave assente). Errori di database
  o indice passano da `ONERROR`.
- `TRIGKEYS` accoda i tasti; in uno script di trigger tutti i tasti sono
  differiti e vengono eseguiti dopo l'evento.
- `EXEC`, `EXECCLR` e `RPL` sono riconosciuti ma non eseguono programmi DOS:
  sollevano un errore gestibile da `ONERROR` (deviazione dichiarata).
- `WAITFOR`, `PAUSE`, `WAITKEY`, `WAITSCRN`, `WAITUNTIL` sono sincroni e non
  bloccano il loop Qt: registrano l'attesa e, nell'host di test, la
  verificano. La UI desktop non mette in pausa l'event loop.

## 4. Variabili

- Nome massimo 24 caratteri, valore character massimo 254, sempre testo.
- `%SYS_*` create dal motore: path script, ultimo tasto, ultimo bottone,
  modalità save/view, tools, conteggio search, flag search vecchia, path
  applicazione e i `%SYS_TRIG_*`.
- `%SYS_CTRLF1`..`%SYS_CTRLF10` scelgono lo script da suonare con CTRL-F1..10;
  se vuote valgono `CTRLF1`..`CTRLF10`.
- `VSAVE`/`VRESTORE` usano file `.VAR` testuali con una variabile per riga;
  il pattern ammette `*` e `?`.

## 5. Trigger

Ventidue eventi del manuale, attivati con
`{SET %SYS_TRIG_<EVENTO>,"SCRIPT"}` e disattivati con `""`:

`REC_ENTER`, `REC_CHANGE`, `REC_DEL`, `REC_UNDEL`, `REC_SAVE`,
`REGION_ENTER`, `REGION_EXIT`, `FIELD_ENTER`, `FIELD_VALID`, `FIELD_EXIT`,
`LETTER_START`, `LETTER_PRINT`, `LETTER_FINISH`, `SEARCH_START`,
`SEARCH_PERFORM`, `SEARCH_SUCCESS`, `SEARCH_FINISH`, `UPDATE_START`,
`UPDATE_PERFORM`, `UPDATE_FINISH`, `ZOOM`, `UNZOOM`.

Agganci reali nel guscio:

- record: ingresso/uscita campo, validazione prima delle field rules, salvataggio,
  cancellazione e richiamo;
- ricerca/sort, lettere, global update: inizio/fine (e per-record dove il
  ciclo lo consente);
- zoom/unzoom nelle regioni 1:N.

I nomi delle variabili che l'OCR del manuale rende in modo ambiguo hanno alias
in `script/triggers.py`.

## 6. Screen test

Lo script conserva le righe che devono comparire sullo schermo. F5 le digita,
F6 marca l'area corrente (l'intera schermata, nel modello a celle). Prima del
playback il confronto è case-insensitive e ignora gli spazi multipli; se
fallisce, lo script non parte e il messaggio è mostrato nella status line.

## 7. Registrazione e playback

- `ALT-F1` registra `UNTITLED` (sovrascrive); `ALT-F2` lo suona.
- `ALT-F3` apre il menu Scripts; `ALT-F4` apre la lista Play.
- Nell'editor F3 registra da capo, F4 aggiunge in coda; ALT-F3 ferma e salva.
- Il playback inietta i tasti in `ShellController.handle`: non esiste un
  secondo percorso di input. I comandi agiscono tramite `ScriptHost`.
- `AUTOEXEC` parte all'avvio dopo il caricamento del database.
- Aprendo un database o un set si cerca `<primi 7 caratteri>!` nella
  directory script.
- `Tools` in View/Browse elenca gli script suonabili; `%SYS_TOOLS` può
  imporre un nome alternativo.

## 8. UI

- **Script Editor**: righe con numero, cursore a cella, F2 elenco comandi,
  F3/F4 learn, F5 screen test, F6 marca area, F7 descrizione, F10 salva.
- **Dialog Box Designer**: pannello impostazioni (titolo, posizione,
  dimensioni, colori, ombra, no-clear), tabella controlli e anteprima; F2/F3/F4
  aggiungono Prompt/Button/Display, F5 cancella.
- **Menu Bar Designer**: tabella Key/Label/Action con anteprima del menu.
- **Script Variables**: elenco `%NOME valore`, ENTER modifica, F4 cancella.
- **Debugger**: F10 esegue un token, F5 fino alla fine, F4 attiva/disattiva il
  debug, F3 mostra le variabili.
- **Dialog runtime**: TAB/UP/DOWN spostano il fuoco, i Prompt accettano testo,
  ENTER su un Button esegue la sua azione; i valori finiscono nelle variabili.

## 9. Test

`tests/test_script_engine.py` copre tokenizer, variabili, tutti i comandi,
trigger, limiti, store/export/import.
`tests/test_scripts_ui.py` copre menu, creazione/editor, screen test,
designer, runtime, debugger, quick record, AUTOEXEC, script `nome!`,
CTRL-F1..F10, trigger di cancellazione, Tools e menu bar personalizzato.

## 10. Deviazioni dichiarate

- `EXEC`/`EXECCLR` non eseguono programmi esterni; `RPL` non ha routine
  residenti.
- Le attese sono cooperative e non sospendono l'event loop Qt.
- Lo screen test conserva le righe attese; il rettangolo è memorizzato ma il
  confronto usa il testo.
- `SHOW` restituisce i valori di default dei controlli e non instrada i
  Button, come prescrive il manuale («ignoring any controls»).
- Il dialog runtime chiude la finestra prima di eseguire l'azione di un
  Button, per evitare rientri nel gestore dei tasti.
- I file di script sono JSON leggibili, non il formato binario `.SCP`
  originale; l'export `.SCP` è testuale.

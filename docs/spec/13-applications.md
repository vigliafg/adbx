# 13 — Applicazioni (O11)

Specifica dell'ondata O11: application editor, parametri, banner, macro,
simulazione, Call-App/GotO-App, password e protezione dei supporting files.
Fonti: Reference Manual cap. 17, Tutorial lezione 21, inventario §3.11.

---

## 1. Modello

Un'**applicazione** sostituisce il main menu con un albero di menu. Ogni
voce ha:

- `Menu text` (fino a 60 caratteri; la prima maiuscola è l'hot key);
- `Help line` (fino a 79 caratteri) e `Help file` ASCII;
- `Menu action`: `Sub-Menu`, `Macro`, `Call-App`, `GotO-App`;
- `Target`: titolo del sottomenu o nome dell'applicazione;
- `Macro`: fino a 3.000 caratteri, con tasti e comandi di script;
- password opzionale (fino a 10 caratteri, case-insensitive, salvata come
  hash SHA-256).

Un menu ha titolo, `Menu flow` (`Return`, `Stay`, `Advance`), `Columns`
(`Single`, `Double`) e `Spacing` (`Single`, `Double`, `Triple`,
`Quadruple`). L'annidamento massimo è 10 livelli. Il nome dell'applicazione è
DOS 8.3 e i file stanno in `objects/apps/<NOME>.JSON`.

## 2. Parametri

La schermata dei parametri espone:

- `Description`;
- `Startup database/set` (nome, `.DBF`/`.SET`, path assoluto o relativo alla
  cartella dati);
- `Startup macro` (massimo 3.000 caratteri);
- `Script path` (con il segnaposto `<DATAPATH>` per la cartella dati);
- `Application banner` (`Yes`/`No`);
- `Allow escape` (`Yes`, `No`, `Password`) e relativa password.

All'avvio il runtime applica il database/set di partenza, imposta
`%SYS_APP_PATH` alla directory delle applicazioni e `%SYS_APP_DESKTOP` alla
cartella dati, quindi esegue la startup macro. Se il banner è attivo e non
vuoto, viene mostrato prima del menu e la macro parte dopo il primo tasto.

## 3. Editor

L'editor ha due finestre:

1. **Outline** — albero indentato; le intestazioni sono prefissate da `=`.
   `F2` aggiunge una voce (o la inserisce dopo quella corrente), `F5` la
   elimina con il suo sottomenu.
2. **Dettagli** — `Menu text`, `Help line`, `Menu action`, `Target`,
   `Macro`, `Password`, `Help file`; per un'intestazione: `Menu title`,
   `Menu flow`, `Columns`, `Spacing`.

`F9`/`TAB` passano da una finestra all'altra. `F3` registra la macro della
voce con lo stesso motore degli script (ALT-F3 ferma). `F4` apre il Macro
Editor multilinea. `F6` apre il banner painter. `F8` simula. `F10` salva.

Il banner painter è una griglia 80×25 con cursore a celle: i caratteri
digitati finiscono nel banner, `F3`/`F4` cambiano colore di primo piano e
sfondo, `F10` salva. I colori sono memorizzati solo dove differiscono da
quelli di base.

## 4. Runtime

- `ENTER` attiva la voce, le lettere maiuscole sono hot key, `UP`/`DOWN`
  spostano l'evidenziazione, `ESC` chiude un sottomenu.
- `Sub-Menu` apre il menu figlio; `Macro` esegue il testo con il motore di
  script; `Call-App` avvia un'altra applicazione e vi torna con `ESC` o
  `{ENDAPP}` (fino a 10 livelli); `GotO-App` la sostituisce e non torna.
- Dopo un'azione si applica il `Menu flow` dell'intestazione: `Return` torna
  al menu chiamante, `Stay` resta, `Advance` sposta la selezione avanti.
- Una voce con password chiede il valore prima dell'azione; una password
  errata chiude il prompt e mostra l'errore nella status line.
- `Allow escape = No` blocca ESC; `Password` lo consente solo con la password.
- La **simulazione** usa lo stesso runtime ma non esegue macro, Call-App o
  GotO-App; mostra solo i menu. ESC al livello radice torna all'editor.

## 5. Prevent/allow file alterations

Le protezioni sono per database o set e per tipo: Forms, Browse tables,
Reports, Mail labels, Letters, Ranges, Search/Sort lists, Field rules. Sono
salvate come JSON nelle impostazioni del workspace. Quando un tipo è
protetto, il comando che aprirebbe il designer mostra un avviso e non
prosegue; la protezione si toglie dallo stesso elenco.

## 6. Menu principale

`Applications` apre:

- `Run an application`;
- `Create/edit application`;
- `Erase an application`;
- `Prevent/allow file alterations`.

La riga di comando `--app NOME` avvia direttamente un'applicazione.

## 7. Test

`tests/test_applications.py` copre modello, outline, hot key, password,
store, runtime, flow, Call/GotO, escape, simulazione, banner e protezioni.
`tests/test_applications_ui.py` copre menu, creazione, parametri, editor,
sottomenu, Macro Editor, runtime, password, banner, simulazione, startup,
protezione, cancellazione, macro recording e help file.

## 8. Deviazioni dichiarate

- Il banner memorizza testo e colori per cella; non c'è un vero screen
  painter con linee e blocchi.
- Le password sono hash senza salt, adatte a proteggere un menu, non a
  sicurezza crittografica.
- Le protezioni bloccano i designer nel guscio, non i file su disco.
- I menu di sfondo (screen painter dei menu) non sono implementati; il
  banner è l'unico sfondo personalizzato.
- La startup macro e le macro delle voci usano il motore di script; le
  attese restano cooperative come in O10.

# O1 — Shell

Descrizione del guscio: cosa si vede all'avvio, come si naviga, quali tasti
esistono e cosa è volutamente rimandato alle ondate successive.

## 1. Avvio

- La shell parte nella **cartella corrente** (o in quella indicata con
  `--data DIR`, o dalla variabile `ADBX_DATA`).
- All'avvio compare la **schermata di apertura (banner)** con l'ultimo
  database/set usato sulla riga di stato, come l'originale.
- `F10` (Continue) — o l'attesa di quattro secondi — carica l'ultimo
  database/set e mostra il **main menu**. `F9` (Change Database/Set) o `ESC`
  apre subito il **Database Directory**.
- Se non c'è un ultimo database (primo avvio, oppure file sparito),
  `F10`/l'attesa portano al **Database Directory**.
- Il main menu senza database mostra `(none)`; i comandi che ne hanno bisogno
  invitano a sceglierne uno. Il Database Directory resta raggiungibile anche
  da `Choose database/set` → `Open a database`.
- L'ultimo database/set aperto è salvato in `config.json`
  (`last_database`), l'equivalente di `A4.DFL`.
- Con `--open FILE` (database `.DBF`) si salta il banner e si arriva
  direttamente al main menu.
- Non c'è un banner grafico disegnabile: quello di adbx è una schermata
  funzionale con logo, database predefinito e tasti. Deviazione dichiarata.

Il controller `ShellController` non conosce Qt: riceve `Key` e coordinate di
cella, produce un `View` (buffer + zone cliccabili). La stessa `handle(Key)`
sarà usata dagli script in O10.

## 2. Database Directory

```
D A T A B A S E   D I R E C T O R Y
Drive/Path : /percorso/corrente/*
Default    : *.SET, *.DBF
Name                 Type   Date
<Parent>             <DIR>
AVMOVIES             DBF    06/01/1993
...

Enter name of the database/set : /percorso/corrente/AVMOVIES.DBF_
F3Import   F4History on   F6Refresh   F5Create Db   F8Detail on   F9DOS
```

- **Accesso**: dal banner con `F9` (Change Database/Set) oppure dal main menu
  con `Choose database/set` → `Open a database`. `ESC` torna al main menu.
- **Elenco**: `<Parent>` (se esiste), sottodirectory, poi file `.SET`/`.DBF`
  in ordine alfabetico. Il nome è il basename; l'estensione va nella colonna
  Type; la data è quella del file (come il `DIR` di DOS).
- **Filtro**: il campo in basso accetta un nome, un percorso, `..`, oppure un
  filtro con `*` e `?` (`AV*`, `*.DBF`, `/altra/cartella/*`). ENTER applica.
- **Selezione**: SU/GIÙ, PgUp/PgDn, Home/End; la riga scelta riempie il campo.
  ENTER apre il file o entra nella directory; `<Parent>` risale.
- **F4 History**: pop-up con gli ultimi 10 database/set aperti; ENTER riapre.
- **F6 Refresh**: rilegge la cartella mantenendo la selezione.
- **F8 Detail on/off**: aggiunge le colonne `Records` e `Fields`, lette
  dall'intestazione DBF.
- **F3 Import**, **F5 Create Db**, **F9 DOS**: mostrano un avviso con l'ondata
  in cui arriveranno (O9, O2) o l'indisponibilità dichiarata (DOS).
- Il tasto destro equivale a ESC; doppio clic su una riga equivale a ENTER.

## 3. Main menu

```
Current database : /percorso/AVMOVIES.DBF      Records in database : 50
Primary index    : by Record Number

             ┌──── Alpha Four Main Menu ────┐
             │ View/enter records           │ Database/set design │
             │ Print                        │ Layouts             │
             │ Search/sort lists            │ Applications        │
             │ Indexes/ranges               │ Utilities           │
             │ Global update/delete         │ Other               │
             │ Choose database/set          │ Quit                │
             └──────────────────────────────┘

View, change, enter or delete records
F1Help  Alt-F1Quick record  Alt-F2Quick play  Alt-F3Script menu  Alt-F9DOS access
```

- **Hot key**: la lettera maiuscola del nome (`V P S I G C D L A U O Q`).
  `W` è la scorciatoia per Choose database/set → sWitch databases.
- **Frecce**: su/giù percorrono i comandi nell'ordine delle colonne; sinistra e
  destra saltano di sei posizioni.
- **F1**: aiuto contestuale sul comando evidenziato.
- **F2 / F3**: struttura del database e schermata di stato (lezioni 3).
- **ENTER**: esegue. In questa ondata solo `Choose database/set` (Desktop
  Options → Open a database) e `Quit` sono attivi; gli altri mostrano un
  avviso con l'ondata prevista, senza fingere di funzionare.
- **Alt-F10** riporta al main menu da ogni schermata; in aiuto chiude la
  finestra e torna al menu.

## 4. Desktop Options

`Choose database/set` apre il menu `Desktop Options`:

| Voce | O1 |
|---|---|
| Open a database | attivo: apre il Database Directory |
| Switch / Close / Save / Retrieve / Erase desktop | avviso, ondata O5 |

## 5. Aiuto

- La finestra si apre con F1 e contiene il titolo del comando, testo e
  **rimandi** (frasi in blu).
- SU/GIÙ spostano la barra sui rimandi, ENTER segue il rimando, BACKSPACE/
  SINISTRA torna al topic precedente, ESC chiude, PgUp/PgDn scorrono.
- Esistono topic per: main menu, i 12 comandi, Database Directory, struttura,
  status, tastiera, uso dell'aiuto. Ogni rimando punta a un topic esistente
  (verificato dai test).
- Il testo è nostro, non copiato dal manuale.

## 6. Struttura e stato

- **F2**: nome database, lunghezza record, elenco campi con tipo, larghezza e
  decimali, 15 per pagina; PgUp/PgDn cambiano pagina, F10/ESC tornano.
- **F3**: file, record, campi, indice primario, set, form, browse, range,
  stampante, versione. I valori non ancora gestiti mostrano `(none)`.

## 7. Mouse

- Clic su un comando del menu: lo evidenzia; doppio clic: lo esegue.
- Clic su una riga del directory: la seleziona; doppio clic: la apre.
- Clic sul campo nome: posiziona il cursore; clic sulle voci della riga menu
  (`F1`, `F6`, …): esegue il tasto.
- Tasto destro: ESC.

## 8. Deviazioni e limiti dichiarati

- Il banner iniziale è funzionale (logo, database predefinito, tasti), non
  riproduce la grafica dell'originale.
- `F9 DOS` non esiste: adbx è una finestra moderna.
- Set, import, creazione database e desktop sono riconosciuti ma rimandati:
  i messaggi dicono l'ondata.
- Il charset è CP437 via Unicode; i nomi file lunghi sono mostrati interi,
  anche se il limite originale era 8.3.

## 9. Accettazione

- Lezione 1: banner con database predefinito, Database Directory, AVMOVIES,
  main menu, help su ogni comando, Quit. Coperta da `tests/test_lesson.py`.
- Lezione 3: Choose database/set → Open a database, cambio database, F2
  struttura (due pagine per AVSALES), F3 status. Coperta dallo stesso file.
- Help contestuale su ogni comando e directory navigabile da tastiera e mouse:
  `tests/test_shell_menu.py`, `tests/test_shell_directory.py`.

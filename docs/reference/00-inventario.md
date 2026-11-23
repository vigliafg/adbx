# Inventario di riferimento — Alpha Four 3.0

Estratto dai manuali originali (`Reference Manual`, 25 capitoli + 8 appendici;
`Tutorial Manual`, 25 lezioni). Serve a non perdere contatto con le
funzionalità durante l'implementazione: **ogni voce qui elencata è un requisito**
salvo quanto escluso in `PLAN.md` §2.

Fonti: `Reference Manual` v3.0 (1993), `Tutorial Manual` v3.0, `README.DOC`
della release 3.0, help in linea `A4HELP.HLP`.

---

## 1. Limiti e capacità

| Elemento | Limite |
|---|---|
| Campi per record | 128 |
| Caratteri per record | 4.000 (esclusi memo) |
| Record per database | ~2 miliardi |
| Character | 254 caratteri |
| Numeric | 19 caratteri totali, 14 decimali (il README 3.0 corregge a 15) |
| Date | 8 caratteri, 01/01/0000 – 12/31/9999 |
| Logical | 1 carattere (`T/t/Y/y`, `F/f/N/n`, blank) |
| Memo | puntatore 10, contenuto 5.000 caratteri, blocchi da 512 in `.DBT` |
| Indici attached | 15 per database |
| Chiave indice | 100 caratteri |
| Range | 26 (A–Z) + `Default Range` + `Current Range` |
| Form | 26 (A–Z), fino a 25 schermate da 22 righe |
| Browse table | 26 (A–Z) |
| Report | 26 (A–Z), 40–240 colonne, 9 livelli di gruppo, 128 calcolati |
| Mail label | 26 (A–Z), 6 per riga, larghezza 10–78, altezza 1–20 |
| Lettere | nomi liberi 8.3, markup `[.IF]` |
| Campi calcolati per layout | 128 |
| Search/Sort | 26 salvate + 10 one-time (36 file), history 10 |
| Global update | 20 campi per definizione, 26 definizioni salvate |
| Crosstab | 26 definizioni salvate |
| Desktop | 10 database per desktop, desktop illimitati |
| Zoom annidati | 5 livelli |
| Database per set | 10 |
| Link 1:N per livello | 1 |
| Livelli Call-App | 10 |
| Script per directory | 400 |
| Caratteri per script | 3.000 |
| Caratteri per comando | 1.000 |
| Annidamento script | 10 |
| Variabili di script | illimitate, nome 24, valore 254 |
| Espressione | 254 caratteri (search/sort 512) |
| Filtro (indice/range/set) | 254 caratteri |
| Macro di applicazione | 3.000 caratteri |
| Driver stampante | 26 (A–Z) |
| Impostazioni import salvate | 26 (A–Z) |
| Applicazioni annidate | 10 |

---

## 2. Tipi di campo e conversioni

Creazione: `Fieldname` (10 char, inizia con lettera, A–Z 0–9 `_`, convertito in
maiuscolo), `Field Type` (`C`, `N`, `D`, `L`, `M`), `Field Length`,
`Decimal Place`.

Conversioni alla riconfigurazione:

| Da → A | Esito |
|---|---|
| Character → Date | corretto solo con `MM/DD/YY`, `MM/DD/YYYY`, `MM-DD-YY`, `MM-DD-YYYY` |
| Character → Logical | conservato se il primo carattere è `T t F f Y y N n` |
| Character → Numeric | fino al primo carattere non numerico; blank → 0; valuta e separatori persi |
| Numeric → Character | conservato |
| Numeric → Date / Logical | perso / `0`→`.F.`, `>0`→`.T.`, `<0` perso |
| Date → Character | `YYYYMMDD` |
| Date → Logical / Numeric | perso |
| Logical → Character | conservato |
| Logical → Date / Numeric | perso |

Effetti sui supporting files: rinomina campo → aggiornati; eliminazione campo
→ riferimenti rimossi, indici invalidati e auto-detached; cambio larghezza →
layout **non** aggiornati; cambio tipo → come eliminazione; aggiunta campo →
nessun effetto. Un calcolato non valido è marcato `?`.

---

## 3. Funzioni (elenco completo)

Tipi argomento: numeric, character, memo, date, logical. Data letterale
`{11/25/91}`.

### Carattere
`*ANY(c1,c2)` c2 ovunque in c1 · `*FIRST(c1,c2)` c2 all'inizio · `*LEADING(c1,c2)`
c2 inizio di parola · `*WORD(c1,c2)` c2 parola intera · `ASC(c)` · `AT(c1,c2)`
posizione · `CHR(n)` · `DIFFERENCE(c1,c2)` soundex 0–4 · `F_UPPER(c)` ·
`ISALPHA(c)` · `ISLOWER(c)` · `ISUPPER(c)` · `LEFT(c,n)` · `LEN(c)` ·
`LIKE(c1,c2)` wildcard `*` `?` · `LOWER(c)` · `LTRIM(c)` · `OCCURS(c1,c2)` ·
`REMSPECIAL(c)` · `REPLICATE(c,n)` · `RIGHT(c,n)` · `RTRIM(c)` ·
`SOUNDEX(c)` · `SPACE(n)` · `STUFF(c1,n1,n2,c2)` · `SUBSTR(c,n1,n2)` ·
`TRIM(c)` · `UPPER(c)` · `VAL(c)` · `WORD(c,n)` n negativo = da destra ·
`W_COUNT(c)` · `W_UPPER(c)` · `AT`, `LEN`, `CHR`, `ASC` come sopra ·
`ZBLANK(n)` numero → 10 char, `""` se zero.

### Numeriche e trigonometriche
`ABS(n)` · `ACOS(n)` · `ASIN(n)` · `ATAN(n)` · `ATAN2(n1,n2)` · `CEILING(n)` ·
`COS(n)` · `DTOR(n)` · `EXP(n)` · `FLOOR(n)` · `FV(n1,n2,n3)` · `INT(n)` ·
`LOG(n)` · `MAX(n1,n2)` · `MIN(n1,n2)` · `MOD(n1,n2)` · `PAYMENT(n1,n2,n3)` ·
`PI()` · `PV(n1,n2,n3)` · `RAND()` · `ROUND(n1,n2)` · `RTOD(n)` · `SIGN(n)` ·
`SIN(n)` · `SQRT(n)` · `STR(n1[,n2],n3)` · `TAN(n)` · `TRANSFORM(e,c)`.

### Date e tempo
`ADDMMONTHS` → `ADDMONTHS(d,n)` · `ADDYEARS(d,n)` · `CDATE(d)` `YYYYMMDD` ·
`CDOW(d)` · `CMONTH(d)` · `CTOD(c)` · `CYEAR(d)` · `DATE()` · `DAY(d)` ·
`DMY(d)` · `DOW(d)` 1=domenica · `DTOC(d)` · `DTOS(d)` · `MDY(d)` ·
`MONTH(d)` · `TOSECONDS(c)` · `TOTIME(n[,n2,n3])` · `YEAR(d)` · `TIME()`.

### Logiche e di stato
`BOF()` · `CCVALID(c)` · `CHKDIGIT(c)` · `DELETED([db])` · `EOF()` ·
`IF(lexp,e1,e2)` · `IIF(lexp,e1,e2)` · `ISBLANK(f)` · `KEY_EXIST(idx,key)` ·
`RECCOUNT()` · `RECNO()` · `RECSIZE()`.

### Database esterni e precedenti
`DBAVG(db,idx,key,fld)` · `DBCOUNT(db,idx,key)` · `DBF()` ·
`DBMAX(db,idx,key,fld)` · `DBMIN(db,idx,key,fld)` · `DBSUM(db,idx,key,fld)` ·
`FIELD(n[,db])` · `PREVIOUS(f)` · `XLOOKUP(db,idx,key,fld)` ·
`XLOOKUPC(db,idx,key,fld)` · `XLOOKUPR(db,n,fld)`.

### Operatori
Aritmetici `+ - * / ** ( )`; precedenza parentesi → `**` → `* /` → `+ -`,
associatività sinistra. Carattere: `+` concatena (con blank), `-` concatena con
trim, `$` substring. Data: `+`/`-` giorni, data − data = giorni. Relazionali:
`< <= > >= = <> ==`. Logici: `.AND. .OR. .NOT.`.

---

## 4. Comandi di script

Convenzioni: `#` numero, `$` stringa, `%` variabile; blocchi `{ ... }`;
commento `{*testo*}`; label `:A`–`:Z` (max 26).

| Comando | Effetto |
|---|---|
| `{ABORT}` | ferma tutti gli script, torna al main menu / menu applicazione |
| `{ALLOWKEYS $keys,{*else}}` | limita i tasti consentiti (`""` = tutti) |
| `{BEEP}` | beep |
| `{CANCEL}` | ferma lo script corrente (child → parent) |
| `{CASE e1,{...}[,e2,{...}]}` | massimo 15 rami, primo TRUE vince |
| `{CLEAR "%pattern"}` | cancella variabili (wildcard) |
| `{DEBUGOFF}` / `{DEBUGON}` | debugger off/on (F4 screen, F5 go, F10 step) |
| `{ENDAPP}` | termina script e applicazione corrente |
| `{EXEC $prog,#paramdb,#minmem}` | programma esterno senza pulire lo schermo |
| `{EXECCLR $prog,#paramdb,#minmem}` | pulisce lo schermo (palette VGA) ed esegue |
| `{GOTO :label}` | salto |
| `{IF e,{...}[,{...}]}` | due rami |
| `{LOOP :label,%var}` | ripete N volte |
| `{MAINMENU}` | all'applicazione → main menu |
| `{MOUSEDCLICK #r,#c}` `{MOUSEDOWN}` `{MOUSEMOVE}` `{MOUSEUP}` | eventi mouse sintetici |
| `{NOCLEAR}` | non cancella il dialog box chiamante |
| `{ONERROR {*...}}` | gestione errori |
| `{ONESCAPE {*...}}` | azioni dopo ESC |
| `{ONKEY $key,{*...}}` | massimo 64 mappature di tasti |
| `{ONMAIN {*...}}` | comandi al ritorno al main menu |
| `{PAUSE}` | attende ENTER |
| `{PLAY "script"}` / `{PLAY %var}` | esegue script figlio |
| `{PROMPT "testo",%var,#len}` | prompt rapido |
| `{READ %var,#r,#c,#len}` | legge caratteri dallo schermo |
| `{RPL #code,$parm,%result,%error}` | routine RPL residente |
| `{SCREENFREEZE}` `{SCREENOFF}` `{SCREENON}` | congelamento/cortina/ripristino |
| `{SET %var,$expr}` | assegna variabile |
| `{SHOW "dialog"}` | mostra dialog box senza eseguirne i controlli |
| `{TONE #freq,#centesimi}` | tono (100–300 Hz) |
| `{TRIGKEYS keystrokes}` | tasti differiti nei trigger |
| `{VRESTORE "$file"}` / `{VSAVE "%pattern",$file}` | variabili da/su file `.VAR` |
| `{WAITFOR #sec}` · `{WAITKEY key}` · `{WAITSCRN #r,#c,$str}` · `{WAITUNTIL $ora}` | attese |
| `{WRITE #r,#c,$str}` | scrittura sullo schermo |
| `{XLOOKUP db,idx,key,%st}` · `{XLOOKUPC ...}` · `{XLOOKUPR db,#rec,%st}` | lookup esterni, creano `%db_campo` |

Errori XLOOKUP: `215` database, `216` indice, `217` indice non attached,
`218` chiave assente, `207` lettura record.

Parameter database (creato da `EXEC`/`EXECCLR`): `TYPE C40`, `DATA1–3 C254`;
`TYPE` = `PATH`, `DBF`, `RECORD`, `NDX`, `PRIMARY NDX`, `PRIMARY KEY`,
`VARIABLE`.

---

## 5. Variabili di sistema

`%SYS_CTRLF1`…`%SYS_CTRLF10` · `%SYS_CURSOR_ROW` (1–25) · `%SYS_CURSOR_COL`
(1–80) · `%SYS_FIELD_NAME` · `%SYS_FORM` · `%SYS_ID_BROWSE` · `%SYS_ID_VIEW` ·
`%SYS_LAST_BUTTON` · `%SYS_LAST_KEY` · `%SYS_REGION_NAME` · `%SYS_SAVE_MODE`
(C/E) · `%SYS_SCRIPT_PATH` · `%SYS_SEARCH_COUNT` · `%SYS_SEARCH_OLD` (Y/N) ·
`%SYS_TOOLS` · `%SYS_VIEW_MODE` (V/B) · `%SYS_XFILE` · `%SYS_XVAR` ·
`%SYS_APP_PATH` · `%SYS_APP_DESKTOP` · `%SYS_DB_DRIVE` · `%SYS_DB_PATH` ·
`%SYS_FIELD_VALUE` · `%SYS_TRIG_*`.

Variabili di registro colore per form: `SYSTEM->PROMPT_CLR`, `DATA_CLR`,
`ERROR_CLR`, `HELP_CLR`, `HEADER_CLR`, `FOOTER_CLR`, `BAR_CLR`,
`BORDER_CLR`.

---

## 6. Trigger

Si attivano assegnando `{SET %SYS_TRIG_<EVENT>, "SCRIPT"}`, si disattivano con
`""`. Valide solo dopo l'esecuzione dello script che le imposta.

| Evento | Quando |
|---|---|
| New record is entered | `E` in View/Browse |
| Existing record is changed | `C` in View/Browse |
| Record is deleted | `ALT-D` / `OD` in View/Browse |
| Record is undeleted | `ALT-U` / `OU` in View/Browse |
| Record is saved | `F10` in Enter/Change |
| Region is entered / exited | ingresso/uscita regione in View |
| Field is entered | ingresso campo in Enter/Change |
| Field is validated | uscita campo, **prima** delle field rules |
| Field is exited | uscita campo, **dopo** le field rules |
| Letter is started / printed / finished | stampa lettera: inizio / per record / fine |
| Search/sort is started / performed / successful / finished | ricerca: inizio / per record / per match / fine |
| Update is started / performed / finished | global update: inizio / per record / fine |
| Zoom is performed | zoom in View/Browse |
| UnZoom is performed | un-zoom |

Nota: i nomi esatti di alcune variabili erano illeggibili nell'OCR del
manuale; vanno verificati su `A4HELP.HLP` e fissati in O10.

---

## 7. Field rules

`database.RLN`. Pagine della schermata: 1) `Value`
(`User-entered`/`Calculated`/`Summary`), `Expression`, `Case Convert`
(`None`/`Caps`/`Lower`/`First`/`Word`/`X`), `Template`, `Mask`,
`Allow Exceptions`, `Default Mode` (`None`/`Value`/`Expression`), `Increment`
(`None`/`Records`/`Updates`), `Auto-advance`, `Prompt`; 2) `Required`
(`No`/`Yes`/`Expression`), `Validation Expn`, `Validation Msg`,
`Double Entry`, `Skip Expression`, `Post data`; 3) `Lookup`,
`Lookup Validation` (`None`/`Exists`/`Doesn't Exist`), `Allow Exceptions`,
`Location` 1–9 o `Hidden`, `Rows in Window` 1–15, `Auto Pop-up`,
`Lookup Source` (`Table`/`Database`/`Advanced`).

- `Template`: caratteri fissi, cursore li salta, non cancellabili.
- `Mask`: `9` cifra, `A` maiuscola, `a` lettera, spazio = qualsiasi.
- `Increment`: `Records` = +1 sull'ultimo record fisico; `Updates` = +1 a ogni
  salvataggio; character incrementa 0–9, A–Z rispettando il template.
- `Calculated`: espressione ≤254, stesso tipo del campo; unica altra regola
  ammessa = `Post data`.
- `Summary`: solo set level, solo database primario.
- Posting rules: `Database name`, `Field to post to`, `Mode`
  (`Add`/`Subtract`/`Replace`), `Condition`, `Expression`.
- Lookup table: prima colonna = campo di lookup, fino a 6 colonne, 255 righe.
- Lookup mapping: `Choice Field`, `Filled Field`, `Condition`, `Expression`;
  fall-through `.T.` obbligatorio.
- Cascading table: outline con `TAB`/`SHIFT-TAB`, endpoint → lookup table,
  `~` separa visualizzato e valore.
- Conditional database: struttura identica per tutti i database.

---

## 8. Set

- `Set Definition`: `Set Description` (40), `Primary Database`, `Show Mode`,
  `Filter`, `Filter Mode` (default `Inactive`). Il filtro del set è valutato
  **prima** del filtro del range.
- `Set Editor`: `F6` add link, `F5` detach, `F7` integrity rule, `F9` switch,
  `F10` save.
- Link: `Linked Database/Set`, `Linking Index`, `Common Field/Expression`,
  `Link to?` (`All`/`First`/`Last`/`Closest`), `Can edit child database?`,
  `Can add new records to child database?` (`Yes`/`No`/`Prompt`),
  `Referential Integrity?`, `Cascading Updates?`, `Cascading Deletes?`.
- `Closest`: se manca il match esatto prende il primo figlio con chiave
  **successiva** nell'indice.
- Link Parameters: `Include Parent If?` (`Always`/`Has Related Child`/
  `Has No Related Child`), `Show Mode`, `Filter`, `Filter Mode`,
  `Zoom Form`, `Zoom Browse`.
- Regioni: `Border style`, colori (inactive/active/background/data), drop
  shadow, `Show Field Titles`, `Titles Frame`, `Use field names as titles`,
  `Show Record Number Column`, `Show Vertical Grid Lines`, `Display Region`,
  `Maximum Number of Records` (default 100), `Filter Expression`.
- Summary di form: richiede regione (anche nascosta); non collocare un summary
  dentro la regione che sommarizza.

---

## 9. Report

Parametri (p. 1): `Report description`, `Report width` 40–240, `Number of
grouping levels` 0–9, `Print Titles` solo pagina 1, `Print Page Footer only
on odd pages`, `Print Summary section on separate page`,
`Suppress blank lines`, `Blank line after how many records` 0–100,
`Page breaks`, `Widow record count`, `Orphan record count`,
`Split lines count`, `Max records per page`, `Reset page number after a
group`, `Re-print group header after a page break`.
Parametri (p. 2): `Left margin`, `Top margin`, `Standard page length`,
`Page length`.

Grouping Parameters: break field, `Re-print Titles at Group Break`,
`Start Group Header on New Page`, `Substitute Group Header for Page Header`,
`Start Group Footer on New Page`, `Substitute Group Footer for Page Footer`,
`Case-sensitive Test for Group Break`.

Summary: `Summary Type` (`First`, `Last`, `Count`, `Biggest`, `Smallest`,
`Total`, `Average`), `Summary Level` (`Grand`, `Page`, `Group n`), `Ignore`
(`None`, `Empty`, `Zero`, `Both`), `Summary Mode` (`Running`,
`Pre-processed`).

Campi di sistema: `SYSTEM->DATE`, `TIME`, `PAGENUMBER`, `REC_NUMBER`,
`CNTR_GRAND`, `CNTR_PAGE`, `CNTR_GRPn`; `SUMMARY->`, `CALC->`.

Codici: carattere `N C L F W X Y Z -`; memo `X @ !`; numerici `$ , X X$`
con sub-formati `*-B C F L W Y Z`; date 1–10 con sub-formati `C L F W Y Z`.

---

## 10. Tasti

| Tasto | Funzione |
|---|---|
| `F1` | help contestuale |
| `F2` | contestuale: Options, Fields, Fieldnames, Fids, Database Directory, Operators, Change Primary Index, Menu items |
| `F3` | contestuale: Status, Key Values, Func, Choices, Commands, Sections, Learn macro, Search/Sort History, Draw |
| `F4` | Pre-defined Sizes, Reorder, Sort order, Block, Append learn, Move |
| `F5` | Create Db, Delete, Refresh search/sort, Sort, Point |
| `F6` | Insert, Add Link, Screen, Position, Add region, Mark screen area |
| `F7` | Retrieve, Integrity rule, Cascading table, Conditionals, Goto, Size |
| `F8` | Detail On, Draw, Simulate, Variables, Box |
| `F9` | DOS, Define Rule/Switch Window, Line, Switch windows, Options |
| `F10` | Continue/Save/Print |
| `ALT-F10` | main menu |
| `ALT-F3` / `ALT-F4` | Script menu / Play script |
| `ALT-F5` / `ALT-F6` | copia / incolla clipboard |
| `ALT-M` | memo editor |
| `ALT-D` / `ALT-U` | delete / undelete record (e data odierna in campo data) |
| `ALT-O` | Formatting Options |
| `ALT-F` | campo precedente / select Field |
| `ALT-A` / `ALT-I` / `ALT-S` | add line / insert menu item / save |
| `ALT-E` | esci dai Range Settings senza Save box |
| `CTRL-HOME` / `CTRL-END` | primo/ultimo record; angoli nel layout |
| `CTRL-LEFT` / `CTRL-RIGHT` | primo/ultimo campo; ±8 colonne nel layout |
| `CTRL-BACKSPACE` | riga vuota non sopprimibile / svuota campo |
| `CTRL-F1..F10` | script `CTRLF1`..`CTRLF10` |
| `TAB` / `SHIFT-TAB` | +10/−10 record; schermate campi; regioni |
| `INSERT` | insert/overstrike |
| `ESC` / tasto destro | annulla, Forget, indietro |
| `SPACE` | Print next / single step |

Hot key dei comandi: `V` View, `E` Enter, `B` Browse, `C` Change, `L` Locate,
`R` Range, `W` sWitch, `M` MainMenu, `D` Database/set design,
`O` Open a database, `S` Screen, `P` permit.

---

## 11. Estensioni di file

| Estensione | Contenuto |
|---|---|
| `.DBF` | database |
| `.DBT` | memo |
| `.NDX` | indice |
| `.SET` | set |
| `.RLC` | composite rules (set + campi) |
| `.APP` | applicazione |
| `.AS4` | banner screen / custom screen |
| `.INx` | form (x = A–Z) |
| `.BNx` | browse table |
| `.RNx` | report |
| `.LNx` | mail label |
| `.LTR` | lettera |
| `.RLN` | field rules |
| `.GNx` | range |
| `.SNx` | criteri search/sort salvati |
| `.UNx` | global update salvato |
| `.XNx` | crosstab salvata |
| `.IDN` | definizione indici attached |
| `.UDN` | user definition (colori, form, browse) |
| `.SCP` | script |
| `.VAR` | variabili `VSAVE` |
| `.DTN` | desktop |
| `.SLx`, `.SL0`–`.SL9` | search/sort list, una-time list |
| `.$A4` | snapshot di swap |
| `A4.DFL` | configurazione |
| `A4.PNx` | driver stampante |
| `.PS` | PostScript |
| `.HPL` | output di stampa a video |
| `A4.PAL` | palette |
| `A4.ICX/IFX/ILX/ISX/ITX/IWPX` | impostazioni import |
| `A4V3.NET` | conteggio utenti (fuori scope) |

---

## 12. Menu principale

`View/enter records` · `Print` · `Search/sort lists` · `Indexes/ranges` ·
`Global update/delete` · `Choose database/set` · `Database/set design` ·
`Layouts` · `Applications` · `Utilities` · `Other` · `Quit`.

Sottomenu principali:

- `Choose database/set`: `Open a database`, `Close a database`,
  `sWitch databases`, `Save current desktop`, `Retrieve a desktop`,
  `Erase a desktop`, `clear desktop`.
- `Database/set design`: `Create a new database`, `Field rules`,
  `Reconfigure database`, `Erase a database or set`, `change Name, description
  or password`, `Duplicate a database or set`, `Set commands`.
- `Layouts`: `Forms`, `Browse tables`, `Reports`, `Mail labels`, `Letters`.
- `Utilities`: `Copy database`, `Append database`, `Summarize database`,
  `Pack database`, `Zap`, `Cross Tabulation`, `Relational commands`.
- `Other`: `Information` (`Status`, `Database/set structure`, `Field
  statistics`), `Configuration` (`Printer configuration`, `Set screen colors`,
  `Default settings`, `Network configuration`, `Telephone dialer setup`).

---

## 13. Dataset di accettazione (dal Tutorial)

Database: `AVMOVIES`, `AVPATRON`, `AVSALES`, `AVSALES2`, `AVHEADER`,
`AVITEMS`, `MOVTUT1`.

- `AVMOVIES`: `TAPE_ID C4`, `TAPE_TITLE C40`, `TAPE_DESC M10`,
  `SUBJECT C30`, `RUNTIME N3`, `RATING C5`, `TAPETYPE C5`, `AVAILABLE L1`,
  `LASTRENTED D8`, `RENTPRICE N5.2`, `SALEPRICE N5.2`, `ON_HAND N3`.
- `AVPATRON`: `CUST_ID`, `SALUTATION C3`, `FIRSTNAME C15`, `LASTNAME C15`,
  `ADDRESS1 C20`, `ADDRESS2 C20`, `CITY C15`, `STATE C2`, `ZIP C5`,
  `HOMEPHONE C14`, `CATEGORY`, `FREERENTAL`, `ACTIVE L`, `EXPIRATION`.
- `AVSALES`: `INV_NUMBER C4`, `INV_DATE D8`, `INV_TYPE C7`, `CUST_ID C4`,
  anagrafica cliente, `TAPE_ID C4`, `TAPETITLE C40`, `ITEMPRICE`,
  `QUANTITY`, `SUBTOTAL`, `TAXRATE`, `INVTOTAL`.
- `AVHEADER` = `AVSALES` senza `TAPE_ID`/`QUANTITY`/`SUBTOTAL`/`INVTOTAL`.
- `AVITEMS`: `INV_NO`, `TAPE_ID`, `QUANTITY`, `RETURNED N3`.

Indici: `AVMOVSUB`, `AVMOVTLE`, `AVMSUBTI`, `AVMOVID`, `AVPATID`, `AVPATLAS`,
`AVSALDAT`, `AVINVNO`.

Set: `AVIDEO` (AVSALES2 + AVPATRON + AVMOVIES), `AVIDE02` (AVHEADER + AVITEMS
+ AVPATRON + AVMOVIES).

Oggetti: form `A` (`Alpha Video Movies`, `Alpha Video Invoice`), browse `A`,
report `Alpha Video Invoice Report 1/2`, label `A`, lettera `POPORNOT`,
range `Movies Rated G, NR, or PG`, update `A`, search `A`/`B`, applicazione
`AVSYSTEM`, script `OPENDBS`, `AUTOEXEC`, `CANCEL`, `GETDATES`, `REVIEWAC`,
`RENGOLD`, `RENSILVR`, `RENPLATN`, `RENEWMEM`.

Questo dataset è la fixture canonica di `tests/tutorial/`.

# Utility e I/O (O9)

Riferimenti: Reference Manual, capitoli 19 (`Utilities`), 20
(`Utilities: Import/Export`) e 21 (`Utilities: Relational Commands`), più il
capitolo 7 per `Global update/delete`, che chiude i comandi rimasti stub
delle ondate precedenti.

L'ondata copre tre famiglie:

1. utility sui record: copy, append, summarize, cross tabulation, post,
   join, intersect, subtract, global update/delete;
2. import/export: dBASE II/III/IV, ASCII carattere-separato (e CSV), ASCII
   tabellare, DIF, SYLK, Lotus WKS/WK1, WordPerfect merge e MultiMate;
3. le schermate che espongono queste operazioni dal menu `Utilities` e dal
   menu `Global update/delete`.

## 1. Modello

Le utility lavorano sullo strato record esistente (PLAN §3.3), non su file
proprietari. Un'operazione che crea un database usa
`Workspace.create_database`, quindi produce subito un `.DBF` interoperabile,
una tabella SQLite e il contatore di revisione. Gli indici non sono copiati:
le chiavi del nuovo database possono non essere valide.

```python
UtilityResult(operation, output, read, written, updated, replaced,
              skipped, unmatched, marked)
```

`UtilityResult.message()` produce il conteggio mostrato nella status line
(«Copy: 3 record(s) written; new database COPY1.»).

Il range attivo (`RangeSettings`) decide quali record leggere. Le schermate
mostrano il range e `F7` apre il Range Settings con `temporary=True`; il
range scelto vale per l'operazione, non viene salvato come range del
database.

## 2. Copy database

`copy_database(database, CopyOptions)`:

- `fields=None` copia tutti i campi. Su un set copia i soli campi del
  database primario, come da manuale.
- `fields=[CopyField(db, field), ...]` copia i campi scelti; su un set
  accetta campi dei database collegati uno-a-uno. I campi uno-a-molti non
  hanno un valore unico e restano vuoti (deviazione dichiarata).
- i nomi duplicati o troppo lunghi vengono normalizzati con `_unique_name`
  (A-Z, 0-9, `_`, massimo 10 caratteri).
- `inherit_support=True` copia regole di campo, form, report, etichette,
  lettere, range e search/sort salvati. Non copia gli indici, come avverte
  il manuale.
- la descrizione è memorizzata in `adbx_databases.description` (colonna
  aggiunta con migrazione automatica).

L'ordine dei record è quello del primary index attivo: copiare in ordine di
indice produce un file fisicamente ordinato, equivalente al sort del DOS.

## 3. Append database

`append_database(target, source, AppendOptions)` con le quattro modalità del
manuale:

| Modalità | Comportamento |
|---|---|
| `All` | aggiunge tutti i record esterni che passano il filtro |
| `Unique` | aggiunge solo i record con chiave primaria assente nel master |
| `Replace existing, add unique` | sostituisce i record con la stessa chiave e aggiunge i nuovi |
| `Replace existing, mark unique` | come sopra, ma marca cancellati nel database esterno i record aggiunti |

Dettagli:

- `filter` è un'espressione valutata sui campi del database esterno.
- `mappings` mappa ogni campo del master su un campo del file esterno;
  `default_mappings` accoppia i nomi uguali e lascia vuoti gli altri.
- la chiave si calcola sui valori che il record avrà nel master; i campi non
  mappati sono vuoti.
- `Unique` e le due modalità `Replace` richiedono un indice reale come
  primary del master. Record Number e Search/Sort list non hanno una chiave
  stabile e vengono rifiutati.
- gli indici del master sono calcolati al volo: non c'è un file indice da
  aggiornare.

## 4. Summarize database

`summarize(database, SummarizeOptions)` crea un record per ogni chiave
distinta del primary index. Le operazioni per campo sono:

`Group`, `Total`, `Count`, `Average`, `Biggest`, `Smallest`, `First`,
`Last`, `Null`.

- `Group`, `First`, `Last`, `Biggest`, `Smallest` mantengono tipo e
  lunghezza del campo di origine; `Null` lascia il campo vuoto.
- `Total` e `Average` richiedono un campo numerico e allargano il campo di
  due caratteri (fino a 19), conservando i decimali.
- `Count` produce un numerico senza decimali.
- se un totale non entra nella lunghezza calcolata, il valore diventa zero,
  come avverte il manuale.
- non si può raggruppare per Record Number o per una Search/Sort list.
- con un set, la schermata propone i campi del database primario; il
  raggruppamento usa il primary index del set. I campi dei figli non sono
  aggregati (deviazione dichiarata).

## 5. Cross Tabulation

`crosstab(database, CrosstabOptions)` incrocia un campo riga con un campo
colonna e riepiloga un terzo campo con:

`Count`, `Biggest`, `Smallest`, `Null`, `First`, `Last`, `Total`, `Average`.

- senza `columns` esplicite, le colonne sono i valori distinti del campo
  colonna, ordinati con la stessa chiave tipizzata degli indici;
- i nomi delle colonne sono normalizzati a 10 caratteri e resi unici;
- `create_names=True` crea un secondo database con `SHORT C10` e
  `FULL C60`, che conserva il valore completo di ogni colonna;
- `columns=[CrosstabColumn(name, expression), ...]` definisce colonne
  esplicite: l'espressione è un filtro valutato su ogni record, come il
  `F7 Columns` del manuale;
- la schermata espone le colonne esplicite con `F3`; ogni riga si scrive
  come `NAME | espressione`, `F5`/`F6` cancellano e inseriscono.

## 6. Post database

`post(master, transaction, PostOptions)` aggiorna il master con i movimenti:

- `common_expression` è l'espressione equivalente sui campi del database
  transazioni; se vuota usa l'espressione del primary index del master.
- `filter` limita i record di transazione, come il `Transaction Filter`.
- per ogni campo si sceglie `master`, `transaction`, `operation`
  (`Add`, `Subtract`, `Replace`) e una `condition` facoltativa.
- `Add`/`Subtract` richiedono campi numerici; `Replace` converte il valore
  nel tipo del campo master.
- se più record del master hanno la stessa chiave, vengono aggiornati tutti,
  come da manuale.
- `status_field` (logico) viene posto a TRUE dopo un post riuscito;
- `mark_unmatched=True` marca cancellati i record di transazione senza
  corrispondenza nel master.
- gli indici del database transazioni non vengono aggiornati subito, come
  nota il manuale: sono ricalcolati quando servono.

## 7. Join, Intersect, Subtract

`relational(primary, secondary, RelationalOptions)` usa l'indice del
database secondario e un'espressione comune valutata sul primario:

| Comando | Record del risultato |
|---|---|
| `Join` | una riga per ogni coppia; se il primario non ha corrispondenze, una riga con i campi secondari vuoti (left outer join) |
| `Intersect` | solo le righe con almeno una corrispondenza (inner join) |
| `Subtract` | solo i record del primario senza corrispondenze (anti-join) |

- i campi si scelgono separatamente dal primario e dal secondario; il totale
  non supera 128;
- un nome duplicato nel risultato viene rinominato (`CUST_ID2`, …);
- il confronto usa la stessa normalizzazione dell'indice secondario
  (maiuscole se l'indice non è case sensitive, padding dei campi
  carattere). Per espressioni con lunghezze diverse vale la nota del
  manuale: usare `TRIM(LASTNAME)+FIRSTNAME`;
- il range del primario limita i record processati.

## 8. Global update/delete

Chiude i comandi del capitolo 7:

- `Update a field`: fino a 20 coppie campo/espressione, valutate sul range
  attivo; i memo non si aggiornano; `F2` sceglie il campo, `F5`/`F6`
  cancellano e inseriscono una riga di definizione.
- `Change case`: `Upper case`, `Lower case`, `First character`, `Word`,
  `X Lower & First`, `Z Lower & Word`; solo campi carattere.
- `Delete range of records` e `Undelete range of records` applicano il range
  attivo. Per richiamare record cancellati il range deve avere `Show` =
  `All` o `Deleted`.
- `Delete duplicate records` resta quello di O3.

Le definizioni salvate di update (`A`–`Z`) non sono implementate: la
schermata esegue un update one-time (deviazione dichiarata).

## 9. Import/Export

`src/adbx/io/` contiene un registro (`FORMATS`) e un modulo per famiglia.
L'API comune è:

```python
table = read_table(path, "csv", ImportOptions(...))   # -> TableData
write_table(path, "dbase3", fields, records, ExportOptions(...))
import_into_workspace(workspace, "NAME", path, "csv", options, fields)
export_from_database(database, path, "csv", fields, options, settings)
```

`TableData` contiene campi proposti, righe grezze e note. `infer_fields`
propone `D`, `N`, `L` o `C` esaminando la colonna, con decimali e lunghezza
massimi; `coerce_table` converte nei tipi scelti.

| Formato | Chiave | Estensione | Import | Export |
|---|---|---|---|---|
| dBASE II | `dbase2` | `.DBF` | sì | sì |
| dBASE III/IV | `dbase3` | `.DBF` | sì | sì |
| ASCII separato | `delimited` | `.ASC` | sì | sì |
| CSV | `csv` | `.CSV` | sì | sì |
| ASCII tabellare | `table` | `.TXT` | sì | sì |
| VisiCalc/DIF | `dif` | `.DIF` | sì | sì |
| SYLK/Multiplan | `sylk` | `.SLK` | sì | sì |
| Lotus 1-2-3 | `lotus` | `.WK1` | WKS/WK1 | WK1 |
| WordPerfect merge | `wordperfect` | `.MRG` | sì | sì |
| MultiMate | `multimate` | `.DOC` | sì | sì |

Note di formato:

- **dBASE II**: intestazione di 10 byte, descrittori di 16 byte, massimo 32
  campi. Non ha il tipo Data: le date si esportano come carattere e, se
  tutte le righe sono date, l'import le riconosce come `D`.
- **ASCII separato/CSV**: separatore e virgoletta configurabili, nomi di
  campo, soppressione degli spazi finali, separatore finale, CR/LF.
  L'intestazione non viene virgolettata. Le date si esportano come
  `MM/DD/YYYY` (o `MM/DD/YY`/`YYYYMMDD`).
- **ASCII tabellare**: campi a larghezza fissa, spaziatura, intestazione,
  file sequenziale o a record di lunghezza fissa.
- **DIF**: blocchi `TABLE`, `VECTORS`, `TUPLES`, `BOT`, `EOD`; stringhe fra
  virgolette con raddoppio.
- **SYLK**: record `C;Y...;X...;K...`, stringhe fra virgolette, fine `E`.
- **Lotus**: record binari `(tipo, lunghezza, corpo)`; `LABEL`, `NUMBER`,
  `INTEGER`, `FORMULA` (risultato). Le date sono numeri seriali con formato
  data; l'esportazione usa WK1 (`BOF 0x0406`) e legge anche WKS
  (`0x0404`).
- **WordPerfect**: sezione `{FIELD NAMES}` facoltativa, campi separati da
  `{END FIELD}`, record da `{END RECORD}` e interruzione di pagina.
- **MultiMate**: documento secondario con una pagina per record e il simbolo
  di merge `»` come separatore di campo. Le codifiche binarie MultiMate non
  sono replicate.

Formati esclusi, coerentemente con i non-obiettivi del PLAN: DBMII,
`PFS:File`, Lotus 3/4 e formati grafici.

## 10. Schermate

Menu `Utilities` (hot key `C`, `A`, `S`, `P`, `Z`, `T`, `R`, `I`, `E`):

```
Copy database          Append to database     Summarize database
Pack database          Zap database           Cross Tabulation
Relational commands    Import data            Export data
```

Menu `Relational commands`: `Post database`, `Join database`,
`Intersect database`, `Subtract database`.

Menu `Global update/delete`: `Update a field`, `Change case`,
`Delete range of records`, `Undelete range of records`,
`Delete duplicate records`.

Tasti comuni delle schermate:

- `F1` aiuto, `F2` elenco campi/database, `F7` Range Settings;
- `F10` continua, `ESC` torna indietro o annulla;
- nelle liste di campi `ENTER` seleziona/deseleziona, `SPACE` cambia
  l'operazione;
- nel cross tab `F3` apre le colonne esplicite, `F5`/`F6` cancellano e
  inseriscono;
- nell'import `ENTER` modifica il campo selezionato, `SPACE` lo include o
  esclude.

## 11. Deviazioni dichiarate

- I formati proprietari non vengono letti o scritti; il workspace SQLite
  resta la verità e i `.DBF` l'unico formato Alpha Four interoperabile.
- `Inherit support files` copia regole, layout e range, non gli indici.
- Copy/summarize da set usano i campi del primario e dei link uno-a-uno; i
  campi uno-a-molti non producono un valore unico.
- Le definizioni di update salvate e le import settings `A4.I?x` non sono
  implementate; le impostazioni si reinseriscono nella schermata.
- Il formato MultiMate è un documento secondario testuale, non la codifica
  binaria originale.
- Non si stampa direttamente: export e PDF restano i canali di uscita.

## 12. Test

- `tests/test_utilities.py`: copy, quattro modalità di append, filtro e
  mapping, summarize (tutte le operazioni, limite del totale), crosstab
  automatico e a colonne esplicite, names database, post (Add/Replace,
  status, unmatched), join/intersect/subtract, collisioni di nome,
  global update/case/delete.
- `tests/test_io.py`: andata e ritorno per tutti e dieci i formati,
  inferenza dei tipi, opzioni ASCII, larghezze fisse, limiti dBASE II,
  struttura DIF/SYLK/WK1, sezione nomi WordPerfect, formato sconosciuto.
- `tests/test_utilities_ui.py`: menu, schermate copy/summarize/crosstab,
  append, join, post, global update/case/delete, import/export.

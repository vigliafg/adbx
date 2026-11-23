# O7 — Report engine

Un report è una definizione di stampa legata a un database o a un set: fino a
26 per proprietario (A–Z), larghezza 40–240 colonne, nove livelli di gruppo.
La definizione vive nel workspace SQLite (`adbx_reports`), non in file `.RPx`.

## 1. Parametri

`Layouts → Reports` offre creazione/modifica, `Borrow a report` ed erase.
Il designer ha due pagine di parametri:

| Parametro | Default | Note |
|---|---|---|
| Report description | — | etichetta nella lista |
| Report width | 80 | 40–240 colonne |
| Number of grouping levels | 0 | 0–9 |
| Print titles only on page 1 | No | |
| Print page footer only on odd pages | No | |
| Print summary on separate page | No | |
| Suppress blank lines | Yes | le righe vuote del layout spariscono |
| Blank line after how many records | 0 | 0–100 |
| Page breaks | Yes | No = una pagina continua |
| Widow record count | 0 | record minimi con il group header |
| Orphan record count | 0 | record minimi con il group footer |
| Split lines count | 0 | righe minime del detail sulla pagina |
| Max records per page | 0 | 0 = nessun limite |
| Reset page number after a group | No | |
| Re-print group header after break | No | |
| Left margin / Top margin | 0 | 0–40 |
| Standard page length | Yes | se No vale `Page length` |
| Page length | 66 | 10–99 righe |

`Blank line after N records` inserisce una riga vuota dopo ogni N record del
detail. Le righe vuote si possono forzare anche con il carattere non
sopprimibile `CHR(127)`, che non compare in stampa.

## 2. Gruppi

Ogni livello ha un break field (campo o campo calcolato), confrontato con il
record precedente; senza `Case-sensitive test` il confronto ignora maiuscole.
Le opzioni per livello sono:

- `Re-print titles at group break`
- `Start group header on new page`
- `Substitute group header for page header`
- `Start group footer on new page`
- `Substitute group footer for page footer`

Un record è assegnato ai gruppi per prefisso di chiavi: cambiando il livello 1
cambiano anche tutti i livelli interni. I report raggruppati vanno stampati con
un indice che ordina sulle stesse chiavi.

## 3. Sezioni e layout

Le sezioni, nell'ordine di stampa, sono: `Report Header`, `Page Header`,
`Titles`, `Group 1..9 Header`, `Detail`, `Group 9..1 Footer`, `Page Footer`,
`Summary`. Il `Report Header` sostituisce il `Page Header` a pagina 1.
`Titles` si può limitare a pagina 1 o ripetere dopo ogni group header.

Il layout è una griglia di righe e colonne per sezione. `F2` inserisce un
campo scegliendo database, campo e tipo (`Value`, `Unique` o un tipo summary);
`F4` apre calcolati e summary; `F3` aggiunge/rimuove sezioni; `F5` cancella;
`F6` aggiunge un livello di gruppo; `F7` va ai parametri; `F9` giustifica o
inserisce/cancella righe; `Alt-O` apre le opzioni di formattazione; `F10`
salva.

`Value` stampa ogni valore; `Unique` stampa solo quando il valore differisce
dal record precedente. I campi possono avere `length` (caratteri stampati),
`window` (larghezza della finestra), giustificazione, formato e decimali.

## 4. Campi calcolati e summary

Fino a 128 campi calcolati; il nome è di 10 caratteri, l'espressione può usare
campi del database/set, campi calcolati già definiti, summary e funzioni.
Sono accettate anche le grafie del manuale `CALC->NOME`, `SUMMARY->NOME` e
`DB->CAMPO`, normalizzate prima della valutazione.

I summary hanno quattro dimensioni:

- **Tipo**: `First`, `Last`, `Count`, `Biggest`, `Smallest`, `Total`,
  `Average`;
- **Livello**: `Grand`, `Page`, `Group n`;
- **Ignore**: `None`, `Empty`, `Zero`, `Both`;
- **Modo**: `Running` o `Pre-processed`.

`Running` aggiorna il valore mentre i record vengono stampati; in un titolo
prima del detail vale zero. `Pre-processed` calcola il valore finale prima
della stampa e può essere usato in un group header. Il motore ripete calcolo,
raggruppamento, summary e paginazione fino a quattro passate, così un calcolo
può usare un summary e un summary può aggregare un calcolo (percentuali sul
totale, margini, deviazione standard).

Campi di sistema: `SYSTEM->DATE`, `TIME`, `PAGENUMBER`, `REC_NUMBER`,
`CNTR_GRAND`, `CNTR_PAGE`, `CNTR_GRPn`.

## 5. Formattazione

| Tipo | Codici |
|---|---|
| Caratteri | `N` nessuno, `C` maiuscolo, `L` minuscolo, `F` prima lettera, `W` ogni parola, `X` word wrap, `Y` minuscolo con iniziale maiuscola, `Z` minuscolo con iniziali maiuscole, `-` sopprime la riga se il campo è vuoto |
| Memo | `X` word wrap, `@` tutto il memo ignorando `Length` |
| Numerici | `$` valuta e migliaia, `,` migliaia, `X` numero in lettere, `X$` numero in lettere con valuta; sottoformati `*` riempimento con asterischi, `B` vuoto se zero, `-` sopprime se vuoto, `C L F W Y Z` per le lettere |
| Date | formati 1–10 (americano, europeo, mese in lettere, ordinale, anno a 2 cifre) con sottoformati di capitalizzazione |

Esempi verificati: `1988.03` con `$*` diventa `***$1,988.03`; con `X$F`
diventa `One thousand nine hundred eighty eight and 03/100 Dollars`.
Il separatore date e il nome della valuta sono le impostazioni predefinite
(quelle modificabili in O12).

## 6. Impaginazione

Il motore compone le pagine rispettando `Page length`, margini, page
header/footer, titoli, group header/footer, summary e `Max records per page`.
`Page breaks = No` produce una sola pagina continua. La riga di detail troppo
lunga viene spezzata rispettando `Split lines count`; i group header tengono
con sé `Widow record count` record e i footer evitano di restare soli
(`Orphan record count`). Quando `Re-print group header after a page break` è
attivo, il group header corrente viene ridisegnato sulla nuova pagina.

`Substitute group header/footer` usa il group header/footer al posto del page
header/footer: il footer sostitutivo viene allineato al fondo della pagina e
il page footer viene omesso su quella pagina.

## 7. Anteprima e PDF

`F10 → Save and preview` salva e apre l'anteprima; da `Print → Report` si
sceglie un report già salvato. Nell'anteprima:

- `PgUp`/`PgDn` cambiano pagina;
- frecce e `Home` scorrono righe e colonne;
- `P` o `F10` scrive un PDF;
- `Esc` torna al menu.

Il PDF è testo monospaziato Courier, formato letter o landscape per i report
oltre 100 colonne, con margini e una pagina PDF per pagina di report. non
dipende da librerie esterne.

## 8. Check writing

Un assegno è un report con la sola sezione `Detail`, lunga quanto il modulo
(per esempio 22 righe), `Suppress blank lines = No`, `Page breaks = Yes`,
`Standard page length = No` e `Page length = 22`. L'importo compare due volte:
`$*` per la cifra numerica e `X$F` per l'importo in lettere. Ogni record
produce una pagina, come nei moduli pre-stampati.

## 9. Accettazione

`tests/test_reports.py` — persistenza e validazione, formati, report 1 e 2 del
Tutorial (righe, `Unique`, totali di gruppo), multipass con percentuale,
paginazione e contatori, righe non sopprimibili, check writing, PDF, report
da set con detail sui figli.

`tests/test_reports_ui.py` — creazione custom dai parametri al layout, picker
dei campi, gruppi e bandiere, salvataggio, anteprima e PDF, menu Print,
borrow/erase, calcolati, summary, sezioni, formatting.

Screenshot: `docs/render/25-report-designer.png`,
`26-report-preview.png`, `27-report-grouping.png`.

## 10. Deviazioni dichiarate

- I report sono nel workspace SQLite, non in file `.RPx`; non ci sono file
  `.SET` per range e stampa (arrivano con O12).
- Il separatore date è `/` e la valuta `Dollars`, non ancora configurabili.
- `Borrow` copia un report dello stesso proprietario; il manuale permette di
  prenderlo da qualsiasi database o set della directory.
- L'orphan control sposta il footer su una nuova pagina ma non ridisegna i
  record già stampati; con sezioni di altezza variabile il conteggio è
  approssimato, come avverte il manuale.
- `Substitute group footer` allinea il footer al fondo ma non gestisce form
  feed o codici stampante.
- Non ci sono ancora stampa diretta su stampante, driver, caratteri
  compressi o range salvati nel report; l'output è anteprima e PDF.

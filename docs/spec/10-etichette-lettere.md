# O8 — Etichette e lettere

Due layout di stampa che condividono i formati dei campi con O7 ma non le
sezioni: le etichette compongono una griglia, le lettere un testo con comandi.

## 1. Mail label

Fino a 26 layout per proprietario (A–Z), salvati in `adbx_labels`.

### Parametri

| Parametro | Limiti / default |
|---|---|
| Label description | etichetta nella lista |
| Label width | 10–78 colonne |
| Label height | 1–20 righe |
| Number of labels across | 1–6 |
| Columns between labels | 1–20 |
| Lines between labels | 0–15 |
| Number of copies | numero, campo o espressione |
| Left margin | 0–40 |
| Continuous feed | Yes/No |
| Rows of labels per page | 1–99 (se pagine) |
| Top margin | 0–20 |

`F4` nei parametri propone alcune misure predefinite (3-1/2 × 15/16 una o due
across, 4 × 1-7/16 tre across, 2-5/8 × 1 quattro across, formato envelope).

### Layout

La griglia rappresenta una singola etichetta; `F2` inserisce un campo (i memo
sono rifiutati), `F4` un calcolato, `F5` cancella, `F9` giustifica o gestisce
le righe, `Alt-O` apre la formattazione, `F10` salva. I campi hanno `length`,
giustificazione, formato e decimali; un campo non può superare il bordo destro.

### Giustificazioni

| Opzione | Effetto |
|---|---|
| `Suppress` | toglie gli spazi finali e sposta a sinistra ciò che segue (default) |
| `Left` / `Right` / `Center` | allinea nella larghezza del campo |
| `None` | stampa il valore così com'è |
| `Float` | si sposta a sinistra per la soppressione precedente, ma il testo seguente resta al suo posto |
| `Trim` | stampa nella posizione originale ignorando la soppressione precedente; sopprime i propri spazi finali |
| `Join` | si sposta a sinistra con la soppressione precedente e porta con sé il testo seguente |
| `Before` | se il campo è vuoto elimina il testo che lo precede |
| `After` | se il campo è vuoto elimina il testo che lo segue |

`Delete line if empty` elimina l'intera riga quando il campo è vuoto. Le righe
vuote sono soppresse automaticamente; `CHR(127)` (CTRL-BACKSPACE) le conserva.

### Stampa

Il motore raccoglie i record nell'ordine del range corrente, calcola le copie
per record (numero, campo o espressione) e compone righe di etichette separate
da `Columns between`. Con `Continuous feed = No` spezza le pagine ogni
`Rows of labels per page` righe e applica il `Top margin`; con Yes produce una
pagina continua. L'anteprima e il PDF usano lo stesso visualizzatore dei
report; `Print → Mail labels` stampa un layout salvato.

## 2. Form letter

Le lettere hanno nome libero di 1–8 caratteri (lettere, cifre, `_`) e sono
salvate in `adbx_letters`. Il corpo è testo con marcatori.

### Marcatori di campo

| Sintassi | Significato |
|---|---|
| `[FIELD]` | campo del database primario |
| `[DB->FIELD]` | campo di un database del set |
| `[SYSTEM->DATE]` | data odierna |
| `[{expression}]` | valore calcolato |
| `[?testo]` | valore chiesto a stampa |

Opzioni dopo il punto: `S` sopprime gli spazi finali (default), `L/R/C`
allineano, `N` lascia com'è, `D` cancella la riga se il campo è vuoto, `X`
numero in lettere, `$` valuta, `,` migliaia; `:lunghezza.decimali` imposta
larghezza e decimali (per esempio `[PRICE.R:10.2]`).

### Comandi

| Comando | Effetto |
|---|---|
| `[.WIDTH n]` | larghezza di riscrittura (10–254) |
| `[.LEFT n]` | margine sinistro |
| `[.TOP n]` / `[.BOTTOM n]` | margini verticali |
| `[.FILL+]` / `[.FILL-]` | attiva/disattiva la riscrittura |
| `[.EJECT]` | nuova pagina |
| `[.INCLUDE file]` | inserisce un file di testo (relativo alla directory) |
| `[@27 100]` | codici stampante, rimossi dall'output PDF |

I comandi devono stare su una riga propria. Con il fill attivo le righe di
solo testo vengono unite in paragrafi e riscritte alla larghezza corrente; le
righe che contengono campi restano righe separate (indirizzi). Con fill
disattivo si conservano le interruzioni del layout.

### Condizionali

```
[.IF espressione]
paragrafo vero
[.ELSEIF espressione2]
paragrafo alternativo
[.ELSE]
paragrafo falso
[.ENDIF]
```

Fino a cinque livelli annidati. Le espressioni usano il parser di O3/O4 e i
valori del record; un errore vale falso. Ogni record produce una lettera e una
nuova pagina; il testo viene paginato a 66 righe meno i margini.

### Editor

`Layouts → Letters` crea/modifica/cancella. Nell'editor: testo libero, `F2`
inserisce un campo (database → campo → formato), `F3` i comandi, `F7` i
condizionali, `F10` salva (Save, Save and preview, Continue, Save as). Il
salvataggio con preview apre il visualizzatore; `P`/`F10` scrive il PDF e
`Print → Letters` stampa una lettera salvata.

## 3. Accettazione

`tests/test_labels.py` — persistenza e validazione, lezione 17 (due etichette
across, soppressione indirizzo, righe non sopprimibili, messaggio), copie da
campo, giustificazioni avanzate (Suppress/Float/Trim/Join/Before/After),
paginazione.

`tests/test_letters.py` — persistenza, lezione 18 (attivi/inattivi, data,
indirizzo, conditional), ELSEIF, prompt, INCLUDE, WIDTH, FILL, EJECT, codici
stampante, numeri in lettere e campi calcolati.

`tests/test_output_ui.py` — creazione etichetta e lettera dal menu, picker,
formattazione, salvataggio, anteprima/PDF, Print → Mail labels/Letters,
borrow/erase.

Screenshot: `docs/render/28-label-designer.png`, `29-label-preview.png`,
`30-letter-editor.png`, `31-letter-preview.png`.

## 4. Deviazioni dichiarate

- Le etichette e le lettere vivono nel workspace SQLite, non in `.LNx`/`.LTR`.
- Non c'è il test pattern di allineamento delle etichette né la pausa per
  fogli singoli: l'output è anteprima/PDF.
- `Continuous feed` produce una sola pagina lunga; la stampante reale arriva
  con O12.
- I codici stampante `[@...]` sono riconosciuti e rimossi, non inviati.
- I prompt `[?testo]` usano la mappa fornita dal chiamante; l'editor non ha
  ancora il dialogo interattivo per ogni lettera.
- Le opzioni dei marker sono un sottoinsieme tollerante della sintassi
  manuale (`OPTION:LENGTH.DEC`), non un parser completo di tutti i codici.
- L'editor non implementa block copy/move e la clipboard delle lettere.

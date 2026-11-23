# adbx

Clone funzionale moderno di **Alpha Four versione 3** (Alpha Software, 1993):
un database relazionale senza programmazione, con regole di campo, set,
report, script e applicazioni.

adbx non emula il DOS: replica **il comportamento** di Alpha Four dentro una
finestra con una griglia di caratteri scalabile (132×43, font TrueType), su un motore SQLite,
su Linux, Windows e macOS.

- Licenza: MIT
- Stato: **O6 completata** — form designer a celle, form personalizzati, regioni, calcolati e summary
- Piano completo: [`PLAN.md`](PLAN.md)
- Diario di implementazione: [`DIARIO.md`](DIARIO.md)
- Inventario funzionale estratto dai manuali:
  [`docs/reference/00-inventario.md`](docs/reference/00-inventario.md)
- Manuali originali (documentazione proprietaria, solo consultazione):
  [`docs/reference/manuals/`](docs/reference/manuals/)
- Specifiche: motore a celle [`docs/spec/00-motore-celle.md`](docs/spec/00-motore-celle.md),
  scalabilità [`docs/spec/01-scalabilita.md`](docs/spec/01-scalabilita.md),
  shell [`docs/spec/02-shell.md`](docs/spec/02-shell.md),
  dati e immissione [`docs/spec/04-dati-immissione.md`](docs/spec/04-dati-immissione.md),
  ricerca e indici [`docs/spec/05-ricerca-indici.md`](docs/spec/05-ricerca-indici.md),
  regole di campo [`docs/spec/06-regole-campo.md`](docs/spec/06-regole-campo.md),
  set e regioni [`docs/spec/07-set.md`](docs/spec/07-set.md),
  form designer [`docs/spec/08-form.md`](docs/spec/08-form.md),
  ambiente DOS di riferimento
  [`docs/spec/03-ambiente-dos-riferimento.md`](docs/spec/03-ambiente-dos-riferimento.md)
- Schermate: [`docs/render/`](docs/render/)

## Perché una griglia di caratteri

Alpha Four è una matrice di celle: report a larghezza fissa, regioni
scorrevoli, designer a placeholder, script che «digitano» tasti e verificano
il contenuto dello schermo. Rendere questa interfaccia con widget moderni
cambierebbe il prodotto; renderla con celle la conserva e rende report,
script e designer molto più semplici e fedeli.

## Avvio

```bash
./start.sh                        # avvia senza attivare un ambiente (crea .venv se serve)
./start.sh --data ~/dati          # parte dalla cartella indicata
./start.sh --open ~/dati/AVMOVIES.DBF  # apre subito un database
python -m adbx --smoke            # avvio headless di verifica
pytest                            # suite completa
python tools/capture_ui.py        # rendering canonici
```

La shell parte dal **Database Directory**: si sceglie un `.DBF`/`.SET`, si
naviga con le frecce, si filtra con `*` e `?`, e con ENTER si arriva al main
menu. `F1` apre l'aiuto contestuale, `F2`/`F3` mostrano struttura e stato,
`ALT-F10` torna al menu, `Quit` chiude la sessione.

Con **O2** i database sono vivi: `F5` nel Database Directory crea un database
(il table designer definisce fino a 128 campi), `View/enter records` apre
View, Enter, Change e Browse, `ALT-M` apre il memo, `ALT-D`/`ALT-U`
cancellano e richiamano record, `Utilities → Pack` compatta. I dati stanno
in SQLite e vengono riscritti nel `.DBF` a ogni salvataggio.

Con **O3** si cerca e si ordina: `Indexes/ranges` crea indici anche a più
livelli, sceglie il primary index e salva fino a 26 range; `Search/sort lists`
costruisce liste one-time o salvate in Table/Expression mode, con storia e
marcatura `♦` quando sono out of date; in View/Browse `F` è Find, `L` è
Locate, `I` è l'indice, `R` il range, e in View `S` sostituisce un testo.
`Global update/delete → Delete duplicate records` usa l'indice primario.

Con **O4** il database diventa dichiarativo: `Database/set design → Field
rules` definisce valori calcolati, default, incrementi automatici, template e
maschere, campi obbligatori, validazioni con messaggio, doppia immissione,
skip, prompt, post data e lookup. Le lookup possono essere tabelle (fino a 6
colonne), database con mapping, cascate ad albero o liste condizionali;
`F3` apre le scelte durante l'immissione e riempie i campi collegati.
`Re-evaluate field rules` applica calcoli e maiuscole ai record esistenti.

Con **O5** più database diventano una sola vista: `Set commands` crea set con
fino a 10 database, link `First/Last/Closest/All`, indice di collegamento e
campo comune, integrità referenziale con cascading updates/deletes e
`Include Parent If`. `View/enter records` su un set combina primario e figli
uno-a-uno, mostra i figli uno-a-molti in una regione dedicata (F6) e permette
lo zoom sul figlio (`Alt-Z`). Enter/Change aggiornano il genitore e i figli
modificabili; il delete cascata sui figli collegati.

Con **O6** le schermate diventano disegnabili: `Layouts → Forms` crea fino a
26 form per database o set, su 10 pagine, con campi, testi, riquadri, regioni
1:N, campi calcolati e summary. `F2` inserisce un campo, `F8` un riquadro,
`F6` una regione, `F9` le opzioni di formattazione, `F7` i parametri
(descrizione, menu, restrict, stampa). Il form salvato diventa attivo e
View/Enter/Change lo usano, rispettando l'ordine dei campi e il formato memo
multilinea.

## Riferimenti

La specifica è la documentazione originale di Alpha Four 3.0 (`Reference
Manual`, 25 capitoli e 8 appendici; `Tutorial Manual`, 25 lezioni). Il
riassunto operativo, con limiti, funzioni, comandi di script, trigger, tasti
ed estensioni di file, è in `docs/reference/00-inventario.md`.

## Riferimento originale in DOSBox-X

L'originale si può avviare senza installare il DOS, per confrontare
comportamenti e schermate:

```bash
sudo apt-get install dosbox-x
tools/run_alpha4_dosbox.sh           # estrae da DRIVEC TERZA VERSIONE.zip e avvia
```

Verificato: DOSBox-X 2026.01.02, macchina `svga_s3`, 16 MB, `A4.EXE` arriva
al main menu con `AVMOVIES` (50 record). Dettagli e screenshot in
[`docs/spec/03-ambiente-dos-riferimento.md`](docs/spec/03-ambiente-dos-riferimento.md).
L'archivio DOS e i suoi file restano fuori dal repository.

## Licenza dei materiali di riferimento

Codice e documentazione prodotta sono MIT. I PDF in
`docs/reference/manuals/` sono manuali Alpha Software depositati **solo per
consultazione** e non sono coperti dalla licenza MIT. I file del programma
originale non sono inclusi.

Alpha Four è un marchio di Alpha Software Corporation. Questo progetto è una
reimplementazione indipendente, non affiliata né autorizzata; non contiene
codice o binari originali.

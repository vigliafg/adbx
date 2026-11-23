# adbx

Clone funzionale moderno di **Alpha Four versione 3** (Alpha Software, 1993):
un database relazionale senza programmazione, con regole di campo, set,
report, script e applicazioni.

adbx non emula il DOS: replica **il comportamento** di Alpha Four dentro una
finestra con una griglia di caratteri scalabile (132×43, font TrueType), su un motore SQLite,
su Linux, Windows e macOS.

- Licenza: MIT
- Stato: **O1 completata** — shell con Database Directory, main menu, aiuto contestuale
- Piano completo: [`PLAN.md`](PLAN.md)
- Diario di implementazione: [`DIARIO.md`](DIARIO.md)
- Inventario funzionale estratto dai manuali:
  [`docs/reference/00-inventario.md`](docs/reference/00-inventario.md)
- Specifiche: motore a celle [`docs/spec/00-motore-celle.md`](docs/spec/00-motore-celle.md),
  scalabilità [`docs/spec/01-scalabilita.md`](docs/spec/01-scalabilita.md),
  shell [`docs/spec/02-shell.md`](docs/spec/02-shell.md)
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

## Riferimenti

La specifica è la documentazione originale di Alpha Four 3.0 (`Reference
Manual`, 25 capitoli e 8 appendici; `Tutorial Manual`, 25 lezioni). Il
riassunto operativo, con limiti, funzioni, comandi di script, trigger, tasti
ed estensioni di file, è in `docs/reference/00-inventario.md`.

Alpha Four è un marchio di Alpha Software Corporation. Questo progetto è una
reimplementazione indipendente, non affiliata né autorizzata; non contiene
codice, binari o testi originali.

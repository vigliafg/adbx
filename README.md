# adbx

Clone funzionale moderno di **Alpha Four versione 3** (Alpha Software, 1993):
un database relazionale senza programmazione, con regole di campo, set,
report, script e applicazioni.

adbx non emula il DOS: replica **il comportamento** di Alpha Four dentro una
finestra con una griglia di caratteri 80×25 (font CP437), su un motore SQLite,
su Linux, Windows e macOS.

- Licenza: MIT
- Stato: pianificazione (O0 in avvio)
- Piano completo: [`PLAN.md`](PLAN.md)
- Diario di implementazione: [`DIARIO.md`](DIARIO.md)
- Inventario funzionale estratto dai manuali:
  [`docs/reference/00-inventario.md`](docs/reference/00-inventario.md)

## Perché una griglia di caratteri

Alpha Four è una matrice di celle: report a larghezza fissa, regioni
scorrevoli, designer a placeholder, script che «digitano» tasti e verificano
il contenuto dello schermo. Rendere questa interfaccia con widget moderni
cambierebbe il prodotto; renderla con celle la conserva e rende report,
script e designer molto più semplici e fedeli.

## Comandi previsti

```bash
./start.sh                # avvia l'app senza attivare un ambiente (crea .venv se serve)
python -m adbx            # avvia l'applicazione (con PyQt6 già disponibile)
python -m adbx --smoke    # avvio headless di verifica
pytest                    # suite completa
python tools/capture_ui.py  # rendering canonici
```

## Riferimenti

La specifica è la documentazione originale di Alpha Four 3.0 (`Reference
Manual`, 25 capitoli e 8 appendici; `Tutorial Manual`, 25 lezioni). Il
riassunto operativo, con limiti, funzioni, comandi di script, trigger, tasti
ed estensioni di file, è in `docs/reference/00-inventario.md`.

Alpha Four è un marchio di Alpha Software Corporation. Questo progetto è una
reimplementazione indipendente, non affiliata né autorizzata; non contiene
codice, binari o testi originali.

# Conferma visiva end-to-end

Immagini generate da `tools/e2e_visual.py`. Ogni scenario guida il
controller reale, verifica il testo atteso e salva il PNG.

```bash
python tools/e2e_visual.py
python tools/e2e_visual.py --dosbox   # richiede dosbox-automation
```

- `adbx/` — rendering della griglia 80×25 tramite il renderer Qt;
- `dosbox/` — Alpha Four 3.0 originale in dosbox-automation,
  catturato via REST API (`/api/v1/video/frame`);
- `manifest.json` — testo atteso, dimensioni, colori e SHA-256.

| Scenario | Atteso | Immagine | Dimensioni |
|---|---|---|---|
| 01-adbx-main-menu | `Alpha Four Main Menu` | ![01-adbx-main-menu](adbx/01-adbx-main-menu.png) | 800x475 |
| 02-adbx-view-records | `Ada` | ![02-adbx-view-records](adbx/02-adbx-view-records.png) | 800x475 |
| 03-adbx-browse | `CUST_ID` | ![03-adbx-browse](adbx/03-adbx-browse.png) | 800x475 |
| 04-adbx-script-editor | `Description:` | ![04-adbx-script-editor](adbx/04-adbx-script-editor.png) | 800x475 |
| 05-adbx-dialog | `Name:` | ![05-adbx-dialog](adbx/05-adbx-dialog.png) | 800x475 |
| 06-adbx-application | `E2E MAIN MENU` | ![06-adbx-application](adbx/06-adbx-application.png) | 800x475 |
| 07-adbx-report-preview | `Ada` | ![07-adbx-report-preview](adbx/07-adbx-report-preview.png) | 800x475 |
| 08-adbx-documentation | `Structure of AVPATRON` | ![08-adbx-documentation](adbx/08-adbx-documentation.png) | 800x475 |

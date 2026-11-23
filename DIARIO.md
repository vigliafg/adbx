# Diario di implementazione — adbx

Append-only: le voci precedenti non si riscrivono e non si cancellano.
Una voce per ondata; più voci solo per sotto-attività rilevanti.

Formato:

```
### AAAA-MM-GG — Ondata N — Titolo
- Stato: in corso | completata | bloccata
- Branch/commit: ...
- Obiettivo: ...
- File toccati: ...
- Scelte/deviazioni: ...
- Test: ...
- Screenshot: ...
- Problemi aperti: ...
- Prossimo passo: ...
```

---

### 2026-11-23 — Avvio progetto — Repository e piano
- Stato: completata
- Branch/commit: `main`; commit iniziale.
- Obiettivo: creare il repository pubblico `adbx` e depositare il piano di
  realizzazione di un clone funzionale di Alpha Four v3, dopo la lettura
  completa della documentazione originale.
- File toccati: `README.md`, `LICENSE`, `PLAN.md`, `DIARIO.md`,
  `docs/reference/00-inventario.md`, `pyproject.toml`, `src/adbx/__init__.py`,
  `.gitignore`.
- Scelte:
  - Licenza MIT, nome `adbx`.
  - Interfaccia a **finestra con griglia di celle** 80×25, font CP437 8×16
    incorporato; motore **SQLite** con strato di emulazione record-based;
    multipiattaforma.
  - Il piano è organizzato in 14 ondate (O0–O13) con criteri di accettazione
    legati ai capitoli del `Reference Manual` e alle lezioni del `Tutorial`.
  - Inventario funzionale consolidato in `docs/reference/00-inventario.md`
    (limiti, funzioni, comandi di script, trigger, tasti, estensioni), per non
    perdere contatto con le funzionalità durante l'implementazione.
  - Deviazioni dichiarate: niente runtime cifrato, installer DOS, multiuser,
    modem, swap EMS/XMS; `.NDX` in sola lettura; form fino a 25 schermate
    (README 3.0) contro le 10 del manuale stampato.
- Test: nessuno (solo struttura).
- Screenshot: nessuno.
- Problemi aperti: i nomi esatti di alcune variabili `%SYS_TRIG_*` sono
  illeggibili nell'OCR del manuale e vanno verificati sull'help in linea
  durante O10; mappatura dei colori di campo 0–255 da fissare in O0.
- Prossimo passo: O0 — motore a celle, font CP437, input, harness di
  rendering.

# Piano — `adbx-legacy`: ripristino dell'interfaccia originale 80×25

> **Stato:** **eseguito e completato** il 2026-11-24.
> **Data:** 2026-11-24.
> **Esito:** tutti i criteri della sezione 8 verificati; dettaglio delle fasi,
> verifiche visive e limiti accettati in `DIARIO-LEGACY.md` (step 1–8).
> **Obiettivo:** creare un worktree `adbx-legacy` autonomo, collegato allo
> stesso repository `adbx`, con la griglia logica originale **80×25** e font
> TrueType scalabile, lasciando `adbx` (132×43) completamente intatto.
>
> **Ripresa dopo compattazione del contesto:** leggere questo file e partire
> dalla sezione 2 (creazione del worktree). Non modificare `adbx`.

---

## 0. Decisioni fissate con l'utente

| Tema | Decisione |
|---|---|
| Posizione worktree | **Sorella**: `/home/vigliafg/Documenti/GitHub/adbx-legacy`, collegata allo stesso `.git` di `adbx` |
| Base di partenza | HEAD `fa845f2` **più** le 24 modifiche non committate presenti il 2026-11-24 |
| Font / zoom | Griglia **80×25** con font **DejaVu Sans Mono TrueType**, zoom 50–200%, fit alla finestra e F11 invariati |
| Identità | Package Python `adbx` invariato; titolo finestra `adbx — legacy (80×25)`; versione `1.0.0` |
| Portata | **Parità funzionale completa**: tutte le 25 lezioni del Tutorial e tutta la suite di test verdi |
| Vincolo assoluto | Il working tree di `adbx` non deve essere modificato, né con commit, né con stash, né con checkout |

### Baseline di `adbx` al momento della pianificazione

```
HEAD:            fa845f20b6d85aaa78e5b3afa31551b390bdc780
status hash:     137362589b27f9016409dc875f5a5278bbc7da6dfb15a2e1d43d7fe350a64ba7
                (sha256 di `git status --porcelain=v1`)
test:            451 funzioni di test, tutte verdi
modifiche non committate: 24 file, +805/−92
untracked:       tests/NEW1.DBF
```

---

## 1. Stato attuale del codice

- Griglia centralizzata in `src/adbx/cell/buffer.py`:
  - `SCREEN_WIDTH = 132`, `SCREEN_HEIGHT = 43`
  - `STATUS_ROW = 40`, `HELP_ROW = 41`, `MENU_ROW = 42`, `WORK_ROWS = 40`
- La maggior parte delle schermate usa già `SCREEN_WIDTH`, `SCREEN_HEIGHT` o
  `STATUS_ROW`, quindi si adatta automaticamente.
- Il motore a celle, il renderer Qt, il font, lo zoom e il full screen non
  dipendono dalla geometria: non vanno riscritti.
- I problemi reali sono layout locali cablati su 132 colonne / 43 righe o su
  altezze fisse.

### 1.1 Problemi rilevati (inventario)

**Menu line oltre 80 colonne** (calcolate con `draw_menu_line`, gap 3):

| Modulo | Larghezza | Voci |
|---|---:|---|
| `shell/screens.py` `MAIN_MENU_KEYS` | 86 | F1, Alt-F1, Alt-F2, Alt-F3, Alt-F9 |
| `shell/forms.py` `FORM_KEYS` | 114 | 10 voci |
| `shell/indexes.py` `INDEX_KEYS` | 82 | 6 voci |
| `shell/labels.py` `LABEL_KEYS` | 86 | 8 voci |
| `shell/reports.py` `REPORT_KEYS` | 103 | 10 voci |
| `shell/rules.py` `RULE_KEYS` | 103 | 7 voci |
| `shell/scripts.py` `EDITOR_KEYS` | 81 | 7 voci |
| `shell/searching.py` `SEARCH_KEYS` | 128 | 10 voci |

Le altre menu line stanno entro 80 (directory 72, set 78, utilities 74,
applications editor 76, ecc.).

**Finestre e aree troppo grandi**

- `shell/record_screens.py`: memo overlay `104×27` (righe 229-230); lookup
  con colonne `30 + 18·n` che può superare 76 (righe 277-280).
- `shell/screens.py`: variabili script `width=90` (riga 550); cronologia
  search `width=82` (riga 614); help `max_body=30` (riga 428).
- `shell/forms.py`: descrizione/calc con `fill_rect(..., 60)` e `80` alla
  colonna 22 (righe 684, 701); `MAX_ROW=40`, `MAX_COL=128` (righe 816-817).
- `src/adbx/data/forms.py`: `MAX_FORM_ROW=41`, `MAX_FORM_COL=130` (righe 20-21).
- `shell/reports.py`: formatting con colonne fino a 84 e larghezze fino a 92
  (righe 1567, 1583).
- `shell/scripts.py`: debugger con codice a colonna 1 e variabili a colonna 98
  (righe 897-909); `lines[:36]`.
- `shell/rules.py`: colonne posting `12+18+10+12+18+14+14 = 98` (righe 1086-1088).
- `shell/searching.py`: `fill_rect(..., 90)` (righe 747, 764).

**Righe fisse che sforano le 22 righe utili**

- Report: `[:22]` con righe da 3 → 24 (`reports.py` 1510, 1544, 1571).
- Label: `[:20]` con righe da 3 → 22 (`labels.py` 827, 860).
- Documentazione: `lines[:36]` (`settings.py` 743).
- Set: child region a `child_row=14` + header + `rows[:12]` → 27
  (`sets.py` 1451, 1468).
- Applications: `OUTLINE_ROWS=14`, `DETAIL_TOP=18` + 7 campi dettaglio
  (`applications.py` 45-47, 203-215).
- Main menu / status: path clippato a 60 dalla colonna 20 e contatori
  allineati a destra: a 80 colonne si sovrappongono (`screens.py` 104-128).

**Altri punti da verificare**

- `shell/designer.py`: `ROW_TOP=5`, `COLUMNS=(2,12,34,44,52)`,
  `per_page=STATUS_ROW-ROW_TOP` → si adatta; verificare pagina e fill 74.
- `shell/indexes.py`: livelli `[:16]` a partire da `TABLE_TOP=5` → ultima
  riga 20, ok; menu keys da compattare.
- `shell/searching.py`: righe `[:16]` da `SEARCH_TOP=5` → ultima riga 20, ok;
  sort `[:12]`, ok.
- `shell/sets.py`: integrità `rows[:18]` da riga 3 → ultima 20, ok.
- `shell/applications.py`: banner painter già derivato da `SCREEN_WIDTH/HEIGHT`.
- `shell/settings.py`: schermate colori/default/printer usano `STATUS_ROW` o
  righe fisse contenute; verificare solo la documentazione.
- `shell/utilities.py`, `shell/transfer.py`, `shell/relational.py`: usano
  costanti derivate o layout stretti; verificare con l'audit.

---

## 2. Creazione del worktree (primo passo dell'esecuzione)

Eseguire da `/home/vigliafg/Documenti/GitHub/adbx`.

```bash
cd /home/vigliafg/Documenti/GitHub/adbx

# 1. Fotografia dello stato di lavoro, senza modificarlo.
git diff --binary > /tmp/opencode/adbx-worktree.patch
git rev-parse HEAD > /tmp/opencode/adbx-main-head.txt
git status --porcelain=v1 | sha256sum > /tmp/opencode/adbx-main-status.txt

# 2. Worktree sorella, ramo dedicato, stesso repository.
git worktree add /home/vigliafg/Documenti/GitHub/adbx-legacy -b adbx-legacy HEAD

# 3. Riporto lo stato di lavoro attuale nel worktree.
cd /home/vigliafg/Documenti/GitHub/adbx-legacy
git apply /tmp/opencode/adbx-worktree.patch
cp ../adbx/tests/NEW1.DBF tests/          # artefatto di test, facoltativo
cp ../adbx/PLAN-LEGACY.md .               # questo piano, per la ripresa
git add -A
git commit -m "legacy: baseline dallo stato di lavoro di adbx"
```

Se `git apply` fallisce, fallback: copiare i 24 file elencati da
`git diff --name-only` e i nuovi file, poi committare.

### Garanzia di isolamento

- `adbx` non riceve commit, stash, checkout o modifiche ai file. L'unica
  scrittura è il metadato `.git/worktrees/adbx-legacy` e il ref del ramo.
- Verifica prima/dopo in `adbx`:

```bash
git rev-parse HEAD
git status --porcelain=v1 | sha256sum
```

Devono coincidere con i valori in `/tmp/opencode/` e con la sezione 0.

- `adbx-legacy` ha `.venv`, `config.json` e `.adbx.sqlite` propri: `start.sh`
  crea il venv nella directory del progetto e `PYTHONPATH` punta alla `src/`
  locale. Nessun conflitto con l'installazione editable dell'altra copia.
- La storia è condivisa fino al baseline, poi i rami sono indipendenti.
  Sincronizzazioni future solo con merge/cherry-pick espliciti.
- Rimozione: `git worktree remove /home/vigliafg/Documenti/GitHub/adbx-legacy`.

---

## 3. Fase core — geometria e identità

1. **`src/adbx/cell/buffer.py`**
   - `SCREEN_WIDTH = 80`
   - `SCREEN_HEIGHT = 25`
   - commento: griglia originale 80×25
   - chrome invariato per formula: `STATUS_ROW=22`, `HELP_ROW=23`,
     `MENU_ROW=24`, `WORK_ROWS=22`.
2. **`src/adbx/data/forms.py`**
   - `MAX_FORM_ROW` e `MAX_FORM_COL` derivati dall'area utile (≈21 e 78).
3. **`src/adbx/shell/forms.py`**
   - `MAX_ROW` e `MAX_COL` derivati da `STATUS_ROW` / `SCREEN_WIDTH`.
4. **`src/adbx/app/window.py`**
   - Titolo `adbx — legacy (80×25)`.
   - Con zoom: `adbx — legacy (80×25) — zoom 130% (max)`.
   - Verificare `MIN_WIDTH/MIN_HEIGHT` e dimensione iniziale: la griglia è
     centrata dal renderer, ma il rapporto è cambiato.
5. **`src/adbx/__main__.py`** e **`src/adbx/__init__.py`**
   - Smoke e dump dichiarano `adbx 80x25`.
   - Aggiungere `VARIANT = "legacy"` senza cambiare `__version__ = "1.0.0"`.
6. **`pyproject.toml`**
   - Descrizione aggiornata a 80×25; nome, versione ed entry point invariati.

Il renderer, il font, lo zoom, il full screen e i canvas di stampa **non
cambiano**.

---

## 4. Fase qualità — audit del clipping

Il `CellBuffer` taglia silenziosamente: un layout sbagliato non solleva
errori. Aggiungere una rete di sicurezza **solo nella legacy**:

- contatore/flag di audit in `CellBuffer.write` e `fill_rect`, attivo solo nei
  test, che registra le scritture fuori bordo;
- test che renderizzano tutte le viste principali e pretendono zero clipping
  non intenzionale;
- test che verificano menu line, help line e status line entro 80 colonne;
- test dedicato: costanti 80/25, chrome 22/23/24, dump `adbx 80x25`.

---

## 5. Fase reflow — interventi per area

Regola generale: sostituire i letterali (`[:22]`, `[:36]`, `width=90/82/104`,
colonne oltre 79) con valori derivati da `STATUS_ROW`, `SCREEN_WIDTH` o da un
helper `visible_rows(top)`. Il canvas di stampa dei report (fino a 240
colonne) resta separato dalla griglia schermo.

| Area | Intervento |
|---|---|
| **Chrome e overlay** (`screens.py`, `widgets.py`) | Compattare le 7 menu line. Ridurre `max_body` dell'help a `STATUS_ROW-6`. Memo/variabili/storico a ≤76 colonne e ≤21 righe. Clamp di messaggi e conferme. Status box con path corto e contatori non sovrapposti. |
| **Record** (`record_screens.py`, `records.py`) | Form e browse sono già derivati. Memo 76×21. Lookup con colonne 24+14·n e massimo 76. Scroll verticale per lookup lunghi. |
| **Table designer** (`designer.py`) | `per_page` già derivato. Verificare colonne 2/12/34/44/52 (stanno in 80), fill 74 e indicatore pagina. |
| **Form designer** (`forms.py`) | Limiti pagina 21×78. Descrizione/calc a 54 colonne. Formatting a colonne compatte. Cursor clamp. Menu keys compatti. |
| **Report designer** (`reports.py`) | Formatting da 92 a ≤78 colonne. Liste `[:22]` → righe visibili reali. Summary/calc coerenti. Anteprima su canvas separato. |
| **Label / letter** (`labels.py`, `letters.py`) | Liste `[:20]` → 17. Formatting label entro 80. Menu keys compatti. |
| **Set** (`sets.py`) | Child region: `child_row=14` + header + 5 righe (non 12). Link e integrità entro 22. |
| **Rules** (`rules.py`) | Posting columns 98 → ≤76. Conditional table 78 al limite. Lookup table con numero di colonne limitato o scroll. Menu keys compatti. |
| **Search / sort / index** (`searching.py`, `indexes.py`) | Fill da 90 → `SCREEN_WIDTH-2`. Menu keys compatti. Righe già quasi tutte entro 22. |
| **Script** (`scripts.py`) | Debugger: righe visibili reali e pannello variabili a colonna ~52 invece di 98. Dialog box clampati a 80×21. Editor keys compatti. |
| **Applications** (`applications.py`) | Editor: outline 10 righe, dettaglio da 13, 7 campi distribuiti su due colonne o ridotti. Banner painter già derivato. Runtime menu a colonne calcolate. |
| **Settings / utilities / transfer** (`settings.py`, `utilities.py`, `transfer.py`) | Documentazione `[:36]` → righe visibili. Menu keys e prompt entro 80. Tabelle di anteprima senza sforare. |
| **Main menu / status** (`screens.py`) | Path clippato a ~26 caratteri. Contatori a destra su righe separate o con priorità. Menu 72×9 resta valido (left=4). |

### 5.1 Criterio per le menu line

Massimo ~8 voci per riga, chiavi e etichette abbreviate, gap 2, totale ≤79.
Le voci secondarie si spostano nella help line. Esempi:

- Main: `F1 Help  Alt-F1 Quick  Alt-F2 Play  Alt-F3 Scripts  Alt-F9 DOS`
- Forms: `F1 Help F2 Fields F4 Calc F5 Del F7 Params F8 Box F9 Fmt F10 Save`
- Searching: `F1 Help F2 Fields F3 Ops F4 Sort F5 Del F6 Ins F9 Expr F10 Go`
- Reports: `F1 Help F2 Flds F3 Sect F4 Calc F6 Group F7 Goto F9 Line F10 Save`

Ogni lista deve essere verificata dal test automatico di larghezza.

---

## 6. Test, golden e screenshot

Da aggiornare:

- `tests/test_cli.py`: `griglia 80x25`; dump con **51 righe** (1 header +
  25 righe di testo + 25 righe di run attributi). Il vincolo attuale
  `out.count("\n") >= 87` deriva da `1 + 2×43` e va portato a `>= 51`.
- `tests/test_render.py`: usare `SCREEN_WIDTH/SCREEN_HEIGHT` o 80/25 nei test
  di fit.
- `tests/test_dosbox_automation.py`: dimensioni E2E `1320×817` → nuove
  dimensioni reali.
- `tests/golden/*.txt`: rigenerare dopo il reflow e **rivedere il diff**, non
  accettarlo alla cieca.
- `tests/test_buffer.py`: i test generici restano; verificare il dump globale.
- `docs/e2e/manifest.json`, `docs/e2e/README.md`, PNG E2E: rigenerare con
  `tools/e2e_visual.py`.
- `docs/render/*.png` (56 immagini): rigenerare con `tools/capture_ui.py`.
- Nuovi test: griglia/chrome, audit clipping, menu line ≤80, smoke 80×25.

Comandi di verifica:

```bash
cd /home/vigliafg/Documenti/GitHub/adbx-legacy
python3 -m pytest -q
ruff check src tests tools
python3 -m adbx --smoke
python3 -m adbx --smoke --dump | head -1          # adbx 80x25
QT_QPA_PLATFORM=offscreen python3 tools/capture_ui.py --out /tmp/render
python3 tools/e2e_visual.py --out /tmp/e2e
python3 tools/benchmark.py --records 500
./start.sh
```

---

## 7. Documentazione

- `README.md`: descrizione 80×25, sezione “adbx-legacy”, isolamento, avvio,
  screenshot, conteggio test reale.
- `PLAN.md`: nota di variante legacy; non riscrivere la storia delle ondate.
- `DIARIO.md`: **nuova voce** datata, senza toccare le voci storiche.
- `docs/CHANGELOG.md`: voce legacy mantenendo `1.0.0` per i test di packaging.
- `docs/spec/00-motore-celle.md`: 80×25, chrome 22/23/24, dump.
- `docs/spec/01-scalabilita.md`: riscrivere il compromesso: griglia 80×25
  fissa, font scalabile; non più “132×43 di default, 80×25 alternativo”.
- `docs/spec/02-shell.md`, `03-ambiente-dos-riferimento.md`,
  `13-applications.md`, `14-config-stampa.md`, `docs/manuale-utente.md`:
  allineare tutte le citazioni 132×43 / 43 righe.
- `docs/e2e/README.md`: griglia 80×25 e nuove dimensioni.

Le vecchie voci di diario e changelog restano storiche: descrivono la versione
a 132×43 e non vanno riscritte.

---

## 8. Criteri di accettazione

1. `adbx` ha **HEAD e working tree identici** al baseline; nessun file
   modificato.
2. `adbx-legacy` è un worktree dello stesso repository, su ramo
   `adbx-legacy`, con `.venv`, `config.json` e dati propri.
3. Smoke e dump dichiarano **80×25**; chrome sulle righe 23/24/25 (1-based).
4. Tutte le schermate principali entro 80×25, senza clipping di testo non
   intenzionale.
5. Suite completa verde, nessuno skip; ruff pulito; benchmark, capture UI ed
   E2E funzionanti.
6. Le 25 lezioni del Tutorial passano senza adattamenti funzionali.
7. Screenshot e manifest rigenerati e coerenti; confronto visivo possibile
   con lo screenshot DOSBox 80×25.
8. Documentazione e riferimenti a 132×43 eliminati nella legacy.

---

## 9. Ordine di lavoro

1. Baseline worktree e verifica isolamento.
2. Griglia core + titolo + test minimi.
3. Audit clipping.
4. Shell, overlay, status/menu line.
5. Record e memo/lookup.
6. Designer: table, form, report, label, set, rules, search/index.
7. Script, applicazioni, impostazioni, utilities.
8. Golden, screenshot, E2E.
9. Documentazione e verifica finale.

Impatto stimato: **~25 moduli shell/app**, **~60 file** tra codice, test,
documenti e immagini. Il rischio maggiore è nei designer e nelle menu line,
non nel motore a celle.

---

## 10. Comandi per la ripresa dopo il riavvio

```bash
cd /home/vigliafg/Documenti/GitHub/adbx
cat PLAN-LEGACY.md
git rev-parse HEAD
git status --porcelain=v1 | sha256sum
```

Poi eseguire la sezione 2 e proseguire con le fasi 3–9.

**Nota:** questo file è un documento di piano nel repository `adbx`. Non è
tracciato da git finché non viene aggiunto. Al momento della creazione del
worktree va copiato anche in `adbx-legacy` (sezione 2, passo 3).

---

# Appendice A — Inventario di dettaglio (integrazione)

Questa appendice raccoglie i punti emersi dall'analisi approfondita che
integrano la sezione 1.1. Non ripete ciò che è già elencato lì.

## A.1 Colonne oltre 80 non ancora elencate

| File | Riga | Problema | Nota |
|---|---:|---|---|
| `shell/scripts.py` | 623-637 | pannello controlli del dialog designer parte da `col=72`, poi `72 + col*9` → fino a ~117 | il pannello di destra va riprogettato, non solo spostato |
| `shell/scripts.py` | 800-804 | anteprima menu-bar a righe fisse `23` e `24` | a 25 righe sono sotto lo status: invisibili |
| `shell/scripts.py` | 645-648 | anteprima dialog max `height=20`, blittata a `row=12` | arriva alla riga 32: va clampata |
| `shell/reports.py` | 1526 | espressione `col=18, clip=100` | termina a 118 |
| `shell/reports.py` | 1443-1445 | parametro `col=58` + valore `width=30` | termina a 88 |
| `shell/searching.py` | 750-752 | valore `col=22, clip=100`; `Region` larga 100 | termina a 122 / 102 |
| `shell/searching.py` | 764-772 | descrizione `col=18, width=90`; region 90 | termina a 108 |
| `shell/applications.py` | 440 | valore parametro `col=27, clip=60` | termina a 87 |
| `shell/applications.py` | 491 | dettaglio outline `col=17, clip=100` | termina a 117 |
| `shell/applications.py` | 615 | macro editor `clip=128` a col 1 | termina a 129 |
| `shell/settings.py` | 471 | valore printer driver `col=24, clip=60` | termina a 84 |
| `shell/settings.py` | 744 | documentazione `clip=128` | termina a 129 |
| `shell/sets.py` | 672 | descrizione set `col=44, clip=60` | termina a 104 |
| `shell/sets.py` | 644-646 | valore form-set `col=22, width=60` | termina a 82 |
| `shell/rules.py` | 597-599 | header campo `Type` a 66, due punti 74, valore 76 + nome | ~85 |
| `shell/labels.py` | 785-787 | parametro `col=56, clip=30` | termina a 86 |
| `shell/labels.py` | 843 | espressione `col=17, clip=100` | termina a 117 |
| `shell/labels.py` | 856,874 | ultima colonna formatting 64 + clip 18 | termina a 82 |
| `shell/forms.py` | 730 | parametri form `col=28, clip=80` | termina a 108 |
| `shell/screens.py` | 257,345 | clip `100` da col 2/18 | troncamento duro, non overflow |

## A.2 Righe e limiti dati aggiuntivi

| File | Riga | Problema |
|---|---:|---|
| `shell/records.py` | 68-69 | `MemoEditor` logico `width=92, height=21`: va ridimensionato **insieme** all'overlay 104×27 di `record_screens.py` |
| `shell/settings.py` | 462-473 | `PrinterSession` ha 21 campi renderizzati da riga 2 → l'ultimo finisce sulla riga di status |
| `shell/rules.py` | 57,607,648 | `RULE_TOP=15`, `visible=9`, ma il break a `STATUS_ROW-3=19` lascia solo ~4 righe visibili: rivedere la divisione |
| `shell/scripts.py` | 192,195 | PgUp/PgDn spostano di `22` righe fisse: derivare da `visible` |
| `shell/letters.py` | 183,187 | PgUp/PgDn spostano di `22` righe fisse: derivare da `visible` |
| `shell/labels.py` | 483,492 | altezza label max 20 + `CONTENT_TOP=4` → bordo inferiore a riga 24, sopra il menu |
| `data/labels.py` | 21-24 | `MAX_LABEL_WIDTH=78`, `MAX_LABEL_HEIGHT=20`: il box con bordo non entra in 25 righe |
| `script/model.py` | 173-195 | `DialogBox` ammette `height` 38 e `width` 128: il runtime va clampato a 80×25 (o il modello va limitato nella legacy) |
| `shell/applications.py` | 458-483 | dettaglio con 4 campi menu / 7 campi item: righe 19-25, sovrapposte al chrome |
| `app/model.py` | menu runtime | `menu_view` calcola `per_column=(STATUS_ROW-5)//spacing`: a 22 righe entrano ~17 voci; le eccedenti finiscono fuori schermo (bug latente, da correggere o documentare) |
| `shell/forms.py` + `data/forms.py` | già citati | `MAX_ROW/COL` e `MAX_FORM_ROW/COL` vanno allineati alla nuova area utile |

## A.3 Accoppiamenti da non dimenticare

- `prompt_overlay` ha `width=66` in `shell/screens.py:384`, ma la matematica
  del click-to-cursor ripete `66` in `shell/controller.py:733`. Se la
  larghezza cambia, vanno cambiate entrambe.
- `test_help.py` verifica che ogni topic si avvolga in meno di 40 righe: non
  impone la griglia, ma l'help overlay deve comunque avere un `max_body`
  compatibile con 22 righe utili.
- `screen.width` / `screen.height` sono promessi in
  `docs/spec/01-scalabilita.md` ma **non implementati** nel motore script.
  Nella legacy o si implementano restituendo 80/25, oppure si aggiorna la
  specifica eliminando la promessa.
- `tests/test_reports.py` usa `132` come **larghezza di stampa** del report:
  non va cambiato. Lo stesso vale per `page_length=22`, `print_width=80`,
  `MAX_LABEL_WIDTH`, i default di `data/reports.py`, `docs/generator.py` e
  `io/common.py`: sono valori di stampa/dati, non righe/colonne schermo.
- `tests/test_packaging.py` controlla solo che i 56 nomi di screenshot
  esistano, non le dimensioni: la suite può restare verde con immagini stale.
  La rigenerazione di `docs/render/*.png` è quindi un passo esplicito, non
  qualcosa che i test segnalano.
- `src/adbx.egg-info/` è ignorato/untracked ma contiene metadati vecchi
  (`0.1.0.dev0`, fonti rimosse). Rigenerarlo con `pip install -e .` nella
  legacy per non avere metadati misti.

## A.4 Isolamento runtime: accorgimenti operativi

- `start.sh` usa `$HERE` per venv e `PYTHONPATH`, ma **non fa `cd`**: se lo
  lanci da un'altra directory, `default_root()` usa la cwd e la legacy
  scriverebbe `config.json`/dati nel posto sbagliato. Eseguire sempre
  `cd /home/vigliafg/Documenti/GitHub/adbx-legacy && ./start.sh`.
- Se `ADBX_DATA` è impostata globalmente, entrambe le copie condividono la
  stessa cartella dati e lo stesso `.adbx.sqlite`: per i test side-by-side
  passare `--data` esplicito o non impostare la variabile.
- Un'installazione editable globale di `adbx` può far sì che il comando
  `adbx` lanci la copia sbagliata. `./start.sh` è sicuro perché antepone la
  `src/` locale; non usare il comando globale per la legacy.
- Se si copia un `.venv` tra i due worktree, il `.pth` e il console script
  puntano ancora alla sorgente originale: ricreare il venv, non copiarlo.
- `--open FILE` sceglie la config dalla cartella del file, ma `state.root`
  resta la cwd: per una sessione legacy prevedibile, lanciare dalla directory
  del worktree e passare `--data` quando serve.

## A.5 Stima aggiornata

L'analisi di dettaglio conferma **~10–17 giornate di sviluppo**, con il carico
maggiore su `screens.py`, `rules.py`, `applications.py`, `reports.py` e
`scripts.py`. La modifica delle costanti è mezza giornata; il resto è reflow,
test e documentazione.

**Prossimo passo dopo la ripresa:** creare il worktree (sezione 2), poi
applicare la fase core (sezione 3) e l'audit (sezione 4) prima di toccare i
designer.

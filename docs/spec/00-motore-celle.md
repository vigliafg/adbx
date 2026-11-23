# O0 — Motore a celle

Specifica delle fondamenta: la griglia, il font, i colori, gli strati, la
tastiera e i dump golden. Tutto il resto del programma scrive in un
`CellBuffer`; nessun modulo conosce widget o layout manager.

## 1. Griglia

- Dimensioni logiche: **80×25** celle (`SCREEN_WIDTH`, `SCREEN_HEIGHT`).
- Area di lavoro: righe **1–22** (`WORK_ROWS`).
- Righe convenzionali: **23** status line, **24** help line, **25** menu line.
- Ogni cella: `Cell(ch, fg, bg, blink, bold)` immutabile.
- Il clipping è silenzioso, come sul video originale: scrivere fuori bordo non
  solleva errori e non disegna.
- La griglia di stampa è un canvas separato, fino a **240 colonne** (report):
  non è lo schermo.

## 2. Font

- Tabella bitmap **CP437 8×16**, 256 glifi × 16 byte, MSB a sinistra,
  in `src/adbx/data/cp437_8x16.bin` (4.096 byte).
- I caratteri **grafici** (cornici singole e doppie, blocchi, retinature) sono
  disegnati proceduralmente da `tools/build_font.py`, non presi dal font
  tipografico: è l'unico modo per avere linee continue tra celle adiacenti.
  Coordinate: verticale singola a `x=3`, orizzontale singola a `y=7`; doppia a
  `x=2,4` e `y=6,8`.
- I caratteri alfabetici derivano da **DejaVu Sans Mono** (licenza Bitstream
  Vera, vedi `src/adbx/data/LICENSE-font.txt`).
- Rigenerazione: `python tools/build_font.py` (richiede Pillow e un font
  monospaziato installato). Il `.bin` è versionato: il programma non dipende
  da font di sistema.
- Il codice 0x00–0x1F di CP437 è reso come spazio.

## 3. Colori

- 16 colori VGA (`DOS_PALETTE`), più attributi `bold` (colore intenso) e
  `blink`.
- I form di Alpha Four ammettono colori **0–255**: `resolve_color()` li riduce
  a 0–15 con la regola provvisoria `indice % 16`, documentata e sostituibile
  quando si importerà la palette originale `A4.PAL`.
- Tema alternativo `NEWPORT_PALETTE` (schema blu monocromatico predefinito del
  prodotto originale).

## 4. Strati

- `Scene` è una pila di `Layer`; ogni strato è un `CellBuffer` con origine
  `(row, col)`.
- `composite()` sovrappone in ordine di inserimento; `bring_to_front()`
  riordina; `layer_at(row, col)` serve al routing del mouse.
- `popup(width, height)` costruisce un buffer di `width+1 × height+1`: cornice
  `width × height`, riga e colonna finali riservate all'ombra (`░`).
- La cornice usa `┌┐└┘─│` oppure la variante doppia `╔╗╚╝═║`.

## 5. Tastiera

- `Key(name, ctrl, alt, shift)` con nomi canonici (`ENTER`, `ESC`, `F10`,
  `PGDN`, `HOME`, …).
- `parse("alt-f")` e `format()` usano la notazione degli script Alpha Four:
  è la stessa rappresentazione che il motore di script userà per digitare.
- `key_from_qt(event)` traduce gli eventi Qt; le lettere diventano maiuscole,
  i simboli hanno nomi stabili (`MINUS`, `SLASH`, `LBRACKET`, …).
- Regola: **un solo gestore di tastiera**. Il playback degli script inietterà
  `Key` in quello stesso gestore.

## 6. Renderer

- `CellRenderer` disegna un `CellBuffer` su `QPainter`, con scala intera
  (default 2× → cella 16×32 px).
- Atlante per colore: 256 glifi in un `QImage` ARGB, costruito in modo lazy e
  memorizzato; nessuna conversione per frame.
- `bold` usa il colore intenso; `blink` alterna la fase (timer a 500 ms).
- `to_image()` produce un `QImage` per screenshot e test.

## 7. Dump golden

Formato testuale stabile, usato per confrontare schermate senza immagini:

```
adbx 80x25
<80 caratteri della riga 1>
<run-length degli attributi: "count@fg,bg,bold,blink" separati da spazio>
...
```

Un dump uniforme di una riga è un solo token (`80@7,0,0,0`); le differenze
sono leggibili in diff.

## 8. Accettazione O0

- Griglia 80×25 con 16 colori, bold e blink.
- Cornici continue tra celle adiacenti (verificato sui glifi).
- Popup con titolo e ombra, compositato su uno strato sottostante.
- Ogni tasto della tabella comandi produce un `Key` canonico.
- `pytest` verde; dump golden stabile; rendering PNG riproducibile.

# O0 — Motore a celle

Specifica delle fondamenta: la griglia, il font, i colori, gli strati, la
tastiera e i dump golden. Tutto il resto del programma scrive in un
`CellBuffer`; nessun modulo conosce widget o layout manager.

## 1. Griglia

- Dimensioni logiche: **132×43** celle (`SCREEN_WIDTH`, `SCREEN_HEIGHT`).
- Area di lavoro: righe **1–40** (`WORK_ROWS`).
- Righe convenzionali, ancorate in fondo: **41** status line (`STATUS_ROW`),
  **42** help line (`HELP_ROW`), **43** menu line (`MENU_ROW`).
- Ogni cella: `Cell(ch, fg, bg, blink, bold)` immutabile.
- Il clipping è silenzioso, come sul video originale: scrivere fuori bordo non
  solleva errori e non disegna.
- La griglia di stampa è un canvas separato, fino a **240 colonne** (report):
  non è lo schermo.
- La griglia **non cambia** con la finestra: gli script indirizzano celle
  assolute. La scalabilità si applica al corpo del font, non alla geometria
  (vedi `01-scalabilita.md`).

## 2. Font

- Font **TrueType** incorporato: **DejaVu Sans Mono** regular e bold, in
  `src/adbx/data/fonts/` (licenza Bitstream Vera, vedi
  `src/adbx/data/LICENSE-font.txt`). Se il caricamento fallisce si ripiega
  sul monospace di sistema (`Consolas`, `Menlo`, `Courier New`, …).
- La cella deriva dalle metriche del font: larghezza = avanzamento del
  carattere, altezza = `ascent + descent`, in pixel di dispositivo. Nessun
  fattore di scala sui glifi: il testo non viene mai stirato.
- Il corpo è scelto **automaticamente** per riempire la finestra, fra 7 e 72
  pixel, con passi di un pixel di dispositivo.
- I caratteri **grafici** (cornici singole e doppie, blocchi, retinature) sono
  disegnati geometricamente da `render/glyphs.py`, non presi dal font: è
  l'unico modo per avere linee continue tra celle adiacenti a qualunque
  corpo. Spessore delle linee: `altezza_cella / 16` pixel di dispositivo;
  doppie a due linee distanziate di uno spessore.
- Il grassetto usa il peso bold del font più il colore intenso (l'attributo
  DOS `bold` era l'intensità).
- Le retinature `░▒▓` sono rese come velo traslucido del colore di primo
  piano (25%, 50%, 75%).

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

- `CellRenderer` disegna un `CellBuffer` su `QPainter`, in pixel di
  dispositivo (`devicePixelRatio`), così il testo resta nitido su schermi HiDPI.
- Atlante di 256 glifi **per colore e per grassetto**, costruito con
  `QPainter` e antialiasing, memorizzato per corpo: nessuna conversione per
  frame.
- Il testo è centrato orizzontalmente nella cella; la linea di base è quella
  del font.
- `bold` usa il colore intenso e il peso bold; `blink` alterna la fase
  (timer a 500 ms).
- `to_image()` produce un `QImage` per screenshot e test.
- `fit(width, height, cols, rows)` sceglie il corpo; `use_natural_size()` è
  usata dagli screenshot canonici.

## 7. Dump golden

Formato testuale stabile, usato per confrontare schermate senza immagini:

```
adbx 132x43
<132 caratteri della riga 1>
<run-length degli attributi: "count@fg,bg,bold,blink" separati da spazio>
...
```

Un dump uniforme di una riga è un solo token (`132@7,1,0,0`); le differenze
sono leggibili in diff. Il dump non dipende dal font né dal ridimensionamento.

## 8. Accettazione O0

- Griglia 132×43 con 16 colori, bold e blink.
- Font TrueType incorporato e corpo scelto per riempire la finestra.
- Cornici continue tra celle adiacenti (verificato sulle giunzioni).
- Popup con titolo e ombra, compositato su uno strato sottostante.
- Ogni tasto della tabella comandi produce un `Key` canonico.
- `pytest` verde; dump golden stabile; rendering PNG riproducibile.

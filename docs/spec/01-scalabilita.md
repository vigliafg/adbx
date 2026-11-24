# Scalabilità dell'interfaccia

Perché la griglia è 80×25 a pixel fissi, come vengono scelti i caratteri e in
che senso l'interfaccia è «fit‑to‑window». Il modello di riferimento è la
finestra DOS/console di Windows XP.

## 1. Come lo faceva Windows XP

La console di Windows NT/XP (`csrss.exe`, dal 2007 `conhost.exe`) non era un
emulatore VGA quando girava in finestra: era un'applicazione **GDI** che
disegnava una matrice di caratteri. I punti che ci interessano:

- **Due famiglie di font.** Una finestra console poteva usare *Raster Fonts*
  (bitmap a misure fisse: 8×12, 12×16, …) oppure un font **TrueType**, in
  pratica `Lucida Console`, introdotto con Windows 2000. Con i font bitmap le
  misure erano poche e fisse; con i TrueType la finestra *Proprietà → Font*
  offriva una lista di **corpi** (point size) molto più ampia.
- **La cella deriva dal font, non dal pixel.** La console chiedeva a GDI le
  metriche del font scelto (`tmHeight`, `tmAveCharWidth`), ne ricavava
  l'altezza e la larghezza della cella e disegnava ogni carattere alla
  dimensione richiesta. Non c'era alcun ingrandimento bitmap: cambiando corpo
  si ottenevano glifi nuovi, non un raster stirato.
- **La finestra si misura in caratteri.** La proprietà *Layout* distingueva
  la dimensione del **buffer** (le righe di scrollback) dalla dimensione della
  **finestra** (le celle visibili). Ridimensionando la finestra cambiava il
  numero di righe e colonne visibili, non la dimensione dei caratteri; il
  contrario accadeva scegliendo un corpo diverso nel dialogo Font.
- **Nessuna scalatura arbitraria.** Le celle erano un rettangolo di
  `larghezza carattere × altezza carattere`: non si allargavano i glifi per
  riempire lo spazio. Eventuali pixel avanzati restavano margine.
- **Testo antialiasato.** Con i TrueType la console usava il rendering GDI
  (font smoothing), quindi il testo era molto più leggibile di quello del
  full screen, che usava una tabella bitmap caricata sulla scheda video.
- **Full screen a parte.** In Windows XP e precedenti il full screen usava un
  vero modo testo VGA (al massimo 80×28), non la stessa pipeline GDI. Era una
  modalità separata, non una scalatura della finestra.

Fonti: Wikipedia, *Windows Console* (full-screen text mode 80×28; font e
palette configurabili), documentazione Win32 Console (buffer di schermo e
finestra come concetti distinti), osservazione diretta della finestra
*Proprietà* della console XP.

## 2. Cosa adottiamo

| Aspetto | Windows XP | adbx |
|---|---|---|
| Font | Raster o TrueType (Lucida Console) | **TrueType incorporato**: DejaVu Sans Mono regular/bold, fallback al monospace di sistema |
| Cella | metriche del font | metriche del font (`advance`, `ascent+descent`) |
| Dimensione carattere | corpo scelto dall'utente | **corpo automatico** con tetto di leggibilità e **zoom 50–200%** |
| Griglia | righe/colonne visibili = area / cella | **fissa 80×25**, perché gli script indirizzano celle assolute |
| Riempimento | margine ai bordi | griglia centrata; margine nel colore di fondo |
| Glifi | mai stirati | **mai stirati** |
| Testo | GDI antialiasato con TrueType | `QPainter` antialiasato, atlante per colore |

Il compromesso è esplicito: XP poteva rimodellare il numero di righe e colonne
perché il contenuto era un flusso di testo; Alpha Four, e quindi adbx, ha
schermate e script che parlano di «riga 23, colonna 40». La griglia logica deve
restare stabile, quindi la scalabilità si applica al **corpo del font**, non
alla geometria logica.

## 3. Griglia

- **80×25** celle, le stesse del modo testo del DOS e dello screenshot di
  riferimento: le schermate originali e le coordinate citate dal Tutorial
  tornano senza riadattamenti.
- Righe convenzionali, ancorate in fondo: **23** status line, **24** help
  line, **25** menu line; area di lavoro nelle righe 1–22.
- Gli script indirizzano celle assolute e non leggono le dimensioni a
  runtime: il linguaggio non espone `screen.width`/`screen.height`. Le
  costanti `STATUS_ROW`, `HELP_ROW`, `MENU_ROW` sono interne al guscio.
- Canvas di stampa separato: fino a 240 colonne, non è lo schermo.

## 4. Scelta del corpo

1. Si parte da un corpo in pixel interi (device pixel), così i glifi restano
   nitidi e non vengono mai riscalati.
2. Per ogni corpo si leggono le metriche: `advance` (larghezza cella) e
   `ascent + descent` (altezza cella).
3. Si sceglie il corpo più grande per cui
   `80 × advance ≤ larghezza` **e** `25 × altezza ≤ altezza finestra`.
4. Il corpo automatico si ferma a **24 px logici** (`COMFORT_FONT_PX`, in
   pixel di dispositivo moltiplicati per il `devicePixelRatio`): su schermi
   molto grandi il testo non diventa enorme e la griglia lascia margini.
   Mai sotto 7 px (illeggibile), mai sopra 72 px.
5. Lo zoom utente è un **fattore** sul corpo di riferimento al 100%:
   `CTRL-+` / `CTRL--` a passi del 10% (50–200%), `CTRL-0` riporta al 100%,
   il livello è salvato in `config.json` (`screen_zoom`). Al 100% il corpo è
   il massimo che entra nella finestra (o il tetto di leggibilità); quando la
   finestra limita, `CTRL-+` allarga anche la finestra fino allo schermo per
   contenere il corpo maggiore, e `F11` usa tutto lo schermo. Lo zoom non
   supera mai il massimo che entra: la griglia non viene tagliata e il titolo
   mostra `(max)` quando il livello richiesto non è raggiungibile.
6. La griglia risultante è centrata nella finestra; i margini usano il colore
   di fondo dell'interfaccia, quindi non appaiono come barre nere.
7. `F11` commuta il full screen; lo stesso algoritmo porta la griglia alla
   dimensione massima consentita dallo schermo.

Il ridimensionamento della finestra cambia quindi il corpo del font a scatti
di un pixel di dispositivo: è la stessa esperienza della console XP quando si
sceglieva il corpo, ma automatica e continua.

## 5. Disegno

- **Testo**: atlante di 256 glifi per colore (e per grassetto) costruito con
  `QPainter` e antialiasing, alla risoluzione del dispositivo
  (`devicePixelRatio`). Nessuna conversione per frame.
- **Caratteri grafici** (`─│┌┐└┘├┤┬┴┼`, doppi, blocchi, retinature): non
  vengono presi dal font, ma **disegnati geometricamente** nella cella, con
  spessori in pixel di dispositivo. Così le linee restano continue tra celle
  adiacenti a qualunque corpo e su qualunque font, cosa che i TrueType
  monospaziati non garantiscono (le cornici di DejaVu lasciano un pixel di
  vuoto ai bordi della cella).
- **Grassetto**: peso bold del font più colore intenso (l'attributo DOS
  `bold` era l'intensità, non il peso).
- **Blink**: fase alternata ogni 500 ms; il glifo viene omesso nella fase
  spenta.

## 6. Conseguenze

- Il dump golden resta testuale: non dipende dal font né dal ridimensionamento.
- Gli screenshot in `docs/render/` sono generati alla stessa griglia logica,
  con margini nulli, per confronti puliti.
- Il vecchio font bitmap CP437 8×16 e il generatore `tools/build_font.py` sono
  stati rimossi: non servono più e non erano più la verità estetica.
- La mappatura colori 0–255 → 16 resta provvisoria finché non si importa la
  palette originale.

# Ambiente DOS di riferimento — Alpha Four 3.0 in DOSBox-X

L'originale non si emula dentro adbx, ma averlo a disposizione serve a
verificare schermate, tasti, messaggi e sequenze del Tutorial. Questa
specifica descrive l'ambiente usato per il confronto.

## 1. Installazione

Su Ubuntu 26.04:

```bash
sudo apt-get install dosbox-x
```

Versione verificata: DOSBox-X 2026.01.02 (pacchetto `2026.01.02+dfsg-2`).

## 2. Avvio

Lo script `tools/run_alpha4_dosbox.sh` cerca l'archivio originale nella
radice del repository, estrae `drivec/` nella cache utente e prepara la
configurazione:

```bash
tools/run_alpha4_dosbox.sh            # primo avvio: estrae e parte
tools/run_alpha4_dosbox.sh --reset    # riestrae da zero
ADBX_ALPHA4_ZIP=~/Downloads/drivec.zip tools/run_alpha4_dosbox.sh
```

La configurazione generata monta la cartella estratta come `C:` e lancia:

```dos
C:
CD \ALPHA4V3
A4.EXE
```

Parametri DOSBox-X: macchina `svga_s3`, 16 MB, EMS/XMS attivi, cicli
automatici. L'archivio originale e i file DOS restano fuori dal repository.

## 3. Esito della verifica

All'avvio l'originale mostra il **main menu** con:

- `Current database : C:\AVMOVIES`
- `Records in database : 50`
- `Primary index : Search/Sort List`
- `Records in list : 12`
- i dodici comandi del menu e le righe di help/menu.

Lo screenshot è in [`../render/06-alpha-four-dosbox.png`](../render/06-alpha-four-dosbox.png).
Il programma risponde alla tastiera e arriva al menu senza errori di memoria:
EMS, XMS e modalità video sono sufficienti.

## 4. Uso come riferimento

- Le schermate vanno confrontate per **contenuto e comportamento**, non per
  i pixel: adbx usa una griglia 132×43 con font TrueType, l'originale gira
  a 80×25 nel DOSBox.
- Il main menu dell'originale ha una finestra più stretta e un solo bordo;
  adbx conserva la stessa disposizione logica e gli stessi hot key.
- Le lezioni del Tutorial vanno eseguite in DOSBox-X quando un
  comportamento non è chiaro dalla documentazione, e il risultato va
  annotato nel diario.

## 5. Catturare una schermata

Nel DOSBox-X si può usare la scorciatoia di cattura predefinita
(`CTRL-F5`), che salva i PNG nella cartella `captures` della cache. In
alternativa, su un display X:

```bash
scrot -o /tmp/alpha4.png
```

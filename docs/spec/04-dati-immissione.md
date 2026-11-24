# O2 — Dati e immissione

Database veri, record veri, un table designer e le modalità di immissione.
Questa ondata introduce il primo strato dati completo; le regole di campo
(O4), gli indici (O3), i set (O5) e i layout progettati (O6) restano fuori.

## 1. Dove vivono i dati

```
cartella/
  .adbx.sqlite     # motore di lavoro: catalogo, tabelle, memo
  AVMOVIES.DBF     # formato di scambio, riscritto al salvataggio
  AVMOVIES.DBT     # memo, riscritto insieme al DBF
```

- Ogni cartella è un **workspace**. Il file nascosto `.adbx.sqlite` contiene
  `adbx_databases`, `t_<db>` (una colonna per campo, `__seq`, `__deleted`) e
  `m_<db>` (memo). È la mappatura del PLAN §3.3.
- Il `.DBF` resta la sorgente: al primo accesso viene importato (intestazione,
  record, memo); a ogni salvataggio esplicito viene riscritto in modo atomico.
  Quindi un database creato da adbx si apre anche con gli strumenti dBASE e i
  file del Tutorial si possono importare senza conversioni manuali.
- `PACK` elimina fisicamente i record marcati e **rinumera** `__seq` da 1.
- `ZAP` non è ancora esposto nella UI, ma lo strato dati lo offre.
- La scrittura del `.DBF` è una deviazione consapevole dal piano originale
  (che parlava solo di SQLite): serve a non sequestrare i dati dell'utente e
  a mantenere il file originale utilizzabile.

## 2. Tipi e valori

| Tipo | Lunghezza | Valore canonico |
|---|---|---|
| Character | 1–254 | testo, spazi finali rimossi |
| Numeric | 1–19, 0–14 decimali | `Decimal` con segno, punto e decimali fissi |
| Date | 8 | `YYYYMMDD` |
| Logical | 1 | `1`, `0`, vuoto |
| Memo | 10 (puntatore) | testo fino a 5.000 caratteri, tabella memo |

- I nomi dei campi: 1–10 caratteri, iniziano con una lettera, poi `A-Z 0-9 _`;
  sono convertiti in maiuscolo.
- Numerici: arrotondamento half-up; valuta, spazi e separatori delle migliaia
  si possono digitare e vengono rimossi. Un valore che non entra nella
  larghezza è rifiutato.
- Date: input `MM/DD/YY`, `MM/DD/YYYY`, `MM-DD-YY`, `MM-DD-YYYY` oppure
  `YYYYMMDD`; viene rifiutata una data inesistente.
- Logici: `T/Y/1`, `F/N/0` (anche `.T.`/`.F.`), oppure vuoto.
- Limiti: 128 campi, 4.000 caratteri per record esclusi i memo.

## 3. Riconfigurazione

La tabella di conversione è quella dell'inventario §2 ed è applicata da
`data/fields.py`:

| Da → A | Esito |
|---|---|
| Character → Date | solo con `MM/DD/YY(YY)` e `MM-DD-YY(YY)`, altrimenti vuoto |
| Character → Logical | primo carattere `T t F f Y y N n`, altrimenti vuoto |
| Character → Numeric | prefisso numerico; blank → 0; valuta/separatori persi |
| Numeric → Character | conservato |
| Numeric → Date / Logical | perso / `0`→F, `>0`→T, `<0` perso |
| Date → Character | `YYYYMMDD` |
| Date → Logical / Numeric | perso |
| Logical → Character | `T`/`F` |
| Logical → Date / Numeric | perso |

- Rinominare un campo conserva i valori; eliminarlo li perde; aggiungerlo lo
  riempie di vuoti.
- Un campo memo convertito in character perde il testo oltre la nuova
  larghezza; un character convertito in memo conserva il testo.
- Il DBF viene riscritto dopo la riconfigurazione.

## 4. Table designer

Si apre con `F5` nel Database Directory (creazione) o con
`Database/set design → Create/Modify database`.

```
Database : AVMOVIES          Fields : 11      Record length : 106
Number  Field Name        Type  Length  Decimal Place
1       TAPE_ID           C     4       0
2       TAPE_TITLE        C     40      0
...
```

| Tasto | Azione |
|---|---|
| `TAB` / `SHIFT-TAB` | colonna successiva/precedente |
| `UP` / `DOWN` | campo precedente/successivo |
| `PGUP` / `PGDN` | pagina di campi |
| `F5` | elimina il campo |
| `F6` | inserisce un campo vuoto dopo quello corrente |
| `F10` | valida, salva e torna al menu |
| `ESC` | annulla |
| `F1` | aiuto |

Date, Logical e Memo hanno lunghezza fissa (8, 1, 10); scegliendo il tipo le
celle Length/Decimal si aggiornano e non sono più modificabili.

## 5. Modalità record

`View/enter records` apre un sottomenu:

| Voce | Modalità | Tasto |
|---|---|---|
| View records | un record per schermata, sola lettura | `V` |
| Enter records | nuovi record | `E` |
| Change records | modifica del record corrente | `C` |
| Browse records | tabella | `B` |
| Delete/recall records | View con i cancellati visibili | `D` |

### Tasti comuni (View e Browse)

| Tasto | Azione |
|---|---|
| `UP` / `DOWN` | record precedente/successivo |
| `TAB` / `SHIFT-TAB` | ±10 record |
| `PGUP` / `PGDN` | ±10 record (una pagina in Browse) |
| `CTRL-HOME` / `CTRL-END` | primo/ultimo record |
| `E` | entra in Enter mode |
| `F7` | mostra/nascondi i cancellati (`*` in Browse) |
| `ALT-D` / `ALT-U` | cancella / richiama il record |
| `ALT-M` | memo del campo corrente (o primo memo) |
| `ALT-F5` / `ALT-F6` | copia / incolla il campo |
| `F10` / `ESC` | chiude la modalità |

### Enter e Change

- Nella form Enter `UP`/`DOWN`/`ENTER`/`TAB` spostano tra i **campi**, non
  tra i record: i record già inseriti si rivedono in View (o Change).
- Da View, `E` entra in Enter mantenendo View come ritorno; `F10` (salva) ed
  `ESC` (annulla) tornano a View, sul record appena salvato o su quello
  corrente. Le frecce scorrono poi i record già inseriti. Entrando in Enter
  dal main menu, invece, `F10`/`ESC` tornano al main menu, come l'originale.
- `TAB` e `ENTER` passano al campo successivo; `SHIFT-TAB`/`UP` al precedente.
- `LEFT`/`RIGHT`/`HOME`/`END` spostano il cursore nel campo;
  `CTRL-LEFT`/`CTRL-RIGHT` vanno al primo/ultimo campo.
- `BACKSPACE`, `DELETE`, `CTRL-BACKSPACE` (svuota), `INSERT`
  (inserimento/sovrascrittura).
- In Enter, `ENTER` sull'ultimo campo o `CTRL-ENTER` da qualunque campo
  salvano e aprono un nuovo record; sull'ultimo campo la command line mostra
  `ENTER Next record`. `F10` salva e torna alla modalità precedente (o al
  menu se Enter è stato scelto dal main menu), come il Continue/Save
  dell'originale.
- In Change, `PGUP`/`PGDN` cambiano record solo dopo il salvataggio o
  l'annullamento delle modifiche.
- Un record completamente vuoto non viene salvato; `F10` su un nuovo record
  vuoto esce dalla modalità senza creare nulla.

### Browse

Tabella a scorrimento: `LEFT`/`RIGHT` scorrono le colonne, `UP`/`DOWN` le
righe, `PGUP`/`PGDN` una pagina. Il record corrente è evidenziato; i
cancellati hanno `*` davanti al numero quando `F7` è attivo.

## 6. Memo e clipboard

- Il memo si apre con `ALT-M`, accetta testo libero, `ENTER` per una nuova
  riga, `BACKSPACE`/`DELETE`, `PGUP`/`PGDN`. `F10` lo tiene con il record,
  `ESC` lo lascia invariato. In View/Browse è in sola lettura.
- Il memo viene scritto in `m_<db>` e nel `.DBT` insieme al record.
- La clipboard è interna alla sessione: `ALT-F5` copia il valore del campo
  corrente, `ALT-F6` lo incolla in un campo di Enter/Change.

## 7. Cancellazione, PACK e password

- `ALT-D` marca `__deleted = 1`; il record sparisce da View/Browse normali.
  `F7` lo mostra, `ALT-U` lo richiama.
- `Utilities → Pack database` elimina i marcati, rinumera `__seq` e riscrive
  il DBF. L'avviso dice quanti record sono stati rimossi e quanti restano.
- `Database/set design → Password` imposta o rimuove una password (PBKDF2-
  SHA256). All'apertura successiva il Database Directory chiede la password;
  finché non è corretta, le modalità record non partono.

## 8. Deviazioni e limiti dichiarati

- **Form di default**: fino a O6 non esiste un form designer. View/Change/Enter
  generano una griglia etichetta/valore, una, due, tre o quattro colonne a
  seconda dei campi. Non è il layout dell'originale, ma è una schermata a
  celle con gli stessi dati e gli stessi tasti.
- **Browse di default**: la tabella mostra le colonne dalla larghezza dei
  campi (massimo 18) e scorre in orizzontale; la browse table progettata
  arriverà con O6.
- **Erase database** elimina il file `.DBF`/`.DBT` solo se il database è stato
  creato da adbx (`origin = created`). Per un database importato il file
  originale resta sul disco: cancellarlo è una scelta dell'utente.
- Le regole di campo, i calcolati, i look-up e i set non sono attivi: le
  colonne esistono, la pipeline arriva con O4/O5.
- La password protegge l'accesso dall'applicazione, non cifra i file.

## 9. Accettazione

Coperta da `tests/test_records.py`:

- **Lezione 2** — creazione di un database dal Database Directory, un campo
  per tipo, salvataggio, comparsa del `.DBF`.
- **Lezione 4** — Enter records, salvataggio con F10, view del record,
  immissione continua con ENTER.
- **Lezione 5** — Change records, modifica e salvataggio.
- **Lezione 6** — cancellazione logica, F7, richiamo con Alt-U, PACK.

Test di supporto: `tests/test_fields.py` (tabella di conversione caso per
caso), `tests/test_workspace.py` (SQLite, import/export DBF, memo, password),
`tests/test_dbf.py` (intestazione). I rendering canonici sono in
`docs/render/07-view-records.png`, `08-browse-records.png`, `09-designer.png`.

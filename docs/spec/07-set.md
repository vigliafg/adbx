# O5 — Set e regioni

Un set presenta più database come una sola vista senza copiare i dati: il
database primario guida i record, i link aggiungono campi uno-a-uno e una
regione uno-a-molti mostra i figli. La definizione vive nel workspace SQLite
(`adbx_sets` + `adbx_set_links`); i `.DBF` restano la sorgente dei dati.

## 1. Definizione

`Database/set design → Set commands` offre:

- `Create a set design`: nome 1–8 caratteri, descrizione, database primario,
  poi l'editor.
- `Modify a set design`: sceglie un set esistente.
- `Erase a set design`: cancellazione con conferma.

`Choose database/set → Open a set` apre un set; `Switch databases` elenca
database e set. La status line mostra `Current set` e il percorso `.SET`.

Il set ha `Set Description`, `Primary Database`, `Show Mode`, `Filter` e
`Filter status` (default `Inactive`). Il filtro del set è valutato **prima**
del filtro del range; il range del database primario continua a controllare
ordine, prime/ultime chiavi e ricerca.

## 2. Link

L'editor ha l'albero in alto (primario e figli, con `->`) e i parametri del
link in basso. `F6` aggiunge un link dal database selezionato, `F5` lo
stacca insieme ai discendenti, `F7` apre la mappa di integrità, `F9` cambia
finestra, `F10` salva.

| Parametro | Valori |
|---|---|
| `Link from` | un database già presente nel set |
| `Linked Database/Set` | un database del workspace |
| `Linking Index` | indice del figlio (vuoto = record number) |
| `Common Field/Expression` | campo o espressione del genitore |
| `Link to?` | `First`, `Last`, `Closest`, `All` |
| `Can edit child database?` | `Yes`, `No`, `Prompt` |
| `Can add new records to child database?` | `Yes`, `No`, `Prompt` |
| `Referential Integrity?` | `No/Yes` |
| `Cascading Updates?` / `Cascading Deletes?` | visibili solo con integrità |
| `Include Parent If?` | `Always`, `Has Related Child`, `Has No Related Child` |
| `Show Mode` | `All`, `Deleted`, `Not deleted` |
| `Filter` / `Filter status` | espressione e interruttore |

`Closest` confronta le chiavi nell'ordine dell'indice: se non c'è il match
esatto prende il primo figlio con chiave **successiva**. `First`/`Last`
prendono il primo/ultimo match, `All` tutti (uno-a-molti).

Limiti verificati: massimo **10 database** per set, un database una sola
volta, un solo link `All` per genitore, endpoint raggiungibili dal primario,
indice di link esistente. Un figlio uno-a-molti può avere a sua volta figli
uno-a-uno (es. righe fattura → film), come nella lezione 22.

## 3. Integrità e cascading

La mappa di integrità collega campi del genitore a campi del figlio. Se non è
definita, il default mappa i campi omonimi; il campo comune viene aggiunto
alla mappa. Con `Referential Integrity` attiva:

- `Cascading Updates`: quando il genitore cambia i campi della mappa, i figli
  collegati ricevono i nuovi valori (usato per cambiare `INV_NO`).
- `Cascading Deletes`: cancellare o richiamare il genitore marca/richiama i
  figli collegati.

`SetDefinition.update_parent`, `delete_parent` e `undelete_parent` applicano
le regole e riscrivono i `.DBF` coinvolti.

## 4. Visualizzazione

`View/enter records` su un set apre `SetSession`:

- **View**: campi del primario e dei figli uno-a-uno, con i figli uno-a-molti
  in una regione separata. `F6` passa dal form alla regione figli; `UP/DOWN`
  scorrono i figli; `Alt-Z` apre il figlio in Browse; `Alt-D`/`Alt-U`
  cancellano/richiamano il genitore con cascata.
- **Browse**: tabella combinata dei campi del primario e dei figli uno-a-uno.
- **Enter/Change**: si modificano i campi del primario e dei figli uno-a-uno
  con `edit_child=Yes`; i figli uno-a-molti si modificano con lo zoom. Al
  salvataggio si aggiorna il genitore, si applicano i cascading updates e si
  aggiornano/creano i figli uno-a-uno. Obbligatorietà, validazione e lookup
  del primario vengono rieseguiti.

Le regole di campo dei figli non vengono applicate nella sessione set; il
form designer di O6 le userà nel layout definitivo.

## 5. Tasti

| Contesto | Tasto | Azione |
|---|---|---|
| Set Editor | `F5` | stacca link e discendenti |
| Set Editor | `F6` | aggiungi link dal database selezionato |
| Set Editor | `F7` | mappa di integrità |
| Set Editor | `F9` | passa tra albero e parametri |
| Set Editor | `F10` | salva |
| Set view | `F6` | passa a/da regione figli |
| Set view | `Alt-Z` | zoom sul figlio selezionato |
| Set view | `Alt-D`/`Alt-U` | delete/undelete con cascata |
| Set browse | `UP/DOWN` | record precedente/successivo |

## 6. Accettazione

`tests/test_sets.py` — persistenza, albero, `First/Last/All/Closest`,
filtri e show mode, campi combinati, integrità di default e custom, cascading
update/delete/undelete, include parent if, limiti e duplicati.

`tests/test_sets_ui.py` — creazione del set dal menu, scelta e modifica,
visualizzazione con regione figli e zoom, enter/change con cascata, erase,
switch e close.

Screenshot: `docs/render/18-set-editor.png`, `19-set-view.png`,
`20-set-browse.png`.

## 7. Deviazioni dichiarate

- I set non sono file `.SET` reali: la definizione è nel workspace SQLite.
- Il form designer personalizzato e le regioni con bordi/colori arrivano con
  O6; qui la regione figli ha un layout predefinito.
- I campi dei figli uno-a-uno annidati (figlio di un figlio uno-a-uno) non
  compaiono nel form combinato; sono raggiungibili via zoom con O6.
- `Can add new records... = Prompt` viene trattato come `Yes` nella sessione
  set, senza una finestra di conferma.
- I link verso un set (non un database) non sono ancora selezionabili.
- Enter/Change sui set applica le regole del primario, non quelle dei figli.

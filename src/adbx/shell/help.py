"""Sistema di aiuto contestuale.

I testi sono nostri (non copiati dal manuale), brevi e in inglese come il
resto dell'interfaccia. Il markup `[[etichetta|argomento]]` crea i rimandi
navigabili: l'utente li seleziona con le frecce e li apre con ENTER.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LINK_RE = re.compile(r"\[\[(.+?)\|(.+?)\]\]")
DEFAULT_WIDTH = 72


@dataclass(frozen=True)
class Topic:
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class LinkSpan:
    line: int
    column: int
    length: int
    target: str


@dataclass(frozen=True)
class Run:
    text: str
    target: str | None = None


def tokenize(text: str) -> list[Run]:
    """Divide una riga sorgente in parole, marcando le etichette-link."""
    runs: list[Run] = []
    position = 0
    for match in LINK_RE.finditer(text):
        if match.start() > position:
            runs.extend(Run(word) for word in text[position:match.start()].split())
        runs.extend(Run(word, match.group(2)) for word in match.group(1).split())
        position = match.end()
    if position < len(text):
        runs.extend(Run(word) for word in text[position:].split())
    return runs


def wrap(text: str, width: int = DEFAULT_WIDTH) -> list[list[Run]]:
    """Righe di parole con link conservati, lunghe al massimo `width`."""
    lines: list[list[Run]] = [[]]
    used = 0
    for run in tokenize(text):
        length = len(run.text)
        if used and used + 1 + length > width:
            lines.append([])
            used = 0
        if used:
            # Lo spazio tra due parole appartiene alla parola successiva
            # (o al link), così gli span restano contigui.
            run = Run(" " + run.text, run.target)
            length += 1
        lines[-1].append(run)
        used += length
    return lines


def wrap_topic(topic: Topic, width: int = DEFAULT_WIDTH) -> list[list[Run]]:
    wrapped: list[list[Run]] = []
    for source in topic.lines:
        if not source:
            wrapped.append([])
            continue
        wrapped.extend(wrap(source, width))
    return wrapped


def link_spans(lines: list[list[Run]]) -> list[LinkSpan]:
    """Span dei link, unendo le parole consecutive dello stesso rimando."""
    spans: list[LinkSpan] = []
    for row, runs in enumerate(lines):
        column = 0
        for run in runs:
            if run.target:
                previous = spans[-1] if spans else None
                if (previous is not None and previous.line == row
                        and previous.target == run.target
                        and previous.column + previous.length == column):
                    spans[-1] = LinkSpan(previous.line, previous.column,
                                         previous.length + len(run.text),
                                         previous.target)
                else:
                    spans.append(LinkSpan(row, column, len(run.text), run.target))
            column += len(run.text)
    return spans


TOPICS: dict[str, Topic] = {
    "main_menu": Topic("Alpha Four Main Menu", (
        "The main menu is the starting point for every command. Use UP and DOWN",
        "to move the highlight, ENTER to execute the highlighted command, or type",
        "the capital letter shown in the command name.",
        "",
        "Commands:",
        "  [[View/enter records|view]]       display and edit records",
        "  [[Print|print]]                   reports, labels, form letters",
        "  [[Search/sort lists|search]]      select and order records",
        "  [[Indexes/ranges|indexes]]        manage indexes and ranges",
        "  [[Global update/delete|global]]   mass updates and deletes",
        "  [[Choose database/set|choose]]    open or switch databases",
        "  [[Database/set design|design]]    create or modify definitions",
        "  [[Layouts|layouts]]               forms, browse, reports",
        "  [[Applications|applications]]     custom menu applications",
        "  [[Utilities|utilities]]           copy, pack, import, export",
        "  [[Other|other]]                   configuration and status",
        "  [[Quit|quit]]                     end the session",
        "",
        "Press F2 for the database structure, F3 for the status screen, or",
        "[[F1|help]] again for general help. ALT-F10 returns here from any screen.",
    )),
    "view": Topic("View/enter records", (
        "Display records from the current database or set: one record at a time",
        "in a form, or as a table in Browse mode.",
        "",
        "Choose [[View records|records]], [[Enter records|records]],",
        "[[Change records|records]] or [[Browse records|browse]] from the submenu.",
        "The status line shows the current mode and record number.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "records": Topic("Record modes", (
        "View shows one record at a time. ENTER in the submenu starts the mode.",
        "",
        "  UP/DOWN       previous/next record",
        "  TAB           forward ten records (SHIFT-TAB back ten)",
        "  CTRL-HOME/END first/last record",
        "  LEFT/RIGHT    previous/next field",
        "  F7            show or hide deleted records",
        "  ALT-D/ALT-U   mark or recall a record",
        "  ALT-M         open the memo editor",
        "  ALT-F5/F6     copy and paste a field",
        "  F10/ESC       return to the main menu",
        "",
        "In Change and Enter, TAB moves between fields; F10 saves the record and",
        "ESC discards it. The memo editor uses F10 to keep and ESC to cancel.",
        "",
        "[[Browse|browse]]   [[Back to main menu|main_menu]]",
    )),
    "browse": Topic("Browse records", (
        "Browse shows the database as a table: one row per record, one column",
        "per field. LEFT and RIGHT scroll the columns; UP and DOWN move the",
        "highlighted row; PAGE keys move a screen at a time.",
        "",
        "Alt-D marks a record for deletion and Alt-U recalls it; deleted rows are",
        "shown with an asterisk when Show deleted (F7) is on.",
        "",
        "[[Record modes|records]]   [[Back to main menu|main_menu]]",
    )),
    "memo": Topic("Memo editor", (
        "ALT-M opens the memo of the current memo field. The editor accepts",
        "normal text, ENTER starts a new line, and BACKSPACE/DELETE edit.",
        "",
        "F10 keeps the memo with the record; ESC leaves it unchanged. The memo is",
        "written when the record is saved.",
        "",
        "[[Record modes|records]]   [[Back to main menu|main_menu]]",
    )),
    "print": Topic("Print", (
        "Print reports, mail labels, forms, browse tables, and form letters to",
        "the screen, a printer, or a file.",
        "",
        "Layouts are created with the Layouts command; printing uses the layouts",
        "saved for the current database or set.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "global": Topic("Global update/delete", (
        "Update one or more fields, change case, delete or undelete records in",
        "the current database, all at once or only within a range.",
        "",
        "A new value can be a constant or an expression. Save the expressions to",
        "use them again, or run them once.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "choose": Topic("Choose database/set", (
        "Open a database or set, switch among the files of the current desktop,",
        "or manage desktops.",
        "",
        "[[Open a database|directory]] shows the Database Directory: select a",
        "file and press ENTER. Press W on the main menu to switch directly.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "design": Topic("Database/set design", (
        "Create, modify, rename, and erase databases and sets, and define field",
        "rules that control data entry.",
        "",
        "The [[table designer|designer]] defines up to 128 fields: name, type",
        "(C, N, D, L, M), length and decimal places. Changing a type converts the",
        "existing values with the conversion table of the manual.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "designer": Topic("Table designer", (
        "The designer edits the field list of a database.",
        "",
        "  TAB / SHIFT-TAB  next/previous column",
        "  UP / DOWN        previous/next field",
        "  F5 / F6          delete / insert a field",
        "  F10              save and continue",
        "  ESC              cancel",
        "",
        "Field names use A-Z, 0-9 and _, at most 10 characters. Character and",
        "numeric fields have an explicit length; Date, Logical and Memo have",
        "fixed lengths. A database holds at most 128 fields.",
        "",
        "[[Database design|design]]   [[Back to main menu|main_menu]]",
    )),
    "layouts": Topic("Layouts", (
        "Create and edit forms, browse tables, reports, mail labels, envelopes,",
        "and form letters for the current database or set.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "applications": Topic("Applications", (
        "Run or edit custom menu applications: your own menus that chain Alpha",
        "Four commands and scripts.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "scripts": Topic("Scripts", (
        "Scripts automate a sequence of keystrokes and commands. Press ALT-F3",
        "anywhere to open the Scripts menu, ALT-F4 to play a script, ALT-F1 to",
        "record the quick script UNTITLED, and ALT-F2 to play it.",
        "",
        "Keystroke scripts contain ordinary keys and commands in curly braces,",
        "for example {SET %NAME,\"Ada\"} or {IF %N>1,{{PLAY \"NEXT\"}}}.",
        "Dialog box scripts define Prompts, Buttons and Displays. Menu bar",
        "scripts replace the View or Browse menu of a form layout.",
        "",
        "CTRL-F1 through CTRL-F10 play the scripts CTRLF1..CTRLF10, or the names",
        "stored in %SYS_CTRLF1..%SYS_CTRLF10. A script named AUTOEXEC plays at",
        "startup; a script named like a database plus ! plays when it is opened.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "utilities": Topic("Utilities", (
        "Copy, append to, or summarize a database; pack or zap it; import and",
        "export data; cross-tabulate; post, join, intersect, or subtract files.",
        "",
        "Copy and summarize use the primary index and the current range. Append",
        "maps each master field to a field of the external database and offers",
        "All, Unique, Replace, and Mark unique. Cross Tabulation creates one row",
        "per key and one column per value, with an optional names database.",
        "",
        "Import and Export handle dBASE II/III/IV, character-separated ASCII and",
        "CSV, fixed-width ASCII, DIF, SYLK, Lotus WKS/WK1, WordPerfect merge, and",
        "MultiMate. F10 continues; F7 edits the range.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "other": Topic("Other", (
        "Configuration, information, and default settings: printer drivers,",
        "screen colors, date formats, and system information.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "quit": Topic("Quit", (
        "End the Alpha Four session and return to DOS.",
        "",
        "Always leave the program with Quit; closing the window in another way",
        "may lose data.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "directory": Topic("Database Directory", (
        "The Database Directory lists the databases (.DBF) and sets (.SET) in",
        "the current directory.",
        "",
        "Type a name, a drive/path, or a filter with * and ? and press ENTER.",
        "UP and DOWN move through the list; ENTER opens the highlighted entry.",
        "<Parent> moves to the parent directory; a sub-directory entry opens it.",
        "",
        "Function keys:",
        "  F3  Import        import a file from another format",
        "  F4  History       recently selected databases and sets",
        "  F5  Create Db     create a new database",
        "  F6  Refresh       re-read the directory",
        "  F8  Detail        show record and field counts",
        "  F9  DOS           temporary DOS access",
        "",
        "[[Help topics|help]]",
    )),
    "structure": Topic("Database structure", (
        "The structure screen lists the fields of the current database with",
        "type, width, and decimal places. PAGE DOWN shows the next page.",
        "",
        "F10 or ESC returns to the main menu.",
    )),
    "status": Topic("Status", (
        "The status screen summarises the current database or set: file, record",
        "count, fields, active index, selected form and browse table, range, and",
        "the printing configuration.",
        "",
        "F10 or ESC returns to the main menu.",
    )),
    "keys": Topic("Keyboard and mouse", (
        "F1 Help          F2 Database structure      F3 Status",
        "F4 History       F5 Create database         F6 Refresh",
        "F8 Detail        F9 DOS access              F10 Continue",
        "",
        "ALT-F10 returns to the main menu. ALT-F3 opens the Scripts menu.",
        "ESC cancels the current command; the right mouse button is equivalent.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "help": Topic("Using help", (
        "Help is contextual: pressing F1 on a menu command shows its topic.",
        "",
        "Highlighted phrases are links. Move the bar with UP and DOWN, then press",
        "ENTER to follow the link. ESC closes help; BACKSPACE returns to the",
        "previous topic.",
        "",
        "Topics:",
        "  [[Main menu|main_menu]]      [[Database Directory|directory]]",
        "  [[Keyboard and mouse|keys]]  [[Status|status]]  [[Structure|structure]]",
    )),
    "indexes": Topic("Indexes and ranges", (
        "An index orders records by an expression. Up to 15 indexes can be",
        "attached; only attached indexes are offered as primary index.",
        "",
        "  F2            field names in Table mode",
        "  F5 / F6       delete / insert a level",
        "  F10           continue, then create the index",
        "",
        "The index options are the expression, a description, a filter",
        "(records that fail it are not indexed), Allow (All, Unique, Unique",
        "with exceptions) and Case sensitive.",
        "",
        "In View and Browse, I selects the primary index, R opens the range",
        "settings. [[Ranges|ranges]]   [[Back to main menu|main_menu]]",
    )),
    "ranges": Topic("Range Settings", (
        "The range decides which records a command sees: primary index,",
        "ascending or descending order, deleted records, first and last key,",
        "unique keys and a filter expression.",
        "",
        "  F2            choose the primary index",
        "  F3            choose a key value for First/Last record",
        "  F7            retrieve the Default Range or a saved range",
        "  F10           continue (then Save or Exit)",
        "  ALT-E         exit and apply without saving",
        "",
        "[[Indexes|indexes]]   [[Back to main menu|main_menu]]",
    )),
    "forms": Topic("Forms", (
        "Layouts → Forms designs the screens used by View, Enter and Change.",
        "Choose a letter A-Z, a description and the form parameters; the saved",
        "form becomes active.",
        "",
        "In the layout F2 places a field at the cursor, F8 draws a box, F6 adds",
        "a one-to-many region on a set, F5 deletes the element under the cursor",
        "and F9 opens the formatting options (length, window, justification,",
        "format). F7 edits the description, custom menu, restricted commands",
        "and print parameters.",
        "",
        "PgUp/PgDn change page; a form can be up to 10 screens. Fields are",
        "visited in the order they were placed. A form for a set may contain",
        "fields from any database and a region for each one-to-many child.",
        "",
        "[[Sets|sets]]   [[Field rules|field_rules]]   "
        "[[Back to main menu|main_menu]]",
    )),
    "labels": Topic("Mail Labels", (
        "Layouts → Mail labels designs up to 26 label layouts (A-Z) for the",
        "current database or set. A layout is 10-78 columns wide and 1-20",
        "lines high; it prints up to six labels across, with adjustable gaps,",
        "copies per record, margins and continuous-feed or page mode.",
        "",
        "F2 places a field (memo fields are not allowed), F4 defines calculated",
        "fields, F9 justifies or inserts/deletes lines, Alt-O edits length,",
        "justification, format and decimals. The justification options include",
        "Suppress, Float, Trim, Join, Before and After: they move or suppress",
        "the text around a field, so a blank address line or a missing title",
        "does not leave gaps.",
        "",
        "Blank lines are suppressed automatically; CTRL-BACKSPACE (CHR 127)",
        "keeps one. F10 saves; Save and preview shows the labels and P/F10",
        "writes a PDF. Print → Mail labels prints a saved layout.",
        "",
        "[[Reports|reports]]   [[Letters|letters]]   "
        "[[Back to main menu|main_menu]]",
    )),
    "letters": Topic("Form Letters", (
        "Layouts → Letters edits a form letter template. Type the letter in the",
        "editor and insert fields with F2; a marker such as [FIRSTNAME.S] is",
        "replaced with the record value at print time. F3 inserts commands,",
        "F7 conditional paragraphs, F10 saves.",
        "",
        "Field options: S suppress, L/R/C align, D delete the line when the",
        "field is empty; numeric and date formats follow the report codes.",
        "Calculated fields use [{(expression)}.X$] syntax, prompted fields",
        "[?text].",
        "",
        "Commands: [.WIDTH n], [.LEFT n], [.TOP n], [.BOTTOM n], [.FILL+] /",
        "[.FILL-], [.EJECT], [.INCLUDE file], [@printer codes]. Conditionals:",
        "[.IF expr], [.ELSEIF expr], [.ELSE], [.ENDIF], nested up to five",
        "levels. Print → Letters previews or writes a PDF.",
        "",
        "[[Mail labels|labels]]   [[Reports|reports]]   "
        "[[Back to main menu|main_menu]]",
    )),
    "reports": Topic("Reports", (
        "Layouts → Reports designs up to 26 reports (A-Z) for the current",
        "database or set. A report can be up to 240 columns wide and use nine",
        "levels of grouping.",
        "",
        "Report Parameters define width, grouping levels, page breaks, blank",
        "lines, widows and orphans, margins and page length. Grouping",
        "Parameters choose the break field and whether headers and footers",
        "start a new page or substitute the page header/footer.",
        "",
        "The Report Layout is divided into sections: report header, page",
        "header, titles, group headers and footers, detail, page footer and",
        "summary. F2 places a field (Value, Unique or a summary type), F4",
        "defines calculated or summary fields, F3 adds and deletes sections,",
        "F9 justifies a line or inserts/deletes lines, Alt-O edits length,",
        "window, justification, format and decimals, F10 saves.",
        "",
        "Summary fields choose type First, Last, Count, Biggest, Smallest,",
        "Total or Average; level Grand, Page or Group n; ignore None, Empty,",
        "Zero or Both; mode Running or Pre-processed. F10 → Save and preview",
        "opens the preview; P or F10 writes a PDF.",
        "",
        "[[Forms|forms]]   [[Sets|sets]]   [[Back to main menu|main_menu]]",
    )),
    "sets": Topic("Sets", (
        "A set links up to 10 databases without copying their data. The",
        "primary database drives the records; links add one-to-one fields or a",
        "one-to-many child list.",
        "",
        "Create a set from Database/set design, Set commands. F6 adds a link",
        "from the selected database, F5 detaches it and F7 edits the integrity",
        "mapping. For each link choose the linking index, the common field or",
        "expression and Link to: First, Last, Closest or All.",
        "",
        "A one-to-many link (All) shows its children in a region; F6 switches",
        "between form and child region, Alt-Z zooms on a child. Referential",
        "integrity can cascade updates and deletes to child records.",
        "",
        "[[Field rules|field_rules]]   [[Back to main menu|main_menu]]",
    )),
    "field_rules": Topic("Field rules", (
        "Field rules control how values are entered and stored. In the upper",
        "window choose a field; F9 opens its rules, F5 deletes them.",
        "",
        "Page 1: Value (user-entered or calculated), expression, case",
        "conversion, template, mask, default value or expression, increment",
        "and auto-advance. Page 2: required, validation message, double entry,",
        "skip expression and post data. Page 3: lookup table or database,",
        "validation mode, window location and automatic pop-up.",
        "",
        "F7 edits the lookup table, mapping, cascade or conditional list.",
        "F8 edits the posting rules. F10 saves all rules. Re-evaluate applies",
        "calculations and case conversion to existing records.",
        "",
        "[[Indexes and ranges|indexes]]   [[Back to main menu|main_menu]]",
    )),
    "search": Topic("Search/sort lists", (
        "A search/sort list is a fixed list of record numbers selected by",
        "search criteria and ordered by sort criteria. It behaves like an",
        "index: while it is the primary index only its records are visible.",
        "",
        "Table mode compares case-insensitively and exactly; AND has precedence",
        "over OR. Expression mode accepts the full expression language and",
        "follows the Pattern matching setting.",
        "",
        "  F4 sort order   F7 use last   F9 expression   F10 continue",
        "",
        "A list becomes out of date when records or the saved criteria change;",
        "the status line marks it with a diamond. Refresh it with F5 in the",
        "history. [[Indexes|indexes]]   [[Back to main menu|main_menu]]",
    )),
}


def topic(topic_id: str) -> Topic:
    return TOPICS.get(topic_id, TOPICS["main_menu"])


__all__ = [
    "LINK_RE",
    "LinkSpan",
    "Run",
    "TOPICS",
    "Topic",
    "link_spans",
    "topic",
    "tokenize",
    "wrap",
    "wrap_topic",
]

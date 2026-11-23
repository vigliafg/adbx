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
        "In View and Browse you can enter new records and change existing ones.",
        "The status line shows the current mode and record number.",
        "",
        "[[Back to main menu|main_menu]]",
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
    "search": Topic("Search/sort lists", (
        "Search and/or sort the current database or set for records meeting",
        "specific criteria. The result is a list of record numbers, not a copy",
        "of the records.",
        "",
        "A search/sort list becomes the primary index; selecting another index",
        "turns it off. Saved criteria can be re-run later.",
        "",
        "[[Back to main menu|main_menu]]",
    )),
    "indexes": Topic("Indexes/ranges", (
        "Indexes control the order in which records are read. Ranges restrict",
        "which records are retrieved, by delete status, duplicates, or a filter",
        "expression.",
        "",
        "You can create, attach, detach, update, and erase indexes, and define up",
        "to 26 ranges per database or set.",
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
        "[[Back to main menu|main_menu]]",
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
    "utilities": Topic("Utilities", (
        "Copy, append to, or summarize a database; pack or zap it; import and",
        "export data; cross-tabulate; post, join, intersect, or subtract files.",
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

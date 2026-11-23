"""Generatore di documentazione (equivalente del programma A4DOC).

Produce Structure reports, Field Rules reports, Script reports e Application
reports in `ReportOutput`, pronti per l'anteprima o per il PDF.
"""

from __future__ import annotations

from pathlib import Path

from ..app.model import Application, outline
from ..config.printers import PrinterDriver
from ..data.report_engine import ReportOutput, ReportPage
from ..data.workspace import Database
from ..render.report_pdf import write_report_pdf
from ..script.model import MAX_SCRIPT_CHARS, Script
from ..script.parser import command_body, command_name, split_args, tokenize, unquote

DEFAULT_WIDTH = 80
DEFAULT_ROWS = 60


class DocumentationError(ValueError):
    """Documentazione impossibile."""


def _output(lines: list[str], *, title: str = "",
            width: int = DEFAULT_WIDTH,
            rows: int = DEFAULT_ROWS) -> ReportOutput:
    header = []
    if title:
        header = [title, "=" * min(width, len(title)), ""]
    body = header + lines
    per_page = max(1, rows - 4)
    pages = []
    for start in range(0, max(1, len(body)), per_page):
        chunk = body[start:start + per_page]
        number = len(pages) + 1
        pages.append(ReportPage(number, chunk + [
            "", f"Page {number}"]))
    if not pages:
        pages = [ReportPage(1, ["Page 1"])]
    return ReportOutput(pages, rows=len(body), width=width)


def database_structure(database: Database, *,
                       width: int = DEFAULT_WIDTH) -> ReportOutput:
    lines = [f"Database: {database.name}",
             f"Source: {database.source}",
             f"Fields: {len(database.fields)}  Records: {database.count()}",
             "",
             f"{'Number':>6}  {'Field name':<10} {'Type':<4} "
             f"{'Length':>6} {'Dec':>3}"]
    for index, field in enumerate(database.fields, 1):
        lines.append(f"{index:>6}  {field.name:<10} {field.type:<4} "
                     f"{field.length:>6} {field.decimals:>3}")
    lines.append("")
    lines.append(f"Record length: {database.record_length()} characters")
    return _output(lines, title=f"Structure of {database.name}", width=width)


def set_structure(definition, *, width: int = DEFAULT_WIDTH) -> ReportOutput:
    lines = [f"Set: {definition.name}",
             f"Description: {definition.description}",
             f"Primary database: {definition.primary}",
             f"Show mode: {definition.show_mode}",
             f"Databases: {', '.join(definition.database_names())}",
             "",
             "Links:"]
    if not definition.links:
        lines.append("  (none)")
    for link in definition.links:
        lines.append(
            f"  {link.parent} -> {link.child}   {link.link_to}")
        lines.append(f"    Index: {link.linking_index or '(none)'}   "
                     f"Common: {link.common or '(none)'}")
        lines.append(f"    Referential: {'Yes' if link.referential else 'No'}  "
                     f"Edit child: {link.edit_child}  "
                     f"Add child: {link.add_child}")
    lines.append("")
    for name in definition.database_names():
        lines.extend(database_structure(definition.database(name),
                                        width=width).pages[0].lines[:12])
        lines.append("")
    return _output(lines, title=f"Set structure {definition.name}", width=width)


def field_rules_report(database: Database, *,
                       by: str = "field",
                       width: int = DEFAULT_WIDTH) -> ReportOutput:
    rules = database.field_rules()
    lines = [f"Field rules for {database.name}", ""]
    if not rules:
        lines.append("(no field rules)")
    elif by == "type":
        groups: dict[str, list[str]] = {}
        for name, rule in sorted(rules.items()):
            for label in _rule_labels(rule):
                groups.setdefault(label, []).append(name)
        for label in sorted(groups):
            lines.append(label)
            for name in groups[label]:
                lines.append(f"    {name}")
    else:
        for name, rule in sorted(rules.items()):
            lines.append(name)
            for label in _rule_labels(rule):
                lines.append(f"    {label}")
            lines.append("")
    return _output(lines, title=f"Field rules {database.name}", width=width)


def _rule_labels(rule) -> list[str]:
    labels = []
    if rule.value == "Calculated":
        labels.append(f"Calculated: {rule.expression}")
    if rule.value == "Summary":
        labels.append(f"Summary: {rule.expression}")
    if rule.default_mode != "None":
        labels.append(f"Default ({rule.default_mode}): {rule.default}")
    if rule.increment != "None":
        labels.append(f"Increment: {rule.increment}")
    if rule.case != "None":
        labels.append(f"Case convert: {rule.case}")
    if rule.template:
        labels.append(f"Template: {rule.template}")
    if rule.mask:
        labels.append(f"Mask: {rule.mask}")
    if rule.required != "No":
        labels.append(f"Required: {rule.required_expression or 'Yes'}")
    if rule.validation:
        labels.append(f"Validation: {rule.validation}")
    if rule.double_entry != "No":
        labels.append(f"Double entry: {rule.double_entry}")
    if rule.skip_expression:
        labels.append(f"Skip: {rule.skip_expression}")
    if rule.post_data:
        labels.append("Post data: Yes")
    if rule.lookup:
        labels.append(f"Lookup: {rule.lookup_source}")
    return labels or ["No rules"]


def application_report(app: Application, *,
                       width: int = DEFAULT_WIDTH) -> ReportOutput:
    lines = [f"Application: {app.name}",
             f"Description: {app.description}",
             f"Startup database/set: {app.startup or '(current)'}",
             f"Startup macro: {app.startup_macro or '(none)'}",
             f"Script path: {app.script_path or '(default)'}",
             f"Banner: {'Yes' if app.banner_enabled else 'No'}",
             f"Allow escape: {app.allow_escape}",
             "", "Outline:"]
    for row in outline(app):
        indent = "  " * row.depth
        lines.append(indent + row.text)
        if row.kind == "item":
            item = row.item
            assert item is not None
            lines.append(indent + f"    Action: {item.action} "
                                  f"{item.target}")
            if item.macro:
                lines.append(indent + f"    Macro: {item.macro}")
            if item.password_hash:
                lines.append(indent + "    Password: Yes")
    return _output(lines, title=f"Application {app.name}", width=width)


def script_report(script: Script, *,
                  width: int = DEFAULT_WIDTH) -> ReportOutput:
    lines = [f"Script: {script.name}",
             f"Type: {script.kind_label}",
             f"Description: {script.description}",
             f"Size: {len(script.source)}/{MAX_SCRIPT_CHARS} characters",
             f"Screen test: {'Yes' if script.has_screen_test else 'No'}"]
    if script.screen_test.enabled:
        lines.append("  " + " | ".join(script.screen_test.lines))
    lines.extend(["", "Source:", script.source or "(empty)", "",
                  "Child scripts:"])
    children = _script_children(script.source)
    if not children:
        lines.append("  (none)")
    else:
        for depth, name in children:
            lines.append("  " * (depth + 1) + name)
    return _output(lines, title=f"Script {script.name}", width=width)


def _script_children(source: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    stack: list[int] = []
    for token in tokenize(source):
        if token.kind != "command":
            continue
        name = command_name(token.value)
        if name == "PLAY":
            try:
                parts = split_args(command_body(token.value))
                child = unquote(parts[0]) if parts else ""
            except (ValueError, IndexError):
                child = ""
            if child:
                result.append((len(stack), child))
        elif name in ("IF", "CASE", "ONKEY", "ONERROR", "ONESCAPE",
                      "ONMAIN", "ALLOWKEYS"):
            stack.append(len(token.value))
            stack.pop()
    return result


def write_document(output: ReportOutput, path: str | Path,
                   title: str, driver: PrinterDriver | None = None) -> Path:
    return write_report_pdf(output, path, title, driver=driver)


__all__ = [
    "DEFAULT_ROWS", "DEFAULT_WIDTH", "DocumentationError",
    "application_report", "database_structure", "field_rules_report",
    "script_report", "set_structure", "write_document",
]

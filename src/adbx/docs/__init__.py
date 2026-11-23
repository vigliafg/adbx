"""Generatore di documentazione di database, set, regole, script e app."""

from .generator import (
    DEFAULT_ROWS,
    DEFAULT_WIDTH,
    DocumentationError,
    application_report,
    database_structure,
    field_rules_report,
    script_report,
    set_structure,
    write_document,
)

__all__ = [
    "DEFAULT_ROWS", "DEFAULT_WIDTH", "DocumentationError",
    "application_report", "database_structure", "field_rules_report",
    "script_report", "set_structure", "write_document",
]

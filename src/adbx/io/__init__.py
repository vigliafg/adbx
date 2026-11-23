"""Import/export dei formati di scambio (O9)."""

from .common import ExportOptions, ImportOptions, TableData, infer_fields
from .formats import (
    FORMATS,
    FormatSpec,
    TransferResult,
    default_extension,
    export_from_database,
    import_into_workspace,
    read_table,
    spec_for,
    with_extension,
    write_table,
)

__all__ = [
    "FORMATS",
    "ExportOptions",
    "FormatSpec",
    "ImportOptions",
    "TableData",
    "TransferResult",
    "default_extension",
    "export_from_database",
    "import_into_workspace",
    "infer_fields",
    "read_table",
    "spec_for",
    "with_extension",
    "write_table",
]

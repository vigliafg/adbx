"""Accesso ai dati: per ora l'intestazione DBF, in O2 il motore SQLite."""

from .dbf import DbfError, DbfField, DbfHeader, read_header, record_count

__all__ = ["DbfError", "DbfField", "DbfHeader", "read_header", "record_count"]

"""Limpiador y validador de datos tabulares (CSV/Excel) con reglas para datos de Chile."""

from limpiador.cleaner import CleaningResult, clean_dataframe
from limpiador.schema import ColumnType, Schema

__all__ = ["CleaningResult", "ColumnType", "Schema", "clean_dataframe"]
__version__ = "0.1.0"

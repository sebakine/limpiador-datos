"""Lectura y escritura de archivos CSV y Excel."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from limpiador.validators import to_snake_case

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xls"}
_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


class UnsupportedFileError(ValueError):
    """El archivo no es CSV ni Excel."""


def detect_encoding(path: Path) -> str:
    """Prueba codificaciones comunes en archivos chilenos (UTF-8 y Windows-1252)."""
    sample = path.read_bytes()[:1_000_000]
    for encoding in _ENCODINGS:
        try:
            sample.decode(encoding)
        except UnicodeDecodeError:
            continue
        return encoding
    return "latin-1"  # pragma: no cover - latin-1 decodifica cualquier byte


def detect_delimiter(text: str) -> str:
    """Detecta el separador; en Chile Excel suele exportar con punto y coma."""
    try:
        return csv.Sniffer().sniff(text, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def read_table(path: Path, *, sheet: str | int = 0) -> pd.DataFrame:
    """Lee un CSV o Excel con todas las columnas como texto.

    Leer todo como texto evita que pandas transforme RUT o teléfonos en números
    y pierda ceros o el dígito verificador ``K``.
    """
    suffix = path.suffix.lower()
    if suffix in EXCEL_SUFFIXES:
        df = pd.read_excel(path, sheet_name=sheet, dtype=str)
    elif suffix in {".csv", ".txt", ".tsv"}:
        encoding = detect_encoding(path)
        with path.open(encoding=encoding, newline="") as fh:
            delimiter = detect_delimiter(fh.read(64_000))
        df = pd.read_csv(
            path,
            dtype=str,
            sep=delimiter,
            encoding=encoding,
            keep_default_na=False,
            skipinitialspace=True,
        )
    else:
        raise UnsupportedFileError(f"formato no soportado: {path.suffix or path.name}")
    df.columns = _unique_names([to_snake_case(c) for c in df.columns])
    return df


def write_table(df: pd.DataFrame, path: Path) -> None:
    """Escribe el resultado en CSV (UTF-8) o Excel según la extensión."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in EXCEL_SUFFIXES:
        df.to_excel(path, index=False)
    elif path.suffix.lower() == ".csv":
        df.to_csv(path, index=False, encoding="utf-8")
    else:
        raise UnsupportedFileError(f"formato de salida no soportado: {path.suffix}")


def _unique_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for name in names:
        count = seen.get(name, 0)
        result.append(name if count == 0 else f"{name}_{count + 1}")
        seen[name] = count + 1
    return result

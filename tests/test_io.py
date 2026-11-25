from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from limpiador.io import (
    UnsupportedFileError,
    detect_delimiter,
    detect_encoding,
    read_table,
    write_table,
)


def test_reads_semicolon_cp1252_and_normalizes_headers(csv_semicolon_cp1252: Path) -> None:
    df = read_table(csv_semicolon_cp1252)
    assert list(df.columns) == ["rut_cliente", "telefono", "fecha_de_compra", "monto"]
    assert df.loc[0, "rut_cliente"] == "12.345.678-5"
    assert detect_encoding(csv_semicolon_cp1252) == "cp1252"


def test_keeps_leading_zeros_as_text(tmp_path: Path) -> None:
    path = tmp_path / "a.csv"
    path.write_text("codigo,telefono\n00123,0223456789\n", encoding="utf-8")
    df = read_table(path)
    assert df.loc[0, "codigo"] == "00123"
    assert df.loc[0, "telefono"] == "0223456789"


def test_duplicate_headers_get_suffix(tmp_path: Path) -> None:
    path = tmp_path / "a.csv"
    path.write_text("Email,email,E-mail\na,b,c\n", encoding="utf-8")
    assert list(read_table(path).columns) == ["email", "email_2", "e_mail"]


def test_excel_roundtrip(tmp_path: Path) -> None:
    df = pd.DataFrame({"RUT": ["12345678-5"], "Monto": ["1.000"]})
    path = tmp_path / "datos.xlsx"
    df.to_excel(path, index=False)
    read = read_table(path)
    assert list(read.columns) == ["rut", "monto"]
    out = tmp_path / "salida" / "limpio.xlsx"
    write_table(read, out)
    assert out.exists()


def test_write_csv(tmp_path: Path) -> None:
    out = tmp_path / "x.csv"
    write_table(pd.DataFrame({"a": [1]}), out)
    assert out.read_text(encoding="utf-8").splitlines() == ["a", "1"]


@pytest.mark.parametrize("name", ["datos.json", "sin_extension"])
def test_unsupported_input(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(UnsupportedFileError):
        read_table(path)


def test_unsupported_output(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFileError):
        write_table(pd.DataFrame(), tmp_path / "x.parquet")


def test_delimiter_fallback() -> None:
    assert detect_delimiter("una sola columna") == ","
    assert detect_delimiter("a;b;c\n1;2;3\n") == ";"

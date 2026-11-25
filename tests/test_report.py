from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from limpiador import clean_dataframe
from limpiador.report import write_report


def test_excel_report_has_three_sheets(tmp_path: Path, dirty_df: pd.DataFrame) -> None:
    path = tmp_path / "reporte.xlsx"
    write_report(clean_dataframe(dirty_df), path, source="clientes.csv")
    sheets = pd.read_excel(path, sheet_name=None)
    assert set(sheets) == {"Resumen", "Anomalías", "Columnas"}
    assert len(sheets["Anomalías"]) == len(clean_dataframe(dirty_df).anomalies)


def test_html_report_escapes_values(tmp_path: Path) -> None:
    df = pd.DataFrame({"email": ["<script>alert(1)</script>"]})
    path = tmp_path / "reporte.html"
    write_report(clean_dataframe(df), path, source="x.csv")
    html = path.read_text(encoding="utf-8")
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "email_invalido" in html


def test_html_report_without_anomalies(tmp_path: Path) -> None:
    path = tmp_path / "r.html"
    write_report(clean_dataframe(pd.DataFrame({"rut": ["1-9"]})), path, source="x.csv")
    assert "No se encontraron anomalías" in path.read_text(encoding="utf-8")


def test_html_report_truncates(tmp_path: Path) -> None:
    from limpiador.report import write_html_report

    df = pd.DataFrame({"rut": ["x"] * 5})
    path = tmp_path / "r.html"
    write_html_report(clean_dataframe(df), path, source="x.csv", max_rows=2)
    assert "primeras 2 de" in path.read_text(encoding="utf-8")


def test_unknown_report_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\.xlsx o \.html"):
        write_report(clean_dataframe(pd.DataFrame({"a": ["1"]})), tmp_path / "r.pdf", source="x")

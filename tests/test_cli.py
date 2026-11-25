from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from limpiador import __version__
from limpiador.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_limpiar_end_to_end(tmp_path: Path, csv_semicolon_cp1252: Path) -> None:
    out = tmp_path / "limpio.csv"
    report = tmp_path / "reporte.html"
    result = runner.invoke(
        app, ["limpiar", str(csv_semicolon_cp1252), "-o", str(out), "-r", str(report)]
    )
    assert result.exit_code == 0, result.output
    cleaned = pd.read_csv(out, dtype=str)
    assert cleaned.to_dict("records") == [
        {
            "rut_cliente": "12345678-5",
            "telefono": "+56987654321",
            "fecha_de_compra": "2024-02-01",
            "monto": "1500.0",
        }
    ]
    assert report.exists()
    assert "Duplicados eliminados" in result.output


def test_default_output_name(csv_semicolon_cp1252: Path) -> None:
    result = runner.invoke(app, ["limpiar", str(csv_semicolon_cp1252)])
    assert result.exit_code == 0, result.output
    assert (csv_semicolon_cp1252.parent / "ventas_limpio.csv").exists()


def test_estricto_fails_when_there_are_anomalies(csv_semicolon_cp1252: Path) -> None:
    result = runner.invoke(app, ["limpiar", str(csv_semicolon_cp1252), "--estricto"])
    assert result.exit_code == 1


def test_esquema(tmp_path: Path, csv_semicolon_cp1252: Path) -> None:
    schema = tmp_path / "esquema.toml"
    schema.write_text('unique_keys = ["rut_cliente"]\n', encoding="utf-8")
    result = runner.invoke(app, ["limpiar", str(csv_semicolon_cp1252), "-e", str(schema)])
    assert result.exit_code == 0, result.output


def test_invalid_esquema(tmp_path: Path, csv_semicolon_cp1252: Path) -> None:
    schema = tmp_path / "esquema.toml"
    schema.write_text('[columns]\nrut_cliente = "otro"\n', encoding="utf-8")
    result = runner.invoke(app, ["limpiar", str(csv_semicolon_cp1252), "-e", str(schema)])
    assert result.exit_code == 2
    assert "Esquema inválido" in result.output


def test_esquema_with_unknown_column(tmp_path: Path, csv_semicolon_cp1252: Path) -> None:
    schema = tmp_path / "esquema.toml"
    schema.write_text('required = ["no_existe"]\n', encoding="utf-8")
    result = runner.invoke(app, ["limpiar", str(csv_semicolon_cp1252), "-e", str(schema)])
    assert result.exit_code == 2


def test_unsupported_file(tmp_path: Path) -> None:
    path = tmp_path / "x.json"
    path.write_text("{}", encoding="utf-8")
    result = runner.invoke(app, ["perfilar", str(path)])
    assert result.exit_code == 2


def test_perfilar(csv_semicolon_cp1252: Path) -> None:
    result = runner.invoke(app, ["perfilar", str(csv_semicolon_cp1252)])
    assert result.exit_code == 0, result.output
    assert "rut_cliente" in result.output
    assert "fecha" in result.output


def test_excel_sheet_by_number(tmp_path: Path) -> None:
    path = tmp_path / "x.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"a": ["1"]}).to_excel(writer, sheet_name="Otra", index=False)
        pd.DataFrame({"rut": ["1-9"]}).to_excel(writer, sheet_name="Clientes", index=False)
    result = runner.invoke(app, ["perfilar", str(path), "--hoja", "1"])
    assert result.exit_code == 0, result.output
    assert "rut" in result.output


def test_ejemplo_then_limpiar(tmp_path: Path) -> None:
    sample = tmp_path / "sucio.csv"
    result = runner.invoke(app, ["ejemplo", str(sample), "--filas", "50", "--semilla", "1"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["limpiar", str(sample), "-r", str(tmp_path / "r.xlsx")])
    assert result.exit_code == 0, result.output

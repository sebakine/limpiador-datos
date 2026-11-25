from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from limpiador import ColumnType, Schema, clean_dataframe
from limpiador.cleaner import is_missing
from limpiador.validators import Issue


def issues(result: object) -> set[tuple[int, str, str]]:
    return {(a.row, a.column, a.issue.value) for a in result.anomalies}  # type: ignore[attr-defined]


def test_normalizes_every_type(dirty_df: pd.DataFrame) -> None:
    result = clean_dataframe(dirty_df)
    first = result.data.iloc[0]
    assert first["rut"] == "12345678-5"
    assert first["nombre"] == "Juan Pérez"
    assert first["email"] == "juan@mail.cl"
    assert first["telefono"] == "+56987654321"
    assert first["fecha"] == date(2024, 2, 1)
    assert first["monto"] == 1234567.0


def test_reports_anomalies_with_file_row_numbers(dirty_df: pd.DataFrame) -> None:
    found = issues(clean_dataframe(dirty_df))
    assert (4, "rut", "rut_digito_verificador") in found
    assert (5, "rut", "rut_invalido") in found
    assert (4, "email", "email_invalido") in found
    assert (4, "telefono", "telefono_invalido") in found
    assert (5, "fecha", "fecha_invalida") in found
    assert (4, "monto", "numero_invalido") in found


def test_identical_rows_after_normalization_are_dropped(dirty_df: pd.DataFrame) -> None:
    result = clean_dataframe(dirty_df)
    # Las filas 2 y 3 del archivo son la misma persona escrita distinto.
    assert result.duplicates_removed == 1
    assert result.rows_in == 5
    assert result.rows_out == 4
    assert (3, "(fila)", "fila_duplicada") in issues(result)


def test_duplicates_by_key() -> None:
    df = pd.DataFrame({"rut": ["1-9", "1-9", "", ""], "monto": ["10", "20", "30", "40"]})
    result = clean_dataframe(df, Schema(unique_keys=["rut"]))
    assert result.rows_out == 3  # las filas sin RUT no se consideran duplicadas entre sí
    dup = next(a for a in result.anomalies if a.issue is Issue.DUPLICATE)
    assert dup.detail == "repite la clave (rut) de la fila 2"


def test_required_columns() -> None:
    df = pd.DataFrame({"rut": ["1-9", "N/A"], "email": ["", ""]})
    result = clean_dataframe(df, Schema(required=["rut"]))
    assert issues(result) == {(3, "rut", "valor_faltante")}


def test_invalid_values_become_empty_but_original_is_reported() -> None:
    df = pd.DataFrame({"rut": ["abc"]})
    result = clean_dataframe(df)
    assert pd.isna(result.data.loc[0, "rut"])
    assert result.anomalies[0].value == "abc"


def test_unknown_schema_columns_raise() -> None:
    with pytest.raises(KeyError, match="no_existe"):
        clean_dataframe(pd.DataFrame({"a": ["1"]}), Schema(required=["no_existe"]))


def test_schema_type_override() -> None:
    df = pd.DataFrame({"codigo": ["12.345.678-5"]})
    result = clean_dataframe(df, Schema(columns={"codigo": ColumnType.RUT}))
    assert result.data.loc[0, "codigo"] == "12345678-5"
    assert result.column_types["codigo"] is ColumnType.RUT


def test_counters_and_frame(dirty_df: pd.DataFrame) -> None:
    result = clean_dataframe(dirty_df)
    assert result.changed_cells > 0
    assert sum(result.anomalies_by_issue.values()) == len(result.anomalies)
    assert sum(result.anomalies_by_column.values()) == len(result.anomalies)
    frame = result.anomalies_frame()
    assert list(frame.columns) == ["fila", "columna", "problema", "valor_original", "detalle"]
    assert frame["fila"].is_monotonic_increasing


@pytest.mark.parametrize("value", [None, float("nan"), "", " NA ", "null", "-", "S/I"])
def test_is_missing(value: object) -> None:
    assert is_missing(value)


def test_clean_input_has_no_anomalies() -> None:
    df = pd.DataFrame({"rut": ["12345678-5"], "email": ["a@b.cl"]})
    result = clean_dataframe(df)
    assert result.anomalies == []
    assert result.changed_cells == 0

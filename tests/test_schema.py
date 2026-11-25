from __future__ import annotations

from pathlib import Path

import pytest

from limpiador.schema import ColumnType, Schema, infer_type


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("rut_cliente", ColumnType.RUT),
        ("run", ColumnType.RUT),
        ("correo", ColumnType.EMAIL),
        ("telefono_contacto", ColumnType.PHONE),
        ("fecha_de_compra", ColumnType.DATE),
        ("monto_total", ColumnType.AMOUNT),
        ("nombre", ColumnType.NAME),
        ("comuna", ColumnType.TEXT),
        ("trust", ColumnType.TEXT),  # contiene "rut" pero no como palabra
    ],
)
def test_infer_type(column: str, expected: ColumnType) -> None:
    assert infer_type(column) is expected


def test_explicit_columns_override_inference() -> None:
    schema = Schema(columns={"codigo": ColumnType.RUT})
    assert schema.resolve(["codigo", "email"]) == {
        "codigo": ColumnType.RUT,
        "email": ColumnType.EMAIL,
    }


def test_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "esquema.toml"
    path.write_text(
        'required = ["rut"]\nunique_keys = ["rut"]\ndayfirst = false\n'
        '[columns]\ncodigo = "rut"\nglosa = "texto"\n',
        encoding="utf-8",
    )
    schema = Schema.from_toml(path)
    assert schema.columns == {"codigo": ColumnType.RUT, "glosa": ColumnType.TEXT}
    assert schema.required == ["rut"]
    assert schema.unique_keys == ["rut"]
    assert schema.dayfirst is False


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"columns": {"a": "desconocido"}}, "tipo desconocido"),
        ({"columns": ["a"]}, "'columns' debe ser una tabla"),
        ({"required": "rut"}, "'required' debe ser una lista"),
        ({"unique_keys": [1]}, "'unique_keys' debe ser una lista"),
    ],
)
def test_invalid_mapping(data: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Schema.from_mapping(data)

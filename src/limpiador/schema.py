"""Definición de qué tipo de dato contiene cada columna.

El esquema puede escribirse en un archivo TOML o inferirse a partir de los
nombres de las columnas (``rut``, ``telefono``, ``email``, ``fecha_*``...).
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class ColumnType(StrEnum):
    """Tipos semánticos de columna que el limpiador sabe normalizar."""

    RUT = "rut"
    PHONE = "telefono"
    EMAIL = "email"
    DATE = "fecha"
    AMOUNT = "monto"
    NAME = "nombre"
    TEXT = "texto"


# Orden importa: la primera regla que calza gana.
_INFERENCE_RULES: tuple[tuple[re.Pattern[str], ColumnType], ...] = (
    (re.compile(r"(^|_)(rut|run)(_|$)"), ColumnType.RUT),
    (re.compile(r"(^|_)(email|correo|mail|e_mail)(_|$)"), ColumnType.EMAIL),
    (re.compile(r"(^|_)(telefono|fono|celular|movil|phone|whatsapp)(_|$)"), ColumnType.PHONE),
    (re.compile(r"(^|_)(fecha|date|nacimiento|vencimiento)(_|$)"), ColumnType.DATE),
    (
        re.compile(r"(^|_)(monto|precio|total|valor|importe|neto|iva|amount|price)(_|$)"),
        ColumnType.AMOUNT,
    ),
    (re.compile(r"(^|_)(nombre|apellido|cliente|name)(_|$)"), ColumnType.NAME),
)


def infer_type(column: str) -> ColumnType:
    """Deduce el tipo de una columna (ya en snake_case) a partir de su nombre."""
    for pattern, column_type in _INFERENCE_RULES:
        if pattern.search(column):
            return column_type
    return ColumnType.TEXT


@dataclass(slots=True)
class Schema:
    """Reglas de limpieza para un archivo.

    Attributes:
        columns: tipo de cada columna. Las columnas que no aparecen se infieren.
        required: columnas que no pueden venir vacías.
        unique_keys: columnas que identifican una fila; se usan para detectar
            duplicados además de las filas idénticas.
        dayfirst: si las fechas vienen como día/mes/año (formato chileno).
    """

    columns: dict[str, ColumnType] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    unique_keys: list[str] = field(default_factory=list)
    dayfirst: bool = True

    def resolve(self, columns: Iterable[str]) -> dict[str, ColumnType]:
        """Devuelve el tipo de todas las columnas, inferendo las que faltan."""
        return {c: self.columns.get(c, infer_type(c)) for c in columns}

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> Schema:
        raw_columns = data.get("columns", {})
        if not isinstance(raw_columns, Mapping):
            raise ValueError("'columns' debe ser una tabla de nombre = tipo")
        valid = {t.value for t in ColumnType}
        columns: dict[str, ColumnType] = {}
        for name, value in raw_columns.items():
            if value not in valid:
                raise ValueError(
                    f"tipo desconocido {value!r} para la columna {name!r}; "
                    f"usa uno de: {', '.join(sorted(valid))}"
                )
            columns[str(name)] = ColumnType(value)
        return cls(
            columns=columns,
            required=_str_list(data.get("required", []), "required"),
            unique_keys=_str_list(data.get("unique_keys", []), "unique_keys"),
            dayfirst=bool(data.get("dayfirst", True)),
        )

    @classmethod
    def from_toml(cls, path: Path) -> Schema:
        with path.open("rb") as fh:
            return cls.from_mapping(tomllib.load(fh))


def _str_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"'{key}' debe ser una lista de nombres de columna")
    return list(value)

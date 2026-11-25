"""Limpieza de un DataFrame completo según un :class:`~limpiador.schema.Schema`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from functools import partial

import pandas as pd

from limpiador import validators as v
from limpiador.schema import ColumnType, Schema

#: Valores que se consideran celdas vacías.
MISSING_TOKENS = frozenset(
    {"", "na", "n/a", "nan", "null", "none", "nulo", "-", "--", "s/i", "sin dato"}
)

#: Desfase entre el índice del DataFrame y la fila que ve el usuario en el archivo
#: (la fila 1 es el encabezado).
HEADER_OFFSET = 2

Normalizer = Callable[[str], v.Outcome]


@dataclass(frozen=True, slots=True)
class Anomaly:
    """Un problema encontrado en una celda o fila."""

    row: int
    column: str
    issue: v.Issue
    value: str
    detail: str


@dataclass(slots=True)
class CleaningResult:
    """Salida de :func:`clean_dataframe`."""

    data: pd.DataFrame
    anomalies: list[Anomaly]
    column_types: dict[str, ColumnType]
    rows_in: int
    changed_cells: int = 0
    duplicates_removed: int = 0

    @property
    def rows_out(self) -> int:
        return len(self.data)

    @property
    def anomalies_by_issue(self) -> dict[str, int]:
        return dict(Counter(a.issue.value for a in self.anomalies).most_common())

    @property
    def anomalies_by_column(self) -> dict[str, int]:
        return dict(Counter(a.column for a in self.anomalies).most_common())

    def anomalies_frame(self) -> pd.DataFrame:
        """Anomalías como tabla, ordenadas por fila."""
        columns = ["fila", "columna", "problema", "valor_original", "detalle"]
        rows = [(a.row, a.column, a.issue.value, a.value, a.detail) for a in self.anomalies]
        return pd.DataFrame(rows, columns=columns).sort_values(["fila", "columna"], kind="stable")


def _normalizer_for(column_type: ColumnType, schema: Schema) -> Normalizer:
    match column_type:
        case ColumnType.RUT:
            return v.normalize_rut
        case ColumnType.PHONE:
            return v.normalize_phone_cl
        case ColumnType.EMAIL:
            return v.normalize_email
        case ColumnType.DATE:
            return partial(v.normalize_date, dayfirst=schema.dayfirst)
        case ColumnType.AMOUNT:
            return v.normalize_amount
        case ColumnType.NAME:
            return v.normalize_name
        case ColumnType.TEXT:
            return v.normalize_text


def is_missing(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    return str(value).strip().lower() in MISSING_TOKENS


def clean_dataframe(df: pd.DataFrame, schema: Schema | None = None) -> CleaningResult:
    """Normaliza cada columna, registra anomalías y elimina filas duplicadas.

    Las celdas que no se pueden normalizar quedan vacías en el resultado y el
    valor original se conserva en el reporte de anomalías, para que nadie pierda
    información sin saberlo.
    """
    schema = schema or Schema()
    unknown = [c for c in [*schema.required, *schema.unique_keys] if c not in df.columns]
    if unknown:
        raise KeyError(f"columnas del esquema que no están en el archivo: {', '.join(unknown)}")

    types = schema.resolve(df.columns)
    anomalies: list[Anomaly] = []
    changed = 0
    cleaned: dict[str, list[object]] = {}

    for column, column_type in types.items():
        normalize = _normalizer_for(column_type, schema)
        required = column in schema.required
        out: list[object] = []
        for idx, raw in zip(df.index, df[column], strict=True):
            row = int(idx) + HEADER_OFFSET
            if is_missing(raw):
                if required:
                    anomalies.append(
                        Anomaly(row, column, v.Issue.MISSING, "", "columna obligatoria vacía")
                    )
                out.append(None)
                continue
            text = str(raw)
            outcome = normalize(text)
            if outcome.issue is not None:
                anomalies.append(Anomaly(row, column, outcome.issue, text, outcome.detail))
            if outcome.value is not None and str(outcome.value) != text:
                changed += 1
            out.append(outcome.value)
        cleaned[column] = out

    result = pd.DataFrame(cleaned, index=df.index)
    result = _apply_dtypes(result, types)
    result, duplicate_anomalies = _drop_duplicates(result, schema.unique_keys)
    anomalies.extend(duplicate_anomalies)

    return CleaningResult(
        data=result.reset_index(drop=True),
        anomalies=anomalies,
        column_types=types,
        rows_in=len(df),
        changed_cells=changed,
        duplicates_removed=len(duplicate_anomalies),
    )


def _apply_dtypes(df: pd.DataFrame, types: dict[str, ColumnType]) -> pd.DataFrame:
    for column, column_type in types.items():
        if column_type is ColumnType.AMOUNT:
            df[column] = pd.array(
                [float(x) if isinstance(x, Decimal) else None for x in df[column]],
                dtype="Float64",
            )
        elif column_type is ColumnType.DATE:
            df[column] = df[column].astype("object")
        else:
            df[column] = df[column].astype("string")
    return df


def _drop_duplicates(
    df: pd.DataFrame, unique_keys: list[str]
) -> tuple[pd.DataFrame, list[Anomaly]]:
    """Elimina filas idénticas y, si hay claves, filas que repiten la clave."""
    anomalies: list[Anomaly] = []
    subsets: list[tuple[list[str] | None, str]] = [(None, "fila idéntica a la fila {first}")]
    if unique_keys:
        keys = ", ".join(unique_keys)
        subsets.append((unique_keys, f"repite la clave ({keys}) de la fila {{first}}"))

    for subset, message in subsets:
        frame = df if subset is None else df[subset]
        # Una clave incompleta no identifica la fila: no se usa para deduplicar.
        comparable = frame.notna().all(axis=1) if subset else pd.Series(True, index=df.index)
        keyed = frame[comparable].astype("string").fillna("\x00")
        dup_mask = keyed.duplicated(keep="first")
        if not dup_mask.any():
            continue
        first_seen = keyed.groupby(list(keyed.columns), sort=False, dropna=False).head(1)
        first_row = {
            tuple(r): int(i)
            for i, r in zip(first_seen.index, first_seen.itertuples(index=False), strict=True)
        }
        for idx in keyed.index[dup_mask]:
            first = first_row[tuple(keyed.loc[idx])] + HEADER_OFFSET
            anomalies.append(
                Anomaly(
                    int(idx) + HEADER_OFFSET,
                    "(fila)" if subset is None else ",".join(subset),
                    v.Issue.DUPLICATE,
                    "",
                    message.format(first=first),
                )
            )
        df = df.drop(index=keyed.index[dup_mask])
    return df, anomalies

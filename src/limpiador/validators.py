"""Normalizadores y validadores de valores individuales.

Cada función recibe un valor crudo y devuelve un :class:`Outcome` con el valor
normalizado (o ``None`` si no se pudo normalizar) y, cuando corresponde, el
problema encontrado. Son funciones puras, sin dependencias de pandas, para que
sean fáciles de probar y reutilizar.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class Issue(StrEnum):
    """Tipos de anomalía que puede reportar un validador."""

    INVALID_RUT = "rut_invalido"
    RUT_CHECK_DIGIT = "rut_digito_verificador"
    INVALID_PHONE = "telefono_invalido"
    INVALID_EMAIL = "email_invalido"
    INVALID_DATE = "fecha_invalida"
    AMBIGUOUS_DATE = "fecha_ambigua"
    INVALID_NUMBER = "numero_invalido"
    MISSING = "valor_faltante"
    DUPLICATE = "fila_duplicada"


@dataclass(frozen=True, slots=True)
class Outcome:
    """Resultado de normalizar un valor."""

    value: object | None
    issue: Issue | None = None
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.issue is None


# ---------------------------------------------------------------------------
# RUT chileno
# ---------------------------------------------------------------------------

_RUT_CLEAN = re.compile(r"[.\s-]")
_RUT_SHAPE = re.compile(r"^(\d{1,8})([\dK])$")


def rut_check_digit(body: int) -> str:
    """Calcula el dígito verificador de un RUT con el algoritmo módulo 11."""
    total, factor = 0, 2
    for digit in reversed(str(body)):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    remainder = 11 - (total % 11)
    return {11: "0", 10: "K"}.get(remainder, str(remainder))


def normalize_rut(raw: str) -> Outcome:
    """Normaliza un RUT al formato ``12345678-5`` y valida su dígito verificador."""
    compact = _RUT_CLEAN.sub("", raw).upper()
    match = _RUT_SHAPE.match(compact)
    if not match:
        return Outcome(None, Issue.INVALID_RUT, f"formato no reconocido: {raw!r}")
    body, dv = int(match.group(1)), match.group(2)
    expected = rut_check_digit(body)
    if dv != expected:
        return Outcome(
            None,
            Issue.RUT_CHECK_DIGIT,
            f"dígito verificador {dv}, se esperaba {expected}",
        )
    return Outcome(f"{body}-{dv}")


# ---------------------------------------------------------------------------
# Teléfonos de Chile
# ---------------------------------------------------------------------------

_NON_DIGITS = re.compile(r"\D")


def normalize_phone_cl(raw: str) -> Outcome:
    """Normaliza un teléfono chileno a formato E.164 (``+56912345678``).

    Acepta móviles (9 dígitos que empiezan con 9) y fijos (9 dígitos con código
    de área), con o sin prefijo ``+56``/``56``/``0``.
    """
    digits = _NON_DIGITS.sub("", raw)
    if digits.startswith("56") and len(digits) == 11:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 10:
        digits = digits[1:]
    if len(digits) == 8 and digits[0] in "3456789":
        # Móvil antiguo de 8 dígitos sin el 9 inicial.
        digits = "9" + digits
    if len(digits) != 9 or digits[0] not in "2345679":
        return Outcome(None, Issue.INVALID_PHONE, f"no es un teléfono chileno válido: {raw!r}")
    return Outcome(f"+56{digits}")


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")


def normalize_email(raw: str) -> Outcome:
    """Pasa el email a minúsculas, quita espacios y valida su forma."""
    value = raw.strip().lower().replace(" ", "")
    if ".." in value or not _EMAIL.match(value):
        return Outcome(None, Issue.INVALID_EMAIL, f"email mal formado: {raw!r}")
    return Outcome(value)


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

_DATE_FORMATS_DMY = ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y")
_DATE_FORMATS_OTHER = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")
_MONTHS_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip
_TEXT_DATE = re.compile(r"^(\d{1,2})\s*(?:de\s+)?([a-záéíóú]+)\.?\s*(?:de\s+|del\s+)?(\d{4})$")


def normalize_date(raw: object, *, dayfirst: bool = True) -> Outcome:
    """Convierte fechas en formatos comunes de Chile a ``date``.

    El formato chileno es día/mes/año, por eso ``dayfirst`` es verdadero por
    defecto. Cuando día y mes son ambos menores o iguales a 12 y el archivo
    podría venir en formato estadounidense, se reporta como ambigua solo si
    ``dayfirst`` es falso.
    """
    if isinstance(raw, datetime):
        return Outcome(raw.date())
    if isinstance(raw, date):
        return Outcome(raw)
    text = str(raw).strip().lower()
    for fmt in _DATE_FORMATS_OTHER:
        try:
            return Outcome(datetime.strptime(text, fmt).date())
        except ValueError:
            continue
    for fmt in _DATE_FORMATS_DMY:
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        if not dayfirst and parsed.day <= 12 and parsed.day != parsed.month:
            return Outcome(parsed, Issue.AMBIGUOUS_DATE, f"día y mes intercambiables: {raw!r}")
        return Outcome(parsed)
    match = _TEXT_DATE.match(_strip_accents(text))
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS_ES.get(month_name[:3])
        if month:
            try:
                return Outcome(date(int(year), month, int(day)))
            except ValueError:
                pass
    return Outcome(None, Issue.INVALID_DATE, f"fecha no reconocida: {raw!r}")


# ---------------------------------------------------------------------------
# Montos y números
# ---------------------------------------------------------------------------

_CURRENCY = re.compile(r"(?i)(clp|usd|us\$|\$|pesos?)")


def normalize_amount(raw: object) -> Outcome:
    """Convierte montos como ``$1.234.567``, ``1.234,50`` o ``1,234.50`` a ``Decimal``.

    En Chile el punto separa miles y la coma los decimales. Si aparecen ambos
    separadores, el que está más a la derecha se toma como decimal.
    """
    if isinstance(raw, bool):
        return Outcome(None, Issue.INVALID_NUMBER, f"valor booleano: {raw!r}")
    if isinstance(raw, int | float | Decimal):
        return Outcome(Decimal(str(raw)))
    text = _CURRENCY.sub("", str(raw)).replace(" ", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    if "," in text and "." in text:
        decimal_sep = "," if text.rfind(",") > text.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        text = text.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in text:
        whole, _, frac = text.rpartition(",")
        text = text.replace(",", "") if len(frac) == 3 and whole else text.replace(",", ".")
    elif text.count(".") > 1 or (text.count(".") == 1 and len(text.rpartition(".")[2]) == 3):
        text = text.replace(".", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        return Outcome(None, Issue.INVALID_NUMBER, f"número no reconocido: {raw!r}")
    return Outcome(-value if negative else value)


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------

_SPACES = re.compile(r"\s+")


def normalize_text(raw: str) -> Outcome:
    """Quita espacios repetidos y en los extremos."""
    return Outcome(_SPACES.sub(" ", raw).strip())


def normalize_name(raw: str) -> Outcome:
    """Normaliza nombres propios: espacios y mayúsculas tipo título en español."""
    small = {"de", "del", "la", "las", "los", "y"}
    words = _SPACES.sub(" ", raw).strip().lower().split(" ")
    titled = [w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words)]
    return Outcome(" ".join(titled))


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def to_snake_case(name: str) -> str:
    """Convierte un encabezado como ``Fecha de Compra`` en ``fecha_de_compra``."""
    text = _strip_accents(str(name)).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "columna"

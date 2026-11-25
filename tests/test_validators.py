from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from limpiador import validators as v
from limpiador.validators import Issue


class TestRut:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("12.345.678-5", "12345678-5"),
            ("12345678-5", "12345678-5"),
            ("123456785", "12345678-5"),
            (" 6.645.651-k ", "6645651-K"),
            ("1-9", "1-9"),
        ],
    )
    def test_valid(self, raw: str, expected: str) -> None:
        assert v.normalize_rut(raw).value == expected

    def test_wrong_check_digit(self) -> None:
        outcome = v.normalize_rut("11.111.111-2")
        assert outcome.issue is Issue.RUT_CHECK_DIGIT
        assert "se esperaba 1" in outcome.detail

    @pytest.mark.parametrize("raw", ["", "abc", "123456789012", "12.345.678-X"])
    def test_bad_shape(self, raw: str) -> None:
        assert v.normalize_rut(raw).issue is Issue.INVALID_RUT

    @given(st.integers(min_value=1, max_value=99_999_999))
    def test_any_body_with_its_check_digit_is_valid(self, body: int) -> None:
        dv = v.rut_check_digit(body)
        dotted = f"{body:,}".replace(",", ".")
        assert v.normalize_rut(f"{dotted}-{dv}").value == f"{body}-{dv}"


class TestPhone:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("9 8765 4321", "+56987654321"),
            ("+56 9 8765 4321", "+56987654321"),
            ("56987654321", "+56987654321"),
            ("(+56) 9-8765-4321", "+56987654321"),
            ("87654321", "+56987654321"),
            ("(2) 2345 6789", "+56223456789"),
            ("0223456789", "+56223456789"),
        ],
    )
    def test_valid(self, raw: str, expected: str) -> None:
        assert v.normalize_phone_cl(raw).value == expected

    @pytest.mark.parametrize("raw", ["123", "12345678", "1987654321", "abc"])
    def test_invalid(self, raw: str) -> None:
        assert v.normalize_phone_cl(raw).issue is Issue.INVALID_PHONE


class TestEmail:
    def test_normalizes_case_and_spaces(self) -> None:
        assert v.normalize_email("  Juan.Perez@Empresa.CL ").value == "juan.perez@empresa.cl"

    @pytest.mark.parametrize("raw", ["malo@", "sin-arroba.cl", "a@b", "a..b@c.cl", "a@b.c"])
    def test_invalid(self, raw: str) -> None:
        assert v.normalize_email(raw).issue is Issue.INVALID_EMAIL


class TestDate:
    @pytest.mark.parametrize(
        "raw",
        [
            "01/02/2024",
            "1-2-2024",
            "01.02.2024",
            "01/02/24",
            "2024-02-01",
            "2024/02/01",
            "20240201",
            "2024-02-01 10:30:00",
            "1 de febrero de 2024",
            "1 feb. 2024",
            "1 de Febrero del 2024",
        ],
    )
    def test_valid(self, raw: str) -> None:
        assert v.normalize_date(raw).value == date(2024, 2, 1)

    def test_accepts_date_objects(self) -> None:
        assert v.normalize_date(datetime(2024, 2, 1, 9)).value == date(2024, 2, 1)
        assert v.normalize_date(date(2024, 2, 1)).value == date(2024, 2, 1)

    @pytest.mark.parametrize(
        "raw", ["31/02/2024", "mañana", "32 de enero de 2024", "1 de xyz de 2024"]
    )
    def test_invalid(self, raw: str) -> None:
        assert v.normalize_date(raw).issue is Issue.INVALID_DATE

    def test_ambiguous_when_not_dayfirst(self) -> None:
        outcome = v.normalize_date("03/04/2024", dayfirst=False)
        assert outcome.issue is Issue.AMBIGUOUS_DATE
        assert outcome.value == date(2024, 4, 3)


class TestAmount:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("$1.234.567", Decimal("1234567")),
            ("1.234,50", Decimal("1234.50")),
            ("1,234.50", Decimal("1234.50")),
            ("1.500", Decimal("1500")),
            ("1,5", Decimal("1.5")),
            ("1,500", Decimal("1500")),
            ("12.5", Decimal("12.5")),
            ("2.298.664 CLP", Decimal("2298664")),
            ("(5.000)", Decimal("-5000")),
            ("-300", Decimal("-300")),
            (1500, Decimal("1500")),
            (12.5, Decimal("12.5")),
        ],
    )
    def test_valid(self, raw: object, expected: Decimal) -> None:
        assert v.normalize_amount(raw).value == expected

    @pytest.mark.parametrize("raw", ["abc", "por confirmar", True, "1.2.3,4,5"])
    def test_invalid(self, raw: object) -> None:
        assert v.normalize_amount(raw).issue is Issue.INVALID_NUMBER


def test_name_title_case_in_spanish() -> None:
    assert v.normalize_name("  ANA   DE LA fuente ").value == "Ana de la Fuente"


def test_text_collapses_spaces() -> None:
    assert v.normalize_text("  hola   mundo ").value == "hola mundo"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Fecha de Compra", "fecha_de_compra"),
        ("Teléfono", "telefono"),
        ("  ", "columna"),
        ("N°", "n"),
    ],
)
def test_snake_case(raw: str, expected: str) -> None:
    assert v.to_snake_case(raw) == expected


def test_outcome_ok() -> None:
    assert v.Outcome("x").ok
    assert not v.Outcome(None, Issue.MISSING).ok

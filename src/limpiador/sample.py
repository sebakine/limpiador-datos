"""Generador de datos de clientes con errores típicos, para demos y pruebas."""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from limpiador.validators import rut_check_digit


def _require_faker() -> object:
    try:
        from faker import Faker
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "el generador de ejemplos necesita Faker: pip install 'limpiador-datos[ejemplos]'"
        ) from exc
    return Faker


def _messy_rut(rng: random.Random) -> str:
    body = rng.randint(5_000_000, 26_000_000)
    dv = rut_check_digit(body)
    if rng.random() < 0.06:  # dígito verificador equivocado
        dv = str((int(dv) + 1) % 10) if dv.isdigit() else "1"
    style = rng.choice(["dots", "plain", "nodash", "lower"])
    if style == "dots":
        return f"{body:,}".replace(",", ".") + f"-{dv}"
    if style == "nodash":
        return f"{body}{dv}"
    return f"{body}-{dv.lower() if style == 'lower' else dv}"


def _messy_phone(rng: random.Random) -> str:
    number = f"9{rng.randint(50_000_000, 99_999_999)}"
    if rng.random() < 0.05:
        return number[: rng.randint(4, 7)]
    return rng.choice(
        [
            f"+56 9 {number[1:5]} {number[5:]}",
            f"56{number}",
            number,
            f"{number[1:]}",
            f"(+56) {number[:1]}-{number[1:5]}-{number[5:]}",
        ]
    )


def _messy_date(rng: random.Random) -> str:
    year, month, day = rng.randint(2022, 2025), rng.randint(1, 12), rng.randint(1, 28)
    months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    if rng.random() < 0.03:
        return f"{rng.randint(29, 31)}/02/{year}"
    return rng.choice(
        [
            f"{day:02d}/{month:02d}/{year}",
            f"{day}-{month}-{year}",
            f"{year}-{month:02d}-{day:02d}",
            f"{day} de {months[month - 1]} de {year}",
        ]
    )


def _messy_amount(rng: random.Random) -> str:
    value = rng.randint(1_000, 2_500_000)
    if rng.random() < 0.03:
        return rng.choice(["por confirmar", "N/A", "abc"])
    return rng.choice(
        [f"${value:,}".replace(",", "."), str(value), f"{value:,}".replace(",", ".") + " CLP"]
    )


def generate_dirty_customers(rows: int = 500, seed: int = 42) -> pd.DataFrame:
    """Genera ventas de clientes con duplicados, nulos y formatos mezclados."""
    faker_cls = _require_faker()
    fake = faker_cls("es_CL")  # type: ignore[operator]
    fake.seed_instance(seed)
    rng = random.Random(seed)
    records = []
    for _ in range(rows):
        email = fake.email()
        if rng.random() < 0.05:
            email = email.replace("@", "")
        elif rng.random() < 0.2:
            email = f"  {email.upper()} "
        name = fake.name()
        records.append(
            {
                "RUT Cliente": _messy_rut(rng),
                "Nombre": rng.choice([name, name.upper(), f"  {name.lower()}  "]),
                "Correo": email if rng.random() > 0.04 else "",
                "Teléfono": _messy_phone(rng),
                "Fecha de Compra": _messy_date(rng),
                "Monto": _messy_amount(rng),
                "Comuna": fake.city(),
            }
        )
    df = pd.DataFrame(records)
    duplicates = df.sample(frac=0.04, random_state=seed)
    return pd.concat([df, duplicates]).sample(frac=1, random_state=seed).reset_index(drop=True)


def write_sample(path: Path, rows: int = 500, seed: int = 42) -> pd.DataFrame:
    df = generate_dirty_customers(rows, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".xlsx":
        df.to_excel(path, index=False)
    else:
        # Separador punto y coma y Windows-1252, como exporta Excel en Chile.
        df.to_csv(path, index=False, sep=";", encoding="cp1252", errors="replace")
    return df

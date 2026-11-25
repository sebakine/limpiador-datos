from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def dirty_df() -> pd.DataFrame:
    """Un set pequeño con un ejemplo de cada problema que el limpiador detecta."""
    return pd.DataFrame(
        {
            "rut": ["12.345.678-5", "12345678-5", "11111111-2", "abc", "7.654.321-6"],
            "nombre": ["  juan  PÉREZ ", "Juan Pérez", "ana de la fuente", "", "LUIS"],
            "email": [" Juan@Mail.CL ", "juan@mail.cl", "malo@", "a@b.cl", ""],
            "telefono": ["9 8765 4321", "+56987654321", "123", "(2) 2345 6789", "56912345678"],
            "fecha": ["01/02/2024", "2024-02-01", "3 de marzo de 2024", "31/02/2024", "-"],
            "monto": ["$1.234.567", "1234567", "abc", "1.234,50", "N/A"],
        }
    )


@pytest.fixture
def csv_semicolon_cp1252(tmp_path: Path) -> Path:
    path = tmp_path / "ventas.csv"
    path.write_bytes(
        "RUT Cliente;Teléfono;Fecha de Compra;Monto\n"
        "12.345.678-5;9 8765 4321;01/02/2024;$1.500\n"
        "12.345.678-5;9 8765 4321;01/02/2024;$1.500\n".encode("cp1252")
    )
    return path

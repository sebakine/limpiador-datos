from __future__ import annotations

from pathlib import Path

from limpiador.sample import generate_dirty_customers, write_sample


def test_is_reproducible() -> None:
    a = generate_dirty_customers(30, seed=7)
    b = generate_dirty_customers(30, seed=7)
    assert a.equals(b)


def test_includes_duplicates() -> None:
    df = generate_dirty_customers(100, seed=3)
    assert len(df) > 100
    assert df.duplicated().any()


def test_write_xlsx(tmp_path: Path) -> None:
    path = tmp_path / "x.xlsx"
    write_sample(path, rows=10)
    assert path.exists()

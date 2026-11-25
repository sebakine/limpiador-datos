"""Interfaz de línea de comandos: ``limpiador limpiar``, ``perfilar`` y ``ejemplo``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from limpiador import __version__
from limpiador.cleaner import clean_dataframe, is_missing
from limpiador.io import UnsupportedFileError, read_table, write_table
from limpiador.report import write_report
from limpiador.schema import Schema

app = typer.Typer(
    help="Limpia y valida archivos CSV/Excel con datos de Chile (RUT, teléfonos, fechas, montos).",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()
err = Console(stderr=True)

InputPath = Annotated[
    Path,
    typer.Argument(exists=True, dir_okay=False, readable=True, help="Archivo CSV o Excel."),
]


def _version(value: bool) -> None:
    if value:
        console.print(f"limpiador {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version, is_eager=True, help="Muestra la versión."),
    ] = False,
) -> None:
    """Limpiador y validador de datos."""


def _load(entrada: Path, hoja: str | None) -> object:
    sheet: str | int = 0 if hoja is None else (int(hoja) if hoja.isdigit() else hoja)
    try:
        return read_table(entrada, sheet=sheet)
    except UnsupportedFileError as exc:
        err.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(2) from exc


@app.command()
def limpiar(
    entrada: InputPath,
    salida: Annotated[
        Path | None,
        typer.Option(
            "--salida", "-o", help="Archivo limpio (.csv o .xlsx). Por defecto <entrada>_limpio.csv"
        ),
    ] = None,
    reporte: Annotated[
        Path | None,
        typer.Option("--reporte", "-r", help="Reporte de anomalías (.xlsx o .html)."),
    ] = None,
    esquema: Annotated[
        Path | None,
        typer.Option("--esquema", "-e", exists=True, dir_okay=False, help="Reglas en TOML."),
    ] = None,
    hoja: Annotated[str | None, typer.Option(help="Hoja de Excel (nombre o número).")] = None,
    estricto: Annotated[
        bool, typer.Option("--estricto", help="Termina con código 1 si hay anomalías (útil en CI).")
    ] = False,
) -> None:
    """Normaliza el archivo, elimina duplicados y reporta las anomalías."""
    try:
        schema = Schema.from_toml(esquema) if esquema else Schema()
    except (ValueError, OSError) as exc:
        err.print(f"[red]Esquema inválido:[/] {exc}")
        raise typer.Exit(2) from exc

    df = _load(entrada, hoja)
    try:
        result = clean_dataframe(df, schema)  # type: ignore[arg-type]
    except KeyError as exc:
        err.print(f"[red]Error:[/] {exc.args[0]}")
        raise typer.Exit(2) from exc

    salida = salida or entrada.with_name(f"{entrada.stem}_limpio.csv")
    write_table(result.data, salida)
    if reporte:
        write_report(result, reporte, source=entrada.name)

    table = Table(title=f"Limpieza de {entrada.name}", show_header=False, title_justify="left")
    table.add_row("Filas leídas", str(result.rows_in))
    table.add_row("Filas en el resultado", str(result.rows_out))
    table.add_row("Duplicados eliminados", str(result.duplicates_removed))
    table.add_row("Celdas normalizadas", str(result.changed_cells))
    style = "yellow" if result.anomalies else "green"
    table.add_row("Anomalías", f"[{style}]{len(result.anomalies)}[/]")
    console.print(table)
    for issue, count in result.anomalies_by_issue.items():
        console.print(f"  • {issue}: {count}")
    console.print(f"[green]✓[/] Resultado en [bold]{salida}[/]")
    if reporte:
        console.print(f"[green]✓[/] Reporte en [bold]{reporte}[/]")
    if estricto and result.anomalies:
        raise typer.Exit(1)


@app.command()
def perfilar(
    entrada: InputPath,
    hoja: Annotated[str | None, typer.Option(help="Hoja de Excel (nombre o número).")] = None,
) -> None:
    """Muestra las columnas, el tipo que se detectó y cuántas celdas vienen vacías."""
    df = _load(entrada, hoja)
    types = Schema().resolve(df.columns)  # type: ignore[attr-defined]
    table = Table(title=f"{entrada.name}: {len(df)} filas")  # type: ignore[arg-type]
    for header in ("Columna", "Tipo detectado", "Vacías", "Distintos", "Ejemplo"):
        table.add_column(header, justify="right" if header in {"Vacías", "Distintos"} else "left")
    for column, column_type in types.items():
        values = df[column]  # type: ignore[index]
        missing = sum(is_missing(x) for x in values)
        example = next((str(x) for x in values if not is_missing(x)), "")
        table.add_row(column, column_type.value, str(missing), str(values.nunique()), example[:30])
    console.print(table)
    console.print(
        "[dim]Para cambiar un tipo, crea un esquema TOML y usa --esquema (ver README).[/]"
    )


@app.command()
def ejemplo(
    salida: Annotated[Path, typer.Argument(help="Dónde guardar el archivo (.csv o .xlsx).")],
    filas: Annotated[int, typer.Option(min=1, max=1_000_000)] = 500,
    semilla: Annotated[
        int, typer.Option(help="Semilla para obtener siempre los mismos datos.")
    ] = 42,
) -> None:
    """Genera un archivo de clientes con errores típicos para probar el limpiador."""
    from limpiador.sample import write_sample

    try:
        df = write_sample(salida, rows=filas, seed=semilla)
    except RuntimeError as exc:
        err.print(f"[red]Error:[/] {exc}")
        raise typer.Exit(2) from exc
    console.print(f"[green]✓[/] {len(df)} filas de ejemplo en [bold]{salida}[/]")


if __name__ == "__main__":  # pragma: no cover
    app()

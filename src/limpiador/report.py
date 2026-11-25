"""Reportes de anomalías en Excel y HTML."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment, select_autoescape
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from limpiador.cleaner import CleaningResult

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(bold=True, color="FFFFFF")


def summary_rows(result: CleaningResult, source: str) -> list[tuple[str, object]]:
    return [
        ("Archivo", source),
        ("Generado", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Filas leídas", result.rows_in),
        ("Filas en el resultado", result.rows_out),
        ("Duplicados eliminados", result.duplicates_removed),
        ("Celdas normalizadas", result.changed_cells),
        ("Anomalías encontradas", len(result.anomalies)),
    ]


def write_excel_report(result: CleaningResult, path: Path, *, source: str) -> None:
    """Escribe un Excel con hojas Resumen, Anomalías y Columnas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(summary_rows(result, source), columns=["Indicador", "Valor"])
    by_issue = pd.DataFrame(
        list(result.anomalies_by_issue.items()), columns=["Problema", "Cantidad"]
    )
    columns = pd.DataFrame(
        [
            (col, typ.value, result.anomalies_by_column.get(col, 0))
            for col, typ in result.column_types.items()
        ],
        columns=["Columna", "Tipo detectado", "Anomalías"],
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Resumen", index=False)
        by_issue.to_excel(writer, sheet_name="Resumen", index=False, startrow=len(summary) + 2)
        result.anomalies_frame().to_excel(writer, sheet_name="Anomalías", index=False)
        columns.to_excel(writer, sheet_name="Columnas", index=False)
        for sheet in writer.book.worksheets:
            _style_sheet(sheet)


def _style_sheet(sheet: object) -> None:
    ws = sheet  # openpyxl Worksheet; tipado laxo para no depender de stubs
    for cell in ws[1]:  # type: ignore[index]
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    ws.freeze_panes = "A2"  # type: ignore[attr-defined]
    for idx, column in enumerate(ws.columns, start=1):  # type: ignore[attr-defined]
        width = max((len(str(c.value)) for c in column if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(idx)].width = min(max(width + 2, 10), 60)  # type: ignore[attr-defined]


_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte de limpieza: {{ source }}</title>
<style>
  :root { --bg:#fff; --fg:#1b1f24; --muted:#5b6470; --line:#d9dee4; --accent:#1f4e78; --warn:#b54708; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f1419; --fg:#e6e9ed; --muted:#9aa4af; --line:#2b333c; --accent:#7fb3e6; --warn:#f79009; }
  }
  body { margin:0; padding:24px 16px; background:var(--bg); color:var(--fg);
         font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width:1100px; margin:0 auto; }
  h1 { font-size:22px; margin:0 0 4px; } h2 { font-size:17px; margin:32px 0 8px; }
  .muted { color:var(--muted); }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-top:16px; }
  .card { border:1px solid var(--line); border-radius:8px; padding:12px; }
  .card b { display:block; font-size:24px; color:var(--accent); font-variant-numeric:tabular-nums; }
  .card.warn b { color:var(--warn); }
  .scroll { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; font-size:14px; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-weight:600; }
  th.num, td.num { text-align:right; font-variant-numeric:tabular-nums; }
  code { font-size:13px; }
</style>
</head>
<body><main>
<h1>Reporte de limpieza</h1>
<div class="muted">{{ source }} · {{ generated }}</div>
<div class="cards">
  <div class="card"><b>{{ r.rows_in }}</b>filas leídas</div>
  <div class="card"><b>{{ r.rows_out }}</b>filas en el resultado</div>
  <div class="card"><b>{{ r.duplicates_removed }}</b>duplicados eliminados</div>
  <div class="card"><b>{{ r.changed_cells }}</b>celdas normalizadas</div>
  <div class="card warn"><b>{{ r.anomalies|length }}</b>anomalías</div>
</div>

<h2>Columnas</h2>
<div class="scroll"><table>
<tr><th>Columna</th><th>Tipo detectado</th><th class="num">Anomalías</th></tr>
{% for col, typ in r.column_types.items() %}
<tr><td><code>{{ col }}</code></td><td>{{ typ.value }}</td><td class="num">{{ by_column.get(col, 0) }}</td></tr>
{% endfor %}
</table></div>

<h2>Anomalías por tipo</h2>
{% if by_issue %}
<div class="scroll"><table>
<tr><th>Problema</th><th class="num">Cantidad</th></tr>
{% for issue, n in by_issue.items() %}<tr><td>{{ issue }}</td><td class="num">{{ n }}</td></tr>{% endfor %}
</table></div>
{% else %}<p>No se encontraron anomalías.</p>{% endif %}

{% if rows %}
<h2>Detalle{% if truncated %} (primeras {{ rows|length }} de {{ r.anomalies|length }}){% endif %}</h2>
<div class="scroll"><table>
<tr><th class="num">Fila</th><th>Columna</th><th>Problema</th><th>Valor original</th><th>Detalle</th></tr>
{% for a in rows %}
<tr><td class="num">{{ a.fila }}</td><td><code>{{ a.columna }}</code></td><td>{{ a.problema }}</td>
<td><code>{{ a.valor_original }}</code></td><td>{{ a.detalle }}</td></tr>
{% endfor %}
</table></div>
{% endif %}
</main></body>
</html>
"""

_env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))


def write_html_report(
    result: CleaningResult, path: Path, *, source: str, max_rows: int = 1000
) -> None:
    """Escribe un reporte HTML autocontenido, sin dependencias externas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = result.anomalies_frame()
    html = _env.from_string(_HTML).render(
        r=result,
        source=source,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        by_issue=result.anomalies_by_issue,
        by_column=result.anomalies_by_column,
        rows=frame.head(max_rows).to_dict("records"),
        truncated=len(frame) > max_rows,
    )
    path.write_text(html, encoding="utf-8")


def write_report(result: CleaningResult, path: Path, *, source: str) -> None:
    """Elige el formato del reporte según la extensión (.xlsx o .html)."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        write_excel_report(result, path, source=source)
    elif suffix in {".html", ".htm"}:
        write_html_report(result, path, source=source)
    else:
        raise ValueError(f"el reporte debe ser .xlsx o .html, no {suffix or path.name}")

# Cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [0.1.0] - 2026-11-25

### Agregado

- Comando `limpiar`: normaliza RUT, teléfonos, emails, fechas, montos y nombres, elimina duplicados y genera un reporte de anomalías en Excel o HTML.
- Comando `perfilar`: muestra el tipo detectado de cada columna y cuántas celdas vienen vacías.
- Comando `ejemplo`: genera un archivo de clientes con errores típicos para probar.
- Esquema opcional en TOML para fijar tipos, columnas obligatorias y claves únicas.
- Lectura de CSV con detección de codificación (UTF-8 o Windows-1252) y separador (`,` o `;`).

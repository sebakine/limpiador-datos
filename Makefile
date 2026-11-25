.PHONY: install lint test check demo build

install:  ## Instala dependencias de desarrollo
	uv sync

lint:  ## Formato, lint y tipos
	uv run ruff format --check src tests
	uv run ruff check src tests
	uv run mypy

test:  ## Tests con cobertura
	uv run pytest

check: lint test

demo:  ## Genera datos sucios y los limpia
	uv run limpiador ejemplo examples/clientes_sucios.csv --filas 500
	uv run limpiador limpiar examples/clientes_sucios.csv -o examples/clientes_limpio.csv -r examples/reporte.html -e examples/esquema.toml

build:
	uv build

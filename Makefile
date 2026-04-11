.PHONY: dev test lint format clean install help

help:
	@echo "NarrativeForge API Commands:"
	@echo "  make install     Instala dependencias con uv"
	@echo "  make dev         Levanta el servidor FastAPI con hot-reload"
	@echo "  make test        Ejecuta todos los tests con pytest"
	@echo "  make lint        Ejecuta Ruff para linter y formato"
	@echo "  make clean       Limpia archivos temporales y cache"

install:
	uv sync

dev:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests -v --cov=src

lint:
	ruff check .
	ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

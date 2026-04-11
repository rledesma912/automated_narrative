.PHONY: dev test lint format clean install help

API_HOST ?= 0.0.0.0:8000

help:
	@echo "NarrativeForge API Commands:"
	@echo "  make install     Instala dependencias con uv"
	@echo "  make dev         Levanta el servidor FastAPI con hot-reload"
	@echo "  make test        Ejecuta todos los tests con pytest"
	@echo "  make lint        Ejecuta Ruff para linter y formato"
	@echo "  make clean       Limpia archivos temporales y cache"
	@echo ""
	@echo "  Variables de entorno:"
	@echo "    API_HOST        Host:puerto para la API (default: 0.0.0.0:8000)"

install:
	uv sync

dev:
	@host=$$(echo $(API_HOST) | cut -d: -f1); \
	port=$$(echo $(API_HOST) | cut -d: -f2); \
	echo "Starting API on $$host:$$port"; \
	uvicorn src.main:app --reload --host $$host --port $$port

test:
	pytest tests -v --cov=src

lint:
	ruff check .
	ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

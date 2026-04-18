.PHONY: dev test lint format clean install help db db-clean list status export generate init

API_HOST ?= 0.0.0.0:8010

help:
	@echo "NarrativeForge Commands:"
	@echo "  make install     Instala dependencias con uv"
	@echo "  make dev         Levanta el servidor FastAPI con hot-reload"
	@echo "  make test        Ejecuta todos los tests con pytest"
	@echo "  make lint        Ejecuta Ruff para linter y formato"
	@echo "  make clean      Limpia archivos temporales y cache"
	@echo ""
	@echo "  make db          Inicializa la base de datos"
	@echo "  make db-clean    Limpia todos los registros (story, beat, journal)"
	@echo "  make list       Lista todas las historias"
	@echo ""
	@echo "  Scripts (uso directo):"
	@echo "    scripts/list.sh              - Listar historias"
	@echo "    scripts/status.sh <id>      - Ver estado de historia"
	@echo "    scripts/generate.sh <id>      - Generar historia completa"
	@echo "    scripts/export.sh <id> [file] - Exportar a Markdown"
	@echo ""
	@echo "  Variables de entorno:"
	@echo "    API_HOST        Host:puerto para la API (default: 0.0.0.0:8010)"

install:
	uv sync

dev:
	@host=$$(echo $(API_HOST) | cut -d: -f1); \
	port=$$(echo $(API_HOST) | cut -d: -f2); \
	echo "Starting API on $$host:$$port"; \
	uv run uvicorn src.main:app --reload --host $$host --port $$port

test:
	PYTHONPATH=. uv run pytest tests -v --cov=src

lint:
	uv run ruff check .
	uv run ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null

db:
	@chmod +x scripts/bash/init_db.sh && ./scripts/bash/init_db.sh

db-clean:
	@chmod +x scripts/bash/db_clean.sh && ./scripts/bash/db_clean.sh

list:
	@chmod +x scripts/bash/list_stories.sh && ./scripts/bash/list_stories.sh

status:
	@chmod +x scripts/status.sh && ./scripts/status.sh $(ARG)
	@echo "Uso: make status ARG=<story_id>"

export:
	@chmod +x scripts/export.sh && ./scripts/export.sh $(ARG)
	@echo "Uso: make export ARG=<story_id> [archivo.md]"

generate:
	@chmod +x scripts/generate_story.sh && ./scripts/generate_story.sh $(ARG)
	@echo "Uso: make generate ARG=<story_id>"

init: db

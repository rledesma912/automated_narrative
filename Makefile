.PHONY: api ui dev-all install test lint format clean help db db-clean list status export generate init

API_HOST    ?= 0.0.0.0:8010
FRONTEND_DIR = frontend

help:
	@echo "NarrativeForge Commands:"
	@echo ""
	@echo "  Desarrollo"
	@echo "    make api          Levanta el Core API (FastAPI, puerto 8010)"
	@echo "    make ui          Levanta el Frontend (Node/Express, puerto 3000)"
	@echo "    make dev-all     Levanta ambos componentes en paralelo"
	@echo "    make install     Instala dependencias Python (uv) y Node (npm)"
	@echo ""
	@echo "  Calidad"
	@echo "    make test        Ejecuta todos los tests con pytest"
	@echo "    make lint        Ejecuta Ruff (linter + format)"
	@echo ""
	@echo "  Base de datos"
	@echo "    make db          Inicializa SQLite"
	@echo "    make db-clean    Limpia todos los registros"
	@echo ""
	@echo "  Historia (CLI)"
	@echo "    make list                      Lista todas las historias"
	@echo "    make generate ARG=<story_id>   Genera una historia"
	@echo "    make export   ARG=<story_id>   Exporta a Markdown"
	@echo ""
	@echo "  Variables"
	@echo "    API_HOST   Host:puerto del Core API (default: 0.0.0.0:8010)"

# ── Dependencias ──────────────────────────────────────────────────────────────

install:
	uv sync
	cd $(FRONTEND_DIR) && npm install

# ── Desarrollo ────────────────────────────────────────────────────────────────

api:
	@host=$$(echo $(API_HOST) | cut -d: -f1); \
	port=$$(echo $(API_HOST) | cut -d: -f2); \
	echo "Core API → http://$$host:$$port"; \
	uv run uvicorn src.main:app --reload --host $$host --port $$port

ui:
	@echo "Frontend UI → http://localhost:3000"
	cd $(FRONTEND_DIR) && npm run dev

dev-all:
	@echo "Levantando Core API (8010) y Frontend (3000)..."
	@trap 'kill 0' SIGINT; \
	($(MAKE) api) & \
	(sleep 2 && $(MAKE) ui) & \
	wait

# ── Calidad ───────────────────────────────────────────────────────────────────

test:
	PYTHONPATH=. uv run pytest tests -v --cov=src

lint:
	uv run ruff check .
	uv run ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null

# ── Base de datos ─────────────────────────────────────────────────────────────

db:
	@chmod +x scripts/bash/init_db.sh
	@# Asegurar permisos antes de crear
	@rm -f data/stories.db && touch data/stories.db
	@./scripts/bash/init_db.sh

db-clean:
	@chmod +x scripts/bash/db_clean.sh && ./scripts/bash/db_clean.sh

init: db

# ── Historia (CLI) ────────────────────────────────────────────────────────────

list:
	@chmod +x scripts/bash/list_stories.sh && ./scripts/bash/list_stories.sh

status:
	@chmod +x scripts/status.sh && ./scripts/status.sh $(ARG)

export:
	@chmod +x scripts/export.sh && ./scripts/export.sh $(ARG)

generate:
	@chmod +x scripts/generate_story.sh && ./scripts/generate_story.sh $(ARG)

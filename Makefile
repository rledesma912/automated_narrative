.PHONY: api ui dev-all install test lint format clean help db db-clean list status export generate init

# ── Variables y Configuración ─────────────────────────────────────────────────

API_HOST     ?= 127.0.0.1:8020
FRONTEND_DIR  = frontend

# Cargar variables de desarrollo si existen (.env.dev)
ifneq ("$(wildcard .env.dev)","")
  include .env.dev
  export
endif

# Extraer puerto de API_HOST para uvicorn
API_PORT = $(shell echo $(API_HOST) | cut -d: -f2)
API_IP   = $(shell echo $(API_HOST) | cut -d: -f1)

help:
	@echo "NarrativeForge Commands (Ambiente de DESARROLLO):"
	@echo ""
	@echo "  Desarrollo (Puertos: API $(API_PORT), UI $(PORT))"
	@echo "    make api          Levanta el Core API con hot-reload"
	@echo "    make ui           Levanta el Frontend con hot-reload"
	@echo "    make dev          Levanta ambos componentes en paralelo"
	@echo "    make install      Instala dependencias Python (uv) y Node (npm)"
	@echo ""
	@echo "  Calidad"
	@echo "    make test         Ejecuta todos los tests con pytest"
	@echo "    make lint         Ejecuta Ruff (linter + format)"
	@echo ""
	@echo "  Base de datos (DESARROLLO)"
	@echo "    make db           Inicializa SQLite de desarrollo"
	@echo "    make db-clean     Limpia todos los registros de desarrollo"
	@echo ""
	@echo "  Historia (CLI)"
	@echo "    make list                      Lista todas las historias"
	@echo "    make generate ARG=<story_id>   Genera una historia"
	@echo "    make export   ARG=<story_id>   Exporta a Markdown"

# ── Dependencias ──────────────────────────────────────────────────────────────

install:
	uv sync
	cd $(FRONTEND_DIR) && npm install

# ── Desarrollo ────────────────────────────────────────────────────────────────

api:
	@echo "🚀 Core API (DEV) → http://$(API_IP):$(API_PORT)"
	uv run uvicorn src.main:app --reload --host $(API_IP) --port $(API_PORT)

ui:
	@echo "🚀 Frontend UI (DEV) → http://localhost:$(PORT)"
	cd $(FRONTEND_DIR) && CORE_API_URL=http://localhost:$(API_PORT) PORT=$(PORT) npm run dev

dev:
	@echo "Levantando entorno de desarrollo completo..."
	@$(MAKE) -j 2 api ui

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

# NarrativeForge

> Sistema de generación granular de relatos de terror con IA local (Ollama).

---

## 🚀 Inicio Rápido

### Requisitos

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (gestor de paquetes)
- [Ollama](https://ollama.com) ejecutarándose con modelo `qwen3.5:9b`

### Instalar y Ejecutar

```bash
# Instalar dependencias (aisla con uv virtual env)
make install

# Iniciar API con hot-reload
make dev

# La API está disponible en http://localhost:8010
```

### Comandos Disponibles

| Comando | Descripción |
|---------|-----------|
| `make install` | Instala dependencias con `uv sync` |
| `make dev` | Levanta API en `0.0.0.0:8010` |
| `make test` | Ejecuta tests con coverage |
| `make lint` | Lint + formato con ruff |
| `make clean` | Limpia cache |

---

## 🏗️ Arquitectura (Clean Architecture)

```
src/
├── main.py                    # FastAPI entrypoint
├── config.py                  # Settings (pydantic-settings)
├── domain/
│   ├── models.py            # Story, Beat, StoryPlan, NarrativeJournal
│   ├── interfaces.py       # Protocols (LLMProvider, Repository)
│   └── exceptions.py       # Domain exceptions
├── application/
│   ├── dto/               # Data Transfer Objects
│   ├── use_cases/          # CreateStory, NarrateBeat, etc.
│   └── services/           # PromptBuilder, MemoryJournalist
├── infrastructure/
│   ├── adapters/         # OllamaAdapter, MockLLMAdapter
│   ├── database/          # SQLite repositories
│   └── normalizers/       # ResponseCleaner
└── presentation/
    └── routers/           # REST endpoints
```

### Flujo de Generación (8 Beats)

```
1. Usuario crea historia → POST /api/v1/stories
2. Director genera escaleta (8 beats) → POST /api/v1/stories/{id}/plan
3. Para cada beat:
   a. Voz genera prosa (150-300 palabras)
   b. Journal actualiza coherencia
4. Exportar a Markdown → GET /api/v1/stories/{id}/export
```

---

## 🔌 API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/api/v1/stories` | Crear historia |
| `GET` | `/api/v1/stories` | Listar historias |
| `GET` | `/api/v1/stories/{id}` | Ver historia |
| `POST` | `/api/v1/stories/{id}/plan` | Generar escaleta (8 beats) |
| `GET` | `/api/v1/stories/{id}/beats` | Listar beats |
| `POST` | `/api/v1/stories/{id}/beats/{n}` | Generar beat específico |
| `GET` | `/api/v1/stories/{id}/export` | Exportar Markdown |

---

## 📋 Roles del LLM

| Rol | Función | Temperatura |
|-----|---------|--------------|
| **Director** | Generar escaleta de beats | 0.4 |
| **Voz** | Generar prosa de cada beat | 0.6 |
| **Journalist** | Mantener coherencia narrativa | 0.3 |

---

## 📂 Estructura de Proyecto

```
narrative-forge/
├── src/                    # Backend Python
├── tests/                  # Tests pytest
├── config/
│   └── prompts/           # Plantillas de prompts
├── scripts/              # Scripts auxiliares
├── specs/                 # Documentación técnica
│   ├── granular_beat_spec.md   # Spec principal (Backend)
│   ├── ui_granular_spec.md     # Spec Frontend
│   └── marco_sdd.md          # Marco SDD
├── .env                   # Variables locales
├── .env.example           # Template
├── pyproject.toml        # Dependencias
└── Makefile              # Comandos
```

---

## 🧪 Tests

```bash
# Ejecutar todos los tests
make test

# Test específico
pytest tests/unit/domain/test_models.py -v

# Con coverage
pytest tests -v --cov=src --cov-report=html
```

---

## ⚙️ Variables de Entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0:8010` | Host de la API |
| `OLLAMA_HOST` | `http://localhost:11434` | URL de Ollama |
| `LLM_MODEL` | `qwen3.5:9b` | Modelo principal |
| `DATABASE_URL` | `sqlite+aiosqlite:///stories.db` | SQLite |

---

## 📚 Specs

| Spec | Descripción |
|------|-------------|
| [`specs/granular_beat_spec.md`](specs/granular_beat_spec.md) | Spec principal (Backend) |
| [`specs/ui_granular_spec.md`](specs/ui_granular_spec.md) | Spec Frontend |
| [`specs/marco_sdd.md`](specs/marco_sdd.md) | Marco SDD |
| [`AGENTS.md`](AGENTS.md) | Configuración del agente |

---

## 🐛 debugging

```bash
# Ver errores en desarrollo
uv run uvicorn src.main:app --reload --log-level debug
```

## 📄 Licencia

MIT
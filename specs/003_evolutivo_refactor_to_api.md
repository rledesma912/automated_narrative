**NarrativeForge API**  
**Spec Técnico – Versión 0.1**  
**Fecha:** 10 de abril de 2026  
**Estado:** Borrador en progreso – Iteración 4  

### 1. Visión y Objetivo

**Propósito**  
Desarrollar una API REST + WebSocket en Python que reciba un archivo `.md` (o los datos de un formulario) con la estructura de un relato de terror y genere automáticamente una historia completa de aproximadamente **2500 palabras** (10–12 minutos de lectura) usando modelos de IA locales vía Ollama.

**Problema que resuelve**  
Reemplazar completamente el flujo basado en **n8n OSS**, eliminando sus limitaciones de orquestación, debugging, visibilidad de estado y control fino. Crear un sistema propio, predecible, testeable y altamente extensible.

**Salida esperada**  
Un archivo `.md` bien estructurado con el relato completo, dividido por actos, con prosa limpia en español, sin residuos de JSON, "Thinking Process" ni explicaciones del modelo.

---

### 2. Arquitectura General

**Stack Principal**

- **Backend:** Python 3.12 + **FastAPI**
- **Real-time:** WebSocket (nativo de FastAPI)
- **Base de datos:** **SQLite** con **aiosqlite** (archivo único compartido)
- **LLM:** Ollama local (`qwen2.5:32b` para generación creativa, `gemma4:e4b` para extracción de estado)
- **Frontend:** Node.js/Express + EJS (mantener el wizard de 4 pasos existente)
- **Orquestación:** Docker Compose
- **Gestión de entorno:** **uv** (reemplazo moderno y ultrarrápido de pip/venv)

**Clean Architecture** (principios clave)
- **Domain**: Entidades y lógica de negocio pura (sin dependencias externas)
- **Application**: Casos de uso (orquestadores)
- **Infrastructure**: Implementaciones técnicas (DB, Ollama, WebSocket)
- **Presentation**: Capas de API y WebSocket

**Diagrama de componentes**
```
UI (Node.js) ──→ FastAPI (REST + WS) ──→ Generation Pipeline
                     ↓
               SQLite (stories.db)
                     ↓
               Ollama (qwen2.5 + gemma4)
                     ↓
               output_stories/*.md
```

---

### 3. Contrato de la API (Endpoints)

**REST Endpoints**

| Método | Endpoint | Descripción |
|--------|----------|-----------|
| `POST` | `/api/v1/generate` | Inicia un nuevo job de generación. Devuelve `{ job_id }` |
| `GET` | `/api/v1/jobs/{job_id}` | Obtiene estado actual del job (para reconexión) |
| `GET` | `/api/v1/stories/{story_id}/output` | Devuelve el relato completo en Markdown + metadatos |
| `POST` | `/api/v1/stories/{story_id}/acts/{n}/retry` | Regenera un acto específico |
| `GET` | `/api/v1/prompts` | Lista prompts disponibles (system, state, etc.) |
| `DELETE` | `/api/v1/stories/{story_id}/output` | Borra solo la generación (conserva el formulario) |

**WebSocket Endpoint**
- `ws://localhost:8000/ws/jobs/{job_id}`

**Protocolo WebSocket (resumen)**

**Eventos del servidor → cliente:**
- `job_started`
- `act_started`
- `act_completed` (incluye `word_count` y `preview`)
- `act_failed`
- `job_completed` (incluye `md_path`)
- `job_failed`

**Eventos del cliente → servidor:**
- `ping` (keepalive)
- `cancel` (abortar job)

---

### 4. Esquema de Base de Datos (SQLite)

**Tablas principales:**

- `stories` – Datos del formulario (nombre, protagonistas, relator, sinopsis, escenarios…)
- `reglas` – Reglas narrativas por historia
- `actos_input` – Misiones y contenido de cada acto (input del wizard)
- `generation_jobs` – Estado del job de generación
- `generated_acts` – Capítulos generados + texto limpio + raw output
- `narrative_states` – Estado narrativo extraído (location, characters, situation, active_threat, goal, last_action)
- `story_sanitized` – (Preparado para v2 – saneamiento)

**Índices clave** y scripts de mantenimiento (reset, seed, delete) están definidos.

---

### 5. Integración con LLM (Ollama)

**Modelos recomendados:**
- **Generación creativa:** `qwen2.5:32b`
- **Extracción de estado:** `gemma4:e4b`

**Flujo por acto:**
1. `build_prompt()` – Combina system prompt + contexto + reglas + estado anterior + misión del acto
2. Llamada a Ollama (chat endpoint)
3. `parse_chapter()` – Limpia output (elimina JSON, thinking process, bloques de código)
4. Validación (mínimo 300 palabras, sin residuos)
5. `extract_state()` – Segunda llamada a Ollama para obtener estado narrativo estructurado
6. Guardado en DB + emisión por WebSocket

**Retry logic:**
- Máximo 3 intentos por acto
- Aumenta temperatura progresivamente (0.7 → 0.8 → 0.9)
- Si falla, marca como `failed` y continúa con el siguiente acto

---

### 6. Gestión del Estado Narrativo

- Se mantiene un **estado acumulado** entre actos (location, characters, situation, active_threat, goal, last_action).
- El estado del acto anterior se inyecta en el prompt del siguiente para garantizar **continuidad estricta**.
- Almacenado en tabla `narrative_states` (relacionada con `generated_acts`).
- Evita contradicciones típicas de generaciones largas.

---

### 7. Calidad y Validación

**Validaciones por acto:**
- `word_count` ≥ 300 palabras
- Capítulo no vacío
- Ausencia de residuos (JSON, "Thinking Process", bloques markdown no deseados)
- Parseo exitoso del texto narrativo limpio

**Manejo de errores:**
- Reintentos automáticos por acto
- Continuación del pipeline aunque un acto falle (modo "best effort")
- Registro de `raw_output` para debugging

**Saneamiento** (preparado para futura iteración)

---

### 8. Entorno de Desarrollo y Plataforma

**Gestión de Python:** `uv` (recomendado)
- Equivalente moderno a `nvm`
- Muy rápido y liviano

**Comandos principales (Makefile):**
- `make dev` → levanta FastAPI con hot-reload
- `make test` / `make test-cov`
- `make lint` / `make fmt` (usando **Ruff**)
- `make db-init` / `make db-reset` / `make db-seed`

**Estructura recomendada del proyecto (`narrative-api/`):**
```
src/
├── domain/
├── application/
├── infrastructure/
├── presentation/
├── config.py
├── main.py
```

**Herramientas recomendadas para desarrollo:**
- VSCode + extensiones (Python, Ruff, SQLite Viewer, Continue)
- Continue.dev + Ollama (asistente de código local)
- Ruff (linter + formatter)
- pytest + pytest-asyncio
- SQLite Viewer (explorar DB directamente en VSCode)

---

### Próximos Pasos (para iterar)

1. Definir el formato exacto del `.md` de entrada (sección 4 pendiente)
2. Detallar las entidades del **Domain** (dataclasses)
3. Escribir los contratos de interfaces del repositorio
4. Definir los Pydantic schemas de la API
5. Crear el primer Use Case (`GenerateStoryUseCase`)

---

¿Quieres que ahora:
- **A)** Expanda alguna sección específica (por ejemplo, el formato del `.md` de entrada, las entidades del Domain, o los Pydantic models)?
- **B)** Genere el boilerplate inicial de carpetas + archivos base según Clean Architecture?
- **C)** Escriba el `pyproject.toml` y el `Makefile` completos?

Decime por dónde querés continuar y lo hacemos paso a paso. Este spec ya está mucho más limpio, ordenado y listo para usar como referencia diaria. 

¿Seguimos? 🚀
# CLI Robusto Spec - NarrativeForge

## 1. Objective

Construir un CLI robusto para ejecutar el núcleo del sistema de generación de relatos de terror desde terminal, sin necesidad de API REST. El usuario especifica los parámetros de la historia y el sistema genera el relato completo con beats, prosa, diálogos y narrativa cohesiva.

---

## 2. Assumptions

| # | Assumption | Valor |
|---|------------|-------|
| 1 | Puerto API | 8010 (no se usa en CLI) |
| 2 | Puerto UI | 3010 (no se usa en CLI) |
| 3 | Python | 3.12+ |
| 4 | LLM por defecto | Mock (flag --real para Ollama) |
| 5 | Beats por defecto | 10 (configurable) |
| 6 | Directorio output | output_stories/ |
| 7 | Directorio logs | logs/ |
| 8 | Formato export | Markdown |
| 9 | DB | stories.db (SQLite) |

---

## 3. Project Structure

```
src/
├── __main__.py                   # Entry point: python -m src
├── cli/
│   ├── __init__.py
│   ├── runner.py                # CLI principal (argparse)
│   ├── commands.py             # Comandos: generate, plan, narrate, export
│   ├── logger.py              # Logging robusto
│   └── exceptions.py          # Excepciones CLI
├── core/
│   ├── __init__.py
│   └── orchestrator.py        # Orquestador flujo completo
├── domain/
│   └── [existente]
├── application/
│   └── [existente]
├── infrastructure/
│   └── [existente]
└── [existente]
```

---

## 4. CLI Commands

### generate

Genera historia completa: plan + todos los beats narrados.

```bash
# Desarrollo (Mock)
python -m src generate --title "La Casa Abandonada" --protagonist "María" --atmosfera terror

# Producción (Ollama real)
python -m src generate --title "La Casa Abandonada" --protagonist "María" --atmosfera terror --real

# Con parámetros custom
python -m src generate \
    --title "Historia" \
    --protagonist "Protagonista" \
    --relator primera_persona \
    --escenarios "Casa embrujada" \
    --sinopsis "Una historia de terror" \
    --atmosfera terror \
    --beats 8 \
    --real
```

| Flag | Requerido | Default | Tipo |
|------|---------|---------|------|
| --title | Sí | - | str |
| --protagonist | Sí | - | str |
| --relator | No | tercera_persona | enum |
| --escenarios | Sí | - | str |
| --sinopsis | Sí | - | str |
| --atmosfera | Sí | - | enum |
| --beats | No | 10 | int |
| --real | No | False | flag |
| --output | No | output_stories/ | path |

### plan

Genera solo el plan (beats) sin narrar.

```bash
python -m src plan --title "Historia" --beats 8 --mock
```

### narrate

Narra beats específicos de una historia existente.

```bash
python -m src narrate --story-id <UUID> --beats 1,2,3 --mock
```

| Flag | Requerido | Default | Tipo |
|------|---------|---------|------|
| --story-id | Sí | - | UUID |
| --beats | Sí | - | str (csv) |
| --real | No | False | flag |

### export

Exporta historia a archivo.

```bash
python -m src export --story-id <UUID> --format markdown --output path/
```

| Flag | Requerido | Default | Tipo |
|------|---------|---------|------|
| --story-id | Sí | - | UUID |
| --format | No | markdown | enum |
| --output | No | output_stories/ | path |

---

## 5. Logging

### Estructura de logs

```
logs/
├── narrative-{YYYYMMDD}.log    # Logs diarios
└── narrative-error-{YYYYMMDD}.log  # Solo errores
```

### Niveles de log

| Nivel | Cuándo usar |
|-------|-----------|
| DEBUG | Depuración,traza de ejecución |
| INFO | Progreso normal (beat completado, etc.) |
| WARNING | ситуации anómalas pero no críticas |
| ERROR | Excepciones capturadas, errores recovery |
| CRITICAL | Errores que中止 el proceso |

### Formato de log

```
[YYYY-MM-DD HH:MM:SS] [LEVEL] [module:function:line] Mensaje
```

Ejemplo:

```
[2025-04-15 10:30:45] [INFO] [orchestrator:run] Starting story generation: La Casa Abandonada
[2025-04-15 10:30:46] [INFO] [narrate_beat:execute] Beat #1 narrating...
[2025-04-15 10:30:52] [INFO] [narrate_beat:execute] Beat #1 completed (6.2s)
[2025-04-15 10:30:52] [INFO] [export:save] Exported to output_stories/la-casa-abandonada.md
```

---

## 6. Exceptions

### CLI Exceptions

| Exception | Hereda de | Cuándo ocurre |
|----------|----------|--------------|
| CLIError | BaseException | Error genérico CLI |
| ValidationError | CLIError | Flag inválido |
| StoryNotFoundError | CLIError | UUID no existe |
| OllamaConnectionError | CLIError | No puede conectar a Ollama |
| GenerationError | CLIError | Error al generar |

---

## 7. Success Criteria

| # | Criterio | Test |
|---|----------|-------|
| 1 | `python -m src generate --title X --mock` executes sin error | Manual |
| 2 | `python -m src generate --title X --real` executes sin error | Manual (Ollama) |
| 3 | Historia se guarda en DB | verify DB |
| 4 | Archivo .md se genera en output_stories/ | verify file |
| 5 | Logs se generan en logs/ | verify file |
| 6 | Exception muestra mensaje friendly en stdout | manual |
| 7 | `--help` muestra ayuda completa | `python -m src --help` |
| 8 | Coverage ≥ 80% | `make test` |

---

## 8. BOUNDARIES

### Always Do

- [ ] Usar `python -m src` como entry point
- [ ] Logging a logs/ con rotación
- [ ] Excepciones con mensajes friendly
- [ ] `--help` en todos los comandos
- [ ] `--mock` por defecto para desarrollo

### Ask First

- [ ] Cambiar estructura de directorios output/logs
- [ ] Modificar formato de log
- [ ] Agregar nuevos comandos CLI

### Never Do

- [ ] Hardcodear paths
- [ ] Logging a stdout solo (sin archivo)
- [ ] Excepciones sin stack trace en log

---

## 9. Hitos de Implementación

### ⏳ Hito CLI-1: CLI Entry Point + Logger

- [ ] Crear `src/__main__.py`
- [ ] Crear `src/cli/__init__.py`
- [ ] Crear `src/cli/logger.py`
- [ ] Crear `src/cli/exceptions.py`
- [ ] Tests: `tests/unit/cli/test_logger.py`

### ⏳ Hito CLI-2: Comandos CLI

- [ ] Crear `src/cli/runner.py`
- [ ] Crear `src/cli/commands.py`
- [ ] Implementar comando generate
- [ ] Implementar comando plan
- [ ] Implementar comando narrate
- [ ] Implementar comando export
- [ ] Tests: `tests/unit/cli/test_commands.py`

### ⏳ Hito CLI-3: Orchestrator

- [ ] Crear `src/core/__init__.py`
- [ ] Crear `src/core/orchestrator.py`
- [ ] Integrar con Use Cases existentes
- [ ] Integrar con DB repositories
- [ ] Tests: `tests/unit/core/test_orchestrator.py`

### ⏳ Hito CLI-4: Integración + Scripts Bash

- [ ] Crear scripts/bash para ejecutar
- [ ] Testing end-to-end
- [ ] Validar Spec completo

### ⏳ Hito CLI-5: Seed Data + Generate desde DB

- [ ] Crear `scripts/sql/insert_story.sql` con datos de prueba
- [ ] Modificar `src/cli/commands.py` para aceptar `--story-id`
- [ ] Modificar `src/cli/runner.py` para nuevo flag
- [ ] Crear lógica para buscar story por ID en DB
- [ ] Tests: `tests/unit/cli/test_commands.py` (caso --story-id)
- [ ] Tests: `tests/integration/test_generate_from_db.py`
- [ ] Actualizar README con documentación de uso

### ⏳ Hito CLI-6: Refactor PromptLoader

- [ ] Crear `src/application/services/prompt_loader.py` (carga MD)
- [ ] Modificar `PromptBuilder` para usar `PromptLoader`
- [ ] Tests: `tests/unit/services/test_prompt_loader.py`
- [ ] Tests: `tests/unit/services/test_prompt_builder.py`

### ⏳ Hito CLI-7: Refactor CLI Commands + DRY

- [ ] Extraer `_init_database` y `_get_llm_adapter` a módulo separado
- [ ] Unificar lógica duplicada en `commands.py`
- [ ] Agregar constantes para status ("pending", "completed")
- [ ] Unificar tipos de story_id (siempre string)
- [ ] Tests: `tests/unit/cli/test_commands_refactored.py`

---

## 8. Análisis de Código - SOLID y Buenas Prácticas

### Principios Violados

| Clase | Problema | Principio |
|-------|----------|----------|
| `commands.py` | Múltiples responsabilidades | SRP |
| `commands.py` | Código duplicado (`_generate_async` vs `_generate_from_db_async`) | DRY |
| `commands.py` | Hardcoded repos (sin DI) | DIP |
| `orchestrator.py` | Magic strings (`"completed"`) | KISS |
| `PromptBuilder` | Carga + construcción | SRP |

### Detalles por Clase

#### commands.py

```
_get_llm_adapter()        → Factory mezclado en comando
_init_database()          → Inicialización mezclada
generate/plan/narrate   → Coordinación excesiva
generate_from_db()      → Lógica duplicada con generate
```

**Problema:** La claseCommandHandler hace:
- Factory de adapters (debería estar en un módulo separado)
- Inicialización de DB (debería estar en connection.py)
- Coordinación de Use Cases (responsabilidad del Orchestrator)
- Logging (ya tiene su propio módulo)

#### orchestrator.py

```python
# Magic string hardcodeado
pending_beats = [b for b in beats if b.status != "completed"]
```

Debería usar `BeatStatus.COMPLETED` o constante.

#### PromptBuilder

Ya identificado en Hito CLI-6: Mezcla carga de archivos con formateo.

### Plan de Refactor

1. **Constantes de Status**: Crear `src/domain/constants.py`
2. **Factory separada**: Extraer a `src/infrastructure/factories.py`
3. **Unificar commands**: Eliminar duplicación

---

## Priorización de Hitos

| Hito | Descripción | Prioridad |
|------|-------------|-----------|
| CLI-1 | CLI Entry Point + Logger | ✅ COMPLETADO |
| CLI-2 | Comandos CLI | ✅ COMPLETADO |
| CLI-3 | Orchestrator | ✅ COMPLETADO |
| CLI-4 | Integración + Scripts Bash | ✅ COMPLETADO |
| CLI-5 | Seed Data + Generate desde DB | ✅ COMPLETADO |
| CLI-6 | Refactor PromptLoader | 🔄 Pendiente (baja) |
| CLI-7 | Refactor CLI Commands + DRY | 🔄 Pendiente |
| CLI-8 | Tests CLI | 🔄 Pendiente |
| CLI-9 | Documentación Final | 🔄 Pendiente |

---

## 6. seed Data Script

### Script SQL para insertar historias

**Ubicación:** `scripts/sql/insert_story.sql`

```sql
-- Seed data: Insertar historia con beats pre-definidos
-- ID: <title_snake_case>_<timestamp_unix>

-- Insertar story
INSERT INTO story (id, title, protagonista, relator, escenarios, sinopsis, atmosfera, status, created_at)
VALUES (
    'el_monte_prohibido_1744742400',
    'El Monte Prohibido',
    'Carlos, Lucía y Marcos',
    'tercera_persona',
    'Un monte aislado en las afueras del pueblo',
    'Un grupo de amigos decide explorar el monte prohibido del pueblo. Lo que comienza como una aventura termina en una pesadilla.',
    'terror_psicologico',
    'pending',
    datetime('now')
);

-- Insertar beats pre-definidos (el LLM expandirá cada summary)
INSERT INTO beat (story_id, number, summary, status) VALUES 
('el_monte_prohibido_1744742400', 1, 'Llegada al sendero', 'pending'),
('el_monte_prohibido_1744742400', 2, 'Primera señal: los pájaros callan', 'pending'),
('el_monte_prohibido_1744742400', 3, 'Encontrar señal antigua de advertencia', 'pending'),
('el_monte_prohibido_1744742400', 4, 'La primera desaparición del grupo', 'pending'),
('el_monte_prohibido_1744742400', 5, 'Escuchar voces en la oscuridad', 'pending'),
('el_monte_prohibido_1744742400', 6, 'Descubrir refugio abandonado', 'pending'),
('el_monte_prohibido_1744742400', 7, 'Revelación del oscuro pasado del monte', 'pending'),
('el_monte_prohibido_1744742400', 8, 'Persecución por fuerza invisible', 'pending'),
('el_monte_prohibido_1744742400', 9, 'Decisión final: quedarse o huir', 'pending'),
('el_monte_prohibido_1744742400', 10, 'El final: sacrifice o escape', 'pending');
```

### Comando generate con --story-id

```bash
# Modo actual (todos los params)
python -m src generate --title "El Monte Prohibido" --protagonist "Carlos" --atmosfera terror

# Nuevo modo (desde DB)
python -m src generate --story-id "el_monte_prohibido_1744742400" --real
```

| Flag | Requerido | Default | Tipo |
|------|-----------|---------|------|
| --story-id | Sí* | - | str (ID único) |
| --real | No | False | flag |

*Obligatorio si no se proveen --title, --protagonist, etc.

---

## 7. ERD - Entity Relationship Diagram

```
┌─────────────────────┐       ┌─────────────────────┐
│       story        │       │        beat         │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)            │───┐   │ id (PK)             │
│ title              │   └──▶│ story_id (FK)       │
│ protagonista       │       │ number              │
│ relator            │       │ summary             │
│ escenarios         │       │ content             │
│ sinopsis           │       │ status              │
│ atmosfera          │       │ technical_context   │
│ status             │       │ created_at          │
│ created_at         │       └─────────────────────┘
└─────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│    narrative_journal        │
├─────────────────────────────┤
│ id (PK)                     │
│ story_id (FK, UNIQUE)       │
│ last_events                 │
│ unresolved_mysteries        │
│ physical_emotional_state    │
└─────────────────────────────┘
```

### Relaciones

- **story → beat:** One-to-Many (una historia tiene muchos beats)
- **story → narrative_journal:** One-to-One (una historia tiene un journal)

### Índices

```sql
CREATE INDEX idx_beats_story_id ON beat(story_id);
CREATE INDEX idx_beats_number ON beat(story_id, number);
CREATE UNIQUE INDEX uq_beats_story_number ON beat(story_id, number);
CREATE INDEX idx_journal_story_id ON narrative_journal(story_id);
```

---

## 10. Open Questions

| # | Pregunta | Estado |
|---|---------|--------|
| 1 | ¿Cantidad fixed de beats o configurable? | → Configurable |
| 2 | ¿Formato de output solo Markdown? | → Markdown + JSON |
| 3 | ¿Rotación de logs? | → Diaria |
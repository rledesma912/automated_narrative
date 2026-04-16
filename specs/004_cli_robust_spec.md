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

---

## 10. Open Questions

| # | Pregunta | Estado |
|---|---------|--------|
| 1 | ¿Cantidad fixed de beats o configurable? | → Configurable |
| 2 | ¿Formato de output solo Markdown? | → Markdown + JSON |
| 3 | ¿Rotación de logs? | → Diaria |
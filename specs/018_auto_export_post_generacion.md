# Spec 018: Auto-export al finalizar la generación

## Objetivo

Al terminar `python -m src generate`, el archivo Markdown del relato debe generarse
automáticamente en `output_stories/`, sin que el usuario tenga que recordar el ID de
la historia ni ejecutar `export` por separado.

Se corrige además un bug descubierto durante el análisis: las `reglas` del archivo
de entrada nunca llegan al LLM porque el flujo `generate → _generate_async → run_full`
las pierde en el camino.

---

## Diagnóstico técnico

### Problema 1 — Auto-export

`StoryRunner.run_full()` retorna el objeto `Story`, pero `_generate_async()` ignora
ese return. Los beats narrados quedan en la variable local `completed_beats` dentro de
`_run_narrate_all()` y nunca se adjuntan a `story.beats`.

```python
# commands.py — estado actual
await runner.run_full(...)   # ← return ignorado

# orchestrator.py — estado actual
async def _run_narrate_all(self, story):
    completed_beats = []
    for beat in pending_beats:
        ...
        completed_beats.append(generated_beat)
    # ← completed_beats nunca se asigna a story.beats
```

### Problema 2 — Reglas perdidas

`generate()` parsea las reglas del archivo YAML pero nunca las pasa al flujo de
generación:

```python
# commands.py — generate()
story_data = parser.parse(input_file)
title = story_data.title
protagonista = story_data.protagonista
...
# ← story_data.reglas NO se lee ni se pasa
```

`run_full()` tampoco acepta `reglas` como parámetro, y `StoryCreateDTO` se construye
sin ellas aunque el campo existe con default `[]`.

---

## Cambios por archivo

| Archivo | Cambio |
|---------|--------|
| `src/core/orchestrator.py` | `_run_narrate_all()` asigna beats a `story.beats`; `run_full()` acepta y propaga `reglas` |
| `src/cli/commands.py` | `generate()` lee `reglas`; `_generate_async()` recibe y pasa `reglas`; captura return de `run_full()` y exporta |

---

## Hitos y tareas

### Hito 1 — Propagar reglas por todo el flujo

**Criterio de aceptación:**
- `run_full()` recibe `reglas: list[str] = []`
- `StoryCreateDTO` se construye con `reglas=reglas`
- `generate()` pasa `story_data.reglas` al llamar a `_generate_async()`
- Test unitario verifica que una story creada con reglas las tiene en `story.reglas`

**Tareas:**

- [ ] **1.1** — Agregar parámetro `reglas` a `StoryRunner.run_full()` y al `StoryCreateDTO`.
  - Archivo: `src/core/orchestrator.py`
  - Firma actual: `run_full(self, title, protagonista, relator, escenarios, sinopsis, atmosfera, num_beats=10)`
  - Firma nueva: agregar `reglas: list[str] | None = None` antes de `num_beats`
  - En el cuerpo: `reglas=reglas or []` al construir `StoryCreateDTO`
  - Verify: `pytest tests/unit/ -q --ignore=tests/unit/core/`

- [ ] **1.2** — Propagar `reglas` desde `generate()` → `_generate_async()`.
  - Archivo: `src/cli/commands.py`
  - En `generate()`: leer `reglas = story_data.reglas if input_file else []` y pasarla a `_generate_async()`
  - En `_generate_async()`: agregar `reglas: list[str] | None = None` a la firma y pasarla a `runner.run_full()`
  - Verify: `pytest tests/unit/ -q --ignore=tests/unit/core/`

---

### Hito 2 — Adjuntar beats al Story antes de retornar

**Criterio de aceptación:**
- `story.beats` está poblado al retornar de `run_full()` y `run_from_story()`
- No se hace ninguna consulta extra a la DB para obtener los beats

**Tareas:**

- [ ] **2.1** — `_run_narrate_all()` asigna `completed_beats` a `story.beats`.
  - Archivo: `src/core/orchestrator.py`
  - Al final de `_run_narrate_all()`, antes del log final: `story.beats = completed_beats`
  - Retornar `story` (en vez de solo `beats`) o actualizar el caller
  - Verify: `pytest tests/unit/ -q --ignore=tests/unit/core/`

- [ ] **2.2** — `run_full()` retorna la `story` con beats adjuntos.
  - El return actual ya devuelve `story`; solo asegurarse de que `story.beats` esté poblado post-narración
  - Verify: smoke check `story.beats` no vacío tras `run_full()`

---

### Hito 3 — Auto-export en `_generate_async()`

**Criterio de aceptación:**
- Al finalizar `generate`, existe un archivo `output_stories/<Titulo>_<timestamp>.md`
- El archivo contiene `# <Título>` y secciones `## Acto N` con prosa
- El log muestra la ruta del archivo generado
- No se hace consulta extra a la DB (se usa el objeto en memoria)

**Tareas:**

- [ ] **3.1** — Capturar el return de `run_full()` en `_generate_async()` y exportar.
  - Archivo: `src/cli/commands.py`
  - Cambiar `await runner.run_full(...)` → `story = await runner.run_full(...)`
  - Después del await: construir el Markdown con `MarkdownRenderer`, escribir el archivo
  - Reutilizar exactamente la lógica de `_export_async()` (timestamp + safe_title + write)
  - Verify: `pytest tests/unit/ -q --ignore=tests/unit/core/`

- [ ] **3.2** — Hacer lo mismo para `generate_from_db` / `run_from_story`.
  - Archivo: `src/cli/commands.py`
  - `_generate_from_db_async()`: capturar return de `runner.run_from_story()` y exportar
  - Verify: misma suite

- [ ] **3.3** — Refactorizar la lógica de export a una función helper privada.
  - Archivo: `src/cli/commands.py`
  - Extraer `_write_markdown(story, output_dir)` para evitar duplicar el bloque
    timestamp + safe_title + render + write
  - Llamarla desde `_generate_async`, `_generate_from_db_async` y `_export_async`
  - Verify: `pytest tests/unit/ -q --ignore=tests/unit/core/`

- [ ] **3.4** — Test unitario del helper `_write_markdown`.
  - Archivo: `tests/unit/cli/test_commands.py` (nuevo o existente)
  - Verificar que el archivo se crea en `output_dir` con el patrón correcto
  - Verify: `pytest tests/unit/cli/ -v`

---

## Orden de implementación

```
Hito 1 (reglas)  →  Hito 2 (beats en memory)  →  Hito 3 (auto-export)
```

Los hitos son secuenciales: el 3 depende del 2 (necesita `story.beats` poblado).

---

## Boundaries

- **Always do:** `pytest tests/unit/ -q --ignore=tests/unit/core/` antes de cerrar cada hito.
- **Ask first:** cambios al esquema de la DB o a la interfaz pública de `StoryRunner`.
- **Never do:** hacer consulta a la DB en `_generate_async` para obtener los beats — usar el objeto en memoria.

---

## Archivos involucrados

| Archivo | Hitos |
|---------|-------|
| `src/core/orchestrator.py` | 1.1, 2.1, 2.2 |
| `src/cli/commands.py` | 1.2, 3.1, 3.2, 3.3 |
| `tests/unit/cli/test_commands.py` | 3.4 |

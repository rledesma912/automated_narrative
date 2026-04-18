# Spec 019: Progress Reporter — salida de terminal limpia con tiempos

## Objetivo

Reemplazar la salida de consola técnica y ruidosa del CLI por una salida limpia,
informativa y con emojis que muestre el progreso real del proceso y el tiempo
que demora cada paso, incluyendo específicamente la latencia de respuesta del LLM.

### Output objetivo

```
🎬  NarrativeForge — El Monte Prohibido
────────────────────────────────────────
📋  Planificando 8 beats...           ✓  3.1s
✍️   Beat 1/8...                       ✓  9.4s  (LLM 8.8s)
✍️   Beat 2/8...                       ✓  7.2s  (LLM 6.9s)
✍️   Beat 3/8...                       ✓  8.1s  (LLM 7.6s)
...
📄  Exportando Markdown...            ✓  0.1s
────────────────────────────────────────
✅  Completado en 82.4s
📁  output_stories/El_Monte_Prohibido_17042026210459.md
```

En caso de error:
```
❌  Error en Beat 3/8: timeout al conectar con Ollama  (9.0s)
```

---

## Diagnóstico del sistema actual

| Problema | Archivo | Detalle |
|----------|---------|---------|
| Console handler al nivel DEBUG | `src/cli/logger.py:44` | Vuelca todo a consola, incluido logs internos de aiosqlite, httpx, etc. |
| Sin timing | Todo el flujo | Ninguna capa mide tiempos |
| Latencia LLM no medida | `src/infrastructure/adapters/ollama_adapter.py` | `generate()` no registra cuánto tarda |
| Formato técnico en consola | `logger.py:28` | `[timestamp] [LEVEL] mensaje` no es legible para el usuario |

---

## Arquitectura de la solución

### Separación de responsabilidades

```
NarrativeLogger  →  archivo de log (DEBUG completo, formato técnico)
                 →  consola solo WARNING+ (errores inesperados)

ProgressReporter →  consola (progreso, emojis, tiempos) — nueva clase
```

### Flujo de datos de timing

```
OllamaAdapter.generate()
    └── mide wall-clock time → retorna (texto, llm_elapsed_s)

VozUseCase.execute()
    └── recibe llm_elapsed de la respuesta del adapter
    └── retorna (beat, journal, llm_elapsed)

StoryRunner._run_narrate_all()
    └── mide step total time (incluye DB, journal, etc.)
    └── llama reporter.beat_done(n, total, step_elapsed, llm_elapsed)

StoryRunner._run_plan()
    └── mide tiempo del Director
    └── llama reporter.plan_done(elapsed)

commands._generate_async()
    └── mide tiempo total
    └── llama reporter.done(total_elapsed, output_path)
```

### Inyección del reporter

`StoryRunner` recibe `reporter: ProgressReporter | None = None`.
Cuando es `None` usa un `SilentReporter` (no-op) para no romper tests ni el modo API.

---

## Hitos y tareas

### Hito 1 — Silenciar consola en NarrativeLogger

**Criterio de aceptación:**
- La consola no muestra logs de nivel DEBUG ni INFO del sistema interno
- Solo aparecen en consola mensajes WARNING o ERROR del logger técnico
- El archivo de log sigue recibiendo DEBUG completo

**Tareas:**

- [ ] **1.1** — Subir el nivel del console handler a `WARNING`.
  - Archivo: `src/cli/logger.py`
  - Línea 46: `console_handler.setLevel(logging.DEBUG)` → `logging.WARNING`
  - Verify: `pytest tests/unit/cli/ -v`

---

### Hito 2 — OllamaAdapter retorna latencia LLM

**Criterio de aceptación:**
- `OllamaAdapter.generate()` retorna una tupla `(text: str, elapsed_s: float)`
- `MockLLMAdapter.generate()` también retorna la tupla (con `elapsed_s=0.0`)
- La interfaz `LLMProvider` refleja el nuevo tipo de retorno
- Los callers (`VozUseCase`, `DirectorUseCase`, `MemoryJournalist`) adaptan el unpack

**Tareas:**

- [ ] **2.1** — Actualizar la interfaz `LLMProvider`.
  - Archivo: `src/domain/interfaces/llm_provider.py`
  - Cambiar signature: `generate(...) -> str` → `generate(...) -> tuple[str, float]`
  - Verify: `pytest tests/unit/ -q --ignore=tests/unit/core/`

- [ ] **2.2** — Medir latencia en `OllamaAdapter.generate()`.
  - Archivo: `src/infrastructure/adapters/ollama_adapter.py`
  - Usar `time.perf_counter()` antes y después del request HTTP
  - Retornar `(text, elapsed_s)`
  - Verify: mismo comando

- [ ] **2.3** — Actualizar `MockLLMAdapter.generate()`.
  - Archivo: `src/infrastructure/adapters/mock_llm_adapter.py`
  - Retornar `(response_text, 0.0)`
  - Verify: `pytest tests/unit/infrastructure/test_mock_llm_adapter.py -v`

- [ ] **2.4** — Adaptar callers: `VozUseCase`, `DirectorUseCase`, `MemoryJournalist`.
  - Desempacar `text, _ = await self.llm.generate(...)` donde no se necesita el tiempo
  - En `VozUseCase.execute()`: capturar `llm_elapsed` y retornarlo en la tupla de retorno
  - Verify: `pytest tests/unit/application/ -v`

---

### Hito 3 — ProgressReporter

**Criterio de aceptación:**
- `ProgressReporter` imprime a consola con el formato del output objetivo
- `SilentReporter` implementa la misma interfaz sin imprimir nada
- Los tests del reporter validan el formato exacto de cada mensaje

**Tareas:**

- [ ] **3.1** — Crear `src/cli/progress.py` con `ProgressReporter` y `SilentReporter`.
  - `ProgressReporter` métodos:
    - `start(title: str)` — imprime cabecera + línea separadora
    - `plan_done(elapsed_s: float)` — `📋  Planificando N beats... ✓  Xs`
    - `beat_done(n: int, total: int, elapsed_s: float, llm_elapsed_s: float)` — `✍️   Beat N/T... ✓  Xs  (LLM Ys)`
    - `export_done(elapsed_s: float)` — `📄  Exportando Markdown... ✓  Xs`
    - `done(total_elapsed_s: float, output_path: Path)` — separador + `✅` + `📁`
    - `error(msg: str, elapsed_s: float)` — `❌  msg  (Xs)`
  - `SilentReporter` — misma interfaz, todos los métodos son no-op
  - Verify: `pytest tests/unit/cli/test_progress.py -v`

- [ ] **3.2** — Tests para `ProgressReporter`.
  - Archivo: `tests/unit/cli/test_progress.py`
  - Verificar con `capsys` que cada método produce la línea correcta

---

### Hito 4 — Integración en StoryRunner y commands

**Criterio de aceptación:**
- `StoryRunner.__init__` acepta `reporter: ProgressReporter | SilentReporter | None = None`
- Si `None`, usa `SilentReporter`
- `commands._generate_async` crea `ProgressReporter()` y lo pasa al runner
- La salida real del CLI muestra el formato del output objetivo

**Tareas:**

- [ ] **4.1** — Inyectar `reporter` en `StoryRunner`.
  - Archivo: `src/core/orchestrator.py`
  - `__init__` agrega `reporter` con default `None` → usa `SilentReporter`
  - `_run_plan()` llama `reporter.plan_done(elapsed_s)`
  - `_run_narrate_all()` llama `reporter.start()`, `reporter.beat_done()` por beat, `reporter.done()`
  - Verify: `pytest tests/unit/ -q --ignore=tests/unit/core/`

- [ ] **4.2** — `_generate_async` crea e inyecta el reporter.
  - Archivo: `src/cli/commands.py`
  - Instanciar `reporter = ProgressReporter()` antes de crear `StoryRunner`
  - Pasar `reporter=reporter` al constructor
  - Llamar `reporter.export_done()` tras `_write_markdown()`
  - Llamar `reporter.done()` al final
  - Verify: smoke run con mock `python -m src generate --input el_monte_prohibido.md`

- [ ] **4.3** — Hacer lo mismo para `_generate_from_db_async`.
  - Mismo patrón
  - Verify: suite completa

---

## Orden de implementación

```
Hito 1 (silenciar logger)
  → Hito 2 (latencia LLM)
    → Hito 3 (ProgressReporter)
      → Hito 4 (integración)
```

Cada hito es independiente en código pero el 4 depende del 3, y el 3 depende del 2
para mostrar la latencia del LLM.

---

## Boundaries

- **Always do:** `pytest tests/unit/ -q --ignore=tests/unit/core/` al cerrar cada hito.
- **Ask first:** cambiar el tipo de retorno de la interfaz `LLMProvider` si hay más adapters desconocidos.
- **Never do:** poner lógica de formato o `print()` fuera de `progress.py`.

---

## Archivos involucrados

| Archivo | Hitos |
|---------|-------|
| `src/cli/logger.py` | 1.1 |
| `src/domain/interfaces/llm_provider.py` | 2.1 |
| `src/infrastructure/adapters/ollama_adapter.py` | 2.2 |
| `src/infrastructure/adapters/mock_llm_adapter.py` | 2.3 |
| `src/application/use_cases/voz_use_case.py` | 2.4 |
| `src/application/use_cases/director_use_case.py` | 2.4 |
| `src/application/services/memory_journalist.py` | 2.4 |
| `src/cli/progress.py` | 3.1 |
| `tests/unit/cli/test_progress.py` | 3.2 |
| `src/core/orchestrator.py` | 4.1 |
| `src/cli/commands.py` | 4.2, 4.3 |

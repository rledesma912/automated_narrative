# Spec-312: Fix — `generated_narrative` no se popula desde CLI/streaming + redundancia con `macro_beat.content`

## Metadata

| Campo | Valor |
|-------|-------|
| **Status** | IMPLEMENT — COMPLETADO 2026-05-05 |
| **Tipo** | Bugfix funcional + revisión arquitectural |
| **Slice base** | S0 |
| **Fecha** | 2026-05-05 |
| **Owner** | Backend (Application + Infrastructure) |
| **Specs relacionados** | 230 (ciclo de vida), 300 (refactor varios relatos), 311 (galería "Ver Relato"), 201 (streaming) |

---

## 1. Objetivo

Resolver dos defectos vinculados a la persistencia del relato generado:

1. **Bug funcional**: la tabla `generated_narrative` queda vacía al generar una historia desde la CLI
   (`python -m src generate ...`) o desde el streaming web (`/api/v1/streaming/...`). Sólo se
   popula cuando se invoca explícitamente el endpoint `POST /story-templates/{id}/generate-narrative`.
   Consecuencia directa: la galería ("Ver Relato" de Spec-311) muestra estado vacío incluso
   tras una generación exitosa.

2. **Revisión arquitectural**: con `generated_narrative` como tabla autoritativa para el relato
   final, evaluar si `macro_beat.content` es redundante y cómo se reordena el flujo de
   persistencia para evitar duplicación de la prosa generada.

Este spec **no implementa** todavía: deja abierta la decisión de diseño (Opción A vs Opción B)
para alineación con el usuario antes de pasar a TASKS.

---

## 2. Hallazgos confirmados

### 2.1 Bug #1 — `generated_narrative` nunca se popula desde CLI/streaming

**Único caller de `narrative_repo.save()` en todo el código:**

```text
src/application/use_cases/generate_narratives_use_case.py:50
    → GenerateNarrativesUseCase.generate_from_existing_beats()
```

**Único caller de `generate_from_existing_beats()`:**

```text
src/presentation/routers/narrative_router.py:42
    → POST /story-templates/{story_template_id}/generate-narrative
```

**Flujos que NO populan `generated_narrative`:**

| Flujo | Archivo / método | Persiste `macro_beat.content` | Persiste `generated_narrative` |
|---|---|---|---|
| CLI `generate` (full) | `src/core/orchestrator.py::StoryRunner.run_full` (línea 45) | sí | **no** |
| CLI `generate-from-db` | `src/core/orchestrator.py::StoryRunner.run_from_story` (línea 161) | sí | **no** |
| CLI `narrate` | `src/cli/commands.py::_narrate_async` (línea 241) | sí | **no** |
| Web streaming SSE | `src/application/services/streaming_service.py::stream_story` (línea 24) | sí | **no** |

**Resultado en BD tras generación CLI/web:**

```sql
SELECT COUNT(*) FROM macro_beat WHERE story_id = ?;          -- 5
SELECT COUNT(*) FROM generated_narrative WHERE story_template_id = ?;  -- 0
```

**Impacto UX (regresión sobre Spec-311):**
- Galería → "Ver Relato" → vista `relatos.ejs` → `GET /api/v1/story-templates/{id}/narratives` →
  lista vacía → fallback de "Aún no se ha generado ningún relato" pese a que la historia está
  marcada como `completed`.
- El único modo actual de poblar la tabla es invocar manualmente el botón de generación de relato
  desde la pantalla de detalle de historia (que llama al `POST` mencionado).

### 2.2 Bug #2 — Duplicación lógica `macro_beat.content` ↔ `generated_narrative.content`

**Estado actual de los datos:**

| Campo | Granularidad | Cuándo se escribe | Quién lo escribe |
|---|---|---|---|
| `macro_beat.content` | Por beat (1 fila × 5) | En cada iteración del Director (`VozUseCase.narrate()`) | `SQLBeatRepository.save()` |
| `generated_narrative.content` | Consolidado (1 fila × historia × variante) | A demanda vía endpoint dedicado | `SQLGeneratedNarrativeRepository.save()` |

**Operación de consolidación (única hoy):**

```python
# src/application/use_cases/generate_narratives_use_case.py:36-41
content_parts = []
for beat in sorted(story.beats, key=lambda b: b.number):
    if beat.content:
        content_parts.append(beat.content)
full_content = "\n\n".join(content_parts)
```

→ La consolidación es **derivable** desde `macro_beat.content`. Hay duplicación efectiva
del texto narrativo entre ambas tablas si la generación se ejecuta una sola vez por historia.

**Casos legítimos hoy de `macro_beat.content`:**
- Streaming UI (`frontend/src/views/streaming-room.ejs`, líneas 48 y 213): renderiza
  `b.content` por beat conforme llegan los SSE.
- CLI `narrate <story_id>`: re-narra beats individuales y los guarda con `beat_repo.save()`.
- `StoryRunner.run_from_story()`: completa beats pendientes basándose en `b.status` y
  reutiliza `b.content` ya persistido.
- `generate_from_existing_beats()`: justamente itera y concatena `beat.content`.

→ Eliminar `macro_beat.content` es viable pero **no trivial**: requiere desplazar todos los
casos anteriores a leer/escribir `generated_narrative` (o un campo derivado nuevo).

---

## 3. Decisiones de producto cerradas (2026-05-05)

### D1 — Cuándo se crea la fila → **D1.c**
**Una nueva variante (`UUID` distinto) cada vez que se ejecuta la generación**, preservando
histórico. Alineado con la semántica del Spec-300/311 ("varias variantes por historia").

### D2 — `macro_beat.content` → **Opción A (mínima)**
**No se elimina** en este spec. Se mantiene como buffer per-beat durante la generación.
`generated_narrative.content` se popula por consolidación al finalizar exitosamente la
generación (los 5 beats). Un eventual Spec-313 podrá atacar Opción B/C en el futuro.

### D3 — Título del relato → **Determinístico**
Default en CLI/streaming: `f"{story.title} · {YYYY-MM-DD HH:MM}"` con timestamp en zona
Argentina (`now_argentina()` ya existente). El endpoint manual `POST /generate-narrative`
sigue aceptando `title` explícito.

---

## 4. Diseño propuesto (asumiendo Opción A + D1.c + título determinístico)

### 4.1 Punto de inserción del save

Al final del éxito de la generación, agregar un paso que consolide `story.beats` y guarde
una nueva fila en `generated_narrative`:

```text
[Director.execute_full] termina los 5 beats
        ↓
[Orchestrator/Stream] persiste último beat + journal
        ↓
[NUEVO] consolidate_and_save_narrative(story)
        ↓
[Repo] generated_narrative INSERT (nueva variante)
        ↓
[CLI/Stream] reportar OK / emitir evento `done` con narrative_id
```

### 4.2 Refactor mínimo del use case

`GenerateNarrativesUseCase.generate_from_existing_beats()` ya hace esto. Bastaría:

1. Refactorizar el use case para que reciba opcionalmente `story` ya cargada (evita un round-trip
   extra a DB cuando el orchestrator ya la tiene).
2. Inyectarlo en `StoryRunner` y `stream_story` vía el `CLIContainer` / DI del router.
3. Llamarlo:
   - En `StoryRunner.run_full()` después del bucle `async for ... director.execute_full()`,
     antes del `update_status(COMPLETED)`.
   - En `StoryRunner.run_from_story()` después del bucle `execute_narration` cuando se
     hayan completado todos los beats pendientes (no si quedan pendientes).
   - En `stream_story()` después del bucle `async for ...` y antes del evento `DONE`,
     incluyendo `narrative_id` en el payload del evento.

### 4.3 Punto de inserción del título por defecto

```python
# Helper compartido en GenerateNarrativesUseCase
def _default_title(story: Story) -> str:
    ts = now_argentina().strftime("%Y-%m-%d %H:%M")
    return f"{story.title} · {ts}"
```

### 4.4 Evento SSE `done` enriquecido

Hoy el evento `DONE` emite:

```json
{"story_id": "...", "total_beats": 5}
```

Pasaría a:

```json
{"story_id": "...", "total_beats": 5, "narrative_id": "..."}
```

→ Permite al frontend redirigir directamente a la vista de relato recién generado.

---

## 5. Scope

### In Scope
- Persistencia automática de `generated_narrative` al finalizar la generación CLI/streaming.
- Consolidación determinística de `macro_beat.content` → `generated_narrative.content`.
- Inyección del use case `GenerateNarrativesUseCase` en `StoryRunner` y stream pipeline.
- Enriquecimiento del evento SSE `DONE` con `narrative_id`.
- Tests unitarios e integración del nuevo paso de consolidación.
- Verificación de que la galería ahora muestra el relato sin acción manual del usuario.

### Out of Scope (este spec)
- Eliminar `macro_beat.content` (queda para spec posterior si se valida).
- Cambios en el formato de `generated_narrative.content` (sigue siendo TEXT plano).
- UX de re-generación múltiple / gestión de variantes en galería (cubierto por Spec-300/311).
- Cambios en `narrative_router.py` (el endpoint manual sigue funcionando para casos
  ad-hoc de regeneración a partir de beats existentes).

---

## 6. TASKS (expandido tras D1.c + Opción A + título determinístico)

### Slice S0 — Baseline
- [ ] **S0-T1** — `make lint` + `make test` snapshot (capturar contador antes/después).
  - Comando: `make test 2>&1 | tail -5`
  - Esperado actual: ~497 passed (referencia Spec-311).
- [ ] **S0-T2** — Reproducción funcional rápida con mock (opcional, ya confirmado por análisis):
  - `uv run python -m src generate --use-mock --title "smoke" --protagonista "x" ...`
  - Verificar: `sqlite3 stories.db "SELECT COUNT(*) FROM generated_narrative"` → 0.

### Slice S1 — Use case + persistencia automática en CLI

- [ ] **S1-T1** — Extender `GenerateNarrativesUseCase` con método para flujo automático.
  - Archivo: `src/application/use_cases/generate_narratives_use_case.py`
  - **Agregar**:
    - Helper privado `_default_title(story: Story) -> str`:
      `f"{story.title} · {now_argentina().strftime('%Y-%m-%d %H:%M')}"`
    - Método nuevo `consolidate_and_save(story: Story, title: str | None = None) -> GeneratedNarrative`
      que:
      1. Si `story.beats` está vacío → `raise ValueError("La historia no tiene beats para consolidar")`.
      2. Construye `content = "\n\n".join(b.content for b in sorted(story.beats, key=lambda b: b.number) if b.content)`.
      3. Si `content` vacío → `raise ValueError("No hay prosa generada en los beats")`.
      4. Crea `GeneratedNarrative(story_template_id=story.id, title=title or self._default_title(story), content=content, status=StoryStatus.COMPLETED)`.
      5. `return await self.narrative_repo.save(narrative)` — siempre `INSERT` (D1.c, nuevo UUID por corrida).
  - **Mantener intacto** `generate_from_existing_beats(story_id, title)` (lo usa el endpoint manual).

- [ ] **S1-T2** — Inyectar use case en `CLIContainer`.
  - Archivo: `src/infrastructure/container.py`
  - Agregar import: `from src.application.use_cases.generate_narratives_use_case import GenerateNarrativesUseCase`
  - Agregar factory:
    ```python
    def narrative_use_case(self) -> GenerateNarrativesUseCase:
        return GenerateNarrativesUseCase()
    ```
  - Pasarlo en `story_runner()` como nuevo arg `narrative_use_case=self.narrative_use_case()`.

- [ ] **S1-T3** — Hookear `StoryRunner` para popular la tabla.
  - Archivo: `src/core/orchestrator.py`
  - Constructor: nuevo arg `narrative_use_case: "GenerateNarrativesUseCase | None" = None` (None = no-op
    para tests legacy que no lo inyecten).
  - Importar `GenerateNarrativesUseCase` bajo `TYPE_CHECKING`.
  - **`run_full()`** — al finalizar el bucle `async for ... director.execute_full()`, **antes** del
    bloque de `debug_collector` y **solo si** `stop_after is None`:
    ```python
    story.beats = completed
    if stop_after is None and self.narrative_use_case is not None:
        try:
            narrative = await self.narrative_use_case.consolidate_and_save(story)
            self._last_narrative_id = narrative.id  # exponer para el caller (CLI lo loggea)
            logger.info(f"[NARRATIVE] Consolidada y persistida: {narrative.id}")
        except Exception as exc:
            logger.warning(f"[NARRATIVE] Fallo consolidación: {exc}")
            # No abortamos: la historia quedó OK aunque la variante no se haya creado.
    ```
  - **`run_from_story()`** — análogo: al final, si **todos** los beats quedaron `COMPLETED`
    (es decir `len(completed) == len(pending_beats)` y los previos también estaban completed),
    invocar `consolidate_and_save(story)`. Recargar `story.beats = await self.beat_repo.get_by_story(story.id)`
    antes de consolidar para incluir los previamente completados.

- [ ] **S1-T4** — Tests unitarios.
  - Archivo nuevo: `tests/unit/application/use_cases/test_generate_narratives_use_case.py`
    - `test_consolidate_and_save_concatenates_beats_in_order`
    - `test_consolidate_and_save_uses_default_title_when_none`
    - `test_consolidate_and_save_uses_explicit_title_when_provided`
    - `test_consolidate_and_save_raises_when_no_beats`
    - `test_consolidate_and_save_raises_when_all_beats_empty`
    - `test_consolidate_and_save_creates_new_uuid_each_call` (verifica D1.c).
  - Archivo: `tests/unit/core/test_orchestrator.py`
    - `test_run_full_persists_generated_narrative_at_end`
    - `test_run_full_skips_narrative_when_stop_after_set`
    - `test_run_full_does_not_fail_if_narrative_save_raises` (logger warning, sigue OK).

### Slice S2 — Persistencia automática en streaming web

- [ ] **S2-T1** — Aceptar `narrative_use_case` en `stream_story`.
  - Archivo: `src/application/services/streaming_service.py`
  - Firma nueva:
    ```python
    async def stream_story(
        director: DirectorUseCase,
        story: Story,
        story_repo=None,
        beat_repo=None,
        narrative_use_case=None,
    ) -> AsyncGenerator[StreamEvent, None]:
    ```
  - Después del `async for ...` y **antes** del bloque que emite `DONE`:
    ```python
    narrative_id = None
    if narrative_use_case is not None and beats_collected:
        try:
            story.beats = beats_collected  # asegurar que el use case ve los beats
            narrative = await narrative_use_case.consolidate_and_save(story)
            narrative_id = str(narrative.id)
            logger.info(f"[STREAM][NARRATIVE] Consolidada: {narrative.id}")
        except Exception as exc:
            logger.warning(f"[STREAM][NARRATIVE] Fallo consolidación: {exc}")
    ```
  - Modificar el evento `DONE`:
    ```python
    StreamEvent(
        event=StreamEventType.DONE,
        data={
            "story_id": str(story.id),
            "total_beats": beat_number,
            "narrative_id": narrative_id,  # nuevo
        },
    )
    ```
  - Importante: respetar Spec-201 → no cambiar el orden ni timing del evento `DONE`,
    sólo enriquecer su `data`.

- [ ] **S2-T2** — Inyectar use case en `stream_router._producer_factory`.
  - Archivo: `src/presentation/routers/stream_router.py`
  - Importar `GenerateNarrativesUseCase` y construirlo.
  - Pasarlo a `stream_story(...)` como `narrative_use_case=GenerateNarrativesUseCase()`.

- [ ] **S2-T3** — Tests del stream.
  - Archivo: `tests/unit/application/services/test_streaming_service.py` (crear si no existe)
    - `test_stream_emits_done_with_narrative_id_when_use_case_injected`
    - `test_stream_emits_done_with_null_narrative_id_when_use_case_omitted` (compat).
    - `test_stream_continues_emitting_done_when_narrative_save_fails` (warning, no error).
  - Si ya existen tests de streaming: parchear/actualizar las aserciones del payload `DONE`.

### Slice S3 — Validación E2E + verificación cross-flujo

- [ ] **S3-T1** — Smoke test CLI con mock:
  ```bash
  uv run python -m src generate --use-mock --title "Spec312 smoke" \
    --protagonista "X" --relator "tercera_persona" --escenarios "casa" \
    --sinopsis "..." --atmosfera "..."
  ```
  Verificar:
  - `sqlite3 stories.db "SELECT id, title FROM generated_narrative ORDER BY created_at DESC LIMIT 1"` → 1 fila reciente.
  - El título incluye sufijo de timestamp.

- [ ] **S3-T2** — Smoke test SSE manual (browser dev tools):
  - Iniciar generación desde frontend de wizard.
  - En la consola SSE, verificar que el evento `done` incluye `narrative_id` válido.
  - Abrir galería → "Ver Relato" → comprobar render no vacío.

- [ ] **S3-T3** — Compatibilidad con endpoint manual:
  - Tras una generación exitosa, llamar `POST /story-templates/{id}/generate-narrative?title=manual`.
  - Verificar que ahora hay **2** filas en `generated_narrative` para esa historia
    y que el switcher de `relatos.ejs` muestra ambas (alineado con D1.c).

- [ ] **S3-T4** — Suite completa:
  - `make lint` (debe pasar).
  - `make test` (sin regresiones — el contador debe ser ≥ baseline + nuevos tests).
  - `cd frontend && npm test` (sin regresiones — 15 passed referencia).

---

## 7. Criterios de aceptación

1. Tras `python -m src generate ...`, `SELECT COUNT(*) FROM generated_narrative WHERE story_template_id = ?`
   devuelve **≥ 1**.
2. Tras una generación SSE exitosa, el evento `DONE` incluye `narrative_id` válido y
   la fila correspondiente existe en `generated_narrative`.
3. Galería → "Ver Relato" muestra contenido inmediatamente tras una generación CLI o web,
   sin requerir clic adicional de "Generar relato" en la pantalla de detalle.
4. El contenido consolidado es exactamente `"\n\n".join(beat.content for beat in sorted_beats)`
   (consistente con la semántica actual del endpoint manual).
5. `CLI narrate <story_id> --beats 1,2` (re-narrar parciales) **NO** crea una nueva variante
   en `generated_narrative` (sólo actualiza `macro_beat.content`); sigue siendo necesario un
   `generate-from-db` o un nuevo `POST` para snapshotear.
6. `make lint`, `make test`, `frontend npm test` verdes.
7. No se introducen migraciones SQL ni `ALTER TABLE`: si hace falta cambio de esquema,
   actualizar `init_db()` y recrear la DB (regla del proyecto).

---

## 8. Riesgos

- **Doble snapshot**: si el usuario invoca el endpoint `POST /generate-narrative` justo
  después de una generación CLI/web, quedan dos filas. Producto: aceptable bajo D1.c (variantes).
  Mitigación: el frontend de Spec-311 ya soporta switcher entre variantes.
- **Generaciones parciales (checkpoint `--hasta`)**: si el pipeline se detiene antes del beat 5,
  no debería crearse `generated_narrative`. Hay que respetar el `stop_after`.
- **Timing del evento `DONE`**: el `narrative_id` debe estar disponible antes de emitir el
  evento; no se puede emitir y guardar en paralelo.
- **Tests existentes** que asumen `COUNT(generated_narrative) = 0` tras una corrida CLI:
  inventariar y actualizar (búsqueda `grep -rn "generated_narrative" tests/`).
- **Stream cancelado a mitad**: no crear narrative si el bucle se interrumpe (ya cubierto
  por el patrón "antes del DONE" — la cancelación corta antes).

---

## 9. Notas y referencias

- `MEMORY.md → feedback_no_migration_scripts`: prohibido `ALTER TABLE`, recrear DB.
- `MEMORY.md → project_spec201_streaming_constraints`: respetar las 5 restricciones del SSE.
  Particularmente: el `narrative_id` debe pasar por el normalizer si se incluye texto;
  como es UUID puro, no aplica.
- Spec-311 (cerrado): habilitó el switcher de variantes en `relatos.ejs`. Este spec
  es el que efectivamente lo alimenta para CLI/streaming.
- Spec-300 (refactor varios relatos): origen del concepto "una historia → muchas variantes".

---

## 10. Estado

- [x] SPECIFY — hallazgos confirmados, opciones de diseño documentadas.
- [x] PLAN — D1.c + Opción A + título determinístico aprobados (2026-05-05).
- [x] TASKS — sección 6 expandida con archivos, funciones, casos de test.
- [x] IMPLEMENT — Slices S0–S3 cerrados (2026-05-05).

## 11. Resultado de implementación (2026-05-05)

**Cambios en código:**
- `src/application/use_cases/generate_narratives_use_case.py` — nuevo método
  `consolidate_and_save(story, title=None)` + helper `_default_title`. Reusa
  `_consolidate_content` y `generate_from_existing_beats` queda como wrapper.
- `src/infrastructure/container.py` — factory `narrative_use_case()` + inyección
  automática a `story_runner()`.
- `src/core/orchestrator.py` — `StoryRunner` acepta `narrative_use_case`,
  expone `last_narrative_id`, invoca `_consolidate_narrative()` en `run_full`
  (si `stop_after is None`) y en `run_from_story` (si todos los beats quedan
  completed). Errores de consolidación se loguean como warning sin abortar.
- `src/application/services/streaming_service.py` — `stream_story()` acepta
  `narrative_use_case`, consolida antes del evento `DONE` y enriquece su
  payload con `narrative_id` (puede ser `null` si la consolidación falla).
- `src/presentation/routers/stream_router.py` — wiring del use case en el
  productor SSE.

**Tests nuevos (12 casos, todos verdes):**
- `tests/unit/application/use_cases/test_generate_narratives_use_case.py` — 6 casos
  (orden, título default, título explícito, beats vacíos, prosa vacía, UUID nuevo por corrida).
- `tests/unit/core/test_orchestrator.py` — 3 casos
  (persistencia automática, skip con `stop_after`, robustez ante fallo del use case).
- `tests/unit/application/services/test_streaming_service.py` — 3 casos
  (DONE con `narrative_id`, DONE con `narrative_id=null` sin use case,
  resiliencia ante fallo).

**Verificación final:**
- `make lint` (`ruff check . && ruff format .`) → All checks passed.
- `pytest tests` → **509 passed** (497 baseline + 12 nuevos).
- `frontend npm test` → **15 passed** (sin regresiones).
- Smoke E2E CLI con mock + DB temporal:
  ```
  Filas en generated_narrative: 1
  {'title': 'Spec312 Smoke · 2026-05-05 14:41', 'bytes': 108, ...}
  ```
  Confirma que `generated_narrative` se popula automáticamente y el título sigue
  el formato determinístico acordado.

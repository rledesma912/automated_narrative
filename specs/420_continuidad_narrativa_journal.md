# SPEC-420: Continuidad Narrativa — Cablear `unresolved_mysteries` al Contexto del Beat Siguiente

**Fecha:** 2026-09-21
**Tipo:** SDD (Spec-Driven Development)
**Estado:** DONE (todas las tareas marcadas; estado actualizado 2026-09-24, Spec-520)

---

## ASSUMPTIONS

1. El pipeline real de generación (usado por `generate` y por streaming web) es `DirectorUseCase.execute_full()` → `VozUseCase.narrate()` → `NarrativeContextAssembler.assemble()`. El método `VozUseCase.execute()` / `build_beat_prompt()` es una ruta legacy usada solo por `execute_narration()` (comando CLI `narrate --beats` para retomar beats sueltos) y **no** se toca en este spec.
2. `MemoryJournalist.extract()` ya extrae correctamente `unresolved_mysteries` del LLM y lo persiste en el objeto `NarrativeJournal` (verificado en `memory_journalist.py:91` y `journal.md:29`) — el dato existe, solo falta consumirlo.
3. El fix es puramente de "wiring": no se toca el prompt de extracción del Journalist (`journal.md`) ni se amplía la riqueza de lo que captura — eso queda fuera de alcance (evaluado y descartado para este evolutivo).
4. No hay conflicto con los cambios sin commitear de Spec-410 (`director_use_case.py`, `scenario_resolver_service.py`): ese trabajo toca la distribución de escenarios, no `narrative_context_assembler.py` ni `build_synopsis_mapper_one_prompt()`.

---

## OBJECTIVE

Las historias generadas pierden hilos narrativos: un misterio o pista plantada en un acto (ej. "algo se movió en el granero") desaparece por completo para los actos siguientes, aunque el Journalist ya lo extrae y lo guarda en `narrative_journal.unresolved_mysteries` cada beat.

**Causa raíz verificada:** ese campo nunca se lee de vuelta.
- `NarrativeContextAssembler.assemble()` (`narrative_context_assembler.py:73-78`) arma el bloque `MEMORIA DEL ACTO ANTERIOR` que recibe la Voz usando solo `last_events` y `physical_emotional_state`.
- `PromptBuilder.build_synopsis_mapper_one_prompt()` (`prompt_builder.py:323-329`) arma `prev_section` para el Mapper con los mismos dos campos, tampoco `unresolved_mysteries`.

**Objetivo:** que ambos consumidores (Mapper y Voz) reciban también `unresolved_mysteries` del journal anterior, para que el modelo pueda decidir retomar, escalar o cerrar un misterio ya planteado en vez de ignorarlo.

**Éxito se ve como:** un misterio introducido en el beat N aparece referenciado (mencionado, retomado o resuelto) en el `narrative_context`/prompt del beat N+1 cuando el journal lo registró.

---

## COMMANDS

```bash
uv run pytest tests/unit/application/services/test_narrative_context_assembler.py -v
uv run pytest tests/unit/application/test_prompt_builder.py -v
make lint
make test
```

---

## PROJECT STRUCTURE

```
src/application/services/
├── narrative_context_assembler.py   # assemble() — agregar unresolved_mysteries al bloque MEMORIA
├── prompt_builder.py                # build_synopsis_mapper_one_prompt() — agregar a prev_section

tests/unit/application/
├── services/test_narrative_context_assembler.py   # nuevos casos
├── test_prompt_builder.py                          # nuevos casos
```

No se tocan templates Markdown (`journal.md`, `synopsis_mapper_one_compact.md`) — el texto se arma en Python antes de interpolarse en `{prev_snapshot_section}`.

---

## 1. NARRATIVE CONTEXT ASSEMBLER (consumidor: Voz)

### Código estilo

**Antes** (`narrative_context_assembler.py:73-78`):
```python
if previous_journal and not previous_journal.is_empty():
    lines += ["", "MEMORIA DEL ACTO ANTERIOR:"]
    if previous_journal.last_events:
        lines.append(previous_journal.last_events)
    if previous_journal.physical_emotional_state:
        lines.append(f"Estado: {previous_journal.physical_emotional_state}")
```

**Después:**
```python
if previous_journal and not previous_journal.is_empty():
    lines += ["", "MEMORIA DEL ACTO ANTERIOR:"]
    if previous_journal.last_events:
        lines.append(previous_journal.last_events)
    if previous_journal.unresolved_mysteries:
        lines.append(f"Misterios sin resolver: {previous_journal.unresolved_mysteries}")
    if previous_journal.physical_emotional_state:
        lines.append(f"Estado: {previous_journal.physical_emotional_state}")
```

Orden: eventos → misterios → estado (mantiene el patrón ya usado en `_build_journal_context`, la única otra función del código que sí combina los tres campos).

---

## 2. SYNOPSIS MAPPER PROMPT (consumidor: Mapper)

### Código estilo

**Antes** (`prompt_builder.py:323-329`):
```python
prev_section = ""
if previous_journal and not previous_journal.is_empty():
    prev_section = (
        f"\nMEMORIA DEL ACTO ANTERIOR:\n"
        f"- Últimos eventos: {previous_journal.last_events}\n"
        f"- Estado: {previous_journal.physical_emotional_state}\n"
    )
```

**Después:**
```python
prev_section = ""
if previous_journal and not previous_journal.is_empty():
    prev_section = (
        f"\nMEMORIA DEL ACTO ANTERIOR:\n"
        f"- Últimos eventos: {previous_journal.last_events}\n"
        f"- Misterios sin resolver: {previous_journal.unresolved_mysteries}\n"
        f"- Estado: {previous_journal.physical_emotional_state}\n"
    )
```

---

## PLAN

### Hito 1: Backend — wiring en NarrativeContextAssembler
1. Agregar línea `unresolved_mysteries` al bloque `MEMORIA DEL ACTO ANTERIOR` en `assemble()`
2. Agregar tests que verifiquen presencia/ausencia del campo

### Hito 2: Backend — wiring en PromptBuilder (Mapper)
3. Agregar línea `unresolved_mysteries` a `prev_section` en `build_synopsis_mapper_one_prompt()`
4. Agregar test equivalente en `test_prompt_builder.py`

### Hito 3: Verificación manual
5. Generar una historia de prueba (`--mock` o perfil local) y confirmar en el debug log (`DebugCollector`) que el `user_prompt` del beat 2 en adelante contiene la línea "Misterios sin resolver" cuando el journal del beat anterior la trae

---

## TASKS

- [x] **T1:** Agregar `unresolved_mysteries` al bloque MEMORIA en `NarrativeContextAssembler.assemble()`
  - Acceptance: si `previous_journal.unresolved_mysteries` no está vacío, aparece como línea `Misterios sin resolver: {valor}` dentro del bloque `MEMORIA DEL ACTO ANTERIOR`
  - Verify: `uv run pytest tests/unit/application/services/test_narrative_context_assembler.py -v`
  - Files: `src/application/services/narrative_context_assembler.py`

- [x] **T2:** Test `test_con_journal_incluye_unresolved_mysteries` — journal con `unresolved_mysteries="Algo se movió en el granero."` → el string aparece en el resultado de `assemble()`
  - Acceptance: test nuevo pasa
  - Files: `tests/unit/application/services/test_narrative_context_assembler.py`

- [x] **T3:** Test `test_unresolved_mysteries_vacio_no_agrega_linea` — journal con `unresolved_mysteries=""` (pero `last_events` no vacío) → no aparece la etiqueta "Misterios sin resolver"
  - Acceptance: test nuevo pasa
  - Files: `tests/unit/application/services/test_narrative_context_assembler.py`

- [x] **T4:** Agregar `unresolved_mysteries` a `prev_section` en `build_synopsis_mapper_one_prompt()`
  - Acceptance: cuando hay `previous_journal` no vacío, `prev_section` incluye la línea `- Misterios sin resolver: {valor}`
  - Verify: `uv run pytest tests/unit/application/test_prompt_builder.py -v`
  - Files: `src/application/services/prompt_builder.py`

- [x] **T5:** Test equivalente en `test_prompt_builder.py` para `build_synopsis_mapper_one_prompt()`
  - Acceptance: test nuevo pasa
  - Files: `tests/unit/application/test_prompt_builder.py`

- [x] **T6:** Verificación manual con historia de prueba (perfil local u `--mock`) inspeccionando `DebugCollector`
  - Acceptance: el prompt del beat 2 muestra la línea de misterios cuando corresponde
  - Verify: inspección manual (no automatizable sin fixture de historia completa)

---

## BOUNDARIES

- **Always:** Correr `make lint` y `make test` después de cambios.
- **Ask first:** Si al tocar `prompt_builder.py` aparece conflicto con los cambios sin commitear de Spec-410 (`director_use_case.py`, `scenario_resolver_service.py`) — no se esperan, pero avisar antes de resolver cualquier solapamiento.
- **Never:** Modificar `journal.md` (extracción) ni el esquema de `narrative_journal` — el dato ya existe, este spec es solo de lectura/propagación. Cualquier cambio de esquema requeriría actualizar `init_db()` y recrear la DB (no aplica aquí).

---

## SUCCESS CRITERIA

- `assemble()` propaga `unresolved_mysteries` cuando el journal anterior lo trae.
- `build_synopsis_mapper_one_prompt()` propaga `unresolved_mysteries` cuando el journal anterior lo trae.
- Ningún test existente se rompe (`make test`).
- Verificación manual: una historia con un misterio explícito en el beat 1 lo muestra disponible en el prompt del beat 2.

---

## OPEN QUESTIONS

Ninguna — alcance acotado y confirmado con el usuario (solo wiring, sin enriquecer la captura del journal).

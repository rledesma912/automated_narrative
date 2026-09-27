# SPEC-570: Limpieza del dominio — cada acto en un solo lugar

**Fecha:** 2026-09-27
**Tipo:** SDD (Spec-Driven Development) — deuda técnica del dominio
**Estado:** IMPLEMENT — D1–D4 decididas; plan y tareas en la Spec-560 §4–§5 (slices S1–S2)
**Rama:** `feat/analisis-asistente-ui-logica` (la implementación, en rama propia)
**Extiende:** Spec-530 (escaleta y pipeline), Spec-190 (modelo relacional).

---

## ASSUMPTIONS

1. Después de la Spec-530 un acto tiene **entrada** (la escaleta, `act_outline`) y **salida** (la prosa, `macro_beat`). La separación es correcta —rearmar la escaleta no debe borrar la prosa, y regenerar la prosa no toca la escaleta—; lo que sobra es lo que `macro_beat` todavía guarda de cuando era también la entrada.
2. Sin migraciones: cambio de esquema = `init_db()` + DB nueva, en dev y en prod. **Datos (2026-09-27):** etapa de desarrollo: las historias de prod son descartables. No se valida ni se migra lo que hay en prod; ante un cambio de esquema o de semántica, se recrea la DB. **Se hace en el mismo pase que la columna nueva de la Spec-560 A1.**
3. Regresión cero en lo que ve el usuario y en los prompts: el snapshot `tests/fixtures/snapshots/pipeline_prompts.json` no cambia.
4. Los YAML de `input_stories/` (fixtures de los tests y del evaluador) se siguen importando.

---

## OBJECTIVE

Que el dominio diga lo que el sistema hace: **la escaleta es la entrada de cada acto y `macro_beat` es solo su salida**, sin columnas que dupliquen la escaleta ni nombres del pipeline viejo.

**Éxito:** ninguna columna de `macro_beat` repite algo de `act_outline`; ningún nombre del código habla de roles o pasos que ya no existen; YAML de ida y vuelta intacto; misma prosa y mismos prompts.

---

## 1. HALLAZGOS

### 1.1 `macro_beat` guarda cosas de la entrada

| Columna | Qué guarda hoy | Quién la escribe | Quién la lee | Veredicto |
|---|---|---|---|---|
| `generated_act` | la prosa del acto | Voz | relato, regenerar, control de repetición | **se queda** |
| `status` | pendiente / completado | pipeline | relato, regenerar | **se queda** |
| `system_prompt`, `user_prompt` | los prompts enviados a la Voz | Voz | debug (`debug_renderer`) | **se queda** (trazabilidad) |
| `summary` | los hechos del acto en viñetas (copia de `act_outline.events`); en historias importadas, «Acto N: tipo» | pipeline (`director_use_case.py:74`), `create_story.py:108` | la sala de generación en modo lectura (`streaming-room.ejs:51`, vía `GET /beats`) | **sale**: la sala lee los hechos de la escaleta |
| `synopsis_beat` | la sinopsis por acto de los YAML viejos | `create_story.py:110`; el pipeline la conserva | el export YAML (`yaml_exporter.py:180`) | **sale**: al importar, pasa a la escaleta (D2) |
| `type` (`beat_type`) | «exposicion», «climax»… | pipeline, `create_story` | eventos de la sala (`beat_start`) | **sale**: se deriva del número de acto (`llm_beats_definition.yaml`) |
| `active_scenario_id` | — | nadie en el camino actual | repos | **sale** |
| `active_scenario_description` | el escenario del acto (copia de `act_outline.scenario`) | pipeline (`director_use_case.py:76`) | nadie más | **sale** |

### 1.2 Nombres del pipeline viejo

- `DirectorUseCase` corre el pipeline de la escaleta; ya no existe un rol «Director» (salió en S7b de la Spec-530).
- `MacroBeat` y el alias `Beat = MacroBeat` (`models.py:155`) conviven con `ActOutline`: el mismo concepto se llama «beat» en la salida y «acto» en la entrada. `BeatType`, `get_beat_info`, `num_beats`, `beat_repository`, `GET /stories/{id}/beats`, el evento `beat_start`, `rule.applies_to_beat`.
- El rol `director` de los perfiles LLM (`config/llm_core_definitions.yaml`) es hoy solo la **base** de `consultor` / `planificador` / `verificador`.

### 1.3 Duplicados en `story` (fuera del punto 4; se listan para decidir alcance)

- `story.sinopsis` y `direction.premise` («¿De qué trata?»): el router del asistente los mantiene iguales (`authoring_router.py:285/301`).
- `story.protagonista` guarda «nombre: qué hace» en un texto, y el protagonista también es el primer `character`.
- `story.relator` y `narrator_config.storyteller_*` dicen quién narra.

---

## 2. CAMBIOS PROPUESTOS

1. **`macro_beat` solo salida:** quedan `id, story_id, number, generated_act, status, system_prompt, user_prompt, created_at`. Salen `summary`, `synopsis_beat`, `type`, `active_scenario_id`, `active_scenario_description`.
2. **Quien leía esas columnas lee la escaleta:**
   - la sala en modo lectura muestra los hechos de `act_outline` (el endpoint trae el `act_outline` del acto, o la sala lo pide aparte);
   - el tipo de acto sale de `get_beat_info(number)`;
   - el export YAML escribe la escaleta (ya lo hace) y deja de leer `synopsis_beat`.
3. **Importar YAML viejos:** la sinopsis por acto (`actos.*.synopsis`) va a la escaleta (D2) en vez de a `macro_beat`.
4. **Nombres** (D3): el concepto es **acto** en todo el dominio.
5. **`story`** (D4): alcance a decidir.

---

## 3. DECISIONES

**✅ 2026-09-27: el usuario aprueba las cuatro recomendaciones** — D1 mismo pase que la Spec-560 A1; D2 (a) la sinopsis por acto va a la escaleta como primer hecho; D3 (a) renombrar solo por dentro; D4 (a) los duplicados de `story` van en una spec aparte.

- **D1 — ¿Cuándo?** Recomendación: **en el mismo pase a prod que la Spec-560 A1** (las dos cambian el esquema: se recrea la DB una sola vez).
- **D2 — La sinopsis por acto de los YAML viejos.** (a) **va a la escaleta como primer hecho** del acto (recomendada: la historia importada arranca con escaleta y el Planificador no tiene que inventarla); (b) se descarta (el Planificador arma la escaleta desde la sinopsis general).
- **D3 — Renombrar.** (a) **Solo por dentro** (recomendada): `MacroBeat` → `ActText`, `DirectorUseCase` → `GenerateStoryUseCase`, `BeatType` → `ActType`, fuera el alias `Beat`; se mantienen los caminos de la API (`/beats`), el evento `beat_start` y `applies_to_beat` para no tocar el frontend ni los YAML. (b) También la API y los eventos (`/acts`, `act_start`): más prolijo, más superficie (frontend, E2E, YAML). (c) No renombrar.
- **D4 — Duplicados de `story` (1.3).** (a) **Fuera de esta spec** (recomendada: tocan la ficha, el export y el asistente; conviene una spec aparte); (b) incluirlos.

---

## 4. CRITERIOS DE ÉXITO

1. `macro_beat` tiene solo las columnas de salida; `init_db()` y los repos, sin las columnas que salen.
2. El snapshot de prompts no cambia; la prosa del mock E2E, igual.
3. `export-yaml` → `import-yaml` de los 3 YAML de `input_stories/`: misma escaleta, dirección, taller y personajes.
4. La sala en modo lectura muestra los hechos de cada acto (desde la escaleta).
5. Sin referencias a `DirectorUseCase`, `MacroBeat` ni al alias `Beat` en `src/` (si D3 = a o b).
6. Suite completa en verde; dev actualizado (Spec-540 §2.5).

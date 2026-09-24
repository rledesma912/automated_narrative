# Spec 190 — Restructuración del modelo relacional

> Estado: **SPECIFY + PLAN + TASKS** (pendiente OK del usuario para pasar a IMPLEMENT).
> Metodología: SDD. Refactor quirúrgico, slices verticales (`incremental-implementation`).
> DB: sin scripts de migración — se reescribe `init_db()` y se recrea `data/dev/stories.db`.

## 1. Objective

El esquema actual acumula deuda: columnas huérfanas, datos no relacionales embebidos en
JSON, una tabla de unión que no refleja la realidad del dominio y nombres que mienten
sobre su contenido. Esta spec define el **modelo relacional definitivo** y el refactor
del código asociado.

Éxito = el sistema genera historias igual que antes (mismo pipeline de 17 llamadas LLM),
pero sobre un esquema normalizado, sin columnas muertas, con reglas asignadas de forma
determinística por el usuario y con trazabilidad completa del prompting por beat.

## 2. Tech Stack

Sin cambios: Python 3 / FastAPI / `aiosqlite` / Pydantic / pytest / `uv`. Frontend
Express + EJS + HTMX.

## 3. Commands

```bash
make db          # recrea data/dev/stories.db con el nuevo esquema
make test        # pytest -v --cov=src
make lint        # ruff check + format
uv run python -m src generate --input input_stories/la_ofrenda.yaml --mock --debug
```

## 4. Decisiones de diseño

### 4.1 Modelo relacional definitivo (8 tablas)

```
story          id, title, protagonista, relator, sinopsis,
               genero, subgenero, tono,        ← reemplazan `atmosfera` (string)
               narrator_config (JSON),         ← ex `storyteller_config`, depurado
               status, created_at
               ✗ narrative_brief  ✗ file_path  ✗ personajes(JSON)  ✗ atmosfera

character      id, story_id FK, name, role, traits(JSON), order_index      ← NUEVA
rule           id, story_id FK, content, type, intensity, applies_to_beat  ← + applies_to_beat
scenario       id, story_id FK, order_index, name, description             ← + description
macro_beat     id, story_id FK, number, summary,
               synopsis_beat,        ← NUEVO  (input del usuario, ex `actos.act_N.text`)
               generated_act,        ← rename de `content`
               system_prompt,        ← NUEVO  (se persiste)
               user_prompt,          ← rename de `narrative_context`
               status, type, active_scenario_id, active_scenario_description, created_at
               ✗ technical_context
narrative_anchors    sin cambios
narrative_journal    sin cambios
generated_narrative  sin cambios

✗ macro_beat_rule    (tabla eliminada)
```

Resultado: 8 tablas (`+character`, `-macro_beat_rule`).

### 4.2 Campos eliminados

| Campo | Tabla | Justificación verificada |
|---|---|---|
| `technical_context` | `macro_beat` | Columna en el esquema, **cero** lecturas/escrituras en `src/`. Muerta. |
| `narrative_brief` | `story` | Solo la escribe el path legacy `DirectorUseCase.execute()`/`SynopsisBeatMapper.map()`. El pipeline actual (`execute_full`→`prepare_story`) no la usa. |
| `file_path` | `story` | Soportaba la exportación a Markdown físico en `frontend/public`, feature discontinuada. |
| `personajes` (JSON) | `story` | Se normaliza a la tabla `character`. |
| `atmosfera` (string) | `story` | Texto libre legacy. Se reemplaza por `genero`/`subgenero`/`tono` estructurados. |

### 4.3 `narrator_config` (ex `storyteller_config`)

`storyteller_config` sí alimenta los prompts (system prompt del VOZ vía
`build_voice_system_compact` + `PersonaService`): `voice`, `perception`, `knowledge`,
`language`, `bias`. Se conserva como JSON pero **depurado**:

- Se renombra a `narrator_config`.
- Se le **quitan** `scenarios`, `rules`, `actos` (pasan a tablas) y `atmosphere` (pasa a
  columnas `genero`/`subgenero`/`tono`).
- El resto (`storyteller_id`, `storyteller_name`, `voice_style`, `voice`, `perception`,
  `knowledge`, `language`, `bias`) queda **tal cual**.

### 4.4 Reglas: globales o por acto (decisión 5a)

- Una `rule` es **global** o está **anclada a un único acto**. Lo decide el usuario en el
  wizard del frontend — **no el LLM**.
- `rule.applies_to_beat`: `INTEGER` nullable. `NULL` = global; `1..N` = ese acto.
- `RuleType` pierde `evento` y `accion_personaje` (lo temporal no es regla: va en
  `macro_beat.synopsis_beat`). Quedan: `psicologica`, `entorno`, `fenomeno`, `indicador`.
- Se elimina la tabla `macro_beat_rule`.
- `RuleScenarioResolverService` deja de distribuir reglas: las reglas activas de un beat
  son `applies_to_beat IS NULL OR applies_to_beat = N`, resuelto en consulta SQL sin LLM.

### 4.5 Renames en `macro_beat`

| Antes | Después | Significado |
|---|---|---|
| `content` | `generated_act` | Prosa generada por el VOZ. |
| `narrative_context` | `user_prompt` | Mensaje *user* que recibe el VOZ. |
| — | `system_prompt` | Mensaje *system* del VOZ (hoy efímero, ahora persistido). |
| — | `synopsis_beat` | Sinopsis del acto que carga el usuario (ex `actos.act_N.text`). |

### 4.6 Renombre y simplificación de `RuleScenarioResolverService`

`RuleScenarioResolverService` → **`ScenarioResolverService`**. Tras quitar la
distribución de reglas, su única responsabilidad es distribuir escenarios — SRP
satisfecho por sustracción, no se divide en dos clases (sería YAGNI). Se elimina el
parseo de `rules` en `_parse_distribution`, el mapeo `id_to_content` y los templates
`rule_resolver_*` se reescriben a solo-escenarios. Spec-041 se actualiza.

### 4.7 Ciclo de vida de `macro_beat`

Hoy las filas `macro_beat` nacen durante la generación. Como `synopsis_beat` es input del
usuario, el wizard **pre-crea las 5 filas** al guardar la historia (`status=pending`,
`synopsis_beat` poblado, `generated_act`/`user_prompt`/`system_prompt` vacíos). La
generación pasa a hacer `UPDATE` sobre filas existentes, no `INSERT`. Afecta Spec-220/230.

## 5. Code Style

`init_db()` — cada tabla con sus constraints explícitos:

```python
await conn.execute("""
    CREATE TABLE IF NOT EXISTS rule (
        id TEXT PRIMARY KEY,
        story_id TEXT NOT NULL,
        content TEXT NOT NULL,
        type TEXT,
        intensity TEXT,
        applies_to_beat INTEGER,                       -- NULL = global; 1..N = ese acto
        FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE,
        CHECK (applies_to_beat IS NULL OR applies_to_beat >= 1)
    )
""")
```

## 6. Project Structure

Sin cambios estructurales. Archivos impactados (capas Clean Architecture):

```
src/infrastructure/database/connection.py            → init_db() reescrito
src/infrastructure/database/repositories/*.py         → story / beat repos
src/domain/models.py                                  → entidades + RuleType
src/application/use_cases/director_use_case.py        → reglas por acto, renames
src/application/services/scenario_resolver_service.py → renombrado desde rule_scenario_*
src/application/services/{prompt_builder,narrative_context_assembler}.py
src/infrastructure/loaders/yaml_loader.py             → character, narrator_config
src/infrastructure/exporters/yaml_exporter.py         → idem
src/presentation/routers/{story_router,stream_router}.py
src/presentation/schemas/{request,response}.py
frontend/                                             → wizard: selector Global/Acto
config/prompts_generation/rule_resolver_*.md          → solo escenarios
specs/041, 180, 220, 230                              → actualización
```

## 7. Testing Strategy

- Framework `pytest`; tests en `tests/unit/` y `tests/integration/`.
- **Política de ejecución:** las suites se entregan al usuario como comando; no se corren
  automáticamente. Cada slice define su comando de validación.
- Cada slice deja la suite existente en verde + agrega tests propios.
- Validación end-to-end por slice: `generate --input input_stories/la_ofrenda.yaml --mock`.
- Cobertura: no bajar respecto del baseline previo al refactor.

## 8. Boundaries

- **Always:** recrear `stories.db` tras cada cambio de esquema; mantener verde la suite
  entre slices; un slice = una preocupación lógica; renombrar de forma total (sin alias
  de compatibilidad nuevos).
- **Ask first:** tocar contratos de API consumidos por el frontend; cambiar el orden de
  los slices; modificar `export-yaml` (Spec-302), que queda fuera de alcance.
- **Never:** generar scripts de migración / `ALTER TABLE`; dejar el build roto entre
  slices; introducir un `RuleResolver` u otra clase para responsabilidad inexistente.

## 9. PLAN — Slices

Orden por riesgo creciente y dependencias. Cada slice deja el sistema funcional.

```
Slice 1  Poda de deuda muerta        → technical_context + narrative_brief + path legacy
Slice 2  Eliminar file_path          → + retiro de export Markdown web + CLI export
Slice 3  Renames en macro_beat       → content/narrative_context + system_prompt/synopsis_beat
Slice 4  Reglas globales/por-acto    → applies_to_beat, drop macro_beat_rule, ScenarioResolverService
Slice 5  Tabla character             → normaliza personajes
Slice 6  narrator_config + atmósfera → depurar JSON, genero/subgenero/tono, scenario.description
Slice 7  Ciclo de vida macro_beat    → pre-creación en wizard + actos → synopsis_beat
```

Dependencias: 3 antes de 4 y 7; 6 antes de 7. 1, 2 y 5 son independientes.

## 10. TASKS — Checklist

### Slice 1 — Poda de deuda muerta
- [x] **T1.1** Eliminar `technical_context` de `macro_beat` (`connection.py`), del modelo
  `MacroBeat` y de `beat_repository` (save/get).
- [x] **T1.2** Eliminar `narrative_brief`: columna `story`, campo `Story`/`StoryMetadata`,
  `story_repository.save`/`get`/`save_narrative_brief`, `orchestrator.py:168-169`.
- [x] **T1.3** Eliminar el path legacy de planificación: `DirectorUseCase.execute()`,
  `SynopsisBeatMapper.map()`, `PromptBuilder.build_synopsis_mapper_prompt()`, templates
  `synopsis_mapper_*` (no `_one`).
- [ ] **T1.4** (cierre de Slice 1) Eliminar el comando CLI `plan` — incompatible con el
  pipeline nuevo (decisión §12.4). Quitar: subparser y dispatch en `cli/runner.py`,
  `commands.plan`/`_plan_async` en `cli/commands.py`, la entidad `StoryPlan` de
  `domain/models.py` y su export en `domain/__init__.py` (ya sin uso tras T1.3).
  - Verify: `make db && make test` verde; `generate --mock` corre; `python -m src plan`
    ya no existe; `generate --hasta analyst` cubre el caso "planificar sin narrar".
  - Files: `cli/runner.py`, `cli/commands.py`, `domain/models.py`, `domain/__init__.py`.

### Slice 2 — Eliminar `file_path` y export Markdown web
- [ ] **T2.1** Eliminar columna `file_path` de `story` y campo de `Story`/schemas
  request/response; quitar `story_repository.update_file_path`.
- [ ] **T2.2** `story_router`: eliminar verificación de archivo físico, endpoint
  `PATCH /file-path`, borrado de `.md` en DELETE. `stream_router`: quitar `file_path` del
  evento `done`. `streaming_service`: `done` sin `file_path`.
- [ ] **T2.3** Eliminar el comando CLI `export`: subparser en `cli/runner.py`, rama de
  dispatch, `commands.export_`/`_export_async` y el helper muerto `_write_markdown`.
  Conservar `export-yaml`.
  - Verify: API levanta; CRUD de stories OK; SSE emite `done` sin `file_path`;
    `python -m src export ...` ya no existe; `export-yaml` sigue funcionando.
  - Files: `connection.py`, `models.py`, `request.py`, `response.py`,
    `story_repository.py`, `story_router.py`, `stream_router.py`, `streaming_service.py`,
    `cli/runner.py`, `cli/commands.py`.

### Slice 3 — Renames en `macro_beat`
- [ ] **T3.1** Esquema: `content`→`generated_act`, `narrative_context`→`user_prompt`,
  agregar `system_prompt`, `synopsis_beat`.
- [ ] **T3.2** `MacroBeat`: renombrar campos; ajustar `is_narrated`/`has_content`;
  agregar `system_prompt`, `synopsis_beat`. Actualizar `beat_repository`, `voz_use_case`,
  `narrative_context_assembler`, `prompt_builder`, `debug_renderer`, exporters.
- [ ] **T3.3** Persistir `system_prompt`: `voz_use_case` asigna `macro_beat.system_prompt`
  antes de guardar; `beat_repository` lo persiste.
  - Verify: `generate --mock --debug`; inspeccionar `macro_beat` — 4 columnas pobladas.
  - Files: ~8 (rename mecánico amplio; subdividir en commits si excede 5/commit).

### Slice 4 — Reglas globales/por-acto
- [ ] **T4.1** Esquema: `rule + applies_to_beat`; eliminar tabla `macro_beat_rule`.
- [ ] **T4.2** `RuleType`: eliminar `evento` y `accion_personaje`. `TypedRule +
  applies_to_beat`. `MacroBeat.active_rules` se elimina como campo per-beat.
- [ ] **T4.3** Renombrar `RuleScenarioResolverService`→`ScenarioResolverService`;
  eliminar distribución/parseo de reglas; reescribir templates `rule_resolver_*`.
- [ ] **T4.4** `director_use_case`/`narrative_context_assembler`/`voz_use_case`: reglas
  activas del beat = consulta `applies_to_beat IS NULL OR = N`. `beat_repository`: quitar
  lectura/escritura de `macro_beat_rule`.
- [ ] **T4.5** Frontend wizard: selector "Global / Acto N" por regla; round-trip YAML.
  - Verify: `generate --mock`; una regla global aparece en los 5 beats, una de acto 3
    solo en el beat 3 — determinístico entre corridas.
  - Files: `connection.py`, `models.py`, `scenario_resolver_service.py`,
    `director_use_case.py`, `narrative_context_assembler.py`, `voz_use_case.py`,
    `beat_repository.py`, `prompt_builder.py`, templates, frontend.

### Slice 5 — Tabla `character`
- [ ] **T5.1** Esquema: tabla `character`; eliminar columna `personajes` de `story`.
- [ ] **T5.2** `story_repository`: save/get de personajes contra `character`.
  `yaml_loader`/`yaml_exporter`: personajes desde/hacia la tabla.
  - Verify: crear historia con personajes; export-yaml round-trip idéntico.
  - Files: `connection.py`, `models.py`, `story_repository.py`, `yaml_loader.py`,
    `yaml_exporter.py`.

### Slice 6 — `narrator_config` + atmósfera + `scenario.description`
- [ ] **T6.1** Esquema: `story` gana `genero`/`subgenero`/`tono`, pierde `atmosfera`;
  `storyteller_config`→`narrator_config`. `scenario` gana `description`.
- [ ] **T6.2** Depurar el JSON: `narrator_config` sin `scenarios`/`rules`/`actos`/
  `atmosphere`. Ajustar `yaml_loader`/`yaml_exporter`, `PersonaService`, `prompt_builder`.
- [ ] **T6.3** Reemplazar usos de `story.atmosfera` por `genero/subgenero/tono`.
  - Verify: `generate --mock`; system prompt del VOZ conserva voz/percepción/etc.
  - Files: `connection.py`, `models.py`, `story_repository.py`, `yaml_loader.py`,
    `yaml_exporter.py`, `persona_service.py`, `prompt_builder.py`, `scenario` repo.

### Slice 7 — Ciclo de vida de `macro_beat`
- [ ] **T7.1** Pre-crear 5 filas `macro_beat` al guardar la historia (`status=pending`,
  `synopsis_beat` poblado desde `actos`). Generación pasa a `UPDATE`.
- [ ] **T7.2** Wizard/loader: mapear `actos.act_N` → `macro_beat` (`synopsis_beat`,`type`).
  - Verify: crear historia desde wizard y YAML; existen 5 `macro_beat` antes de generar;
    `generate` las actualiza sin duplicar.
  - Files: `create_story.py`, `story_router.py`, `beat_repository.py`, `yaml_loader.py`,
    `director_use_case.py`, frontend wizard.

## 11. Success Criteria

- [ ] `init_db()` crea exactamente 8 tablas; `data/dev/stories.db` recreada.
- [ ] Cero referencias en `src/` a: `technical_context`, `narrative_brief`, `file_path`,
  `storyteller_config`, `macro_beat_rule`, `atmosfera`, `RuleType.evento/accion_personaje`.
- [ ] `generate --input input_stories/la_ofrenda.yaml --mock` completa las 17 llamadas y
  consolida `generated_narrative`.
- [ ] Reglas asignadas de forma determinística: misma asignación en corridas repetidas.
- [ ] `macro_beat` persiste `synopsis_beat`, `generated_act`, `user_prompt`, `system_prompt`.
- [ ] Suite `make test` verde; `make lint` sin findings; cobertura ≥ baseline.
- [ ] Specs 041/180/220/230 actualizadas; CLAUDE.md (sección Database) actualizada.

## 12. Decisiones resueltas

1. **CLI `export` — se elimina.** El comando `export --story-id --format markdown|json`
   ya está vaciado (`_export_async` solo carga y loguea "sin archivo markdown"). Se retira
   en el Slice 2: subparser, dispatch, `commands.export_`/`_export_async` y el helper
   muerto `_write_markdown`. `export-yaml` (Spec-302) **no se toca**.
2. **`applies_to_beat`** — `INTEGER` nullable. CHECK en esquema solo
   `applies_to_beat IS NULL OR applies_to_beat >= 1`; el límite superior (`<= num_beats`,
   dinámico) se valida en la capa de aplicación al guardar la regla.
3. **Slice 3** — se mantiene como un único slice lógico (rename de 2 campos + alta de 2),
   subdividido en commits ≤5 archivos. No se parte en dos para no dejar un estado
   intermedio donde modelo y esquema no coincidan.
4. **CLI `plan` — se elimina** (decisión posterior al inicio del Slice 1). El comando solo
   recibe `--title`, sin sinopsis, y la planificación nueva (analyst + resolver) requiere
   sinopsis real para extraer anclajes. Los checkpoints `--hasta` de `generate` ya cubren
   "planificar sin narrar" con un YAML real. Se ejecuta como tarea **T1.4** (cierre del
   Slice 1) y arrastra la eliminación de la entidad `StoryPlan`, sin uso tras T1.3.

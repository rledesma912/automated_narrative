# SPEC-450: Entidades narrativas (la Amenaza) como parámetro del pipeline

**Fecha:** 2026-09-22
**Tipo:** SDD (Spec-Driven Development)
**Estado:** TASKS — PLAN aprobado (2026-09-23); tareas pendientes de OK para pasar a IMPLEMENT
**Depende de:** Spec-440 (catálogo de géneros en DB, wizard compacto)

---

## ASSUMPTIONS

1. Las entidades son **opcionales**: el terror psicológico, el suspenso o el slasher con asesino humano pueden no tener una entidad sobrenatural, o dejarla ambigua a propósito.
2. **Varias entidades por historia, con una principal** (1:0..N con `story`, máximo 3). La principal es la de `order_index = 0` (la primera card del wizard) y es la que gobierna la curva de revelación de los beats (§2).
3. Las **naturalezas** de entidad son dominio de datos, igual que los géneros en Spec-440: viven en DB, con seed en `init_db()`.
4. Sin llamadas LLM extra: las entidades entran por **ensamblado determinístico** en prompts existentes (se mantienen 17 llamadas).
6. **Sin recrear bases:** todo el esquema nuevo son tablas nuevas (`CREATE TABLE IF NOT EXISTS`), así que `init_db()` las agrega sobre las DB de dev y prod sin perder relatos generados.
5. El wizard sigue en 5 pasos: la entidad se agrega como grupo del paso *El Mundo*.

---

## OBJECTIVE

Hoy el pipeline no tiene concepto de antagonista. La búsqueda de `antagonist|entidad|criatura|amenaza` en `src/` y `config/prompts_generation/` solo encuentra "el espacio como antagonista" (pilar Peripeteia). El demonio, el espíritu o la criatura existen solo si el usuario los describe dentro de los actos o de las reglas, y cada rol LLM los reinterpreta por separado.

**Síntomas esperables:**

- **Deriva entre beats:** la entidad cambia de aspecto, de poder o de nombre de un acto a otro.
- **Revelación sin control:** no hay forma de decidir cuánto se muestra en cada acto, algo central en horror.
- **Reglas sin dueño:** los límites de la entidad ("no puede cruzar la sal") se mezclan con reglas del mundo sin quedar atados a ella.

**Éxito:** cada entidad definida en el wizard aparece coherente en los 5 actos, con el nivel de revelación elegido para ella, y su estado queda registrado en el Journal para dar continuidad.

---

## 1. MODELO DE DATOS

```sql
CREATE TABLE IF NOT EXISTS entity_nature (
    id          TEXT PRIMARY KEY,     -- 'espiritu'
    label       TEXT NOT NULL,        -- 'Espíritu / aparecido'
    order_index INTEGER NOT NULL
);

-- Qué naturalezas tienen sentido en cada género (filtra el combo)
CREATE TABLE IF NOT EXISTS genre_entity_nature (
    genre_id  TEXT NOT NULL,
    nature_id TEXT NOT NULL,
    PRIMARY KEY (genre_id, nature_id),
    FOREIGN KEY (genre_id)  REFERENCES genre(id),
    FOREIGN KEY (nature_id) REFERENCES entity_nature(id)
);

CREATE TABLE IF NOT EXISTS entity (
    id             TEXT PRIMARY KEY,
    story_id       TEXT NOT NULL,
    order_index    INTEGER NOT NULL,              -- 0 = principal
    name           TEXT,                           -- puede no tener nombre
    nature_id      TEXT NOT NULL,
    description    TEXT DEFAULT '',                -- qué es, qué quiere
    manifestations TEXT DEFAULT '',                -- cómo se percibe
    limits         TEXT DEFAULT '',                -- reglas y debilidades
    reveal_level   TEXT NOT NULL DEFAULT 'insinuada',
    UNIQUE (story_id, order_index),
    FOREIGN KEY (story_id)  REFERENCES story(id) ON DELETE CASCADE,
    FOREIGN KEY (nature_id) REFERENCES entity_nature(id)
);

-- Estado de las entidades por beat (lo escribe el Journal). Tabla aparte de
-- narrative_journal para no alterar su esquema (sin recrear bases).
CREATE TABLE IF NOT EXISTS entity_journal (
    id           TEXT PRIMARY KEY,
    story_id     TEXT NOT NULL,
    beat_number  INTEGER NOT NULL,
    entity_state TEXT NOT NULL DEFAULT '',        -- qué sabe el narrador y qué hizo cada entidad
    UNIQUE (story_id, beat_number),
    FOREIGN KEY (story_id) REFERENCES story(id) ON DELETE CASCADE
);
```

- **Por qué `entity_journal` no referencia a `entity`:** al editar una historia, `update_inputs()` borra y reinserta los hijos (`character`, `rule`, `scenario`; `entity` seguirá el mismo patrón), así que los ids de entidad cambian. La regeneración de un acto (Spec-430) lee el journal del beat anterior y no debe perderlo por una edición. Un registro por beat también coincide con que el Journal es una sola llamada LLM por beat.
- **Límite de 3 entidades:** se valida en el dominio y en el wizard (card list con máximo 3, como personajes/escenarios/reglas).

**Naturalezas (seed, a validar):** `espiritu` Espíritu / aparecido · `demonio` Demonio · `criatura` Criatura / monstruo · `humano` Humano (asesino, acosador) · `culto` Culto / colectivo · `contagio` Contagio / organismo · `lugar` Lugar vivo o maldito · `cosmica` Entidad cósmica · `folklorica` Ser del folklore · `desconocida` Desconocida / ambigua.

Mapeo género → naturalezas en `genre_entity_nature` (ej. `folk_horror` → `folklorica, espiritu, culto, lugar, desconocida`). `desconocida` está habilitada en todos los géneros. El mapeo completo se arma en PLAN junto con el seed.

**Catálogo editable a futuro:** la lista inicial son las 10 naturalezas. Para agregar o modificar se edita el seed; `init_db()` lo aplica con upsert (`INSERT … ON CONFLICT DO UPDATE` de `label`/`order_index`), así un cambio de etiqueta llega a las bases existentes sin recrearlas. (El seed de géneros de Spec-440 usa `INSERT OR IGNORE`: agrega, pero no modifica.) Un ABM del catálogo en la UI queda fuera de alcance. Una entidad cuya naturaleza no corresponde al género → 422 (mismo criterio que el par género/subgénero de Spec-440).

Dominio: `Entity` en `src/domain/models.py`; `Story.entities: list[Entity]` (máx. 3, ordenada) y `Story.principal_entity` (la primera o `None`). Persistencia en `SQLStoryRepository` (mismo patrón que `scenario`).

---

## 2. NIVEL DE REVELACIÓN

Cada entidad tiene su propio `reveal_level` (ej. un culto `explicita` que sirve a un demonio `insinuada`).

| `reveal_level` | Beat 1 | Beat 2 | Beat 3 (Anagnorisis) | Beat 4 | Beat 5 |
|---|---|---|---|---|---|
| `nunca` | señales | señales | señales intensas, sin confirmar | señales | **lo decide el acto 5** |
| `insinuada` | señales | manifestación parcial | **revelación** | límites y consecuencias | huella |
| `progresiva` | señales | manifestación parcial | presencia directa | presencia plena | huella |
| `explicita` | presencia | presencia | confrontación | consecuencias | huella |

- **Señales** = solo `manifestations`, sin nombre ni naturaleza.
- **Revelación** = `name` + `nature` + `description`.
- **Límites** = `limits` (se exponen cuando el relato los necesita).
- **Beat 5 con `nunca` (decidido 2026-09-23):** el final no se fuerza ambiguo. Si el acto 5 del escritor identifica a la entidad, se identifica; si no, queda la ambigüedad. `nunca` gobierna los beats 1–4.

La graduación vive en `config/llm_beats_definition.yaml` (fuente de verdad de beats): cada `macro_beat` suma `entity_exposure: {nunca: ..., insinuada: ..., ...}`.

**Reglas de revelación de los beats (decidido 2026-09-23: dependen del nivel).** Los beats actuales traen una curva de revelación fija que choca con algunos niveles:

| Beat | Regla actual | Choca con |
|---|---|---|
| 1 | `must_not: "confirmar lo paranormal"` | `explicita` |
| 2 | `must_not: "aceptar lo paranormal como hecho"` | `explicita` |
| 3 | `must: "mostrar amenaza o presencia directa"` | `nunca` |

- Solo estas reglas de revelación pasan a depender del `reveal_level` **de la entidad principal** (en el YAML, variantes por nivel; el resto de `must`/`must_not` queda fijo).
- **Sin entidades, los beats quedan exactamente como hoy** (se usa la variante actual).
- **Queda fija (decidido 2026-09-23):** beat 3 `must_not: "explicar origen o reglas completas del fenomeno"`. Revelar a la entidad (nombre, naturaleza, descripción) no es explicar su origen; vale para todos los niveles, incluido `explicita`.

---

## 3. INTEGRACIÓN EN EL PIPELINE

| Rol | Qué recibe | Dónde |
|---|---|---|
| Analyst | Fichas completas, principal primero (para anclar los 5 pilares a la amenaza) | template `story_analyst_*compact.md` |
| Mapper | Fichas completas + `entity_exposure` del beat por entidad (decide el evento sin revelar de más) | `synopsis_mapper_*compact.md` |
| Voz | **Solo** el bloque graduado del beat N de cada entidad | `narrative_context` vía `NarrativeContextAssembler` |
| Journal | Fichas completas → devuelve `entity_state` (un texto que cubre todas las entidades) → `entity_journal` | `journal.md` + `MemoryJournalist.extract()` |

- `PromptBuilder.build_narrative_context()` pasa `story.entities` al assembler, que agrega un bloque por entidad según su `reveal_level` y el número de beat, y elige la variante de reglas de revelación según la principal.
- **Presupuesto de tokens:** con 3 entidades el bloque de la Voz crece; en PLAN se mide el tamaño del `narrative_context` con 0, 1 y 3 entidades para los modelos locales (Ollama).
- `narrative_context = beat_spec + resonance + synopsis_event + active_scenario + entity_exposure + memory_snapshot`.
- El `entity_state` del journal del beat N-1 viaja en `memory_snapshot` al beat N (continuidad, Spec-420).
- Regeneración parcial (Spec-430): la Voz regenerada recibe el mismo bloque, sin cambios adicionales.

---

## 4. WIZARD Y ROUND-TRIP

- Grupo **"La Amenaza"** en el paso *El Mundo*: card list como personajes/escenarios/reglas, **máximo 3**, arranca vacía (sin cards → la historia no tiene entidades y no se envía nada). La card 1 se rotula "ENTIDAD 1 — PRINCIPAL".
- Campos por card N: `entity_N_name`, `entity_N_nature` (combo filtrado por el género del paso 1; el catálogo sale de `GET /api/v1/catalog/entity-natures?genre=` o se embebe en `GET /catalog/genres`, a definir en PLAN), `entity_N_description`, `entity_N_manifestations`, `entity_N_limits` y `entity_N_reveal` (radio con los 4 niveles).
- Si el usuario cambia el género del paso 1 y una naturaleza elegida deja de corresponder, esa entidad queda sin naturaleza y el paso 4 lo marca (mismo criterio que el subgénero en Spec-440).
- `mapWizardToCore()` → `narrator_config.entities` (lista). `mapStoryToWizard()` rehidrata.
- YAML (Spec-302/320): `storyteller_config.entities` en `YamlStoryLoader` y en el exporter.
- CLI `generate --input` acepta la entidad desde YAML.

---

## BOUNDARIES

- **Siempre:** entidad opcional; historias sin entidad generan exactamente igual que hoy (regresión cero).
- **Consultar antes:** cambios en los `must`/`must_not` de `llm_beats_definition.yaml` que no sean de revelación.
- **Nunca:** llamadas LLM nuevas; scripts de migración (`init_db()` + recrear `stories.db`).

---

## DECISIONES (2026-09-23)

1. **Cantidad:** varias entidades por historia (máximo 3), con una principal (la primera).
2. **Naturalezas:** combo filtrado por género (`genre_entity_nature`), `desconocida` en todos.
3. **Reglas de revelación de los beats:** dependen del `reveal_level` de la entidad principal (tabla §2); el resto de `must`/`must_not` queda fijo; sin entidades, nada cambia.
4. **Journal:** tabla nueva `entity_journal` (una fila por historia y beat), sin tocar `narrative_journal` → no hay que recrear bases.

---

## RESPUESTAS A LAS PREGUNTAS ABIERTAS (2026-09-23)

1. **Máximo de entidades:** 3.
2. **Nivel `nunca`:** no fuerza un final ambiguo; el acto 5 del escritor decide si la entidad queda identificada (§2).
3. **Naturalezas:** las 10 del seed; se podrán agregar o modificar a futuro editando el seed (upsert en `init_db()`).
4. **Evaluación:** generar `el_monte_prohibido.yaml` con y sin entidades y comparar a mano la coherencia de la entidad entre actos.

---

## PLAN

### Estrategia

De adentro hacia afuera, como en Spec-440: primero el catálogo y los datos (sin efecto en la generación), después los beats y el pipeline (con regresión cero verificada sin entidades), y al final el wizard. Todo el esquema nuevo son tablas nuevas: `init_db()` las crea al arrancar sobre las bases existentes, **sin recarga de prod**.

### Mapa

```
S0 Catálogo de naturalezas ─▶ S1 Dominio + persistencia + API + YAML ─┬─▶ S2 Beats: revelación por nivel ─▶ S3 Pipeline (5 roles + journal)
                                                                       └─▶ S4 Wizard «La Amenaza» ◀───────────────────────────────┘
                                                                                     S5 Evaluación con el_monte_prohibido ─▶ S6 Docs + DONE
```

### Decisiones técnicas del plan

1. **De dónde saca el wizard las naturalezas:** se embeben en la respuesta de `GET /catalog/genres` (cada género trae `entity_natures: [{id, label}]`). El frontend ya cachea y embebe ese catálogo; el género se elige en el paso 1 y las entidades están en el paso 4, así que el filtro se hace en el render del servidor con el género de la sesión. No hace falta un endpoint nuevo ni JS dependiente.
2. **Mapeo género → naturalezas (seed inicial; `desconocida` en todos):**

| Género | Naturalezas |
|---|---|
| `terror_psicologico` | humano, espiritu, lugar, desconocida |
| `horror_cosmico` | cosmica, culto, criatura, lugar, desconocida |
| `terror_gotico` | espiritu, demonio, criatura, lugar, humano, desconocida |
| `body_horror` | contagio, criatura, humano, cosmica, desconocida |
| `paranormal` | espiritu, demonio, lugar, folklorica, desconocida |
| `folk_horror` | folklorica, espiritu, culto, lugar, demonio, desconocida |
| `suspenso` | humano, culto, desconocida |
| `terror_supervivencia` | criatura, humano, contagio, culto, desconocida |

3. **Reglas de revelación en el YAML de beats:** las 3 reglas que chocan salen de `must`/`must_not` y pasan a un bloque `reveal_rules` por beat, con una variante `default` (la de hoy) y overrides por nivel. `BeatSpecRepository.get_by_id(beat_id, reveal_level=None)` devuelve el beat resuelto: `must_not = fijos + reveal_rules.must_not[nivel | default]` (ídem `must`). Sin entidades se usa `default` y, como las 3 reglas hoy van al final de su lista, **el texto resultante es idéntico al actual** (se verifica con un test de snapshot antes de tocar el YAML). El mismo bloque trae `entity_exposure` por nivel (la tabla de §2).
4. **Topes de largo por campo** (para los contextos de 4096 tokens del Analyst y el Journal): `name` 60, `description` 400, `manifestations` 300, `limits` 300 caracteres. Se validan en el dominio (422) y se muestran como `maxlength` en el wizard. Se ajustan con la medición de S3.
5. **Journal:** la plantilla suma la clave `entity_state` al JSON **solo si la historia tiene entidades** (sin entidades el prompt no cambia). `NarrativeJournal` suma `entity_state` opcional; el repo lo guarda en `entity_journal`, y `get_journal()` lo trae de vuelta, así llega a la Voz del beat siguiente y a la regeneración de un acto (Spec-430) sin tocar esos llamadores.

### S0 — Catálogo de naturalezas (backend)

- **Qué:** tablas `entity_nature` y `genre_entity_nature` con seed (upsert) y el mapeo de arriba; `GET /catalog/genres` suma `entity_natures` por género; `SQLGenreRepository` las lee.
- **Verificación:** pytest (seed idempotente; upsert actualiza una etiqueta; endpoint con natures ordenadas; `desconocida` en los 8 géneros).
- **Despliegue:** se puede desplegar solo (aditivo, nadie lo consume todavía).

### S1 — Dominio, persistencia, API y YAML

- **Qué:** `Entity` + `Story.entities` (máx. 3, topes de largo), tabla `entity`, `SQLStoryRepository` (save, `update_inputs` borra y reinserta, carga ordenada); `narrator_config.entities` en request/response y en `_request_to_dto`; validación naturaleza ↔ género (422); `YamlStoryLoader`/exporter (`storyteller_config.entities`) e `import-yaml`.
- **Verificación:** pytest (round-trip DB y YAML con 0, 1 y 3 entidades; 4 → error; naturaleza de otro género → 422; editar una historia no toca `entity_journal`).
- **Sin efecto en la generación** todavía: el pipeline no lee `story.entities`.

### S2 — Beats: revelación por nivel

- **Qué:** snapshot de las salidas actuales (`format_for_beat` compact/frontier, `assemble`, `acts_json` del resolver) → mover las 3 reglas a `reveal_rules` + `entity_exposure` en `llm_beats_definition.yaml` → `get_by_id(beat_id, reveal_level)`.
- **Verificación:** pytest — sin nivel, el snapshot es idéntico byte a byte; `explicita` quita los `must_not` de los beats 1 y 2; `nunca` quita el `must` de presencia directa del beat 3.

### S3 — Pipeline (Analyst, Resolver, Mapper, Voz, Journal)

- **Qué:**
  - Analyst y Mapper: bloque de fichas (principal primero) en sus templates; el Mapper suma la exposición del beat por entidad.
  - Resolver y Mapper usan el beat resuelto con el nivel de la principal.
  - Voz: `NarrativeContextAssembler` agrega un bloque «AMENAZA EN ESTE ACTO» con la exposición graduada de cada entidad y `entity_state` en la memoria del acto anterior.
  - Journal: `entity_state` → `entity_journal`.
- **Regresión cero:** test que genera con `MockLLMAdapter` una historia sin entidades y compara los 17 prompts contra los de antes del cambio.
- **Medición:** script que arma los prompts de los 5 roles con 0, 1 y 3 entidades (campos al tope) y reporta tokens estimados contra el `num_ctx` de cada rol del perfil activo. Si algún rol se pasa, se ajustan los topes o se resume la ficha para ese rol.
- **Verificación:** pytest (bloques presentes/ausentes según nivel y beat; `entity_state` persiste y vuelve en `get_journal`; regeneración de un acto recibe el estado).

### S4 — Wizard «La Amenaza»

- **Qué:** grupo `amenaza` en el paso 4 con `wizard_card_list` (máx. 3, arranca vacío, card 1 «PRINCIPAL»); campos `entity_N_*` en `ui_definitions.yaml` con `source: entity_natures` (filtrado por el género de la sesión) y `maxlength`; `submitStep` descarta naturalezas que no corresponden al género (como el subgénero); `mapWizardToCore`/`mapStoryToWizard`; la confirmación muestra las entidades.
- **Verificación:** Vitest (mapper ida y vuelta, render filtrado, descarte al cambiar de género) + Playwright (agregar 2 entidades, guardar, editar y verlas rehidratadas; cambiar el género deja sin naturaleza la que no corresponde).
- **Despliegue:** S2 + S3 + S4 salen juntos (antes de S4 nadie puede cargar entidades desde la web).

### S5 — Evaluación

- **Qué:** generar `el_monte_prohibido.yaml` con el perfil activo, sin entidades y con entidades (principal `insinuada` + una secundaria), y comparar a mano la coherencia de la entidad entre los 5 actos y el respeto del nivel de revelación. Resultado anotado en la spec.

### S6 — Documentación y cierre

- `CLAUDE.md` (tablas, `narrative_context`, journal, wizard), notas en Spec-180/220, Spec-450 → DONE.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Los prompts con 3 entidades no entran en el `num_ctx` de 4096 del Analyst/Journal | Topes de largo por campo + medición en S3 antes de cerrar el slice. |
| El modelo local revela de más aunque el nivel diga «señales» | La Voz recibe solo el bloque graduado (nunca la ficha completa); se evalúa en S5. |
| Cambiar el YAML de beats altera historias sin entidades | Snapshot byte a byte antes y después (S2) + regresión de los 17 prompts con mock (S3). |
| Editar una historia borra el estado del journal de entidades | `entity_journal` cuelga de `story`, no de `entity`; test en S1. |
| El E2E de guardado de Spec-460 recorre el paso 4 | El grupo arranca vacío (sin cards), no agrega obligatorios. |

---

## TASKS

Formato: **Acceptance** / **Verify** / **Files**. Checkpoint por slice: lint + pytest + tsc + Vitest + Playwright en verde → commit (y despliegue donde se indica) con tu OK.

### S0 — Catálogo de naturalezas (backend)

- [ ] **T0.1:** Tablas y seed.
  - Acceptance: `init_db()` crea `entity_nature` y `genre_entity_nature` y siembra las 10 naturalezas y el mapeo del PLAN con upsert (`ON CONFLICT DO UPDATE` de `label`/`order_index` en naturalezas; `INSERT OR IGNORE` en el mapeo). `desconocida` en los 8 géneros. Corre sobre una DB existente sin tocar sus datos.
  - Verify: pytest — 2 corridas = mismas filas; cambiar una etiqueta en el seed y re-correr la actualiza; DB con historias previas conserva sus filas.
  - Files: `src/infrastructure/database/seeds/entity_natures.py` (nuevo), `src/infrastructure/database/connection.py`
- [ ] **T0.2:** Catálogo en la API.
  - Acceptance: `GET /api/v1/catalog/genres` suma `entity_natures: [{id, label}]` por género, ordenadas por `order_index`; `SQLGenreRepository` expone `natures_of(genre_id)` y `nature_allowed(genre_id, nature_id)`.
  - Verify: pytest del repo y del router (forma de la respuesta; `suspenso` → humano, culto, desconocida).
  - Files: `src/domain/models.py` (`EntityNature`, `Genre.entity_natures`), `src/domain/interfaces.py`, `src/infrastructure/database/repositories/genre_repository.py`, `src/presentation/routers/catalog_router.py`
- [ ] **Checkpoint S0:** lint + pytest + Vitest (el `catalog.service` del frontend tolera el campo nuevo) → commit + despliegue (aditivo).

### S1 — Dominio, persistencia, API y YAML

- [ ] **T1.1:** Dominio.
  - Acceptance: `Entity` (name, nature_id, description, manifestations, limits, reveal_level ∈ {nunca, insinuada, progresiva, explicita}, default `insinuada`); `Story.entities: list[Entity]` (máx. 3) y `Story.principal_entity`. Topes: name 60, description 400, manifestations 300, limits 300 → error de validación.
  - Verify: pytest `tests/unit/domain/test_models.py` (4 entidades → error; tope excedido → error; principal = primera; sin entidades → `None`).
  - Files: `src/domain/models.py`
- [ ] **T1.2:** Persistencia.
  - Acceptance: tabla `entity` (esquema §1); `save()` y `update_inputs()` borran y reinsertan con `order_index`; `get_by_id()`/listados cargan `entities` ordenadas. Tabla `entity_journal` creada (se usa en S3).
  - Verify: pytest de integración — round-trip con 0, 1 y 3 entidades; editar una historia no borra filas de `entity_journal`; borrar la historia las borra (cascade).
  - Files: `src/infrastructure/database/connection.py`, `src/infrastructure/database/repositories/story_repository.py`
- [ ] **T1.3:** API.
  - Acceptance: `narrator_config.entities` entra por `POST`/`PATCH /stories` y sale en la respuesta (`storyteller_config.entities`); naturaleza que no corresponde al género → 422 legible (`ensure_valid_entities`, junto a `ensure_valid_genre`); más de 3 o tope excedido → 422.
  - Verify: pytest `tests/unit/presentation/routers/test_story_router.py` (alta, edición, 422 por naturaleza/cantidad/largo).
  - Files: `src/presentation/schemas/request.py`, `src/presentation/schemas/response.py`, `src/presentation/routers/story_router.py`, `src/application/dto/story_dto.py`, `src/application/use_cases/create_story.py`, `src/application/services/narrator_config_sanitizer.py`
- [ ] **T1.4:** YAML.
  - Acceptance: `YamlStoryLoader` lee `storyteller_config.entities`; el exporter las escribe; `export-yaml` → `import-yaml` conserva las entidades; `generate --input` las acepta.
  - Verify: pytest (round-trip YAML con 2 entidades; YAML sin `entities` → historia sin entidades).
  - Files: `src/infrastructure/loaders/yaml_loader.py`, `src/infrastructure/exporters/yaml_exporter.py`, `src/cli/commands.py`
- [ ] **Checkpoint S1:** lint + pytest → commit (sin despliegue: nadie carga entidades todavía).

### S2 — Beats: revelación por nivel

- [ ] **T2.1:** Snapshot de hoy.
  - Acceptance: test que congela, para los 5 beats, la salida de `format_for_beat` (compact y frontier), de `NarrativeContextAssembler.assemble()` con un `MacroBeat` fijo y del `acts_json` del resolver. Se escribe **antes** de tocar el YAML.
  - Verify: pytest en verde contra el código actual.
  - Files: `tests/unit/application/test_beat_reveal_snapshot.py` (nuevo) + fixture de snapshot
- [ ] **T2.2:** `reveal_rules` y `entity_exposure` en el YAML.
  - Acceptance: las 3 reglas de §2 salen de `must`/`must_not` y pasan a `reveal_rules` con `default` + overrides (`explicita` sin los `must_not` de los beats 1 y 2; `nunca` sin el `must` de presencia del beat 3); cada beat suma `entity_exposure` con los 4 niveles (tabla §2; beat 5 de `nunca` = "lo que decida el acto 5"). La regla de origen del beat 3 queda fija.
  - Verify: el snapshot de T2.1 sigue idéntico.
  - Files: `config/llm_beats_definition.yaml`
- [ ] **T2.3:** Resolución por nivel.
  - Acceptance: `BeatSpecRepository.get_by_id(beat_id, reveal_level=None)` y `format_for_beat(..., reveal_level=None)` devuelven el beat resuelto; sin nivel = `default`; `exposure_for(beat_id, reveal_level)` devuelve el texto de exposición.
  - Verify: pytest — sin nivel = snapshot; `explicita` beat 1 sin «confirmar lo paranormal»; `nunca` beat 3 sin «mostrar amenaza o presencia directa»; `insinuada` = default.
  - Files: `src/application/services/beat_spec_repository.py`
- [ ] **Checkpoint S2:** lint + pytest → commit.

### S3 — Pipeline

- [ ] **T3.1:** Regresión cero (antes de tocar prompts).
  - Acceptance: test que corre el pipeline completo con `MockLLMAdapter` sobre una historia sin entidades y congela los 17 prompts (system + user).
  - Verify: pytest en verde contra el código actual y al final del slice.
  - Files: `tests/integration/test_pipeline_prompts_snapshot.py` (nuevo)
- [ ] **T3.2:** Analyst y Mapper.
  - Acceptance: bloque «AMENAZA» con las fichas (principal primero) en `story_analyst_*compact.md` y `synopsis_mapper_*compact.md`, solo si hay entidades; el Mapper suma la exposición del beat por entidad; Resolver y Mapper usan el beat resuelto con el nivel de la principal.
  - Verify: pytest de `PromptBuilder` (con entidades: bloque presente y en orden; sin entidades: T3.1 idéntico).
  - Files: `src/application/services/prompt_builder.py`, `config/prompts_generation/story_analyst_compact.md`, `config/prompts_generation/synopsis_mapper_one_compact.md`
- [ ] **T3.3:** Voz.
  - Acceptance: `NarrativeContextAssembler.assemble()` recibe las entidades y el nivel de la principal: bloque «AMENAZA EN ESTE ACTO» con solo la exposición graduada de cada entidad (nunca la ficha completa); `PROHIBIDO`/`Efecto buscado` salen del beat resuelto; `entity_state` del acto anterior en la memoria.
  - Verify: pytest (con `nunca` en el beat 1 no aparecen nombre ni naturaleza; con `explicita` sí; sin entidades = snapshot).
  - Files: `src/application/services/narrative_context_assembler.py`, `src/application/services/prompt_builder.py`
- [ ] **T3.4:** Journal.
  - Acceptance: `journal.md` pide `entity_state` solo si hay entidades; `NarrativeJournal.entity_state` opcional; `save_journal()` lo guarda en `entity_journal` y `get_journal()` lo devuelve; llega a la Voz del beat siguiente y a la regeneración de un acto (Spec-430).
  - Verify: pytest (parseo con y sin la clave; persistencia; `RegenerateBeatVozUseCase` recibe el estado).
  - Files: `config/prompts_generation/journal.md`, `src/application/services/memory_journalist.py`, `src/domain/models.py`, `src/infrastructure/database/repositories/story_repository.py`
- [ ] **T3.5:** Medición de tokens.
  - Acceptance: script que arma los prompts de los 5 roles con 0, 1 y 3 entidades (campos al tope) y reporta tokens estimados vs `num_ctx` de cada rol del perfil activo; resultado anotado en la spec. Si un rol se pasa, se ajustan topes o se resume la ficha para ese rol antes de cerrar el slice.
  - Verify: salida del script en la spec.
  - Files: `scripts/measure_entity_prompts.py` (nuevo)
- [ ] **Checkpoint S3:** lint + pytest (T3.1 idéntico) → commit (despliegue junto con S4).

### S4 — Wizard «La Amenaza»

- [ ] **T4.1:** Definición y render.
  - Acceptance: grupo `amenaza` en el paso 4 con `wizard_card_list` (máx. 3, **arranca vacío**, card 1 «ENTIDAD 1 — PRINCIPAL»); campos `entity_N_name|nature|description|manifestations|limits|reveal` con `maxlength` según topes; `entity_N_nature` con `source: entity_natures` filtrado en el servidor por el género de la sesión (sin género → deshabilitado con aviso).
  - Verify: Vitest de la vista (filtrado por género; sin género; card list vacía por defecto).
  - Files: `frontend/config/ui_definitions.yaml`, `frontend/src/views/wizard.ejs`, `frontend/src/views/partials/wizard_card_list.ejs`, `frontend/src/controllers/wizard.controller.ts`, `frontend/src/services/catalog.service.ts`, `frontend/public/js/wizard.js`
- [ ] **T4.2:** Validación del paso.
  - Acceptance: `submitStep` descarta una naturaleza que no corresponde al género (como el subgénero en Spec-440); una card con naturaleza vacía se marca con error.
  - Verify: Vitest del controller.
  - Files: `frontend/src/controllers/wizard.controller.ts`
- [ ] **T4.3:** Mapeo ida y vuelta + confirmación.
  - Acceptance: `mapWizardToCore()` → `narrator_config.entities` (solo cards con naturaleza, en orden); `mapStoryToWizard()` rehidrata; la confirmación lista las entidades con su nivel.
  - Verify: Vitest `mapper.service.test.ts` (0, 1 y 3 entidades; round-trip).
  - Files: `frontend/src/services/mapper.service.ts`, `frontend/src/services/wizard.service.ts`, `frontend/src/views/wizard-confirm.ejs`
- [ ] **T4.4:** E2E.
  - Acceptance: agregar 2 entidades → guardar → editar → rehidratadas; cambiar el género a uno donde la naturaleza no corresponde → queda sin naturaleza; el E2E de guardado de Spec-460 sigue en verde sin cambios.
  - Verify: Playwright `tests/e2e/entities.spec.ts` (nuevo) + suite completa.
- [ ] **Checkpoint S4:** lint + pytest + tsc + Vitest + Playwright → commit + **despliegue de S2+S3+S4** (backend y frontend; `init_db()` crea las tablas en prod al arrancar).

### S5 — Evaluación

- [ ] **T5.1:** Generar `el_monte_prohibido.yaml` con el perfil activo, sin entidades y con entidades (principal `insinuada` + una secundaria), y comparar a mano: coherencia de nombre/aspecto/poderes entre actos, respeto del nivel de revelación por beat, uso de los límites. Resultado y ejemplos anotados en la spec.

### S6 — Documentación y cierre

- [ ] **T6.1:** `CLAUDE.md` (tablas nuevas, fórmula del `narrative_context`, journal, wizard, catálogo), notas en Spec-180 y Spec-220, Spec-450 → DONE.


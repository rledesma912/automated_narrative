# SPEC-450: Entidades narrativas (la Amenaza) como parámetro del pipeline

**Fecha:** 2026-09-22
**Tipo:** SDD (Spec-Driven Development)
**Estado:** SPECIFY — preguntas cerradas (2026-09-23); pendiente de OK para pasar a PLAN
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

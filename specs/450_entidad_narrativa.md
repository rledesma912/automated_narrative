# SPEC-450: Entidad narrativa (la Amenaza) como parámetro del pipeline

**Fecha:** 2026-09-22
**Tipo:** SDD (Spec-Driven Development)
**Estado:** SPECIFY — borrador, pendiente de OK
**Depende de:** Spec-440 (catálogo de géneros en DB, wizard compacto)

---

## ASSUMPTIONS

1. La entidad es **opcional**: el terror psicológico, el suspenso o el slasher con asesino humano pueden no tener una entidad sobrenatural, o dejarla ambigua a propósito.
2. **Una entidad por historia** en esta versión (1:0..1 con `story`). Ver Open Questions.
3. Las **naturalezas** de entidad son dominio de datos, igual que los géneros en Spec-440: viven en DB, con seed en `init_db()`.
4. Sin llamadas LLM extra: la entidad entra por **ensamblado determinístico** en prompts existentes (se mantienen 17 llamadas).
5. El wizard sigue en 5 pasos: la entidad se agrega como grupo del paso *El Mundo*.

---

## OBJECTIVE

Hoy el pipeline no tiene concepto de antagonista. La búsqueda de `antagonist|entidad|criatura|amenaza` en `src/` y `config/prompts_generation/` solo encuentra "el espacio como antagonista" (pilar Peripeteia). El demonio, el espíritu o la criatura existen solo si el usuario los describe dentro de los actos o de las reglas, y cada rol LLM los reinterpreta por separado.

**Síntomas esperables:**

- **Deriva entre beats:** la entidad cambia de aspecto, de poder o de nombre de un acto a otro.
- **Revelación sin control:** no hay forma de decidir cuánto se muestra en cada acto, algo central en horror.
- **Reglas sin dueño:** los límites de la entidad ("no puede cruzar la sal") se mezclan con reglas del mundo sin quedar atados a ella.

**Éxito:** la entidad definida en el wizard aparece coherente en los 5 actos, con un nivel de revelación que respeta el elegido, y su estado queda registrado en el Journal para dar continuidad.

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
    story_id       TEXT NOT NULL UNIQUE,          -- 1:0..1
    name           TEXT,                           -- puede no tener nombre
    nature_id      TEXT NOT NULL,
    description    TEXT DEFAULT '',                -- qué es, qué quiere
    manifestations TEXT DEFAULT '',                -- cómo se percibe
    limits         TEXT DEFAULT '',                -- reglas y debilidades
    reveal_level   TEXT NOT NULL DEFAULT 'insinuada',
    FOREIGN KEY (story_id)  REFERENCES story(id) ON DELETE CASCADE,
    FOREIGN KEY (nature_id) REFERENCES entity_nature(id)
);
```

`narrative_journal` suma la columna `entity_state TEXT DEFAULT ''` (qué sabe el narrador de la entidad y qué hizo la entidad hasta este beat).

**Naturalezas (seed, a validar):** `espiritu` Espíritu / aparecido · `demonio` Demonio · `criatura` Criatura / monstruo · `humano` Humano (asesino, acosador) · `culto` Culto / colectivo · `contagio` Contagio / organismo · `lugar` Lugar vivo o maldito · `cosmica` Entidad cósmica · `folklorica` Ser del folklore · `desconocida` Desconocida / ambigua.

Mapeo género → naturalezas en `genre_entity_nature` (ej. `folk_horror` → `folklorica, espiritu, culto, lugar, desconocida`). `desconocida` está habilitada en todos los géneros.

Dominio: entidad `Entity` en `src/domain/models.py`; `Story.entity: Entity | None`. Persistencia en `SQLStoryRepository` (mismo patrón que `scenario`).

---

## 2. NIVEL DE REVELACIÓN

| `reveal_level` | Beat 1 | Beat 2 | Beat 3 (Anagnorisis) | Beat 4 | Beat 5 |
|---|---|---|---|---|---|
| `nunca` | señales | señales | señales intensas, nunca confirmada | señales | ambigüedad residual |
| `insinuada` | señales | manifestación parcial | **revelación** | límites y consecuencias | huella |
| `progresiva` | señales | manifestación parcial | presencia directa | presencia plena | huella |
| `explicita` | presencia | presencia | confrontación | consecuencias | huella |

- **Señales** = solo `manifestations`, sin nombre ni naturaleza.
- **Revelación** = `name` + `nature` + `description`.
- **Límites** = `limits` (se exponen cuando el relato los necesita).

La graduación vive en `config/llm_beats_definition.yaml` (fuente de verdad de beats): cada `macro_beat` suma `entity_exposure: {nunca: ..., insinuada: ..., ...}`.

**Conflicto a resolver:** los beats actuales ya traen una curva de revelación hardcodeada. Por ejemplo, el beat 1 tiene `must_not: "confirmar lo paranormal"` y el beat 2 `must_not: "aceptar lo paranormal como hecho"`. Con `explicita`, esas restricciones contradicen la elección del usuario. Propuesta: los `must_not` relacionados con la revelación pasan a depender de `reveal_level`, y los demás quedan fijos.

---

## 3. INTEGRACIÓN EN EL PIPELINE

| Rol | Qué recibe | Dónde |
|---|---|---|
| Analyst | Ficha completa (para anclar los 5 pilares a la entidad) | template `story_analyst_*compact.md` |
| Mapper | Ficha completa + `entity_exposure` del beat (decide el evento sin revelar de más) | `synopsis_mapper_*compact.md` |
| Voz | **Solo** el bloque graduado del beat N | `narrative_context` vía `NarrativeContextAssembler` |
| Journal | Ficha completa → devuelve `entity_state` | `journal.md` + `MemoryJournalist.extract()` |

- `PromptBuilder.build_narrative_context()` pasa `story.entity` al assembler, que agrega el bloque `entity` según `reveal_level` y el número de beat.
- `narrative_context = beat_spec + resonance + synopsis_event + active_scenario + entity_exposure + memory_snapshot`.
- El `entity_state` del journal del beat N-1 viaja en `memory_snapshot` al beat N (continuidad, Spec-420).
- Regeneración parcial (Spec-430): la Voz regenerada recibe el mismo bloque, sin cambios adicionales.

---

## 4. WIZARD Y ROUND-TRIP

- Grupo **"La Amenaza"** en el paso *El Mundo*, con toggle "Esta historia tiene una entidad" (apagado → no se envía nada).
- Campos: `entity_name`, `entity_nature` (combo filtrado por el género del paso 1, vía `GET /api/v1/catalog/entity-natures?genre=`), `entity_description`, `entity_manifestations`, `entity_limits` y `entity_reveal` (radio con los 4 niveles).
- `mapWizardToCore()` → `narrator_config.entity`. `mapStoryToWizard()` rehidrata.
- YAML (Spec-302/320): `storyteller_config.entity` en `YamlStoryLoader` y en el exporter.
- CLI `generate --input` acepta la entidad desde YAML.

---

## BOUNDARIES

- **Siempre:** entidad opcional; historias sin entidad generan exactamente igual que hoy (regresión cero).
- **Consultar antes:** cambios en los `must`/`must_not` de `llm_beats_definition.yaml` que no sean de revelación.
- **Nunca:** llamadas LLM nuevas; scripts de migración (`init_db()` + recrear `stories.db`).

---

## OPEN QUESTIONS

1. **Cantidad:** ¿una entidad alcanza, o soportamos varias (ej. culto + demonio, con una principal)?
2. **Naturalezas:** ¿la lista del seed te cierra? ¿Filtrarla por género (propuesto) o dejarla libre?
3. **Curva de revelación:** ¿te cierra la tabla §2? En particular, ¿`nunca` debe dejar el final ambiguo siempre?
4. **Conflicto con `must_not`:** ¿OK con que los `must_not` de revelación dependan de `reveal_level`?
5. **Evaluación:** para medir si reduce la deriva, propongo generar `el_monte_prohibido.yaml` con y sin entidad y comparar la coherencia de la entidad entre actos (revisión manual). ¿Suficiente?

# SPEC-038: Arquitectura de Anclajes Narrativos y Construcción Secuencial de Macro-Beats

**Estado:** IMPLEMENTADO — Slices 1–9 completos  
**Fecha:** 2026-04-21  
**Rama destino:** `fix_flow_ollama_local`

## Objetivo

**El VOZ recibe un `narrative_context` completamente pre-construido y su única responsabilidad es generar prosa literaria.**

Todo lo demás — qué ocurre en el acto, qué elementos sensoriales y dramáticos son relevantes, cuál es el estado emocional heredado del acto anterior — llega ya resuelto y estructurado. El VOZ no interpreta la sinopsis, no infiere contexto, no toma decisiones narrativas.

**Motivación:** El flujo actual entrega al VOZ demasiada responsabilidad de interpretación (sinopsis completa o fragmento sin estructura) y construye todos los macro-beats en batch antes de narrar cualquiera. Esto genera que modelos locales aluCinen, pierdan el hilo narrativo entre actos e ignoren restricciones del acto.

---

## Terminología de este spec

| Término | Significado |
|---|---|
| `macro_beat` | Unidad narrativa estructural (acto). Reemplaza el nombre genérico "beat" en toda la arquitectura nueva. |
| `narrative_anchors` | Los 4 elementos concretos extraídos de la sinopsis por el Analista (ver sección 2). |
| `narrative_context` | El contexto pre-construido que recibe el VOZ para un macro-beat: anclajes + extracto de evento + escenario activo + memoria anterior. |
| `memory_snapshot` | Instantánea del estado narrativo extraída por el Journalist después de narrar un macro-beat. |
| `cronologic_scenarios` | Lista ordenada cronológicamente de los escenarios de la historia, definida por el usuario en el input. Reemplaza el campo `scenarios`. Cada ítem es el lugar donde transcurre una parte de la historia, en el orden en que aparece. |

---

## 1. Visión General

El cambio central es pasar de un pipeline **batch-then-narrate** a un pipeline **macro-beat-by-macro-beat secuencial**:

```
ANTES:
  Analista → Mapper (5 macro-beats en batch) → VOZ × 5

DESPUÉS:
  Analista (extrae narrative_anchors globales — 1 llamada LLM)
       ↓
  Para cada macro_beat (1..N):
    Mapper (construye 1 macro-beat: extrae evento de sinopsis + recibe anchors + memoria anterior — 1 llamada LLM)
         ↓
    DirectorUseCase arma narrative_context (determinístico, sin LLM)
         ↓
    VOZ (solo genera prosa sobre narrative_context — 1 llamada LLM)
         ↓
    Journalist (extrae memory_snapshot del macro-beat narrado — 1 llamada LLM)
```

**Total de llamadas LLM:** 1 (analista) + 5×3 (mapper + voz + journalist) = **16 llamadas**.  
El tiempo total aumenta respecto al flujo actual (12 llamadas), pero la coherencia y fidelidad a la sinopsis justifican el costo. Un relato de calidad en 15 minutos supera a uno genérico en 10.

La memoria del macro-beat N-1 entra en la **construcción** del macro-beat N (en el Mapper), no solo en el prompt del VOZ. Cuando el VOZ recibe el `narrative_context`, ya tiene todo lo que necesita para generar prosa sin inferir ni inventar.

---

## 2. Narrative Anchors — Definición y Naturaleza

### Los anchors son estáticos

Los `NarrativeAnchors` se extraen **una sola vez**, de la **sinopsis global**, antes de que comience el loop de macro-beats. No se actualizan, no crecen, no se poda ninguno. Son 4 campos fijos que representan la estructura dramática invariante de la historia: qué ES el horror de esta historia, cómo opera, cuál es el escenario concreto, cuál es el estado inicial del narrador.

Esto es posible porque la sinopsis ya contiene la historia completa. Los anchors no necesitan evolucionar — son los pilares que no cambian mientras la historia se narra.

El Analista usa `cronologic_scenarios` al extraer el `spatial_anchor`: en lugar de inferir el escenario desde la prosa de la sinopsis, tiene disponible la lista cronológica de lugares definida por el usuario. Esto permite que `spatial_anchor` capture los detalles sensoriales del lugar donde ocurre el horror principal con mayor precisión y sin alucinación.

### Dos sistemas de memoria con roles distintos

El sistema tiene dos mecanismos de memoria que no se superponen:

| Sistema | Naturaleza | Origen | Se actualiza | Qué captura |
|---|---|---|---|---|
| `NarrativeAnchors` | **Estático** | Sinopsis global | Nunca (1 extracción) | Estructura dramática: el horror, el escenario, el estado inicial, el pico de terror |
| `memory_snapshot` / `NarrativeJournal` | **Dinámico** | Prosa generada por VOZ | Después de cada macro-beat | Estado narrativo: qué ocurrió, misterios abiertos, estado físico/emocional actual |

`NarrativeAnchors` responde "qué ES esta historia". `memory_snapshot` responde "qué HA PASADO hasta ahora en la historia generada". Ambos se combinan en `narrative_context` para cada macro-beat pero no son intercambiables ni redundantes.

### Jerarquía por beat

La relevancia de cada anchor por acto está codificada en el YAML (`anchor_priorities: principal / contexto`). El anchor `principal` es el dominante del acto; `contexto` es de soporte. Esta jerarquía es configuración fija, no una decisión en runtime.

---

### Los cuatro campos

Cuatro elementos extraídos por el Analista de la sinopsis global. Se extraen **una sola vez** por historia.

| Anclaje | Clave | Qué captura |
|---|---|---|
| Estado Inicial | `initial_state` | Situación emocional y cognitiva del narrador al comenzar. No la situación objetiva del grupo — la experiencia subjetiva del que narra. |
| Naturaleza de la Amenaza | `threat_nature` | Qué es exactamente el horror y cómo opera en esta historia concreta (reglas implícitas, forma de manifestarse). |
| Pico de Terror | `horror_peak` | El evento paranormal o de máximo impacto. El momento que no tiene vuelta atrás. |
| Anclaje Espacial | `spatial_anchor` | Detalles físicos y sensoriales concretos del lugar. No atmósfera general — especificidades (el olor, la textura, la luz, los sonidos del escenario). |

---

## 3. Distribución de Anclajes — Guiada por Configuración (YAML)

**Decisión de diseño:** la asignación de qué `narrative_anchors` corresponden a cada macro-beat es **configuración, no decisión LLM**. El LLM extrae los valores; el YAML determina cuáles se usan en cada acto. Esto elimina variabilidad no deseada y hace el sistema predecible y auditable.

Se agrega el campo `anchor_priorities` a cada macro-beat en `config/llm_beats_definition.yaml`.  
La clave tiene exactamente dos subcampos: `principal` (anclaje dominante del acto) y `contexto` (anclaje de soporte).

```yaml
beats_spec:
  version: "2.0"
  granularity: "5_actos"

  macro_beats:                      # renombrado de "beats" → "macro_beats"

    - id: 1
      name: "exposicion"
      intent: "establecer normalidad y sembrar una fisura"
      anchor_priorities:
        principal: "initial_state"
        contexto: "spatial_anchor"
        # horror_peak ausente — must_not prohíbe confirmar lo paranormal en este acto
      must: [...]
      must_not: [...]
      ...

    - id: 2
      name: "accion_ascendente"
      anchor_priorities:
        principal: "threat_nature"
        contexto: "initial_state"

    - id: 3
      name: "climax"
      anchor_priorities:
        principal: "horror_peak"
        contexto: "threat_nature"

    - id: 4
      name: "accion_descendente"
      anchor_priorities:
        principal: "spatial_anchor"
        contexto: "threat_nature"

    - id: 5
      name: "desenlace"
      anchor_priorities:
        principal: "initial_state"
        contexto: "threat_nature"
```

**Nota:** el YAML también renombra la clave raíz `beats` → `macro_beats`. Requiere actualizar `PromptBuilder._load_beats_definition()` para leer la nueva clave.

---

## 4. Nuevo Modelo de Dominio

### 4.1 Nueva entidad: `NarrativeAnchors`

```python
@dataclass
class NarrativeAnchors:
    story_id: UUID
    initial_state: str     # estado emocional/cognitivo del narrador al inicio
    threat_nature: str     # naturaleza concreta del horror
    horror_peak: str       # el evento paranormal de máximo impacto
    spatial_anchor: str    # detalles físicos/sensoriales del escenario
```

Una por historia. Se persiste en nueva tabla `narrative_anchors`.

### 4.2 Nueva entidad: `Scenario`

Los escenarios cronológicos son una entidad de dominio propia. Reemplazan el campo de texto libre `escenarios` en `Story`.

```python
@dataclass
class Scenario:
    id: UUID
    story_id: UUID
    order_index: int    # posición cronológica (1, 2, 3...)
    name: str           # descripción del lugar tal como la escribe el usuario
```

Una historia tiene N escenarios (uno por ítem en `cronologic_scenarios` del input). El parser de input crea los objetos `Scenario` al leer la lista YAML.

### 4.3 Renombre: `Beat` → `MacroBeat`

La clase de dominio `Beat` pasa a llamarse `MacroBeat` en toda la arquitectura nueva. La tabla en DB se renombra de `beat` → `macro_beat` como parte de la migración.

Campos existentes que se mantienen: `id`, `story_id`, `number`, `summary`, `content`, `status`, `technical_context`.

Campos nuevos:

| Campo | Tipo | Descripción |
|---|---|---|
| `active_scenario_id` | `TEXT NULL (FK)` | FK a `scenario.id`. El escenario activo en este macro-beat, identificado por el Mapper. |
| `narrative_context` | `TEXT NULL` | Contexto pre-construido para el VOZ: anclajes del acto + extracto del evento + escenario activo + memoria anterior. Construido por `DirectorUseCase`, persiste para debugging y re-narración. |
| `memory_snapshot` | `TEXT NULL` | JSON extraído por el Journalist DESPUÉS de narrar este macro-beat. Usado por el Mapper del macro-beat siguiente. Esquema: `{last_events, unresolved_mysteries, physical_emotional_state}`. |

### 4.4 Diagrama ER — nuevo estado completo

```
story (1) ──────────────── narrative_anchors (1)      ← NUEVA TABLA
  │                            story_id (FK)
  │                            initial_state
  │                            threat_nature
  │                            horror_peak
  │                            spatial_anchor
  │
  ├───────────────────────── scenario (N)              ← NUEVA TABLA (ex campo escenarios)
  │                            story_id (FK)
  │                            order_index             ← orden cronológico
  │                            name                    ← descripción del lugar
  │
  └────────────────────────── macro_beat (N)           ← TABLA RENOMBRADA (ex beat)
                                  story_id (FK)
                                  number
                                  summary               ← evento extraído por Mapper
                                  active_scenario_id    ← CAMPO NUEVO: FK → scenario.id
                                  narrative_context     ← CAMPO NUEVO: pre-baked para VOZ
                                  content               ← prosa generada por VOZ
                                  memory_snapshot       ← CAMPO NUEVO: JSON del Journalist
                                  status
                                  technical_context

story                          (campo escenarios eliminado → tabla scenario)

story (1) ──────────────── narrative_journal (1)       ← SIN CAMBIOS (estado vivo)
```

`narrative_journal` se mantiene para representar el estado vivo de la historia. `macro_beat.memory_snapshot` es la instantánea histórica de cada acto, usada en la construcción secuencial.

---

## 5. Responsabilidades del Analista (2 responsabilidades)

El componente `StoryAnalystService` — actualmente `_analyze_story()` dentro de `DirectorUseCase` — se extrae como clase propia y asume dos responsabilidades explícitas.

### Responsabilidad 1: Extracción de narrative_anchors (LLM)

**Input:** sinopsis, protagonistas, escenarios, atmósfera  
**Output:** `NarrativeAnchors` (objeto estructurado, no texto libre)  
**Cómo:** llamada LLM con system prompt + user prompt de extracción. La respuesta es JSON con los 4 campos exactos. Se parsea directamente a `NarrativeAnchors`.

Diferencia con el actual `story_analyst`: la salida deja de ser texto libre de 5 líneas y pasa a ser un objeto estructurado con 4 claves fijas y valores concretos.

### Responsabilidad 2: Resolución de anclajes por macro-beat (determinístico, sin LLM)

**Input:** `NarrativeAnchors` + `macro_beat_id` + `anchor_priorities` del YAML  
**Output:** `dict` con los valores de anclaje para ese macro-beat específico

```python
def resolve_beat_anchors(anchors: NarrativeAnchors, macro_beat_id: int) -> dict:
    spec = macro_beats_spec[macro_beat_id]
    priorities = spec["anchor_priorities"]
    return {
        "principal": getattr(anchors, priorities["principal"]),
        "contexto": getattr(anchors, priorities["contexto"]),
    }
```

Sin LLM. Solo lookup en el objeto `NarrativeAnchors`. El resultado se pasa al Mapper como input.

---

## 6. Fórmula de Composición del `narrative_context`

Este es el principio central del spec. El `narrative_context` que recibe el VOZ para cada macro-beat es la suma de cinco insumos:

```
narrative_context =
    beat_spec              (YAML: intent, must, must_not, arco emocional del acto)
  + narrative_anchors      (los 2 anclajes asignados a este acto por YAML anchor_priorities)
  + synopsis_event         (qué ocurre en este momento, extraído de la sinopsis por el Mapper)
  + active_scenario        (el escenario activo en este beat, identificado por el Mapper desde cronologic_scenarios)
  + memory_snapshot        (estado y últimos eventos del acto anterior, del Journalist)
```

| Insumo | Origen | Quién lo produce |
|---|---|---|
| `beat_spec` | `llm_beats_definition.yaml` | Configuración — sin LLM |
| `narrative_anchors` | Sinopsis global | `StoryAnalystService` (LLM) + resolución por YAML (sin LLM) |
| `synopsis_event` | Sinopsis, fragmento del acto N | `SynopsisBeatMapper.map_one()` (LLM) |
| `active_scenario` | `cronologic_scenarios` del input | `SynopsisBeatMapper.map_one()` identifica cuál aplica al beat N (LLM) |
| `memory_snapshot` | Beat anterior narrado | `MemoryJournalist` (LLM) |

El ensamblado final en el string `narrative_context` lo hace `DirectorUseCase` llamando a `PromptBuilder.build_narrative_context()` — determinístico, sin LLM.

### Separación: qué va en `narrative_context` vs qué va en el system prompt del VOZ

El VOZ tiene dos inputs: el **system prompt** (estable, igual en todos los beats) y el **user prompt** (que contiene `narrative_context`, cambia por beat).

| Input | Contenido | Por qué va ahí |
|---|---|---|
| **System prompt** | `relator`, `atmósfera`, `protagonistas`, `reglas` | Son constantes de la historia. El LLM los carga una vez y los aplica a todos los beats. |
| **`narrative_context`** (user prompt) | `beat_spec` + `narrative_anchors` + `synopsis_event` + `active_scenario` + `memory_snapshot` | Cambia en cada beat. Contiene exactamente lo que el VOZ necesita para ESTE momento. |

Esta separación es deliberada: el system prompt establece el "mundo" de la historia (quién narra, qué atmósfera, quiénes son los personajes, qué reglas rigen). El `narrative_context` establece "qué pasa ahora". El VOZ no necesita inferir nada — solo expandir a prosa.

---

## 7. Flujo Secuencial Completo

```
DirectorUseCase.execute_full(story):

  ── FASE GLOBAL (1 vez) ──────────────────────────────────────────────────────

  [1] analyst = StoryAnalystService(llm, prompt_builder)
      narrative_anchors = await analyst.extract_anchors(story)
      persist(narrative_anchors)                         ← tabla narrative_anchors

  ── LOOP POR MACRO-BEAT (N iteraciones) ──────────────────────────────────────

  [2] para macro_beat_id en 1..N:

      [2a] CONSTRUCCIÓN DEL MACRO-BEAT
           prev_snapshot = macro_beat[id-1].memory_snapshot  (None si id == 1)
           beat_anchors  = analyst.resolve_beat_anchors(narrative_anchors, macro_beat_id)

           macro_beat = await mapper.map_one(
               story,
               macro_beat_id,
               beat_anchors,
               prev_snapshot,               ← memoria del acto anterior
               story.sinopsis,              ← el Mapper extrae el fragmento relevante
               story.cronologic_scenarios,  ← lista ordenada de escenarios; el Mapper identifica el activo
           )
           # → macro_beat.summary + macro_beat.active_scenario listos

           macro_beat.narrative_context = prompt_builder.build_narrative_context(
               macro_beat,
               beat_anchors,
               prev_snapshot,
           )
           persist(macro_beat)                            ← summary + narrative_context

      [2b] NARRACIÓN
           macro_beat = await voz.narrate(macro_beat)    ← solo lee narrative_context
           persist(macro_beat.content)

      [2c] MEMORIA
           memory = await journalist.extract(story, macro_beat)
           macro_beat.memory_snapshot = memory            ← JSON
           narrative_journal.update(memory)
           persist(macro_beat.memory_snapshot, narrative_journal)

      yield (macro_beat, memory)
```

### El Mapper y la sinopsis completa

El Mapper recibe la **sinopsis completa** en cada llamada. Su tarea es identificar qué parte de la sinopsis corresponde al macro-beat N y extraer los eventos concretos de ese momento. El prompt del Mapper incluye: sinopsis completa + ID del acto + nombre del acto + anclajes resueltos para ese acto + memoria anterior. El Mapper no decide distribución — solo extrae el fragmento que le corresponde al acto indicado.

### Lo que recibe el VOZ

**System prompt** (igual en todos los beats):
```
Sos [relator], narrando en primera persona.
Atmósfera: [atmosfera]
Personajes: [protagonistas]
Reglas del relato: [reglas]
```

**User prompt** — `macro_beat.narrative_context`:
```
ACTO: [nombre] — [intent]
ARCO EMOCIONAL: [from] → [to]

ESCENARIO ACTIVO:
[active_scenario — el lugar cronológico donde ocurre este acto]

EVENTO DE ESTE MOMENTO:
[summary extraído por el Mapper]

ANCLAJE PRINCIPAL:
[valor del anchor principal — hecho concreto]

ANCLAJE DE CONTEXTO:
[valor del anchor de soporte — hecho concreto]

MEMORIA DEL ACTO ANTERIOR:
[last_events | physical_emotional_state del memory_snapshot anterior]

RESTRICCIONES:
Debe incluir: [must]
PROHIBIDO: [must_not]
Objetivo: [success_signal]
```

El VOZ **no recibe la sinopsis completa ni la lista de cronologic_scenarios**. Recibe el escenario activo ya identificado. `context_strategy` queda obsoleto y se elimina. El VOZ tiene un solo objetivo: expandir `narrative_context` en prosa literaria en primera persona.

---

## 8. Cambios por Componente

### `StoryAnalystService` — clase nueva

Extrae de `DirectorUseCase._analyze_story()`. Archivo: `src/application/services/story_analyst_service.py`.

- `extract_anchors(story) → NarrativeAnchors` — LLM, parsea JSON a dominio
- `resolve_beat_anchors(anchors, macro_beat_id) → dict` — determinístico, usa YAML

Prompts: `story_analyst_compact.md` (reescribir para pedir JSON con 4 claves) + `story_analyst_system_compact.md`.

### `SynopsisBeatMapper`

- `map()` (batch) → deprecado internamente
- Nuevo: `map_one(story, macro_beat_id, beat_anchors, prev_snapshot) → MacroBeat`
- Recibe sinopsis completa + `cronologic_scenarios` completa + beat_anchors + prev_snapshot
- Identifica el `active_scenario` de la lista para el beat N y lo incluye en su output
- Produce `MacroBeat` con `summary` (evento) y `active_scenario` (lugar) poblados
- No construye `narrative_context` — eso es responsabilidad de `DirectorUseCase`

Prompt: `synopsis_mapper_compact.md` reescrito para operar sobre un macro-beat específico, recibiendo `cronologic_scenarios` como lista de referencia.

### `DirectorUseCase`

- `execute_full()` reimplementado con loop secuencial (ver sección 7)
- Instancia `StoryAnalystService` en lugar de llamar `_analyze_story()`
- Llama `prompt_builder.build_narrative_context()` después de cada `map_one()`
- `execute()` (plan-only): también secuencial, genera macro-beats uno a uno sin narrar

### `VozUseCase`

- `narrate(macro_beat) → MacroBeat` simplificado: lee `macro_beat.narrative_context`
- Eliminar: lógica de `context_strategy`, `_resolve_sinopsis()`, `_get_beat_sinopsis_hint()`
- `voice_system_compact.md` reescrito: contiene `{relator}`, `{atmosfera}`, `{protagonistas}`, `{reglas}` — estables por historia
- `voice_compact.md` reescrito: contiene solo `{narrative_context}` como variable de contexto narrativo por beat

### `MemoryJournalist`

- `extract(story, macro_beat) → str` (JSON): igual al actual `update_journal()` pero el caller persiste en `macro_beat.memory_snapshot` y en `narrative_journal`
- Sin cambio de esquema JSON (`last_events`, `unresolved_mysteries`, `physical_emotional_state`)

### `DebugCollector` y `DebugMarkdownRenderer`

El debug `.md` es la herramienta principal de diagnóstico del pipeline. Con la nueva arquitectura, la secuencia de llamadas cambia y aparece un nuevo tipo de evento: el ensamblado determinístico del `narrative_context` (no es una llamada LLM, pero es el dato más importante para auditar qué recibió el VOZ).

**`LLMCallRecord` — cambios:**

| Campo | Cambio |
|---|---|
| `context_strategy` | **Eliminar** — queda obsoleto |
| `narrative_context` | **Agregar** (`str \| None`) — para registrar el contexto ensamblado |
| `active_scenario` | **Agregar** (`str \| None`) — nombre del escenario activo (en registros del Mapper) |
| `is_llm_call` | **Agregar** (`bool = True`) — `False` para registros de ensamblado determinístico |

**Nuevo método `DebugCollector.record_assembled()`:**
Registra el `narrative_context` ensamblado por `DirectorUseCase` (sin LLM). Crea un `LLMCallRecord` con `is_llm_call=False`, `elapsed_s=0.0`, y `narrative_context` populado.

**Secuencia de registros en el nuevo debug `.md`:**

```
Llamada 1  — ANALYST           → extracción de NarrativeAnchors (JSON)
Llamada 2  — MAPPER  Beat #1   → synopsis_event + active_scenario del beat 1
Llamada 3  — [ASSEMBLED] #1    → narrative_context armado para beat 1 (sin LLM)
Llamada 4  — VOZ     Beat #1   → prosa del beat 1
Llamada 5  — JOURNAL Beat #1   → memory_snapshot del beat 1
Llamada 6  — MAPPER  Beat #2   → synopsis_event + active_scenario del beat 2
Llamada 7  — [ASSEMBLED] #2    → narrative_context armado para beat 2
...
```

**`DebugMarkdownRenderer` — cambios:**

- `_story_params()`: agregar `cronologic_scenarios` como lista numerada (no texto plano)
- `_call_section()`: para registros `is_llm_call=False`, renderizar como sección **"Contexto Ensamblado"** con el `narrative_context` en bloque de código (sin tabla de inferencia ni timing)
- `_call_section()`: para registros del Mapper, agregar subsección **"Escenario Activo"** mostrando `active_scenario`
- `_call_section()`: eliminar sección "Context Strategy aplicada" (campo eliminado)
- `_summary_table()`: agregar columna `Escenario` (para filas del Mapper)

**Ejemplo de sección ensamblada en el debug:**

```markdown
## [ASSEMBLED] — Contexto Ensamblado Beat #1

**Tipo:** Determinístico (sin llamada LLM)
**Componente:** DirectorUseCase (director_use_case.py)

### Narrative Context

​```
ACTO: exposicion — establecer normalidad y sembrar una fisura
ARCO EMOCIONAL: estabilidad → incomodidad leve
ESCENARIO ACTIVO: La casa de campo de la abuela María
EVENTO DE ESTE MOMENTO:
- La familia llega temprano a la casa de María en zona rural apartada.
- La abuela advierte casi al pasar sobre el Monte de los Espinillos; su tono basta.
...
​```
```

### `PromptBuilder`

- Nuevo: `build_narrative_context(macro_beat, beat_anchors, prev_snapshot) → str`
- Reescribir: `build_story_analyst_extraction_prompt()` — pide JSON con 4 claves
- Reescribir: `build_synopsis_mapper_one_prompt()` — para un solo macro-beat
- Simplificar: `build_beat_prompt()` → solo toma `macro_beat.narrative_context`
- Eliminar: `_resolve_sinopsis()`, `_get_beat_sinopsis_hint()`, `context_strategy` logic
- Actualizar: `_load_beats_definition()` para leer clave `macro_beats` del YAML

### `config/llm_beats_definition.yaml`

- Renombrar clave raíz `beats` → `macro_beats`
- Agregar `anchor_priorities` a cada uno de los 5 macro-beats
- Incrementar version: `"1.0"` → `"2.0"`

### `config/llm_core_definitions.yaml`

- Eliminar `context_strategy` de todos los perfiles (`beat_slice`, `full`, `none` quedan obsoletos)

### Modelos de dominio (`src/domain/models.py`)

- Nueva clase: `NarrativeAnchors`
- Nueva clase: `Scenario` (`id`, `story_id`, `order_index`, `name`)
- Renombre: `Beat` → `MacroBeat` (con alias `Beat = MacroBeat` para backwards compat en tests)
- Nuevos campos en `MacroBeat`: `active_scenario_id: str | None`, `narrative_context: str | None`, `memory_snapshot: str | None`
- `Story`: eliminar campo `escenarios: str`; agregar `scenarios: list[Scenario]` (cargado desde tabla `scenario`)
- Parser de input (`_sanitize_frontmatter`): leer `cronologic_scenarios` del YAML, crear objetos `Scenario` ordenados

### DB / Migrations (`scripts/bash/migrate_038.sh`)

```sql
-- 1. Renombrar tabla beat → macro_beat
ALTER TABLE beat RENAME TO macro_beat;

-- 2. Campos nuevos en macro_beat
ALTER TABLE macro_beat ADD COLUMN active_scenario_id TEXT REFERENCES scenario(id);
ALTER TABLE macro_beat ADD COLUMN narrative_context TEXT;
ALTER TABLE macro_beat ADD COLUMN memory_snapshot TEXT;

-- 3. Eliminar columna escenarios de story (requiere recrear la tabla en SQLite)
--    Ver script completo en scripts/bash/migrate_038.sh

-- 4. Nueva tabla: scenario
CREATE TABLE IF NOT EXISTS scenario (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL REFERENCES story(id),
    order_index INTEGER NOT NULL,
    name TEXT NOT NULL
);

-- 5. Nueva tabla: narrative_anchors
CREATE TABLE IF NOT EXISTS narrative_anchors (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL REFERENCES story(id),
    initial_state TEXT NOT NULL,
    threat_nature TEXT NOT NULL,
    horror_peak TEXT NOT NULL,
    spatial_anchor TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 9. Lo que NO cambia

- `ResponseNormalizer` — sin cambios
- `LLMProvider` y adapters (Ollama, Anthropic, Gemini, Mock)
- `CreateStoryUseCase`, `ExportStoryUseCase`
- CLI y FastAPI routers (ajustes mínimos de nombre, no de lógica)
- `NarrativeJournal` (modelo, tabla y esquema JSON se mantienen)
- `beat_parser.py` — sin cambios (sigue parseando el output del Mapper)
- Tests de infrastructure — sin cambios

---

## 10. Tradeoffs documentados

| Tradeoff | Decisión |
|---|---|
| Mapper ahora hace N llamadas LLM en lugar de 1 | Aceptado. Un relato coherente en 15 min supera a uno genérico en 10. |
| VOZ sin sinopsis | Intencional. El VOZ solo expande `narrative_context`. Elimina hallucination por contexto excesivo. |
| `context_strategy` queda obsoleto | Se elimina en todos los perfiles. Con `narrative_context` pre-baked no tiene sentido. |
| Analista con 2 responsabilidades | Aceptado. Extracción + resolución de anclajes son semánticamente parte del mismo rol analítico. |
| `narrative_context` persiste en DB | Intencional. Permite debugging preciso y re-narrar un macro-beat sin reejecutar el Mapper. |
| Renombre Beat → MacroBeat + tabla | Aceptado como parte del refactor. Se agrega alias para compatibilidad con tests existentes durante la transición. |
| Mapper recibe sinopsis completa | Intencional. El Mapper decide qué fragmento corresponde al acto N. Simplifica el caller. |

---

## 11. Criterios de Aceptación

Organizados por capa. Cada criterio tiene un test nombrado que lo verifica.

### Dominio y configuración

| # | Criterio | Test |
|---|---|---|
| A1 | `resolve_beat_anchors(anchors, beat_id=1)` retorna `initial_state` como `principal` y `spatial_anchor` como `contexto` | `test_resolve_beat_anchors_exposicion_uses_yaml_priorities` |
| A2 | `resolve_beat_anchors(anchors, beat_id=3)` retorna `horror_peak` como `principal` | `test_resolve_beat_anchors_climax_uses_horror_peak` |
| A3 | `NarrativeAnchors` tiene los 4 campos no vacíos tras parsear una respuesta JSON válida | `test_narrative_anchors_parsed_from_json` |
| A4 | `MacroBeat` acepta `narrative_context` y `memory_snapshot` como campos opcionales | `test_macro_beat_new_fields` |

### Servicios y prompts

| # | Criterio | Test |
|---|---|---|
| B1 | El prompt enviado al Mapper incluye: ID del acto, anclaje principal, anclaje de contexto, y `memory_snapshot` del acto anterior | `test_mapper_prompt_contains_anchors_and_prev_memory` |
| B2 | El prompt enviado al Mapper para el acto 1 **no** incluye sección de memoria anterior | `test_mapper_prompt_beat1_has_no_prev_memory` |
| B3 | `build_narrative_context()` produce un string que contiene: el `summary` del macro-beat, los valores de los dos anclajes, y el `last_events` del snapshot anterior | `test_build_narrative_context_contains_all_insumos` |
| B4 | El prompt enviado al VOZ contiene `narrative_context` y **no** contiene la sinopsis completa | `test_voz_prompt_has_narrative_context_not_sinopsis` |
| B5 | `StoryAnalystService.extract_anchors()` llama al LLM y retorna `NarrativeAnchors` (no texto libre) | `test_story_analyst_returns_narrative_anchors_object` |

### System prompt del VOZ y datos de historia

| # | Criterio | Test |
|---|---|---|
| B6 | El system prompt del VOZ contiene `protagonistas` y `reglas` | `test_voz_system_prompt_contains_protagonistas_and_reglas` |
| B7 | El user prompt del VOZ (narrative_context) **no** contiene `protagonistas` ni `reglas` | `test_voz_narrative_context_has_no_protagonistas` |
| B8 | El prompt del Mapper para beat N incluye `cronologic_scenarios` como lista | `test_mapper_prompt_contains_cronologic_scenarios` |
| B9 | `macro_beat.active_scenario` queda populado tras `map_one()` con un valor de `cronologic_scenarios` | `test_map_one_populates_active_scenario` |
| B10 | `narrative_context` incluye el `active_scenario` del macro-beat | `test_build_narrative_context_includes_active_scenario` |

### Pipeline end-to-end

| # | Criterio | Verificación |
|---|---|---|
| C1 | Tras ejecutar `generate` con `el_monte_prohibido.md`, la DB tiene 1 fila en `narrative_anchors` con los 4 campos populados | Query: `SELECT * FROM narrative_anchors WHERE story_id = ?` |
| C2 | Cada `macro_beat` tiene `narrative_context` y `memory_snapshot` populados después de la generación | Query: `SELECT narrative_context, memory_snapshot FROM macro_beat WHERE story_id = ?` |
| C3 | El relato generado contiene "caballo" y "Monte de los Espinillos" y **no** contiene "auto" ni "celular" | `grep` sobre el archivo `.md` de salida |
| C4 | El relato generado tiene exactamente 5 macro-beats con `status = completed` | Query: `SELECT count(*) FROM macro_beat WHERE story_id = ? AND status = 'completed'` |

---

## 12. Decisiones cerradas

Todas las preguntas abiertas de la versión anterior quedan resueltas:

| Pregunta | Decisión |
|---|---|
| ¿Quién construye `narrative_context`? | `DirectorUseCase`, después de `map_one()`, usando `PromptBuilder.build_narrative_context()`. El Mapper solo produce `summary`. |
| Formato de `memory_snapshot` | Mismo esquema JSON actual del Journalist: `{last_events, unresolved_mysteries, physical_emotional_state}`. Sin cambio de contrato. |
| ¿`execute()` (plan-only) se mantiene o depreca? | Se mantiene, implementado como loop secuencial que genera macro-beats uno a uno sin llamar al VOZ. |
| ¿El Mapper recibe sinopsis completa o fragmento? | Sinopsis completa. El Mapper extrae el fragmento correspondiente al macro-beat N según su posición en el arco. |

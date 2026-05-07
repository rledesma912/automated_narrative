# Proceso de Generación — `generate`

Flujo completo que se ejecuta cuando el usuario corre:

```bash
python -m src generate --input input_stories/historia.md
```

El pipeline produce **17 llamadas LLM** por historia: 1 Analyst + 1 Resolver + 5 × (Mapper + Voz + Journal).

---

## Paso 0 — Ingesta del input

**Componente:** `MarkdownStoryParser` (`src/infrastructure/parsers/markdown_parser.py`) via `CLIContainer.markdown_parser`
**LLM:** ninguno
**Qué hace:** Lee el archivo `.md` o `.yaml` del usuario y extrae todos los campos del frontmatter YAML.

**Datos que extrae:**

| Campo YAML | Destino en `MarkdownStoryData` |
|---|---|
| `title` | `title` |
| `narrator` | `relator` |
| `protagonists[].name/role` | `protagonista` (primer nombre) + `personajes_full` (lista completa) |
| `sinopsis` (bloque) | `sinopsis` |
| `atmosphere.tone` | `atmosfera` |
| `scenarios[].name` | `cronologic_scenarios` (lista ordenada) |
| `rules[]` / `typed_rules[]` | `reglas` / `typed_rules` |
| `storyteller` | `storyteller_config` |

**SQLite:** ninguna escritura todavía.

---

## Paso 1 — Creación de la historia en DB

**Componente:** `CreateStoryUseCase` (`src/application/use_cases/create_story.py`)
**LLM:** ninguno
**Qué hace:** Construye el objeto `Story` con toda la data del parser y lo persiste.

**Datos de entrada:** `StoryCreateDTO` (todos los campos del parser)

**SQLite — escrituras:**

| Tabla | Columnas escritas | Valores |
|---|---|---|
| `story` | `id, title, protagonista, relator, sinopsis, atmosfera, storyteller_config, personajes, status, created_at` | Data del parser; `status = "pending"` |
| `rule` | `id, story_id, content, type, intensity` | Una fila por cada regla/typed_rule del input |
| `scenario` | `id, story_id, order_index, name` | Una fila por cada escenario del input, en orden cronológico |

---

## Paso 2 — Preparación global (Spec-500 S-B)

**Componente:** `DirectorUseCase.prepare_story()` (`src/application/use_cases/director_use_case.py`)
**LLM:** 2 llamadas — `story_analyst` + `director` (resolver)
**Qué hace:** Extrae anclajes narrativos y distribuye reglas/escenarios. Disponible como método público independiente para `only-plan` o para `RegenerateBeatUseCase`.

**Datos que alimentan el prompt:**

| Dato | Fuente |
|---|---|
| `PROTAGONISTAS` | `story.protagonista` |
| `ESCENARIOS` | `story.scenarios` (lista de nombres) |
| `ATMÓSFERA` | `story.atmosfera` |
| `SINOPSIS` (completa) | `story.sinopsis` |

**Resultado en memoria:** `(narrative_anchors, rule_distribution, num_beats)`

**Datos que alimentan el prompt:**

| Dato | Fuente |
|---|---|
| `PROTAGONISTAS` | `story.protagonista` |
| `ESCENARIOS` | `story.scenarios` (lista de nombres) |
| `ATMÓSFERA` | `story.atmosfera` |
| `SINOPSIS` (completa) | `story.sinopsis` |

**Prompts usados:**

El system prompt se selecciona según `effective_prompting_strategy` (Spec-170):

| Estrategia | System prompt | Comportamiento |
|------------|---------------|----------------|
| `assertive` | `story_analyst_system_assertive.md` | Términos técnicos puros — activa esquemas preentrenados del LLM |
| `auto` (default) | `story_analyst_system_assertive.md` → fallback a compact | Intenta assertive; reintenta con descriptive si el auditor falla |
| `descriptive` | `story_analyst_system_compact.md` | Prompt con definiciones completas. Comportamiento legacy. |

User prompt: `story_analyst_compact.md` (igual en todos los modos)

**NarrativeAuditor (Spec-170):** En modos `assertive` y `auto`, `NarrativeAuditor` evalúa la respuesta antes de aceptarla con tres heurísticas: boilerplate (explica en vez de aplicar), sensoriality (densidad de imágenes concretas) y entropy (calco literal de la sinopsis). Si falla en modo `assertive` → `NarrativeLiteracyError`. Si falla en modo `auto` → reintento con prompt descriptivo.

**Respuesta del LLM:** Markdown con 5 secciones `## resonance_*`

**Resultado en memoria:** `NarrativeAnchors` con 5 pilares aristotélicos:
- `resonance_hamartia` (Exposición) — La vulnerabilidad psicológica: la grieta del narrador
- `resonance_hybris` (Acción Ascendente) — La Transgresión: la lógica que permite cruzar la frontera
- `resonance_anagnorisis` (Clímax) — La Violación de lo Sagrado: el detalle sensorial insoportable
- `resonance_peripeteia` (Acción Descendente) — La Trampa Espacial: el entorno como cómplice
- `resonance_residual` (Desenlace) — La Mancha Residual: el daño observable que permanece

La definición de cada pilar (concepto, guía de extracción, label_voz) vive en `config/llm_narrative_definition.yaml`.

**SQLite — escrituras:**

| Tabla | Columnas escritas |
|---|---|
| `narrative_anchors` | `story_id, resonance_hamartia, resonance_hybris, resonance_anagnorisis, resonance_peripeteia, resonance_residual` |

---

## Paso 3 — RESOLVER: distribución de reglas y escenarios

**Componente:** `RuleScenarioResolverService.resolve_distribution()` (`src/application/services/rule_scenario_resolver_service.py`)
**LLM:** 1 llamada — modelo `director` del perfil activo
**Qué hace:** Asigna a cada beat qué reglas activas tiene y cuál escenario le corresponde.

**Datos que alimentan el prompt:**

| Dato | Fuente |
|---|---|
| Anclajes (JSON parcial) | `NarrativeAnchors` del paso 2 |
| Definición de los 5 actos | `config/llm_beats_definition.yaml` (via `PromptBuilder`) |
| Reglas tipadas | `story.typed_rules` (del input) |
| Escenarios ordenados | `story.scenarios` |

**Prompts usados:**
- System: `rule_resolver_system_compact.md`
- User: `rule_resolver_compact.md`

**Respuesta del LLM:** JSON `{"1": {"rules": [...], "scenario_id": "S1"}, ...}` — una entrada por beat

**Resultado en memoria:** `rule_distribution: dict` — diccionario que el Director consulta en cada iteración del loop.

**SQLite:** ninguna escritura directa en este paso.

---

## Loop por beat (repite 5 veces, beats 1→5)

Los pasos 4 a 7 se ejecutan en secuencia para cada beat. La salida del Journal de un beat alimenta el Mapper del siguiente.

---

### Paso 4 — Resolución de resonancia por beat (sin LLM)

**Componente:** `StoryAnalystService.resolve_beat_anchors()` — método de servicio puro
**LLM:** ninguno
**Qué hace:** Mapeo 1:1 — Beat N recibe exactamente el Pilar N definido en `config/llm_narrative_definition.yaml`. No hay cross-lookup ni prioridades (Spec-081).

**Datos de entrada:**

| Dato | Fuente |
|---|---|
| `NarrativeAnchors` (los 5 pilares) | Memoria — resultado del paso 2 |
| Pilares ordenados por `beat` | `config/llm_narrative_definition.yaml` |

**Resultado en memoria:** `beat_anchors: dict` con claves `resonance` (valor del pilar) y `label_voz` (etiqueta semántica del pilar para el VOZ).

**SQLite:** ninguna escritura.

---

### Paso 5 — MAPPER: extracción del evento del beat

**Componente:** `SynopsisBeatMapper.map_one()` (`src/application/use_cases/synopsis_beat_mapper.py`)
**LLM:** 1 llamada — modelo `director` del perfil activo
**Qué hace:** Dado el fragmento de sinopsis correspondiente a este beat, extrae los eventos concretos que ocurren y el escenario activo.

**Datos que alimentan el prompt:**

| Dato | Fuente |
|---|---|
| Tipo/intención/intensidad del acto | `config/llm_beats_definition.yaml` (via `PromptBuilder`) |
| `ESCENARIO DESIGNADO` | `rule_distribution[beat_id].scenario_id` → `story.scenarios[idx].name` |
| `FRAGMENTO DE SINOPSIS` | `SynopsisSliceResolver.get_beat_sinopsis_slice(story.sinopsis, beat_id, num_beats)` — corta la sinopsis en N partes |
| `REGLAS ACTIVAS` | `rule_distribution[beat_id].rules` |
| `RESONANCIA DEL ACTO` | `beat_anchors["resonance"]` del paso 4 |
| `MEMORIA DEL ACTO ANTERIOR` | `prev_snapshot` (JSON del Journal del beat anterior; `None` en el beat 1) |

**Prompts usados:**
- System: `synopsis_mapper_system_compact.md`
- User: `synopsis_mapper_one_compact.md`

**Respuesta del LLM:** Bloque de texto con `ESCENARIO:` y `EVENTOS:` (lista de bullets)

**Resultado en memoria:** `MacroBeat` con:
- `summary` — bullets de eventos extraídos
- `active_scenario_id` — nombre del escenario activo
- `active_scenario_description` — nombre del escenario (del input)
- `active_rules` — lista de reglas activas para este beat
- `beat_type` — tipo del acto (del YAML)

**SQLite:** ninguna escritura en este sub-paso (el beat se persiste completo al final del loop).

---

### Paso 6 — Ensamblado del narrative_context (sin LLM)

**Componente:** `NarrativeContextAssembler.assemble()` (`src/application/services/narrative_context_assembler.py`) vía `PromptBuilder.build_narrative_context()`
**LLM:** ninguno
**Qué hace:** Combina todos los datos del beat en un bloque de texto estructurado que recibe el VOZ. Completamente determinístico.

**Datos que ensambla (en este orden en el prompt resultante):**

| Bloque | Fuente |
|---|---|
| `EVENTO DE ESTE MOMENTO` | `macro_beat.summary` (del Mapper) |
| `PERSONAJES EN ESCENA` | `story.personajes_full` (del input, via parser) |
| `ESCENARIO` | `macro_beat.active_scenario_id` |
| `ACTO / INTENSIDAD / ARCO EMOCIONAL` | `config/llm_beats_definition.yaml` |
| `GUÍA DE VOZ (RESONANCIA)` | `beat_anchors["resonance"]` (del paso 4) |
| `REGLAS ESPECÍFICAS` | `macro_beat.active_rules` (del Resolver) |
| `MEMORIA DEL ACTO ANTERIOR` | `prev_snapshot` (JSON del Journal del beat anterior) |
| `FIDELIDAD / PROHIBIDO` | `must_not` y `success_signal` del YAML para el beat |

**Resultado en memoria:** `macro_beat.narrative_context` (string pre-baked).

**SQLite:** ninguna escritura todavía.

---

### Paso 7 — VOZ: generación de prosa

**Componente:** `VozUseCase.narrate()` (`src/application/use_cases/voz_use_case.py`)
**LLM:** 1 llamada — modelo `voz` del perfil activo
**Qué hace:** Transforma el `narrative_context` pre-ensamblado en prosa literaria en primera persona.

**Datos que alimentan el prompt:**

| Componente | Dato | Fuente |
|---|---|---|
| **System prompt** | Relator, atmósfera, elenco completo con roles, reglas del relato, límite de palabras, config del storyteller | `story` completo (via `build_voice_system_compact()`) |
| **User prompt** | `narrative_context` + "Escribí el fragmento del relato para este acto." | `macro_beat.narrative_context` (del paso 6) |

**Prompts usados:**
- System: `voice_system_compact.md` (con `{relator}`, `{atmosfera}`, `{protagonistas}`, `{reglas}`, `{word_limit}`, `{storyteller_config_block}`)
- User: `narrative_context` inline (construido en paso 6) + cierre

**Respuesta del LLM:** prosa en primera persona, normalizada por `ResponseNormalizer` (elimina `<think>`, strips de encabezados, etc.)

**Resultado en memoria:** `macro_beat.content` + `macro_beat.status = "completed"`

**SQLite:** ninguna escritura directa aquí — el beat se persiste al volver al orquestador (paso 9).

---

### Paso 8 — JOURNAL: extracción de memoria narrativa

**Componente:** `MemoryJournalist.extract()` → `update_journal()` (`src/application/services/memory_journalist.py`)
**LLM:** 1 llamada — modelo `journal` del perfil activo
**Qué hace:** Lee la prosa generada y extrae el estado narrativo actual para pasarlo al próximo beat.

**Datos que alimentan el prompt:**

| Dato | Fuente |
|---|---|
| Título de la historia | `story.title` |
| Elenco | `story.personajes_full` (via `_format_cast()`) |
| Atmósfera | `story.atmosfera` |
| Estado del journal anterior | `previous_journal` (del beat N-1; `None` en beat 1) |
| Número y summary del beat actual | `macro_beat.number`, `macro_beat.summary` |
| Prosa generada | `macro_beat.content` (del paso 7) |

**Prompts usados:**
- System: hardcoded (`"Eres un asistente que genera resúmenes narrativos en JSON..."`)
- User: `journal.md` (con `{title}`, `{protagonistas}`, `{atmosfera}`, `{beat_number}`, `{beat_summary}`, `{beat_content}`, `{previous_state_section}`, `{consistency_rules}`)

**Respuesta del LLM:** JSON con 3 campos:
```json
{
  "last_events": "...",
  "unresolved_mysteries": "...",
  "physical_emotional_state": "..."
}
```

**Resultado en memoria:**
- `NarrativeJournal` actualizado → se pasa como `previous_journal` al Mapper/Assembler del beat siguiente
- **Spec-222:** Se persiste en la tabla `narrative_journal` con `story_id` y `beat_number`.

---

### Paso 9 — Persistencia del beat completo

**Componente:** `StoryRunner` (`src/core/orchestrator.py`) → `SQLBeatRepository.save()`
**LLM:** ninguno
**Qué hace:** Persiste el beat con toda la información acumulada en los pasos 5-8.

**SQLite — escrituras:**

| Tabla | Columnas escritas | Cuándo se rellena |
|---|---|---|
| `macro_beat` | `story_id, number` | Siempre |
| | `summary` | Paso 5 (Mapper) |
| | `active_scenario_id, active_scenario_description` | Paso 5 (Mapper) |
| | `narrative_context` | Paso 6 (Assembler) |
| | `content` | Paso 7 (VOZ) |
| | `status` | Paso 7 (`"completed"`) |
| | `type` | Paso 5 (YAML via Director) |
| `macro_beat_rule` | `macro_beat_id, rule_id` | Reglas activas del Resolver |

**SQLite — escritura adicional por beat:**

| Tabla | Qué se escribe | Cuándo |
|---|---|---|
| `narrative_journal` | `story_id, beat_number, last_events, unresolved_mysteries, physical_emotional_state` | Después de guardar el beat, via `story_repo.save_journal()` |

---

## Paso 10 — Exportación a Markdown

**Componente:** `MarkdownRenderer` → `_write_markdown()` (`src/cli/commands.py`)
**LLM:** ninguno
**Qué hace:** Lee el objeto `Story` con todos los beats en memoria y genera el archivo `.md` de salida.

**SQLite:** ninguna lectura ni escritura adicional (trabaja con el objeto ya en memoria).

**Salida:** `output_stories/<titulo>_<timestamp>.md`

**Opcional (`--debug`):** `DebugMarkdownRenderer` genera además `output_stories/debug_prompts_responses_<timestamp>.md` con todos los prompts y respuestas de cada llamada LLM.

---

## Resumen de escrituras SQLite por tabla

| Tabla | Quién escribe | Momento |
|---|---|---|
| `story` | `CreateStoryUseCase` | Paso 1 — una sola vez al inicio |
| `rule` | `CreateStoryUseCase` | Paso 1 — una fila por regla del input |
| `scenario` | `CreateStoryUseCase` | Paso 1 — una fila por escenario del input |
| `narrative_anchors` | `DirectorUseCase.prepare_story()` (via `story_repo`) | Paso 2 — una sola vez, después del Analyst |
| `macro_beat` | `SQLBeatRepository.save()` | Paso 9 — una vez por beat (INSERT OR REPLACE) |
| `macro_beat_rule` | `SQLBeatRepository.save()` | Paso 9 — N filas por beat según reglas activas |
| `narrative_journal` | `StoryRunner._narrate_beats()` (via `story_repo.save_journal()`) | Paso 9 — una vez por beat |

---

## Resumen de llamadas LLM

| # | Rol | Componente | Modelo (perfil activo) | Prompts | Nro de llamadas |
|---|---|---|---|---|---|
| 1 | `story_analyst` | `StoryAnalystService` | `roles.story_analyst.model` | `story_analyst_system_assertive.md` o `_compact.md` (según `prompting_strategy`) + `story_analyst_compact.md` | 1–2 (global; 2 solo en modo `auto` si auditor falla) |
| 2 | `director` | `RuleScenarioResolverService` | `roles.director.model` | `rule_resolver_system_compact.md` + `rule_resolver_compact.md` | 1 (global) |
| 3–7 | `director` | `SynopsisBeatMapper` | `roles.director.model` | `synopsis_mapper_system_compact.md` + `synopsis_mapper_one_compact.md` | 5 (1 por beat) |
| 8–12 | `voz` | `VozUseCase` | `roles.voz.model` | `voice_system_compact.md` + `narrative_context` inline | 5 (1 por beat) |
| 13–17 | `journal` | `MemoryJournalist` | `roles.journal.model` | system hardcoded + `journal.md` | 5 (1 por beat) |

**Total: 17 llamadas LLM por historia completa.**

---

## Flujo de datos entre beats (cadena de memoria)

```
Beat 1                Beat 2                Beat 3  ...
  │                     │
  │ Journal.extract()   │
  ├─ prev_snapshot ────>│ Mapper prompt
  │                     │   (MEMORIA DEL ACTO ANTERIOR)
  │                     │
  │                     │ build_narrative_context()
  ├─ prev_snapshot ────>│   (MEMORIA DEL ACTO ANTERIOR en narrative_context)
  │                     │
  │                     │ Journal.extract()
  │                     ├─ prev_snapshot ──────────> Beat 3 Mapper ...
```

El `prev_snapshot` es el JSON string `{last_events, unresolved_mysteries, physical_emotional_state}` que:
1. El Mapper del beat N+1 recibe para saber qué pasó antes (contexto de continuidad)
2. El `build_narrative_context()` del beat N+1 incluye como bloque `MEMORIA DEL ACTO ANTERIOR`

# Spec 023: Expansor de Sinopsis (Narrative Brief)

**Estado:** IMPLEMENTED  
**Fecha:** 2026-04-19  
**Rama destino:** `fix_flow_ollama_local`  
**Motivación:** El mapper recibe la sinopsis como texto libre y debe segmentarla en N beats en una sola llamada LLM. Sin análisis previo, el modelo tiende a producir summaries genéricos que no anclan los beats a los elementos concretos de la historia. Un paso de expansión estructurada antes del mapper produce summaries específicos y acotados.

**Ejemplo del problema:**

Sinopsis: *"Una pareja se muda a una casa en el monte y descubre que el terreno tiene una historia oscura."*

- Beat 1 sin expansor: *"La pareja llega al nuevo hogar."* → genérico
- Beat 1 con expansor: *"Claudia ordena las cajas en la cocina mientras Marcos revisa el terreno; ella nota que las baldosas del sótano tienen marcas de dedos raspadas desde adentro."* → anclado

---

## 1. Diseño

### Flujo resultante

```
DirectorUseCase.execute() / execute_full()
    │
    ├── Fase 0 (nueva): _expand_synopsis(story)
    │       └── LLM → narrative_brief (texto estructurado)
    │               └── persiste en story.narrative_brief (DB)
    │
    └── Fase 1: SynopsisBeatMapper.map(story, narrative_brief)
            └── narrative_brief se inyecta en el prompt del mapper
```

El expansor corre **siempre**, sin flag. El `narrative_brief` se pasa a `map()` como parámetro explícito.

### Posición en `DirectorUseCase`

```python
async def execute(self, story: Story) -> StoryPlan:
    narrative_brief = await self._expand_synopsis(story)
    # persiste en story antes de llamar al mapper
    mapper = SynopsisBeatMapper(...)
    beats = await mapper.map(story, narrative_brief=narrative_brief)
    return StoryPlan(story_id=story.id, title=story.title, beats=beats)

async def execute_full(self, story, initial_journal=None, on_plan_ready=None):
    narrative_brief = await self._expand_synopsis(story)
    mapper = SynopsisBeatMapper(...)
    beats = await mapper.map(story, narrative_brief=narrative_brief)
    ...

async def _expand_synopsis(self, story: Story) -> str:
    """Fase 0: expande la sinopsis en un narrative brief estructurado."""
    prompt = self.prompt_builder.build_expander_prompt(story)
    role_cfg = settings.role_config("expander")
    model = role_cfg.get("model") or settings.llm_model
    response = await self.llm.generate(
        prompt=prompt,
        system_prompt=None,
        model=model,
        temperature=role_cfg.get("temperature", 0.3),
        role="expander",
    )
    return self.normalizer.normalize(response.text, model_name=model).strip()
```

### Cambio en `SynopsisBeatMapper.map()`

```python
async def map(self, story: Story, narrative_brief: str = "") -> list[Beat]:
    prompt = self.prompt_builder.build_synopsis_mapper_prompt(story, narrative_brief)
    ...
```

El `narrative_brief` vacío produce comportamiento idéntico al actual — backwards compatible.

---

## 2. Configuración YAML — rol `expander`

Cada perfil en `config/llm_core_definitions.yaml` recibe un bloque `expander` bajo `roles:`:

```yaml
profiles:
  ollama-mistral:
    roles:
      director: ...
      voz: ...
      journal: ...
      expander:
        model: mistral:latest
        temperature: 0.3
        num_ctx: 2048
        num_predict: 500
        stop: ["---", "##"]

  anthropic-sonnet:
    roles:
      expander:
        model: claude-sonnet-4-6
        temperature: 0.3
        num_ctx: null
        num_predict: 600
```

`num_predict` acotado porque el brief es texto estructurado corto — no prosa narrativa.  
`temperature: 0.3` en todos los perfiles — el expansor busca análisis, no creatividad.

---

## 3. Prompts

### Variante frontier — `expander.md`

```markdown
# ANÁLISIS NARRATIVO

Eres un analista de estructura narrativa. Extraés los elementos concretos de una
sinopsis para guiar la planificación de beats.

## Historia

- Título: {title}
- Protagonistas: {protagonistas}
- Escenarios: {escenarios}
- Atmósfera: {atmosfera}
- Sinopsis: {sinopsis}

## Reglas
{reglas}

## Tarea

Responde con este formato exacto:

**Amenaza concreta:**
[Qué es exactamente el elemento de horror: su naturaleza, cómo se manifiesta]

**Estado inicial del protagonista:**
[Cómo llega emocionalmente: qué espera, qué ignora antes del primer beat]

**Momentos clave (3 eventos que DEBEN ocurrir en algún beat):**
1. [Evento 1]
2. [Evento 2]
3. [Evento 3]

**Arco emocional:**
[Inicio] → [Tensión] → [Crisis] → [Colapso] → [Secuela]

**Detalle sensorial del escenario:**
[2-3 detalles físicos/atmosféricos concretos del lugar]
```

### Variante compact — `expander_compact.md`

```markdown
SINOPSIS:
{sinopsis}

PROTAGONISTAS: {protagonistas}
ESCENARIO: {escenarios}
ATMÓSFERA: {atmosfera}

TAREA: Extraé los elementos concretos de esta historia en 5 líneas.

1. Amenaza: [qué es exactamente el horror, cómo se manifiesta]
2. Estado inicial: [cómo llega emocionalmente el protagonista]
3. Momento clave A: [evento concreto que debe ocurrir]
4. Momento clave B: [segundo evento concreto]
5. Detalle del escenario: [1-2 detalles físicos específicos del lugar]
```

La variante compact usa el mismo `_get_prompt_variant()` del perfil activo que el resto del sistema.

### Inyección en el mapper

`{narrative_brief}` se agrega a `synopsis_mapper.md` (frontier) y `synopsis_mapper_compact.md` (compact).

**Frontier** — agregar sección después de `## Sinopsis completa`:

```markdown
## Análisis narrativo previo

{narrative_brief}
```

**Compact** — agregar bloque antes de `INSTRUCCIONES:`:

```markdown
ANÁLISIS:
{narrative_brief}
```

Si `narrative_brief` está vacío, la sección queda en blanco sin romper el prompt.

---

## 4. Persistencia

Agregar columna `narrative_brief TEXT` a la tabla `story`:

```sql
ALTER TABLE story ADD COLUMN narrative_brief TEXT DEFAULT '';
```

Agregar campo al modelo de dominio:

```python
# src/domain/models/story.py
narrative_brief: str = ""
```

`StoryRunner` persiste el brief en DB después de `_expand_synopsis()` y antes de llamar al mapper, igual que persiste el journal.

---

## 5. Archivos afectados

| Archivo | Cambio |
|---|---|
| `config/llm_core_definitions.yaml` | Agregar bloque `expander` en cada perfil |
| `config/prompts_generation/expander.md` | CREAR — variante frontier |
| `config/prompts_generation/expander_compact.md` | CREAR — variante compact |
| `config/prompts_generation/synopsis_mapper.md` | Agregar sección `{narrative_brief}` |
| `config/prompts_generation/synopsis_mapper_compact.md` | Agregar bloque `ANÁLISIS: {narrative_brief}` |
| `src/application/services/prompt_builder.py` | Agregar `build_expander_prompt()` y `narrative_brief` en `build_synopsis_mapper_prompt()` |
| `src/application/use_cases/director_use_case.py` | Agregar `_expand_synopsis()`, llamarlo en `execute()` y `execute_full()` |
| `src/application/use_cases/synopsis_beat_mapper.py` | Agregar `narrative_brief: str = ""` en `map()` |
| `src/domain/models/story.py` | Agregar campo `narrative_brief: str = ""` |
| `src/infrastructure/database/` | Migración: columna `narrative_brief` en tabla `story` |
| `scripts/sql/init_db.sql` | Actualizar schema |
| `CLAUDE.md` | Actualizar descripción del Director (Fase 0 + Fase 1) |
| `README.md` | Actualizar diagrama de secuencia (Fase 0 visible), ERD (columna `narrative_brief`) |

---

## 6. Tests

| Test | Descripción |
|---|---|
| `test_expand_synopsis_returns_string` | `_expand_synopsis()` retorna string no vacío con MockLLMAdapter |
| `test_execute_calls_expander_before_mapper` | El LLM es llamado 2 veces en `execute()`: expansor primero, mapper después |
| `test_execute_passes_brief_to_mapper` | El `narrative_brief` del expansor llega al prompt del mapper |
| `test_map_with_empty_brief_unchanged` | `map(story, narrative_brief="")` produce el mismo resultado que hoy — no rompe tests existentes |
| `test_expander_uses_expander_role_config` | El expansor llama al LLM con `role="expander"`, no `role="director"` |
| `test_build_expander_prompt_frontier` | Carga `expander.md` con perfil frontier |
| `test_build_expander_prompt_compact` | Carga `expander_compact.md` con perfil compact |

---

## 7. Criterios de éxito

| Criterio | Verificación |
|---|---|
| El brief aparece en el debug file como Llamada 1 (rol: expander) | `--debug`: sección `## Llamada 1 — EXPANDER` presente |
| El mapper recibe el brief en su prompt | Debug Llamada 2: texto del brief visible en `### Prompt Enviado` |
| Beat summaries mencionan elementos concretos de la sinopsis | Revisión manual con LLM real |
| `narrative_brief` persiste en DB | `SELECT narrative_brief FROM story WHERE id = '...'` retorna texto |
| Tests existentes pasan sin modificación | `pytest tests/unit/ -v` — sin FAILED |
| `map()` sin `narrative_brief` es backward compatible | Tests actuales del mapper siguen pasando |

---

## 8. Boundaries

| Categoría | Regla |
|---|---|
| **Always Do** | `_expand_synopsis()` es privado — no es un caso de uso independiente |
| **Always Do** | Persistir `narrative_brief` en DB antes de llamar al mapper |
| **Always Do** | Pasar `narrative_brief=""` como default en `map()` para backwards compatibility |
| **Ask First** | Usar un modelo diferente al del perfil activo para el expansor |
| **Never Do** | Incluir `narrative_brief` en el output Markdown final — es artefacto de planificación |
| **Never Do** | Correr el expansor después del mapper o en paralelo — es una pre-fase secuencial |

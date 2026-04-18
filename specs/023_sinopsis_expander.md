# SPEC 023: Expansor de Sinopsis (Narrative Brief)

## Estado

> Borrador — **prioridad baja**, pendiente priorización junto al resto de specs

## Prioridad y dependencias

- **No implementar** hasta que el usuario lo priorice explícitamente en una sesión de revisión de specs.
- **Depende de:** Spec 022 (tests saneados) — prerequisito técnico mínimo.
- **Habilita:** Spec 003 User Story 6 — revisión/edición del narrative brief en la UI.

---

## 1. Problema

El Director recibe la sinopsis como texto libre de longitud arbitraria y debe generar 5 beat summaries en una sola llamada LLM. Sin un paso previo de análisis, el LLM tiende a producir summaries genéricos que no anclan los beats a los elementos concretos de la historia (el antagonista específico, el lugar exacto, el estado emocional inicial, los eventos que deben ocurrir).

**Ejemplo del problema actual:**

Sinopsis: *"Una pareja se muda a una casa en el monte y descubre que el terreno tiene una historia oscura."*

Beat 1 generado hoy: *"La pareja llega al nuevo hogar."* → genérico, podría ser cualquier historia.

Beat 1 esperado tras el spec: *"Claudia ordena las cajas en la cocina mientras Marcos revisa el terreno; ella nota que las baldosas del sótano tienen marcas de dedos raspadas desde adentro."* → anclado a la historia.

---

## 2. Solución: Dos Fases en el Director

El `DirectorUseCase.execute()` pasa de **1 llamada LLM** a **2 llamadas secuenciales**:

```
Fase 1: _expand_synopsis(story) → narrative_brief (texto)
Fase 2: _generate_beats(story, narrative_brief) → StoryPlan
```

### Fase 1 — Expansor (nueva)

LLM recibe la sinopsis raw y los datos de la historia, y devuelve un **narrative brief** estructurado en texto libre que incluye:

- **Amenaza concreta**: qué es exactamente el elemento de horror (objeto, entidad, lugar, patrón)
- **Estado inicial del protagonista**: cómo llega emocionalmente al comienzo de la historia
- **3 momentos clave obligatorios**: eventos específicos que DEBEN ocurrir en algún beat
- **Arco emocional**: la curva de estados que atraviesa el protagonista (de A → B → C → D → E)
- **Detalle sensorial del escenario**: 2-3 detalles físicos/atmosféricos específicos del lugar

Temperatura baja (`expander_temperature = 0.3`): se busca análisis, no creatividad.

### Fase 2 — Planificación de beats (existente, modificada)

El `build_planner_prompt()` recibe el `narrative_brief` como parámetro adicional y lo inyecta en el prompt con el placeholder `{narrative_brief}`.

---

## 3. Diseño Técnico

### 3.1 `config.py` — Nuevo campo

```python
expander_temperature: float = 0.3
```

Variable de entorno: `EXPANDER_TEMPERATURE=0.3`

### 3.2 Nuevo prompt `config/prompts_generation/expander.md`

```markdown
# EXPANSIÓN DE SINOPSIS

Eres un analista narrativo. Tu tarea es extraer los elementos concretos de esta historia
para guiar la planificación de beats.

## Historia
- Título: {title}
- Protagonistas: {protagonistas}
- Escenarios: {escenarios}
- Atmósfera: {atmosfera}
- Sinopsis: {sinopsis}

## Reglas de la historia
{reglas}

## Tu tarea

Responde con este formato exacto (completa cada sección con 1-3 oraciones específicas):

**Amenaza concreta:**
[Qué es exactamente el elemento de horror: su naturaleza, cómo se manifiesta, qué quiere]

**Estado inicial del protagonista:**
[Cómo llega emocionalmente: qué espera, qué ignora, qué le preocupa antes del primer beat]

**Momentos clave (3 eventos específicos que DEBEN ocurrir):**
1. [Evento 1]
2. [Evento 2]
3. [Evento 3]

**Arco emocional:**
[Inicio] → [Tensión] → [Crisis] → [Colapso] → [Secuela]

**Detalle sensorial del escenario:**
[2-3 detalles físicos/atmosféricos concretos del lugar que deben aparecer en la narración]
```

### 3.3 `PromptBuilder` — Nuevos métodos

```python
def build_expander_prompt(self, story: Story) -> str:
    """Build el prompt para expandir la sinopsis."""
    # Carga expander.md, fallback inline

def build_planner_prompt(self, story: Story, narrative_brief: str = "") -> str:
    """Build el prompt del Director. Acepta narrative_brief opcional."""
    # Si narrative_brief está presente, lo inyecta con {narrative_brief}
    # Si está vacío, usa un fallback neutro ("Sin análisis previo")
```

### 3.4 `DirectorUseCase` — Nuevo método privado

```python
async def execute(self, story: Story) -> StoryPlan:
    narrative_brief = await self._expand_synopsis(story)
    num_beats = self.prompt_builder.num_beats
    prompt = self.prompt_builder.build_planner_prompt(story, narrative_brief)
    system_prompt = self.prompt_builder.build_system_prompt(story)
    response = await self.llm.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        model=None,
        temperature=settings.director_temperature,
    )
    beats = self._parse_beats(response.text, story.id, num_beats)
    return StoryPlan(story_id=story.id, title=story.title, beats=beats)

async def _expand_synopsis(self, story: Story) -> str:
    """Fase 1: expande la sinopsis en un narrative brief."""
    prompt = self.prompt_builder.build_expander_prompt(story)
    response = await self.llm.generate(
        prompt=prompt,
        system_prompt=None,
        model=None,
        temperature=settings.expander_temperature,
    )
    return response.text.strip()
```

### 3.5 `planner.md` — Actualización

Agregar sección después de Sinopsis:

```markdown
## Análisis narrativo previo

{narrative_brief}
```

---

## 4. Archivos Afectados

| Archivo | Cambio |
|---|---|
| `src/config.py` | Agregar `expander_temperature: float = 0.3` |
| `config/prompts_generation/expander.md` | CREAR — prompt del Expansor |
| `config/prompts_generation/planner.md` | Agregar sección `{narrative_brief}` |
| `src/application/services/prompt_builder.py` | Agregar `build_expander_prompt()`, actualizar `build_planner_prompt()` |
| `src/application/use_cases/director_use_case.py` | Agregar `_expand_synopsis()`, actualizar `execute()` |
| `CLAUDE.md` | Actualizar descripción del Director (2 fases) |

---

## 5. Impacto en Tests

- `DirectorUseCase` hace 2 llamadas LLM en lugar de 1. Los tests de `MockLLMAdapter` con `fixed_response` devolverán el mismo texto para ambas llamadas — válido para tests unitarios.
- Si se necesita verificar las dos fases por separado, el `MockLLMAdapter` podría extenderse con `responses: list[str]` (cola de respuestas). Esto queda como mejora opcional, no bloqueante.

---

## 6. Criterios de Éxito

- [ ] `DirectorUseCase.execute()` realiza 2 llamadas LLM secuenciales
- [ ] `narrative_brief` aparece en el prompt de planificación
- [ ] Beat summaries generados contienen referencias concretas a la historia (validar manualmente con LLM real)
- [ ] Tests unitarios existentes pasan sin modificación (MockLLMAdapter devuelve fixed_response para ambas llamadas)
- [ ] `config.py` expone `expander_temperature`

---

## 7. Persistencia del Narrative Brief (requisito UI)

El `narrative_brief` **debe persistirse en DB** para que la UI pueda presentarlo al usuario antes de ejecutar la Fase 2 (planificación de beats), permitiendo revisión y edición.

### Modelo de datos propuesto

Agregar columna `narrative_brief TEXT` a la tabla `story`:

```sql
ALTER TABLE story ADD COLUMN narrative_brief TEXT;
```

### Flujo con UI

```
Fase 1: _expand_synopsis() → narrative_brief → save en story.narrative_brief
                                   ↓
                         UI muestra narrative_brief al usuario
                         Usuario puede editar el texto
                                   ↓
Fase 2: _generate_beats() lee story.narrative_brief (posiblemente editado)
```

### Sin UI (CLI actual)

El CLI ejecuta Fase 1 → persiste → ejecuta Fase 2 en secuencia sin intervención. El brief se guarda en DB igual, disponible para consulta posterior.

---

## 8. Archivos Afectados (actualizado)

| Archivo | Cambio |
|---|---|
| `src/config.py` | Agregar `expander_temperature: float = 0.3` |
| `config/prompts_generation/expander.md` | CREAR — prompt del Expansor |
| `config/prompts_generation/planner.md` | Agregar sección `{narrative_brief}` |
| `src/application/services/prompt_builder.py` | Agregar `build_expander_prompt()`, actualizar `build_planner_prompt()` |
| `src/application/use_cases/director_use_case.py` | Agregar `_expand_synopsis()`, actualizar `execute()` |
| `src/domain/models/story.py` | Agregar campo `narrative_brief: str = ""` |
| `src/infrastructure/database/` | Migración: columna `narrative_brief` en tabla `story` |
| `scripts/sql/` | Actualizar script de init DB |
| `CLAUDE.md` | Actualizar descripción del Director (2 fases) |

---

## 9. Boundaries

| Categoría | Regla |
|---|---|
| **Always Do** | `_expand_synopsis()` debe ser privado — no es un caso de uso independiente |
| **Always Do** | Persistir `narrative_brief` en DB tras Fase 1, antes de Fase 2 |
| **Ask First** | Usar un modelo diferente para el Expansor (si se quiere optimizar costo/velocidad) |
| **Never Do** | Incluir `narrative_brief` en el output Markdown final — es artefacto de planificación, no prosa |

---

## 10. Preguntas Abiertas

Ninguna. El diseño está autocontenido.

# SPEC 021: Reducción a 5 Beats y Generación Spec-Driven

## Estado

> Borrador revisado — pendiente OK del usuario para avanzar a PLAN

## 1. Objetivo

**Reducir el número de beats de 10 a 5** y hacer que la generación sea **spec-driven**: el `llm_beats_definition.yaml` existente en `config/` es la fuente de verdad para la estructura narrativa. El Director debe recibir las definiciones de cada beat (intent, must, must_not, state_change) para generar summaries acotados a esa guía.

### Decisiones de diseño confirmadas

| Decisión | Resolución |
|---|---|
| ¿Director recibe sinopsis una vez o por beat? | **Una vez** — `DirectorUseCase.execute()` se llama una sola vez en `_run_plan()`. Sinopsis completa va en el prompt. |
| ¿`PromptBuilder` carga el YAML en `__init__` o lazy? | **`__init__`** — detalle de implementación, no requiere configuración. |
| ¿`num_beats` viene del YAML o de `config.py`? | **Del YAML** — el YAML es el spec, `num_beats = len(beats_spec.beats)`. No se agrega variable `NUM_BEATS` en config ni en `.env`. |

### Motivación

- 10 beats generan demasiado contexto de prompt acumulado entre iteraciones, degradando la coherencia.
- El `llm_beats_definition.yaml` ya define una estructura de 5 actos narrativos coherente y autocontenida.
- Centralizar la definición de beats en el YAML permite cambiarla sin tocar código.

---

## 2. Estado Actual vs. Estado Objetivo

| Punto | Actual | Objetivo |
|---|---|---|
| Número de beats | 10 (default hardcodeado) | 5 (leído del YAML) |
| Fuente de estructura | Parámetro `num_beats: int` | `config/llm_beats_definition.yaml` |
| Prompt del Director | Genérico ("genera N beats") | Incluye `intent`, `must`, `must_not` por beat |
| Configuración | Sin variable `num_beats` en `config.py` | `num_beats: int = 5` en `Settings` |
| Planner prompt | No existe `planner.md` | `config/prompts_generation/planner.md` creado |
| `system.md` | Menciona arco de 4 fases sin numeración | Actualizado a 5 actos alineado con el YAML |

---

## 3. Archivos Afectados

### Nuevos

| Archivo | Descripción |
|---|---|
| `config/prompts_generation/planner.md` | Prompt del Director que inyecta el spec de cada beat |

### Modificados

| Archivo | Cambio |
|---|---|
| `src/config.py` | Agregar `num_beats: int = 5` y `beats_definition_file: str = "config/llm_beats_definition.yaml"` |
| `src/application/services/prompt_builder.py` | Cargar YAML y construir `build_planner_prompt()` con definiciones por beat |
| `src/application/use_cases/director_use_case.py` | Usar `settings.num_beats` como default; recibir `beats_spec` del builder |
| `src/core/orchestrator.py` | Cambiar default `num_beats=10` → `settings.num_beats` |
| `config/prompts_generation/system.md` | Actualizar sección "ESTRUCTURA" para reflejar los 5 actos del YAML |
| `CLAUDE.md` | Actualizar "10-Beat" → "5-Beat Story Generation" y variables de entorno |

### No tocar (specs históricos)

Todos los specs anteriores (001–020) documentan decisiones de otro momento y no deben editarse.

---

## 4. Diseño Técnico

### 4.1 `config.py` — Nuevo campo

```python
beats_definition_file: str = "config/llm_beats_definition.yaml"
```

No se agrega `num_beats` — ese valor se deriva de `len(yaml_data['beats_spec']['beats'])` al leer el YAML. El YAML es la única fuente de verdad.

### 4.2 `PromptBuilder.build_planner_prompt()`

El builder carga el YAML en `__init__` (una sola vez) y formatea cada beat como bloque de instrucciones. `num_beats` se deriva de `len(beats_spec)` del YAML:

```
Beat 1 — exposicion
  Intent: establecer normalidad y sembrar una fisura
  Debe incluir: presentar situacion base del narrador / introducir una anomalia sutil / ...
  No debe incluir: confirmar lo paranormal
  Cambio de estado: estabilidad → incomodidad leve
```

Este bloque se inyecta en `planner.md` como `{beats_spec}`.

### 4.3 `planner.md` — Nuevo prompt del Director

```markdown
# TAREA DEL DIRECTOR

Eres el Director de la historia. Tu trabajo es generar exactamente {num_beats} summaries,
uno por cada acto, siguiendo la estructura narrativa definida abajo.

## Historia
Título: {title}
Protagonista: {protagonista}
Sinopsis: {sinopsis}

## Estructura de Actos (obligatoria)

{beats_spec}

## Instrucciones de salida
- Responde SOLO con los {num_beats} summaries, uno por línea.
- Formato: `N. [summary del acto]`
- Cada summary debe ser específico a esta historia, no genérico.
- Cada summary debe respetar el intent y los must/must_not del acto correspondiente.
- No incluyas explicaciones ni encabezados adicionales.
```

### 4.4 `DirectorUseCase.execute()`

`num_beats` ya no es parámetro — el builder lo provee internamente desde el YAML:

```python
async def execute(self, story: Story) -> StoryPlan:
    prompt = self.prompt_builder.build_planner_prompt(story)
    num_beats = self.prompt_builder.num_beats  # derivado del YAML
    ...
```

### 4.5 `StoryRunner.run_full()` y `_run_plan()`

Eliminar el parámetro `num_beats` del orquestador — ya no es necesario. El YAML lo define.

---

## 5. Criterios de Éxito

- [ ] `config.py` expone `num_beats=5` y `beats_definition_file`
- [ ] `PromptBuilder` carga el YAML y genera `beats_spec` correctamente
- [ ] `planner.md` existe y contiene los placeholders `{beats_spec}`, `{num_beats}`
- [ ] `DirectorUseCase` genera exactamente 5 beats por defecto
- [ ] `_parse_beats()` sigue funcionando con 5 líneas
- [ ] `system.md` menciona los 5 actos del YAML
- [ ] `CLAUDE.md` dice "5-Beat" en el concepto central
- [ ] Tests existentes pasan sin modificación (el mock no depende de num_beats)
- [ ] `python -m src generate --title "..." --protagonista "..." --sinopsis "..."` genera 5 beats

---

## 6. Boundaries

| Categoría | Regla |
|---|---|
| **Always Do** | Leer `num_beats` y `beats_definition_file` de `settings`; no hardcodear |
| **Ask First** | Cambios al schema de DB; cambios a los campos del YAML |
| **Never Do** | Modificar specs 001–020; hardcodear paths al YAML |

---

## 7. Preguntas Abiertas

Ninguna. Las decisiones de diseño están resueltas en la sección §1.

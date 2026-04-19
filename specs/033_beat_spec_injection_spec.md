# Spec 033 — Inyección de Beat Spec + Restauración de DirectorUseCase como Orquestador

**Estado:** DRAFT  
**Fecha:** 2026-04-19  
**Rama destino:** `fix_flow_ollama_local`  
**Motivación:** Dos problemas relacionados. Primero: el `llm_beats_definition.yaml` define la estructura dramática completa de cada beat (`must`, `must_not`, `state_change`, `success_signal`), pero esa información nunca llega al pipeline de generación. Segundo: `DirectorUseCase` fue desplazado del pipeline activo cuando se introdujo `SynopsisBeatMapper`, perdiendo su rol de orquestador de la fase de planificación. `StoryRunner` llama directamente al mapper, sin pasar por el Director. Esto rompe la arquitectura conceptual donde el Director es quien toma la responsabilidad del plan narrativo y el mapper es una herramienta que él usa.

---

## 1. Objetivo

Tres cambios coordinados:

1. **Restaurar `DirectorUseCase` como orquestador** de la fase de planificación. `StoryRunner` debe llamar al Director, y el Director usa internamente `SynopsisBeatMapper` como herramienta de extracción. El mapper deja de ser invocado directamente desde el runner.

2. **Inyectar restricciones del YAML en el Mapper** — para que los beat summaries que produce incorporen la intención dramática (`must`, `must_not`), no solo el evento de la sinopsis.

3. **Inyectar restricciones del YAML en Voz** — para que al narrar cada beat sepa qué debe lograr, qué evitar y qué transición emocional producir.

Aplicar en **ambos perfiles**: compact y frontier, con nivel de detalle diferente por perfil.

---

## 2. Diagnóstico del estado actual

### Mapper (compact)
Recibe `{beats_spec_compact}` que resuelve a:
```
Acto 1 (exposicion): establecer normalidad y sembrar una fisura
Acto 2 (accion_ascendente): activar el conflicto mediante transgresion
...
```
Solo nombre e intent. Sin must/must_not. El modelo extrae el evento correcto pero sin saber cómo debe estar encuadrado.

### Mapper (frontier)
Recibe `{beats_spec}` que incluye must, must_not, state_change y success_signal completos pero en formato texto genérico no diferenciado por beat.

### Voz (compact y frontier)
Recibe `{beat_summary}` — texto libre del mapper. No recibe ninguna restricción del YAML para el beat actual. Narra el evento pero sin ancla dramática.

---

## 3. Diseño de la solución

### 3.1 Nuevo método en `PromptBuilder`: `_format_beat_spec_for_beat(beat_number, variant)`

```python
def _format_beat_spec_for_beat(self, beat_number: int, variant: str = "frontier") -> str:
    """Retorna las restricciones del YAML para un beat específico."""
```

- Busca en `self._beats_spec` el beat con `id == beat_number`.
- Versión **compact**: solo `must` y `must_not` como listas breves.
- Versión **frontier**: `must`, `must_not`, `state_change` y `success_signal` completos.

**Salida compact (ejemplo Beat 1):**
```
Debe incluir: situacion base del narrador / anomalia sutil / advertencia implicita
No debe incluir: confirmacion de lo paranormal
```

**Salida frontier (ejemplo Beat 1):**
```
Debe incluir:
- presentar situacion base del narrador
- introducir una anomalia sutil
- incluir regla, advertencia o limite implicito

No debe incluir:
- confirmar lo paranormal

Transición emocional: estabilidad → incomodidad leve
Señal de éxito: el lector percibe que algo no encaja pero no sabe qué
```

### 3.2 Mapper — enriquecer el formato de salida pedido

**Compact** — cambio en `synopsis_mapper_compact.md`:

El formato de respuesta actual pide:
```
1. [qué ocurre en la sinopsis en este acto, una oración]
```

El nuevo formato pide una oración que integre el evento de la sinopsis Y la restricción del beat:
```
1. [qué ocurre + cómo debe quedar encuadrado dramáticamente]
```

Ejemplo esperado para Beat 1:
> "La familia llega a la casa de María y escucha la advertencia de la abuela sobre el monte, sembrando incomodidad sin confirmar nada paranormal."

Para lograrlo, el template recibe una nueva variable `{beats_spec_with_constraints}` que combina nombre, intent, must y must_not por beat.

**Frontier** — el `synopsis_mapper.md` ya recibe `{beats_spec}` completo. Se revisa si el formato actual es suficiente o necesita ajuste de énfasis.

### 3.3 Voz — inyectar restricciones del beat actual

Agregar variable `{beat_spec}` en ambos templates.

**`voice_compact.md`** — sección nueva antes de `--- ESCRIBE EL SIGUIENTE FRAGMENTO ---`:
```
--- RESTRICCIONES DE ESTE FRAGMENTO ---
{beat_spec}
```

**`voice.md` (frontier)** — sección nueva dentro de `## BEAT ACTUAL`:
```
## BEAT ACTUAL
- Numero: {beat_number} de {total_beats}
- Resumen: {beat_summary}
- Restricciones dramáticas:
{beat_spec}
```

`{beat_spec}` se resuelve con `_format_beat_spec_for_beat(beat.number, variant)`.

---

## 4. Arquitectura: DirectorUseCase como orquestador

### Estado actual (roto)
```
StoryRunner._run_plan()
    └── SynopsisBeatMapper.map()   ← mapper invocado directamente
            └── llm.generate()
```

`DirectorUseCase` existe en el código pero no participa del pipeline activo de `generate`.

### Estado objetivo
```
StoryRunner._run_plan()
    └── DirectorUseCase.execute()  ← Director es el punto de entrada
            └── SynopsisBeatMapper.map()   ← mapper es una herramienta interna
                    └── llm.generate()
```

### Responsabilidades redefinidas

| Componente | Responsabilidad |
|---|---|
| `DirectorUseCase` | Punto de entrada de la planificación. Recibe la `Story`, delega la extracción al mapper, valida que se produzcan exactamente `num_beats` beats y retorna el `StoryPlan`. Es el dueño del contrato de salida. |
| `SynopsisBeatMapper` | Herramienta de extracción. Toma la sinopsis y el beat spec, produce beat summaries alineados al YAML. No conoce ni valida el plan completo. |

### Cambios en `DirectorUseCase.execute()`

```python
async def execute(self, story: Story) -> StoryPlan:
    mapper = SynopsisBeatMapper(
        self.llm,
        self.prompt_builder,
        normalizer=self.normalizer,
        debug_collector=self.debug_collector,
    )
    beats = await mapper.map(story)
    return StoryPlan(story_id=story.id, title=story.title, beats=beats)
```

`DirectorUseCase` recibe `debug_collector` en su constructor (igual que hoy tenía el mapper en `StoryRunner`).

### Cambios en `StoryRunner._run_plan()`

```python
async def _run_plan(self, story: Story) -> list[Beat]:
    director = DirectorUseCase(
        self.llm,
        self.prompt_builder,
        normalizer=self.normalizer,
        debug_collector=self.debug_collector,
    )
    plan = await director.execute(story)
    beats = plan.beats
    ...
```

El mapper desaparece de `StoryRunner` — solo el Director es visible desde el runner.

---

## 5. Cambios de código

### 5.1 `src/application/use_cases/director_use_case.py`

| Cambio | Detalle |
|---|---|
| Constructor recibe `debug_collector` | Igual al mapper actual — backwards compatible con default `NullDebugCollector()` |
| `execute()` instancia y llama `SynopsisBeatMapper` internamente | El mapper deja de tener lógica LLM propia en este contexto — es invocado por el Director |

### 5.2 `src/core/orchestrator.py` — `StoryRunner._run_plan()`

| Cambio | Detalle |
|---|---|
| Reemplazar instanciación de `SynopsisBeatMapper` por `DirectorUseCase` | Una línea de cambio efectivo |
| `SynopsisBeatMapper` desaparece del import de `orchestrator.py` | Ya no es responsabilidad del runner |

### 5.3 `src/application/services/prompt_builder.py`

| Método | Cambio |
|---|---|
| `_format_beat_spec_for_beat(beat_number, variant)` | NUEVO |
| `_format_beats_spec_with_constraints()` | NUEVO — must/must_not por beat para el mapper |
| `build_beat_prompt()` | Agrega `beat_spec` al `format()` |
| `build_synopsis_mapper_prompt()` | Agrega `beats_spec_with_constraints` al `format()` |

### 5.4 Templates de prompts

| Archivo | Cambio |
|---|---|
| `config/prompts_generation/synopsis_mapper_compact.md` | Reemplaza `{beats_spec_compact}` por `{beats_spec_with_constraints}` |
| `config/prompts_generation/synopsis_mapper.md` | Ajustar énfasis en must/must_not |
| `config/prompts_generation/voice_compact.md` | Agregar sección `{beat_spec}` |
| `config/prompts_generation/voice.md` | Agregar `{beat_spec}` en sección BEAT ACTUAL |

---

## 5. Formato de `beats_spec_with_constraints` para el mapper compact

```
Acto 1 (exposicion): establecer normalidad y sembrar una fisura
  Debe incluir: situacion base del narrador / anomalia sutil / advertencia implicita
  No debe incluir: confirmacion de lo paranormal

Acto 2 (accion_ascendente): activar el conflicto mediante transgresion
  Debe incluir: romper la advertencia / evento anomalo concreto / intento de explicacion racional
  No debe incluir: aceptar lo paranormal como hecho

Acto 3 (climax): forzar reconocimiento del horror
  Debe incluir: invalidar explicacion racional / presencia directa
  No debe incluir: explicar origen completo del fenomeno

Acto 4 (accion_descendente): llevar al protagonista al colapso y reaccion
  Debe incluir: perdida de control / intento de escape o respuesta
  No debe incluir: resolver el conflicto facilmente

Acto 5 (desenlace): cerrar con escape incompleto y secuela
  Debe incluir: salida del peligro / marca persistente o evidencia ambigua
  No debe incluir: cerrar completamente el misterio
```

---

## 6. Flujo de prueba antes de implementar

Antes de modificar código, probar en LM Studio / Ollama los dos prompts nuevos:

1. **Mapper con `beats_spec_with_constraints`** — verificar que los summaries incorporen la restricción dramática además del evento.
2. **Voz Beat 1 con `{beat_spec}` inyectado** — verificar que la prosa respeta `must` y `must_not`.

Solo si ambas pruebas son satisfactorias → implementar los cambios de código.

---

## 7. Success Criteria

| Criterio | Verificación |
|---|---|
| Beat summaries del mapper incluyen restricción dramática | Leer Llamada 1 del debug file — el summary menciona qué evitar |
| VOZ Beat 1 no confirma lo paranormal en la exposición | Leer Llamada 2 del debug file — la prosa planta incomodidad sin revelar |
| VOZ Beat 3 (clímax) incluye presencia directa e invalida lógica racional | Leer Llamada 6 |
| Tests unitarios pasan | `pytest tests/unit/ -v` |
| Funciona en ambos perfiles compact y frontier | Ejecutar con `ollama-mistral` y `gemini-pro` |

---

## 8. Boundaries

### Always Do
- `_format_beat_spec_for_beat()` falla silenciosamente si el beat_number no existe en el YAML (retorna string vacío).
- La variable `{beat_spec}` siempre se pasa al template aunque sea vacía — evitar `KeyError`.

### Never Do
- Inyectar el spec completo de TODOS los beats a VOZ — solo el beat actual.
- Modificar el YAML `llm_beats_definition.yaml` como parte de este spec.

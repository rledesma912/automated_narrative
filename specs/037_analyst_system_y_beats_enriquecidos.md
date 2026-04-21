# Spec 037 — Story Analyst System Prompt + Beats Enriquecidos en Mapper (Compact)

**Estado:** DRAFT  
**Fecha:** 2026-04-20  
**Rama destino:** `fix_flow_ollama_local`  
**Motivación:** El flujo compact (Ollama/LLMs locales) tiene dos puntos débiles identificados en el debug `output_stories/debug_prompts_responses_202604200909.md`:
1. El STORY_ANALYST opera sin system prompt, lo que produce extracciones genéricas (ej: "Estado inicial" describe la situación familiar en vez del estado emocional del narrador).
2. Los beats del MAPPER son de una sola línea extractiva, dejando a la VOZ con contexto insuficiente para narrar con riqueza.

---

## 1. Diagnóstico

### 1.1 STORY_ANALYST sin system prompt

Debug — Llamada 1:
```
System Prompt: _(ninguno)_
```

El modelo recibe solo el user prompt y responde en modo genérico. El "Estado inicial" extraído fue:
```
2. Estado inicial: La familia llega a la casa rural para pasar unas horas con María y prepararse para una fiesta familiar en una estancia cercana.
```

Correcto como situación, pero incorrecto como **estado emocional del narrador** (Irene). El model no tiene instrucción de rol que le diga que está extrayendo **desde la perspectiva y experiencia del narrador**, no como sinopsis objetiva.

### 1.2 Beats de una sola línea

Debug — Llamada 2, output del Mapper:
```
1. La familia llega a la casa rural de María para pasar unas horas con ella y prepararse para una fiesta familiar
2. Durante el regreso de la fiesta, se produce una tormenta eléctrica que obliga a tomar el atajo por el Monte de los Espinillos
```

Cada beat es un evento puro, sin el contexto de la amenaza, del estado del narrador, ni de los detalles físicos del escenario. La VOZ luego tiene que inferir toda esa densidad narrativa a partir del beat_summary solo, sin que el narrative_brief haya "cargado" esa información en el beat.

---

## 2. Cambio conceptual

Este spec introduce una **estrategia de enriquecimiento progresivo de contexto**:

```
STORY_ANALYST     → extrae 5 elementos clave (narrative_brief)
       ↓
MAPPER            → cada beat fusiona: evento extractivo + elementos del brief + reglas del input
       ↓
VOZ               → recibe un beat_summary denso, no solo un evento
```

El objetivo es que el narrative_brief no quede "flotando" como texto auxiliar, sino que sus elementos se **distribuyan y anclen** en los beats donde son relevantes. El beat_summary se convierte en la unidad mínima de contexto narrativo para la VOZ.

---

## 3. Cambio 1 — System prompt para story_analyst_compact

### 3.1 Nuevo archivo

`config/prompts_generation/story_analyst_system_compact.md` (CREAR)

```
Sos un analista de narrativa. Tu tarea es extraer elementos concretos de una sinopsis.

No sos un escritor. No expandís, no reinterpretás, no completás información ausente.

REGLAS:
- Extraé exactamente lo que está escrito en la sinopsis
- "Estado inicial" = estado emocional y situacional del NARRADOR al comienzo
- "Amenaza" = la naturaleza concreta del horror, cómo se manifiesta en la historia
- "Momentos clave" = eventos puntuales que ocurren, no tendencias ni climas
- "Detalle del escenario" = especificidades físicas concretas del lugar, no atmósfera general

FORMATO DE SALIDA:
- Exactamente 5 líneas numeradas
- Sin texto adicional, sin explicaciones, sin encabezados
- Cada línea: "N. Etiqueta: [extracción concreta]"
```

### 3.2 Cambios en código

**`src/application/services/prompt_builder.py`**

Agregar método:
```python
def build_story_analyst_system(self) -> str | None:
    """Carga el system prompt para story_analyst según la variante activa."""
    variant = self._get_prompt_variant()
    if variant == "compact":
        path = self._prompts_dir / "story_analyst_system_compact.md"
        return path.read_text(encoding="utf-8").strip() if path.exists() else None
    return None
```

**`src/application/use_cases/director_use_case.py::_analyze_story()`** (línea 75-82)

```python
# antes:
prompt = self.prompt_builder.build_story_analyst_prompt(story)
response = await self.llm.generate(
    prompt=prompt,
    system_prompt=None,
    ...
)

# después:
prompt = self.prompt_builder.build_story_analyst_prompt(story)
system_prompt = self.prompt_builder.build_story_analyst_system()
response = await self.llm.generate(
    prompt=prompt,
    system_prompt=system_prompt,
    ...
)
```

También actualizar el `debug_collector.record()` en esa función para pasar `system_prompt=system_prompt` en lugar de `system_prompt=None`.

---

## 4. Cambio 2 — Beats enriquecidos en synopsis_mapper_compact

### 4.1 Formato de beat nuevo

Cada beat pasa de **1 oración** a un **agrupador numerado con listado de oraciones concretas**. El LLM decide cuántas oraciones incluye en cada beat según la densidad de la sinopsis para ese acto — no se impone un número fijo. El contrato fijo es solo la cantidad de beats (5).

| Fuente | Qué aporta |
|---|---|
| Sinopsis (extractivo) | Los eventos concretos del acto — anclaje a la realidad de la historia |
| narrative_brief | Los elementos del brief relevantes para ese acto (amenaza, estado, momento clave, detalle) |
| reglas del input | Las restricciones narrativas que el autor definió (si aplican al acto) |

**Ejemplo con el debug actual:**

*Antes (beat 1):*
```
1. La familia llega a la casa rural de María para pasar unas horas con ella y prepararse para una fiesta familiar
```

*Después (beat 1):*
```
1.
- La familia llega a la casa de campo de María en zona rural para pasar unas horas antes de una fiesta.
- La abuela advierte casi al pasar sobre el Monte de los Espinillos; no da explicaciones, pero su tono basta.
- Irene queda con una incomodidad latente que no logra sacudirse.
```

*Después (beat 5, desenlace más escueto):*
```
5.
- La familia sale del monte al amanecer, exhaustos, sin poder ordenar lo vivido.
- Nadie logra explicar la figura en el claro, pero la certeza persiste: estaba colocada allí para ellos.
```

La cantidad de oraciones varía por beat según lo que la sinopsis y el análisis aportan en ese acto.

### 4.2 Modificación de synopsis_mapper_compact.md

Agregar `{reglas}` como nueva variable (actualmente ausente).

Cambiar la instrucción de formato de:
```
Para cada acto:
- seleccioná el fragmento más representativo de la sinopsis
- condensalo en una sola oración
- mantené fidelidad semántica total
```

A:
```
Para cada acto, listá todas las oraciones concretas que identifiques en la sinopsis y el análisis para ese momento.
No hay un número fijo — ponés las que el acto requiera (mínimo 2).

Cada oración debe:
- derivarse directamente de la sinopsis o del ANÁLISIS
- describir una acción, percepción o evento observable
- ser concreta (sin lenguaje abstracto ni interpretativo)

Fidelidad total: no inventés ni expandás creativamente.
```

Cambiar el formato de respuesta de:
```
1. ...   (una oración)
```

A:
```
1.
- [oración concreta del acto]
- [oración concreta del acto]
- [...]

2.
- [...]
```

### 4.3 Contexto de la VOZ en el system prompt del mapper

Para que el criterio de selección "solo incluí lo que la VOZ no puede inferir sola" sea significativo, el mapper necesita saber mínimamente qué es la VOZ y qué contexto tiene disponible. Sin eso, el criterio es vacío para el modelo.

Se agregan **dos líneas al inicio** de `synopsis_mapper_system_compact.md`:

```
Tu output será usado por un narrador en primera persona para escribir prosa literaria.
Ese narrador conoce la atmósfera y los personajes, pero no sabe qué eventos concretos ocurren en cada momento del relato.
```

Esto le da al mapper el "por qué" de su tarea: los eventos específicos y las percepciones sensoriales concretas deben ir en el beat porque el narrador no los tiene. Las generalidades de atmósfera o carácter ya las tiene el narrador — no hace falta repetirlas.

El mapper pasa de ser un **extractor ciego** a un **extractor con propósito**: elige qué incluir en función de lo que el narrador necesita saber.

### 4.4 Rol de {reglas} en el mapper

Las reglas se incluyen como contexto para el mapper, **no como anotación explícita por beat**. El LLM interpreta solo dónde aplica cada regla al seleccionar los puntos de cada acto. No se le pide que etiquete "regla X aplica acá" — ese filtrado es implícito.

Esto produce un efecto de **doble refuerzo** para la VOZ:

```
(1) voice_compact.md ya incluye {reglas} como instrucción directa  ← existente
(2) beat_summary contiene puntos ya filtrados por las reglas via el mapper  ← nuevo
```

Los LLMs locales (Mistral, Llama) tienden a perder instrucciones en contextos largos. Si las reglas ya "moldearon" el beat_summary antes de que la VOZ lo reciba, hay menos chance de violación aunque el modelo pierda el hilo de las instrucciones explícitas.

### 4.4 Agregar {reglas} al método del PromptBuilder

**`src/application/services/prompt_builder.py::build_synopsis_mapper_prompt()`**

Verificar si `story.reglas` ya se pasa. Si no, agregarlo como variable `{reglas}` en el template y en el `.format()`.

---

## 5. Archivos afectados

| Archivo | Tipo de cambio |
|---|---|
| `config/prompts_generation/story_analyst_system_compact.md` | CREAR |
| `config/prompts_generation/synopsis_mapper_compact.md` | MODIFICAR (instrucciones de formato + agregar `{reglas}`, tope blando 2-4) |
| `config/prompts_generation/synopsis_mapper_system_compact.md` | MODIFICAR (agregar 2 líneas de contexto VOZ al inicio) |
| `src/application/services/prompt_builder.py` | MODIFICAR (agregar `build_story_analyst_system()`, verificar `{reglas}` en mapper) |
| `src/application/services/beat_parser.py` | MODIFICAR (capturar contenido multi-línea entre marcadores `N.`) |
| `src/application/use_cases/director_use_case.py` | MODIFICAR (`_analyze_story()` línea 75-100, inyectar system_prompt) |

---

## 6. Boundaries

### Always Do
- `build_story_analyst_system()` retorna `None` si el archivo no existe → compatibilidad con perfiles frontier y nuevos perfiles sin system prompt
- `beat_parser.py` debe capturar **todo el contenido** entre marcadores `N.` y `N+1.` como el summary (actualmente solo toma la primera línea) — este es el único cambio de código necesario en el parser
- El debug_collector registra el system_prompt real (no `None` hardcodeado)

### Never Do
- No cambiar la variante `frontier` — este spec es exclusivo de compact
- No hardcodear un número de oraciones por beat — el LLM decide la granularidad
- No cambiar el número de beats — sigue siendo `{num_beats}` del YAML (el agrupador `N.` sigue siendo el contrato fijo)

---

## 7. Success Criteria

| Criterio | Verificación |
|---|---|
| STORY_ANALYST tiene system prompt no vacío | Debug Llamada 1: `System Prompt:` muestra texto |
| "Estado inicial" extrae estado emocional del narrador | Debug Llamada 1: línea 2 describe cómo se siente Irene |
| Beats del MAPPER son agrupadores con oraciones listadas | Debug Llamada 2: cada beat tiene formato `N.\n- oración\n- oración...` |
| Cantidad de oraciones varía por beat según densidad del acto | Debug Llamada 2: no todos los beats tienen el mismo número de ítems |
| `{reglas}` aparece en el prompt del MAPPER | Debug Llamada 2: sección REGLAS en prompt enviado |
| Parser sigue funcionando con beats más largos | Debug Llamada 2: `Estado: ok: 5 beats` |
| VOZ genera prosa más rica al tener beat_summary denso | Salida narrativa final con más detalle sensorial y emocional |
| Tests unitarios pasan | `pytest tests/unit/ -v` |

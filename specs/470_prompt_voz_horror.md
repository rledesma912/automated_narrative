# SPEC-470: Prompt de la Voz con oficio de horror (EV-3)

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development)
**Estado:** PLAN — SPECIFY aprobada (2026-09-24); plan pendiente de OK para pasar a TASKS
**Roadmap:** EV-3 (calidad narrativa, sin costo). EV-2 (Voz en Anthropic) queda para después.

---

## ASSUMPTIONS

1. Se trabaja sobre las **dos variantes** del system prompt de la Voz: compact (`voice_system_compact.md`, la del perfil activo `ollama-gemma3-12b`) y frontier (`system.md`, vía `build_voice_prompt()`), más el `narrative_context` que arma `NarrativeContextAssembler` (común a las dos). La frontier no se puede evaluar con el perfil activo: se valida con tests de prompt y queda lista para EV-2. `voice.md` / `voice_compact.md` son del camino legado (`build_beat_prompt`) y no se tocan.
2. **Sin llamadas LLM nuevas** y sin cambiar de modelo: solo texto de prompts y bloques determinísticos (se mantienen 16 llamadas).
3. El resto del pipeline (Analyst, Mapper, Journal) no se toca; si la evaluación muestra que un problema nace en el Mapper, se anota como pendiente.
4. La calidad se mide con el mismo arnés de Spec-450 S5 (`el_monte_prohibido`, `gemma3:12b`, DB descartable) más métricas automáticas simples, y lectura manual.

---

## OBJECTIVE

Las relatoras (esposa e hija del usuario, canal de YouTube) dejaron de usar la app porque las historias les parecían de baja calidad. La Spec-450 mejoró la coherencia de la amenaza; lo que queda son **defectos de la prosa de la Voz**, visibles en las cuatro generaciones de la evaluación S5:

| Problema | Evidencia (relatos de la S5) |
|---|---|
| **Clichés** | 5–8 por relato (~1900 palabras): «me heló la sangre», «me revolvió el estómago», «nudo en el estómago», «escalofrío», «un silencio pesado», «como una mortaja». |
| **Parentescos equivocados** | La narradora (Irene, nuera de María) llama a María «mi madre» o menciona «las leyendas de mi abuela» (2 por relato en v2/v3). El elenco dice «Suegra de Irene», pero el prompt no le dice a la Voz cómo *la narradora* nombra a cada uno. |
| **Tercera persona filtrada** | Oraciones copiadas del evento en tercera persona dentro de un relato en primera: «Ricardo se sume en un silencio catatónico que Irene no se atreve a romper». |
| **Palabras inventadas / mal usadas** | «La arbolé con la manta», «el bólido» (por el caballo). |
| **Sin oficio de horror** | El prompt solo tiene «zoom sensorial» anti-relleno: no guía el ritmo según la intensidad del acto, la contención (sugerir antes que mostrar), el cierre de cada acto, ni prohíbe explicar el miedo en lugar de provocarlo. |

**Éxito:** en la evaluación, menos clichés, cero parentescos equivocados, cero oraciones de narración en tercera persona sobre la narradora, y una lectura manual que confirme mejor ritmo y tensión, **sin** perder fidelidad a los eventos ni a la graduación de la amenaza (Spec-450).

---

## 1. CAMBIOS PROPUESTOS

### 1.1 Guía de oficio en el system prompt de la Voz

Sección nueva en `voice_system_compact.md`, breve (el contexto de la Voz tiene margen: ~5000 tokens libres de 8192, medición Spec-450 T3.5):

- **Ritmo según la intensidad del acto** (`baja` / `media` / `media-alta` / `alta`, ya viene en el `narrative_context`): frases más largas y respiradas en intensidad baja; cortas y concretas en alta.
- **Contención:** sugerir antes que mostrar; el miedo se provoca con detalles concretos, no se nombra («tenía miedo», «me heló la sangre»).
- **Cierre del acto:** terminar en una imagen o un detalle inquietante, no en una reflexión que resume (salvo el acto 5, que cierra).
- **Clichés prohibidos:** lista corta y explícita (la de la tabla de arriba), con la indicación de reemplazarlos por una sensación física concreta y propia de la escena.

### 1.2 Parentescos desde la voz del narrador

Bloque determinístico **«CÓMO LLAMÁS A CADA PERSONAJE»** en el system prompt, armado desde el elenco:
- Para cada personaje: su nombre y su rol **tal como lo cargó el autor** (ej. «María — Suegra de Irene; madre de Ricardo»), precedido por la instrucción: «Sos Irene. Cuando nombres a alguien por su parentesco, usá la relación que tiene *con vos* según su rol (María es tu suegra, no tu madre)».
- El narrador sale de `narrator_config.storyteller_id` (como hoy). Sin LLM: el rol es texto libre, la instrucción le pide a la Voz leerlo desde su perspectiva.

### 1.3 Primera persona sin fugas

- Instrucción explícita: «Los EVENTOS vienen escritos en tercera persona. Contalos siempre desde vos: "Irene no se atreve" → "no me atrevo". Tu nombre solo aparece cuando otro personaje te habla».
- En el `narrative_context`, el encabezado de EVENTO dice quién narra: «EVENTO DE ESTE MOMENTO (contalo en primera persona, como {narrador})».

### 1.4 Léxico

- «Usá solo palabras que existan en el español rioplatense; si dudás de una palabra, elegí una más simple».
- Los objetos y animales se nombran como en el evento («el caballo», no «el bólido»).

---

## 2. MEDICIÓN

Script `scripts/evaluate_voice.py` (reusa el arnés de la S5: genera `el_monte_prohibido` con el perfil activo en una DB descartable, con y sin entidades) y reporta por relato y por acto:

| Métrica | Cómo | Meta |
|---|---|---|
| Clichés | Conteo de la lista prohibida (§1.1) | ≤ 1 por relato |
| Parentescos equivocados | «mi madre / mi abuela / mi mamá» cuando el personaje es suegra/suegro (según el elenco) | 0 |
| Narradora en tercera persona | Nombre del narrador fuera de diálogo (fuera de «…» / —) | 0 |
| Repetición | 4-gramas presentes en ≥ 3 actos | ≤ 2 |
| Fidelidad | Lectura manual: los eventos del Mapper aparecen, en orden | sin regresión |
| Graduación Spec-450 | Lectura manual: la entidad no se nombra antes del clímax (`insinuada`) | sin regresión |

Se generan **2 corridas por variante** (antes / después) para no confundir una mejora con la variación del modelo.

---

## BOUNDARIES

- **Siempre:** medir antes y después con el mismo arnés; los snapshots de Spec-450 se actualizan a propósito (`SNAPSHOT_UPDATE=1`) solo donde el texto del prompt cambia, y el diff se revisa.
- **Consultar antes:** cambiar parámetros del modelo (temperatura, `num_predict`) o tocar prompts de Analyst/Mapper/Journal.
- **Nunca:** llamadas LLM nuevas; cambiar de proveedor (eso es EV-2).

---

## DECISIONES (2026-09-24)

1. **Variantes:** compact **y** frontier (`voice_system_compact.md` + `system.md`); las secciones nuevas son las mismas en las dos.
2. **Clichés:** la lista propuesta en §1.1; se amplía después editando el template.
3. **Temperatura:** la evaluación suma una corrida con el prompt nuevo y `temperature: 0.5` en la Voz (override temporal por variable de entorno o perfil de evaluación, sin tocar el perfil activo). Si mejora el léxico sin empobrecer la prosa, se propone el cambio del perfil (cambio de config, con OK).
4. **Metas:** las de la tabla §2.

---

## PLAN

### Estrategia

Primero la **medición** y la línea base con el prompt de hoy (si no, no hay contra qué comparar); después los cambios de prompt con sus tests; al final la evaluación comparada y el cierre. Nada de esto cambia el esquema ni agrega llamadas LLM.

```
S0 Arnés + métricas + línea base ─▶ S1 Prompts (compact + frontier + narrative_context) ─▶ S2 Evaluación comparada ─▶ S3 Docs + deploy + DONE
```

### Decisiones técnicas

1. **Arnés en proceso, sin código de producción nuevo:** `scripts/evaluate_voice.py` corre el pipeline con la app FastAPI en proceso (como `measure_entity_prompts.py`), con el adapter real del perfil activo y una DB temporal. La temperatura de la Voz se sobrescribe **dentro del proceso del script** (`--voz-temperature 0.5` parchea `settings.role_config("voz")`), sin tocar el perfil ni agregar variables de entorno al código.
2. **Historias de la evaluación:** `input_stories/el_monte_prohibido.yaml` sin entidades y con las 2 entidades de la S5 de Spec-450 (quedan como constante del script, para que la evaluación sea reproducible).
3. **Métricas como funciones puras** en `scripts/voice_metrics.py`, con tests unitarios:
   - `cliches(text)` → conteo por expresión de la lista (la misma lista que se publica en el prompt, leída de un único lugar: `config/prompts_generation/voice_cliches.txt`).
   - `wrong_kinship(text, narrator, cast)` → «mi <parentesco>» que no corresponde: los parentescos válidos salen de los roles que dicen «<parentesco> de <narrador>» (en *El monte prohibido* nadie es madre ni abuela de Irene, así que «mi madre» cuenta como error).
   - `narrator_outside_dialogue(text, narrator)` → apariciones del nombre fuera de diálogo (líneas que arrancan con «—» o texto entre comillas).
   - `repeated_4grams(acts)` → 4-gramas presentes en ≥ 3 actos.
4. **Bloque de parentescos (§1.2):** `PromptBuilder._format_kinship(story)` arma «CÓMO LLAMÁS A CADA PERSONAJE» desde `personajes_full` y el narrador (`narrator_config.storyteller_id` → personaje, o `storyteller_name`). Placeholder `{parentescos}` en los dos templates. Sin narrador identificable → bloque vacío.
5. **Lista de clichés en un solo lugar:** `voice_cliches.txt` alimenta el placeholder `{cliches}` de los dos templates y las métricas. Agregar un cliché = una línea.
6. **Guía de oficio (§1.1) y léxico (§1.4):** texto fijo en los dos templates (`voice_system_compact.md`, `system.md`).
7. **Encabezado del evento (§1.3):** `NarrativeContextAssembler.assemble(..., narrator=...)` → «EVENTO DE ESTE MOMENTO (contalo en primera persona, como Irene; narrá EXACTAMENTE estos eventos, en orden)». Sin narrador, el encabezado de hoy. Cambia el texto para todas las historias con narrador: los snapshots de Spec-450 (`beat_reveal.json`, `pipeline_prompts.json`) se regeneran **a propósito** y el diff se revisa en el commit.
8. **Presupuesto de tokens:** se vuelve a correr `scripts/measure_entity_prompts.py`; la Voz tiene ~4800 tokens libres con 3 entidades (Spec-450 T3.5) y los agregados son del orden de 300–400.

### S0 — Arnés, métricas y línea base

- **Qué:** `voice_metrics.py` + tests; `evaluate_voice.py` (genera N corridas por variante: sin/con entidades, reporta métricas por relato y por acto, guarda los relatos en `--out`); `voice_cliches.txt`.
- **Línea base:** 2 corridas × (sin, con entidades) con el prompt de hoy (~15 min con `gemma3:12b`). Resultado en la spec.
- **Verificación:** pytest de las métricas (casos armados a mano con los ejemplos reales de la S5).

### S1 — Prompts

- **Qué:** §1.1–§1.4 en `voice_system_compact.md` y `system.md`; `_format_kinship` + `{parentescos}` + `{cliches}`; encabezado del evento con el narrador; snapshots regenerados; `measure_entity_prompts.py` de nuevo.
- **Verificación:** pytest (bloques presentes en las dos variantes; sin narrador → sin bloque y encabezado de hoy; `format()` de los dos templates sin `KeyError`; snapshot regenerado con diff revisado); lint.

### S2 — Evaluación comparada

- **Qué:** 2 corridas × (sin, con entidades) con el prompt nuevo, y 2 × con entidades con el prompt nuevo + `temperature 0.5`. Tabla antes / después / después+0.5 y lectura manual (fidelidad, graduación de Spec-450, ritmo y tensión).
- **Salida:** resultado en la spec; si 0.5 ayuda sin empobrecer la prosa, **propuesta** de cambio del perfil (con OK, commit aparte).

### S3 — Documentación, deploy y cierre

- `CLAUDE.md` (Prompt System: guía de oficio, parentescos, lista de clichés, `evaluate_voice.py`), nota en Spec-170; deploy del backend (los templates viajan en la imagen); Spec-470 → DONE.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| El modelo local ignora instrucciones largas | Guía corta y concreta; se mide. Si no alcanza, es argumento para EV-2. |
| Prohibir clichés los reemplaza por otros | La métrica cuenta la lista; la lectura manual busca reemplazos repetidos (4-gramas). |
| La variación del modelo confunde la comparación | 2 corridas por variante; se miran tendencias, no un relato. |
| Cambiar el encabezado del evento altera todas las historias | Es intencional; snapshot regenerado con diff revisado; la evaluación cubre sin y con entidades. |
| La frontier no se puede evaluar con el perfil activo | Tests de prompt; queda lista para EV-2. |


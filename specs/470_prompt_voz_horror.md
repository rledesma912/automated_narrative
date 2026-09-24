# SPEC-470: Prompt de la Voz con oficio de horror (EV-3)

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development)
**Estado:** DONE (2026-09-24) — S0–S3 completos; backend desplegado en prod
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

---

## TASKS

Formato: **Acceptance** / **Verify** / **Files**. Checkpoint por slice: lint + pytest (+ Vitest/Playwright si cambia algo que use el frontend) en verde → commit con tu OK.

### S0 — Arnés, métricas y línea base

- [x] **T0.1:** Lista de clichés. *(Nota: «escalofrío» suelto no entra —es una palabra legítima—; sí la frase hecha «un escalofrío me recorrió».)*
  - Acceptance: `config/prompts_generation/voice_cliches.txt`, una expresión por línea (la lista de §1.1), comentarios con `#`; un loader la lee (sin duplicados, en minúsculas para comparar).
  - Verify: pytest (lee la lista; ignora comentarios y líneas vacías).
  - Files: `config/prompts_generation/voice_cliches.txt`, `src/application/services/voice_cliches.py` (nuevo)
- [x] **T0.2:** Métricas.
  - Acceptance: `cliches(text)`, `wrong_kinship(text, narrator, cast)`, `narrator_outside_dialogue(text, narrator)` y `repeated_4grams(acts)` como funciones puras, con los criterios de la decisión técnica 3.
  - Verify: pytest con fragmentos reales de la S5 de Spec-450 («me heló la sangre», «¿Será que… las leyendas de mi abuela…?», «Ricardo se sume en un silencio catatónico que Irene no se atreve a romper», diálogo «—Irene, no seas supersticiosa» que **no** cuenta).
  - Files: `scripts/voice_metrics.py`, `tests/unit/scripts/test_voice_metrics.py`
- [x] **T0.3:** Arnés de evaluación.
  - Acceptance: `uv run python scripts/evaluate_voice.py --runs 2 --variants sin,con [--voz-temperature 0.5] --out <dir> --label <nombre>` genera con el perfil activo en una DB temporal, guarda cada relato y un `metrics.json`, e imprime una tabla (por relato y promedio por variante). La historia con entidades usa las 2 entidades de Spec-450 S5 (constante del script).
  - Verify: corrida con `--mock` (sin Ollama) de punta a punta en un test; corrida real en T0.4.
  - Files: `scripts/evaluate_voice.py`, `tests/unit/scripts/test_evaluate_voice.py`
- [x] **T0.4:** Línea base.
  - Acceptance: 2 corridas × (sin, con) con el prompt de hoy; tabla y observaciones en la spec.
  - **Resultado (2026-09-24, `gemma3:12b`, Voz T=0.6, ~4 min por relato):**

| Corrida | Clichés | Parentescos (candidatos) | Narradora 3ra persona | Frases repetidas | Palabras |
|---|---|---|---|---|---|
| sin #1 | 2 | 0 | 0 | 2 | 2045 |
| sin #2 | 2 | 2* | 0 | 1 | 1978 |
| con #1 | 7 | 0 | 0 | 3 | 2005 |
| con #2 | 3 | 0 | 0 | 0 | 1978 |
| **Promedio sin / con** | **2 / 5** | **1 / 0** | **0 / 0** | **1,5 / 1,5** | ~2000 |

  - Clichés más frecuentes: «me heló la sangre» (6 en 4 relatos), «me revolvió el estómago» (4).
  - \* Falsos positivos: «en casa de mi abuela», «una canción que mi abuela me enseñó» hablan de la abuela propia de Irene (fuera del elenco), no de María. **La métrica de parentescos cuenta candidatos; se revisan a mano.**
  - Error que la métrica no ve: en «con #1» Ricardo le dice a Irene «las historias de **tu** madre» (María es madre de Ricardo). Se revisa en la lectura manual.
  - Narradora en 3ra persona: 0 (todas las apariciones de «Irene» están en diálogo; métrica validada contra el texto). En esta línea base la Voz no filtró la tercera persona; se sigue midiendo.
- [x] **Checkpoint S0:** lint + pytest → commit.

### S1 — Prompts

- [x] **T1.1:** Bloque de parentescos.
  - Acceptance: `PromptBuilder._format_kinship(story)` → «CÓMO LLAMÁS A CADA PERSONAJE» con la instrucción de §1.2 y un renglón por personaje (nombre — rol), sin el narrador; narrador desde `storyteller_id`/`storyteller_name`; sin narrador identificable o sin elenco → `""`.
  - Verify: pytest (Irene narra: aparece María con «Suegra de Irene…», no aparece Irene; sin `personajes_full` → vacío).
  - Files: `src/application/services/prompt_builder.py`
- [x] **T1.2:** Templates compact y frontier.
  - Acceptance: guía de oficio (§1.1), primera persona (§1.3), léxico (§1.4), `{parentescos}` y `{cliches}` en `voice_system_compact.md` y `system.md`; `build_voice_system_compact()` y `build_voice_prompt()` los completan.
  - Verify: pytest (las dos variantes contienen guía, clichés y parentescos; `format()` sin `KeyError`).
  - Files: `config/prompts_generation/voice_system_compact.md`, `config/prompts_generation/system.md`, `src/application/services/prompt_builder.py`
- [x] **T1.3:** Encabezado del evento con el narrador.
  - Acceptance: `assemble(..., narrator=...)` usa «EVENTO DE ESTE MOMENTO (contalo en primera persona, como <narrador>; narrá EXACTAMENTE estos eventos, en orden):»; sin narrador, el de hoy. `build_narrative_context` pasa el narrador.
  - Verify: pytest del assembler (con y sin narrador).
  - Files: `src/application/services/narrative_context_assembler.py`, `src/application/services/prompt_builder.py`
- [x] **T1.4:** Snapshots y presupuesto.
  - Acceptance: `beat_reveal.json` y `pipeline_prompts.json` regenerados con `SNAPSHOT_UPDATE=1`; el diff solo muestra los textos de §1 (revisado); `measure_entity_prompts.py` sin roles fuera de margen (tabla actualizada en la spec).
  - Verify: pytest completo en verde; salida del script de medición.
  - Files: `tests/fixtures/snapshots/*.json`
- [x] **Notas de S1 (2026-09-24):**
  - **Guía compartida:** el texto de oficio, primera persona y léxico vive en `config/prompts_generation/voice_craft.md` (`{cliches}` y `{narrador}` adentro) y entra por `{guia_oficio}` en `voice_system_compact.md` y `system.md`; `PromptBuilder._voice_extras()` lo completa en los tres builders que usan esos templates (`build_voice_system_compact`, `build_voice_prompt`, `build_system_prompt`).
  - **Presentación con nombre (agregado):** la primera línea del compact decía «Sos Primera persona en pasado. Narrador: Irene. Tono: …, narrando en primera persona…» (el string `relator` entero). Ahora «Sos Irene y contás en primera persona los hechos de la historia (<relator>)»; sin narrador identificable, como antes.
  - **Snapshot:** `pipeline_prompts.json` regenerado; el diff cambia **solo** las 10 llamadas de la Voz (system + contexto); Analyst, Mapper y Journal idénticos. `beat_reveal.json` sin cambios.
  - **Tokens (T1.4, `gemma3:12b`):** la Voz pasa de 1365/1747/2371 a 1878/2304/2928 tokens (0/1/3 entidades); margen mínimo 4264 de 8192. El resto de los roles sin cambios relevantes.
- [x] **Checkpoint S1:** lint + pytest + Playwright (el arnés E2E genera con el backend) → commit.

### S2 — Evaluación comparada

- [x] **T2.1:** Prompt nuevo: 2 corridas × (sin, con).
- [x] **T2.2:** Prompt nuevo + `--voz-temperature 0.5`: 2 corridas × con entidades.
- [x] **T2.3:** Comparación y lectura manual.

**Resultado S2 (2026-09-24, `gemma3:12b`, promedios por relato; ~4 min por relato):**

| Versión | Clichés sin / con | Parentescos reales* | Narradora 3ra persona | Frases repetidas sin / con | Palabras |
|---|---|---|---|---|---|
| Antes (T 0.6) | 2 / 5 | 0 (+1 «tu madre» en diálogo) | 0 | 1,5 / 1,5 | ~2000 |
| **Después (T 0.6)** | **0,5 / 0,5** | **0** | **0** | 1 / 4 | ~2130 |
| Después, T 0.5 (solo con) | — / 1 | 1 («No era mi madre») | 0 | — / 6,5 | ~2000 |

\* Revisados a mano: los candidatos «mi abuela me enseñó» (una oración, una canción) son la abuela propia de Irene, no María. La métrica se corrigió para que «Bebé de Irene» valga como hijo/hija («la manta de mi hija» era un falso positivo).

- **Metas de §2:** clichés ≤ 1 ✔ (0,5); parentescos 0 ✔ (después de la revisión manual); narradora en 3ra persona 0 ✔; frases repetidas ≤ 2 ✘ con entidades (4), pero casi todo es el motivo de la entidad («olor a tierra mojada», «una y otra vez» del acto 4), no muletillas.
- **Lectura manual (después, con #1):** «el rostro de mi suegra» y Ricardo le dice «mamá» a María; primera persona sostenida; cierres de acto en una imagen («La rama de espinillo seguía ahí, oscura y fría contra la tela de la manta»); graduación de Spec-450 respetada (la entidad no se nombra; se la reconoce por los ojos que no parpadean en el acto 3). El modelo esquiva la lista con variantes («me heló el alma», «un nudo en la garganta»).
- **Problemas que quedan:** (1) **adelanto de manifestaciones**: en el acto 1 aparecen el camino que se deforma y los espinillos repetidos (del acto 4) — el efecto checklist de Spec-450 que v2/v3 habían corregido vuelve en esta corrida; (2) frases torpes o mal armadas («El taxi toco la puerta de barro», «Alargar la manta sobre los chiquitos, sentí algo áspero», «Rezad» en una narradora rioplatense, «pies descalzos» después de zapatos).
- **Temperatura 0.5:** no conviene — más repetición de estilo («con la voz tensa», «la mirada fija en», «gritó Ricardo con la»), un error de parentesco y más clichés. **Se mantiene 0.6** (sin cambio de perfil).
- **Conclusión:** el prompt nuevo cumple las metas de clichés, parentescos y primera persona con el modelo local. Lo que queda (adelanto de manifestaciones de la entidad y gramática) excede a esta spec: el primero es de Spec-450 (§1.1 de las guías de exposición) y el segundo es el techo del modelo local → argumento para EV-2.

### S3 — Documentación, deploy y cierre

- [x] **T3.1:** `CLAUDE.md` (Prompt System: guía de oficio, parentescos, `voice_cliches.txt`, `evaluate_voice.py`), nota en Spec-170, Spec-470 → DONE.
- [x] **T3.2:** Deploy del backend (con tu OK) y prueba rápida: una generación corta en prod no hace falta; se verifica que el contenedor tenga los templates nuevos y que la API responda.

## PENDIENTES (fuera de Spec-470)

- **Adelanto de manifestaciones de la entidad** (Spec-450): con «señales» la Voz a veces usa manifestaciones de actos posteriores (en la S2, el camino que se deforma en el acto 1). Idea: con `senales` / `manifestacion_parcial`, pasarle a la Voz 1–2 manifestaciones y no la lista completa.
- **Gramática del modelo local** («El taxi toco la puerta de barro», «Rezad» en una narradora rioplatense): techo de `gemma3:12b` → EV-2 (Voz en Anthropic), medible con `scripts/evaluate_voice.py`.
- **Métrica de parentescos:** no ve «tu madre» dicho a la narradora en un diálogo; los candidatos se siguen revisando a mano.


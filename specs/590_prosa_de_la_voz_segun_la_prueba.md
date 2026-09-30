# SPEC-590: La prosa que piden quienes la usan — oraciones completas, sin diálogo, más material y continuidad

**Fecha:** 2026-09-30
**Tipo:** SDD (Spec-Driven Development) — calidad de la prosa (Voz y Memoria)
**Estado:** CERRADA 2026-09-30 — S0–S3 implementados; S4 reducido a documentación y PR por la [Spec-600](600_rumbo_voz_frontier_y_cierre.md) (D4: la Voz pasa a Claude y la medición «después» se hace allí, local contra híbrido)
**Rama:** `feat/spec-590-prosa` (desde `development`)
**Evidencia:** [`590_anexo_prueba_usuarias.md`](590_anexo_prueba_usuarias.md) — correcciones de las beta testers sobre «NO TE DETENGAS EN EL BOSQUE».
**Extiende:** Spec-470 (oficio de la Voz), Spec-530 §8 (pipeline: Voz, Memoria, control de repetición) y Spec-560 A1/A2 (puente, final del acto anterior, regenerar sin repetir).

---

## PRINCIPIO

**Quién lee el relato (2026-09-30):** la esposa y la hija del usuario. Lo **editan** antes de pasarlo al TTS (`audiogen`, Spec-490). Para ellas: cortar lo que sobra es fácil; inventar lo que falta, no. **Mejor que sobre material a que falte.**

**Máxima del pipeline (2026-09-27):** la Voz recibe un arnés **simple y asertivo**. Esta spec **saca reglas y suma datos**: el límite no es la ventana de contexto (§1.2) sino la atención del modelo de 12b, que se dispersa con reglas y se contradice cuando dos reglas chocan. Cada cambio responde a una corrección del anexo.

**Lo que solo aparece en la prosa se detecta después y se muestra; nunca se corrige solo** (F).

---

## ALCANCE

- **Sí:** los prompts de la Voz (`outline_voice*.md`, `voice_craft.md`), la forma de contar «confesión» (`config/authoring_options.yaml`), la Memoria (`outline_journal*.md` + esquema `Memoria` + tabla `narrative_journal`), lo que arma `OutlineNarrator.voice_prompts`, la extensión (`word_range`, `num_predict` de `voz` y `journal`), el control de repetición (`repetition_check.py` + panel del relato) y las métricas (`scripts/voice_metrics.py`, `scripts/evaluate_voice.py`).
- **No:** el asistente (Consultor, Planificador, Verificador) ni la escaleta: sus prompts y su UI no cambian (ver §3, «Lo que no entra»).
- **No:** una ficha del protagonista ni ningún campo nuevo para quien escribe (D3: son muchos datos; la personalidad la pone el modelo).
- **No:** la estructura de 5 actos ni la cantidad de llamadas (siguen 10 por relato, 2 por acto regenerado).

---

## ASSUMPTIONS

1. Modelo de referencia: `gemma3:12b` (`ollama-gemma3-12b`). El perfil `anthropic-sonnet5` se usa **solo para comparar** al final (S4), con presupuesto aprobado.
2. Datos descartables (2026-09-27): el cambio de esquema de `narrative_journal` se hace en `init_db()` + `make dev-db`; en prod, con el procedimiento de siempre (export → DB nueva → import). No hay migraciones.
3. `num_ctx: 8192` alcanza (§1.2): no se toca.
4. El formato de export para el TTS (Spec-490) no cambia; sin diálogo directo, `narrative_script_formatter` simplemente tiene menos para convertir.
5. El snapshot `tests/fixtures/snapshots/pipeline_prompts.json` cambia **a propósito** (Voz y Memoria); los del asistente quedan iguales.

---

## OBJECTIVE

Que el relato salga como lo escribirían ellas:

1. **Oraciones completas y enlazadas:** con verbo conjugado y conectores («después», «entonces», «pero», «porque»), no una lista de fragmentos.
2. **Sin diálogo directo:** lo que alguien dice se cuenta («me preguntó si…», «le juré que…»).
3. **Más material:** actos más largos, con pensamientos, opiniones, gustos, manías y algún miedo de quien narra, **inventados por el modelo**, coherentes entre actos.
4. **Continuidad física:** una herida, un objeto o un cansancio del acto N sigue igual en el N+1.

**Éxito (medido en S0 y S4, §4):**
- Oraciones cortadas (§2.F), en % de las oraciones de la narración: baja al menos a la mitad respecto de la línea base.
- Diálogo directo: 0 líneas en todas las corridas.
- Palabras por relato: ≥ 1,5 × la línea base, sin que suban las frases repetidas ni los clichés.
- Continuidad: en «NO TE DETENGAS EN EL BOSQUE», la herida del oído aparece bien (o no aparece) en los actos 3–5 de todas las corridas; nunca en otro lugar del cuerpo.
- Rasgos del narrador: al menos 2 por relato y ninguna contradicción entre actos (lectura).
- Adelantos: la premisa no filtra hechos de actos posteriores (lectura: en el acto 1 no hay astas).
- **Prueba con ellas:** generan un relato nuevo en `storymaker.test` y anotan si las cuatro correcciones del anexo siguen apareciendo.

---

## 1. DIAGNÓSTICO (sobre el relato del anexo)

### 1.1 Qué causa cada corrección

| Corrección del anexo | Causa en el código |
|---|---|
| Oraciones muy cortas, sin conectores, sin verbo | `voice_craft.md`: «en intensidad alta, frases cortas y concretas»; «Terminá en una imagen». La forma de contar «confesión»: «frases que **a veces se detienen antes de decir lo peor**» → «Pero ahora… ahora estaba varado. Solo.». «ASÍ TERMINÓ EL ACTO ANTERIOR» le pasa 3 oraciones sueltas que modelan el mismo estilo. Pasa en todos los actos, también en el 1 (intensidad baja). |
| Diálogos | `outline_voice_system.md`: «Si hay diálogo, que sea breve (1 a 3 líneas)» lo **permite**. La escaleta (actos 4 y 5) y el final del autor traen las frases entre comillas y la Voz las copia. |
| Falta material y personalidad | «No inventes hechos nuevos» corta también los gestos chicos. `word_range` tope 550 palabras (y el acto 5, 280) + `num_predict: 1000` (~620 palabras). La Voz **no recibe la premisa**: «no está en buen estado físico» nunca le llegó. |
| Incongruencia (oído → muslo) | La prosa del acto 2 dice «me entraron en el oído». La **Memoria** lo resume como «Se lastima» y el estado como «herido y desorientado» (256 tokens, «2 o 3 frases»); la Voz del acto 3 eligió una herida al azar. La Memoria también inventa: «pueblo abandonado», «El camión se avería» dos veces. Mientras tanto la escaleta —confirmada por quien escribe— dice exactamente qué pasó y no le llega a la Voz. |

Hallazgo extra: **«YA USADO» le prohíbe la amenaza.** En el acto 3 decía «no repitas: ojos brillantes, susurros», que son los rasgos que la escaleta pide mostrar.

### 1.2 El espacio no es el problema (medido 2026-09-30, tokens reales de gemma3 en Ollama)

| | Tokens |
|---|---|
| Prompt completo de la Voz (sistema + acto), actos 2 y 5 | 1 491 / 1 793 |
| Salida de un acto de ~500 palabras | ~790 (≈ 1,6 tokens por palabra) |
| `num_ctx` configurado | 8 192 (gemma3 admite 131 072) |
| Libre | ~6 000 |

Los límites son nuestros (`word_range`, `num_predict`). Lo que sí tiene el 12b es que escribe menos de lo pedido y se desordena en textos largos: pedir «N palabras» le sirve poco; pedir **párrafos por evento** le sirve más. Un frontier respeta mejor extensión y estilo, pero obedecería igual las instrucciones que hoy piden cortar las frases: primero se corrigen las instrucciones.

---

## 2. CAMBIOS

### A — Oraciones completas (oficio y forma de contar)

- **`voice_craft.md` reescrito como narración oral:** oraciones completas con verbo conjugado; conectores que enlazan lo que pasa; quien narra dice **por qué** hace lo que hace. El ritmo se marca con el **largo de los párrafos** (más cortos cuando sube la tensión), no cortando las oraciones. Se van: «frases cortas y concretas» y «terminá en una imagen» (queda: cerrar el acto con algo concreto que inquiete, contado en una oración completa). Se mantienen: sugerir antes de nombrar el miedo, clichés prohibidos, primera persona, léxico rioplatense.
- **Un ejemplo corto** de antes/después en el propio `voice_craft.md`, con la forma del del anexo pero de otra escena (una puerta abierta y un olor a quemado): el del chasquido es de la historia de prueba y contaminaría la medición. Un ejemplo pesa más que una regla en el 12b; se vigila en S4 que no lo copie textual.
- **«Confesión»** (`authoring_options.yaml`): sin «frases que se detienen». Queda el tono bajo, íntimo, de quien carga algo. Se revisan las otras tres formas de contar para que ninguna pida fragmentar (hoy «caso» pide «alternar cortas y largas»: se deja, sin «cortas» como fragmento).
- **Una sola instrucción por tema:** el estilo solo en `voice_craft.md`; `outline_voice_system.md` no repite ni contradice.

### B — Sin diálogo directo

- En `outline_voice_system.md`, en lugar de «Si hay diálogo…»: **«Nunca escribas diálogo: ni rayas ni comillas. Lo que alguien dice lo contás vos: "me preguntó si…", "le contesté que…", "me aseguró que…". También cuando los EVENTOS o el final traen una frase entre comillas: contala con tus palabras sin cambiar lo que significa.»**
- En `voice_craft.md` sale «Tu nombre solo aparece cuando otro personaje te habla» (sin diálogo pierde sentido); queda «tu nombre no aparece en lo que narrás».
- El final que escribió quien arma la historia sigue mandando (Spec-530 S2); solo cambia la forma: indirecta.

### C — Personalidad: la pone el modelo (sin datos nuevos)

- **La Voz** (sistema), en lugar de «no inventes hechos nuevos»: «Podés sumar lo que piensa y opina quien narra, sus gustos, manías y algún miedo o inseguridad, y gestos chicos (comer algo, prender la radio) que no cambien lo que pasa. Inventalos vos. No inventes hechos que cambien la historia ni personajes que no estén EN ESCENA.»
- **La Memoria sostiene lo inventado:** campo nuevo `asi_es` («cómo es quien narra»: gustos, manías, miedos, opiniones que **aparecieron en el texto**, hasta 8, acumulados como `used_motifs`). La Voz de los actos siguientes lo recibe como **«ASÍ ES {NARRADOR} (mantenelo; podés sumar)»**.
- Si quien escribe quiere cambiar algo, edita el relato (como hoy); no hay pantalla nueva.

### D — Más material

- `word_range`: `WORDS_PER_EVENT` 110 → 170, `MIN_WORDS` 250 → 400, `MAX_WORDS` 550 → 900; desenlace (`LAST_ACT_WORDS`) 150–280 → 250–450.
- La extensión se pide **en párrafos y en palabras**: «Contá cada evento en uno o dos párrafos; el momento más fuerte, en más. EXTENSIÓN: entre N y M palabras.»
- `num_predict` de `voz`: 1000 → 1800 en `ollama-gemma3-12b` (900 palabras ≈ 1 450 tokens + margen); en `anthropic-sonnet5` pasa de 2000 a 2500 por margen. `journal`: `remember()` ya pide `min_predict=700`; sube a 900 por los campos nuevos (el `num_predict: 256` del perfil queda pisado, como hoy).
- `estimated_seconds.full_generation` y `regenerate_voz` se actualizan con lo medido en S4 (≈ +1 a 1,5 min por relato).

### E — Continuidad desde la escaleta + el cuerpo

- **«LO QUE YA PASÓ» sale de la escaleta:** los EVENTOS de los actos anteriores (`act_outline.events`), confirmados por quien escribe, en lugar del resumen de la Memoria. La Memoria sigue guardando sus `hechos` (los usan el panel y `/debug`), pero no alimenta a la Voz.
- **Campo nuevo `cuerpo` en la Memoria:** «cómo quedó el cuerpo de quien narra y qué lleva encima: heridas **con el lugar exacto**, cansancio, ropa, objetos. Conservá lo del acto anterior salvo que el texto diga que cambió.» La Voz lo recibe como **«CÓMO ESTÁ {NARRADOR} AHORA (no lo contradigas)»**. Reemplaza a la línea «Estado:» (el `estado` actual —dónde está y cómo se siente— queda dentro de esa sección).
- Regenerar un acto (Spec-560 A2) usa lo mismo: escaleta de los actos anteriores + memoria del acto anterior.

### Lo que le llega a la Voz (además de A–E)

1. **La premisa** (`direction.premise`, o la sinopsis en las importadas) como **«LA HISTORIA, PARA QUE CONOZCAS A {NARRADOR} Y SU MUNDO (no cuentes nada de acá que no esté en los EVENTOS de este acto)»**. Riesgo: adelantos; se mide en S4.
2. **«YA USADO» filtrado:** se saca todo motivo cuyas palabras con contenido (> 3 letras, normalizadas) estén en los EVENTOS del acto o en la ficha de la amenaza (nombre, descripción, manifestaciones). Determinístico, en `OutlineNarrator`.
3. **«ASÍ TERMINÓ EL ACTO ANTERIOR»:** el **último párrafo** completo en lugar de 3 oraciones (tope ~120 palabras; si el párrafo es más largo, sus últimas oraciones hasta ese tope).

Presupuesto: +~1 200 tokens de escaleta en el acto 5 y +~300 del resto. El prompt más largo queda ≈ 3 300 tokens; con 1 800 de salida, ~5 100 de 8 192.

### F — Detectar después (se muestra, no corrige)

En `repetition_check.py` (y reusado por `voice_metrics.py`), dos hallazgos nuevos por acto en `ActRepetition`:

- **`cut_sentences`** — «oraciones cortadas»: oraciones sin verbo conjugado o de menos de 5 palabras. Se **avisa** cuando llegan al 25 % de las oraciones del acto (`too_cut`): un fragmento suelto usado a propósito no es aviso. Heurística sin dependencias nuevas: terminaciones verbales del español (pretérito, imperfecto, presente, condicional, futuro) + una lista corta de irregulares (`era`, `fue`, `hay`, `vi`, `dijo`, `estaba`…); gerundios e infinitivos no cuentan como verbo conjugado. Se muestran hasta 3 ejemplos y el total.
- **`dialogue`** — líneas de diálogo directo (raya o guion inicial, o texto entre comillas de más de 3 palabras).

Contrato de la heurística (test): las 5 oraciones del anexo que ellas marcaron («El sonido de mis pies golpeando la tierra.», «El sabor metálico de la sangre en mi boca.», «Un sonido.», «Más cerca.», «Solo.») **se detectan**; sus reescrituras («Solo escuchaba el sonido de mis pies golpeando la tierra.», «Pude sentir el sabor metálico de la sangre en mi boca.», el párrafo del chasquido) **no**, salvo su cierre «Esta vez más cerca de mí.», que no tiene verbo: un fragmento suelto usado a propósito está bien; lo que molesta es la proporción. Por eso el criterio de éxito se mide en **% de oraciones cortadas**, no en cero.

- Panel del relato (`relato_panel.ejs`), en tono coloquial (Spec-580): «Oraciones cortadas: 12 (por ejemplo: «Más cerca.»)» y «Diálogo: 2 líneas». Con `sin-jerga` en verde.
- Al regenerar un acto, «EN LA VERSIÓN ANTERIOR DE ESTE ACTO PASÓ ESTO» suma «tenía N oraciones cortadas» y «tenía diálogo» cuando corresponda (`last_version_findings`).

---

## 3. LO QUE NO ENTRA

- **Pasar el diálogo a indirecto en el Planificador** (que la escaleta ya no traiga comillas): solo si en S4 la Voz sigue copiando comillas.
- **Ficha del protagonista** para quien escribe (descartado, D3).
- **Corregir sola** la prosa (reintentar si hay oraciones cortadas o diálogo): va contra la máxima; F solo muestra.
- **Cambiar de modelo:** la comparación con Sonnet es medición, no cambio de perfil activo.

---

## 4. CÓMO SE MIDE

- **Historia de prueba:** «NO TE DETENGAS EN EL BOSQUE» exportada de prod con su escaleta (`input_stories/no_te_detengas_en_el_bosque.yaml`). Con la escaleta fija, las corridas comparan **solo la Voz y la Memoria**.
- `scripts/evaluate_voice.py` suma `--input <yaml>` (hoy fija «El monte prohibido») y las métricas nuevas: oraciones cortadas por acto, líneas de diálogo, palabras por acto.
- **Línea base (S0):** código actual, gemma3:12b, 2 corridas. **Después (S4):** mismo protocolo. Se guarda en `scripts/research/590/{base,despues}/`.
- **Lectura** (por el usuario y por Claude): continuidad de la herida, rasgos del narrador y contradicciones, adelantos de la premisa, ejemplo del oficio copiado textual.
- **Frontier (S4, opcional):** 1 corrida con `--profile anthropic-sonnet5`, primero sin `--yes` (estima el costo) y con OK del usuario.

---

## 5. PLAN

Cinco slices, en este orden: primero se mide (S0) y se construye el instrumento que muestra el problema (S1), después se cambia la forma de escribir (S2) y lo que recibe la Voz (S3), y se vuelve a medir (S4). S1 va antes que S2/S3 porque sus contadores son los que usa la medición.

| Slice | Toca | Snapshot de prompts | DB | Dev |
|---|---|---|---|---|
| S0 | `scripts/`, `input_stories/` | igual | — | — |
| S1 | `repetition_check.py`, `narrative_router`, `outline_narrator._avoid`, `relato_panel.ejs`, `story.service.ts` | igual | — | recarga sola |
| S2 | `voice_craft.md`, `outline_voice*.md`, `authoring_options.yaml`, `outline_narrator.word_range`, `llm_core_definitions.yaml` | **cambia** (Voz) | — | recarga sola |
| S3 | `outline_narrator` (Voz + Memoria), `outline_journal*.md`, `NarrativeJournal`, `narrative_journal`, `story_repository` | **cambia** (Voz y Memoria) | **columnas nuevas** | `make dev-db` |
| S4 | `scripts/research/590/`, `estimated_seconds`, `CLAUDE.md`, esta spec | igual | — | — |

**Diseño de los puntos con más código:**

- **Heurística de F** (`repetition_check.py`): `split_sentences(text)` (reusa el corte de `_ending_of`: `.`, `!`, `?`, `…`, `»`), `has_finite_verb(words)` y `cut_sentences(text) -> list[str]`. Verbo conjugado = alguna palabra normalizada que termina en una desinencia finita (`-é`, `-ó`, `-aba(n|s)?`, `-ía(n|s)?`, `-aron`, `-ieron`, `-amos`, `-emos`, `-imos`, `-aría`, `-ería`, `-iría`, `-ará`/`-erá`/`-irá`…, presente `-o`/`-a`/`-e`/`-an`/`-en` **solo** si la palabra anterior es un pronombre átono o de sujeto: `me`, `te`, `se`, `le`, `lo`, `la`, `nos`, `yo`, `él`, `ella`, `no`) o está en `_IRREGULAR` (`es`, `era`, `fue`, `hay`, `había`, `hubo`, `está`, `estaba`, `estuvo`, `vi`, `dijo`, `dije`, `pude`, `puso`, `tuve`, `tenía`, `hice`, `hizo`, `fui`, `iba`, `sé`, `sabía`, `quería`, `podía`, `debía`…). Oración cortada = menos de 5 palabras **o** sin verbo conjugado. Los falsos positivos de sustantivos en `-ía`/`-aba` se aceptan (es un aviso). `dialogue_lines(text)` = líneas que arrancan con raya o guion + tramos entre comillas («», “”, "") de más de 3 palabras. `ActRepetition` suma `cut_sentences: list[str]` (hasta 3 ejemplos), `cut_count: int` y `dialogue: int`.
- **«Lo que ya pasó»** (`OutlineNarrator._already_happened(story, act)`): por cada acto anterior de `story.outline`, «Acto N: » + sus eventos unidos por espacio; si la historia no tiene escaleta para esos actos (no debería pasar: generar arma la escaleta antes), cae a `memory.last_events` como hoy.
- **«Ya usado» filtrado** (`_motifs_for(story, act, motifs)`): palabras con contenido (> 3 letras, `workshop_rules.normalize`) de los EVENTOS del acto + nombre, descripción y manifestaciones de las entidades; un motivo sale si **todas** sus palabras con contenido están en ese conjunto.
- **Último párrafo** (`_ending_of`): parte `previous_text` por líneas en blanco, toma el último párrafo no vacío; si pasa de 120 palabras, sus últimas oraciones hasta 120.
- **Memoria**: `Memoria` suma `cuerpo: str` y `asi_es: list[str]`; `remember()` le pasa al prompt la memoria anterior **completa** (hechos, cuerpo, así es) para que conserve lo físico y no repita rasgos; `NarrativeJournal` suma `body_state: str = ""` y `narrator_traits: list[str] = []` (acumulado con `merge_motifs`, tope 12); tabla `narrative_journal` suma `body_state TEXT DEFAULT ''` y `narrator_traits TEXT DEFAULT '[]'`.
- **Sin cambios en los casos de uso:** `GenerateStoryUseCase` y `RegenerateBeatVozUseCase` ya le pasan a `voice_prompts` la historia (con su escaleta), la memoria del acto anterior y el texto anterior.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Actos más largos → más repetición entre actos | «YA USADO» sigue; F y las frases repetidas se miden en S4; si suben, se baja `MAX_WORDS`. |
| La premisa hace que la Voz adelante hechos | Instrucción explícita + lectura en S4; si filtra, se pasa solo la primera oración de la premisa o se saca. |
| El permiso de «gestos chicos» deriva en giros de trama (ya pasó: «sombra en el copiloto» del acto 5) | La frase lo acota («que no cambien lo que pasa»); lectura en S4. |
| La heurística de verbos da falsos positivos | Es un aviso con ejemplos, no un bloqueo; el contrato del anexo fija lo mínimo. |
| gemma no llega a la extensión pedida | Se mide; el pedido en párrafos es la palanca; si no alcanza, queda como dato para la comparación con el frontier. |
| El 12b copia textual el ejemplo del oficio | Se busca en S4; si aparece, se saca el ejemplo. |

---

## 6. DECISIONES

| # | Decisión | Fecha |
|---|---|---|
| D1 | Revisar la extensión (A/D): el límite es nuestro, no la ventana; se sube con pedido en párrafos. | 2026-09-30 |
| D2 | Sin diálogo directo, **siempre** y para todas las historias (B). | 2026-09-30 |
| D3 | Sin ficha del protagonista: «son muchos datos» (si no, es más fácil un chat con una IA frontier). La personalidad la inventa el modelo y la Memoria la sostiene (C). | 2026-09-30 |
| D4 | Actos ~60 % más largos aunque el relato tarde ~1 min más (D). | 2026-09-30 |
| D5 | «Lo que ya pasó» desde la escaleta + el cuerpo en la Memoria (E). | 2026-09-30 |
| D6 | Detectar oraciones cortadas y diálogo, mostrar sin corregir (F). | 2026-09-30 |
| D7 | Sumar datos a la Voz (premisa, «ya usado» filtrado, último párrafo) y sacar reglas que se contradicen. | 2026-09-30 |

---

## 7. RESULTADOS

### S0 — Línea base · ✅ 2026-09-30

`base` (gemma3:12b, Voz T=0,6, «NO TE DETENGAS EN EL BOSQUE» con su escaleta fija, 2 corridas; relatos en `scripts/research/590/base/`). Referencia: el relato que leyeron ellas (prod), medido con las mismas métricas.

| | Palabras | Oraciones cortadas | Diálogo (fragmentos) | Frases repetidas | Clichés | Narrador en 3.ª |
|---|---|---|---|---|---|---|
| Relato del anexo (prod) | 2 206 | 52 % | 12 | 6 | 0 | 0 |
| `base` #1 | 2 009 | 51 % | 12 | 2 | 2 | 0 |
| `base` #2 | 1 968 | 55 % | 15 | 1 | 0 | 1 |
| **`base` promedio** | **1 989** | **53 %** | **13,5** | **1,5** | **1,0** | **0,5** |

- **Oraciones cortadas por acto** (#1 / #2): 56/48 · 57/67 · 51/51 · 35/50 · 62/54 %. Pasa en todos los actos, también en el 1 (tensión baja): confirma que no depende de la intensidad sino del estilo que se le pide.
- **Diálogo:** se concentra en los actos 4 y 5 (6–9 y 4–5 fragmentos), justo donde la escaleta y el final traen frases entre comillas.
- **Extensión:** los actos 2–4 quedan entre 400 y 475 palabras (tope 550) y el 5 entre 214 y 267 (tope 280).
- **Continuidad de la herida:** en estas dos corridas no saltó de lugar (#1 la retoma como «el golpe en la oreja» y «una mota de vidrio»; #2, como «un zumbido en el oído»). El error del anexo es **intermitente**; se sigue leyendo en S4.
- **Objetivo de S4** (criterios de éxito): oraciones cortadas ≤ 26 %, diálogo 0, palabras ≥ 2 980, frases repetidas y clichés sin subir.

### S2 — Control intermedio (1 relato en dev, sin la Memoria nueva) · 2026-09-30

Relato `90a9ae38-…` generado en `storymaker.test` con la historia del bosque (gemma3:12b, 288 s).

| | Palabras | Oraciones cortadas | Diálogo | Frases repetidas | Clichés |
|---|---|---|---|---|---|
| `base` promedio | 1 989 | 53 % | 13,5 | 1,5 | 1,0 |
| S2 (1 relato) | **3 268** | **17 %** | **3** | **0** | 2 |

- Por acto: 718 / 686 / 538 / 879 / 432 palabras; cortadas 14 / 27 / 18 / 5 / 24 %.
- **Diálogo que queda:** las frases que la escaleta y el final traen entre comillas («Entonces no tenemos de qué preocuparnos», «Entonces todavía no salieron del bosque») y un «¿Está todo bien?» del acto 5. El resto del acto 4 pasó a indirecto («Me preguntó si había visto cuántos eran»).
- **Personalidad sin datos cargados:** café frío de la térmica, «me pongo nervioso si llego tarde… es una manía», fuma para pensar, se muerde el labio cuando está nervioso, piensa en «mi vieja». El cigarrillo aparece en los actos 1, 2 y 3 (coherente, sin la Memoria nueva).
- **Para S3/S4:** la herida del oído no se retoma después del acto 2; el acto 4 cierra en presente («Ahora estoy aquí…») y suma un hecho que no está en la escaleta (la radio se apaga); 2 clichés («me heló la sangre», «como una mortaja»).

### S3 — Control en dev (memoria nueva) · 2026-09-30

Dos relatos en `storymaker.test` con la historia del bosque (gemma3:12b): el primero con la premisa completa (301 s) y el segundo con solo su primera oración (267 s).

| | Palabras | Oraciones cortadas | Diálogo | Frases repetidas | Clichés |
|---|---|---|---|---|---|
| S2 (1 relato) | 3 268 | 17 % | 3 | 0 | 2 |
| S3, premisa completa | 3 306 | 13 % | 15 | 2 | 3 |
| S3, primera oración | 3 190 | 15 % | 10 | 5 | 3 |

- **La premisa completa adelantaba hechos:** con ella, en los actos 1 y 2 ya había «astas» y «ojos brillantes» (las astas son del acto 3). Se aplicó la mitigación de §9: pasa **solo la primera oración**. Con eso el acto 1 cierra con «una silueta… oscura y difusa», las astas aparecen recién en el acto 3.
- **Herida del oído:** con la premisa completa la Voz se salteó el hecho (7.º de 7 del acto 2). Con la primera oración lo cuenta y la retoma en el acto 3 («me doliera la oreja por los cristales», «el corte de la oreja»); en los actos 4 y 5 no vuelve.
- **Rasgos:** se sostienen (ciática, termo, radio, rezarle a la Virgen en el primero; cigarrillo, «mi viejo» y los paseos por el campo en el segundo). En el segundo hay una contradicción: la radio «siempre prendida» (acto 1) y «apagada, como siempre» (acto 2). El recuerdo del viejo aparece en los 5 actos y «un tango viejo que sonaba como de otro mundo» se repite en los actos 4 y 5.
- **Diálogo:** se concentra en el acto 4 (12 y 6 fragmentos), donde la escaleta trae las preguntas del almacenero entre comillas; en el segundo relato sale como diálogo con raya. Queda para S4.
- **Hecho inventado al cierre:** el acto 4 termina con «Alguien golpeó la puerta del almacén.» y el acto 5 cierra copiando esa misma oración.

### S4 — Después · no se mide acá

La [Spec-600](600_rumbo_voz_frontier_y_cierre.md) decidió (D1, D4) llevar la Voz a Claude Sonnet 5.5 y dejar de ajustar el 12b. La medición «después» se hace una sola vez en su S1, con la misma historia y las mismas métricas, y compara la base local (§7, S0 y S3) contra el perfil híbrido. El diálogo del acto 4 (preguntas entre comillas de la escaleta) queda sin ajuste: se vuelve a mirar con la Voz en Claude.

---

## 8. TASKS

Cada slice cierra con: `make lint`, `make test`, `cd frontend && npm test`, `npx playwright test` en verde (output filtrado), `make dev-status` en verde y la URL de `storymaker.test` con qué mirar. Commit por slice en `feat/spec-590-prosa`.

### S0 — Línea base · ✅ 2026-09-30
- [x] T0.1 Copiar `data/prod/stories.db` al scratchpad y, contra la copia (`DATABASE_URL=…`), `export-yaml 8385f6ea-…` → `input_stories/no_te_detengas_en_el_bosque.yaml` (dirección, taller y escaleta). Nunca apuntar el CLI a la DB de prod directamente.
- [x] T0.2 `scripts/evaluate_voice.py`: `--input <yaml>` (default: «El monte prohibido»); con `--input` las entidades salen del YAML y no se usan las variantes `sin,con` fijas del monte. La escaleta del YAML se respeta (no se re-planifica). Test en `tests/unit/scripts/test_evaluate_voice.py`.
- [x] T0.3 Heurística de F en `repetition_check.py` (`split_sentences`, `has_finite_verb`, `cut_sentences`, `dialogue_lines`) con el **contrato del anexo** en `tests/unit/application/test_repetition_check.py`: detecta «El sonido de mis pies golpeando la tierra.», «El sabor metálico de la sangre en mi boca.», «Un sonido.», «Más cerca.», «Solo.»; no detecta sus reescrituras (salvo «Esta vez más cerca de mí.», ver §2.F). Diálogo: detecta `“¿Viste cuántos eran?” preguntó` y una línea con raya; no detecta «me preguntó si había visto cuántos eran».
- [x] T0.4 `scripts/voice_metrics.py`: `cut_sentences` (total y por acto), `dialogue_lines` y palabras por acto en `evaluate()`, importando de `repetition_check`. Test en `test_voice_metrics.py`.
- [x] T0.5 Correr `evaluate_voice.py --input input_stories/no_te_detengas_en_el_bosque.yaml --label base --runs 2 --out scripts/research/590` (→ `scripts/research/590/base/`) con gemma3:12b. Anotar en §7: oraciones cortadas por acto, diálogo, palabras, frases repetidas, clichés, y la lectura de la herida del oído.

### S1 — F: mostrar oraciones cortadas y diálogo · ✅ 2026-09-30
- [x] T1.1 `ActRepetition` + `check()`: `cut_sentences` (hasta 3), `cut_count`, `cut_pct`, `too_cut` (desde el 25 %: un fragmento suelto no es aviso) y `dialogue`; `has_findings()` lo usa también `last_version_findings`. Test.
- [x] T1.2 `GET /generated-narratives/{id}/repetition` los devuelve (test del router en `tests/integration/`).
- [x] T1.3 `story.service.ts` (tipo) y `relato_panel.ejs`: en el resumen del acto, «N oraciones cortadas» y «diálogo: N líneas»; en el detalle, los ejemplos («Oración cortada: «Más cerca.»»). Tono coloquial; `sin-jerga`, `gramatica-visual` y `no-hardcoded-colors` en verde. Test de vista en `relatos.view.test.ts`.
- [x] T1.4 `_avoid()` (regenerar un acto): «- Tenía N oraciones cortadas (por ejemplo: «…»): escribí oraciones completas» y «- Tenía diálogo: contá lo que dicen, sin rayas ni comillas». Test en `test_outline_narrator.py`. El snapshot no cambia (sin versión anterior no aparece).
- [x] T1.5 Validar en dev: un relato existente de `storymaker.test` muestra los contadores nuevos en su panel.

### S2 — A + B + D: la forma de escribir · ✅ 2026-09-30
- [x] T2.1 `voice_craft.md` reescrito (A): narración oral con oraciones completas y conectores; ritmo por largo de párrafo; cierre concreto en oración completa; se mantienen sugerir, clichés, primera persona y léxico; ejemplo antes/después **nuevo** con la misma forma que el del anexo (una puerta abierta: el del chasquido es de la historia de prueba y contaminaría la medición); «tu nombre no aparece en lo que narrás».
- [x] T2.2 `outline_voice_system.md`: regla de diálogo indirecto (B) en lugar de «Si hay diálogo…»; permiso de rasgos y gestos chicos (C) en lugar de «no inventes hechos nuevos»; nada de estilo acá (vive en `voice_craft.md`).
- [x] T2.3 `authoring_options.yaml`: «confesión» sin «frases que se detienen»; «caso» sin «cortas» como fragmento. `test_authoring_options` (o el que cubra el catálogo) en verde.
- [x] T2.4 `outline_voice.md`: «Contá cada evento en uno o dos párrafos; el momento más fuerte, en más.» antes de EXTENSIÓN.
- [x] T2.5 `word_range`: 170 / 400 / 900 y desenlace 250–450; tests de `word_range` actualizados.
- [x] T2.6 `llm_core_definitions.yaml`: `voz.num_predict` 1000 → 1800 (gemma) y 2000 → 2500 (Sonnet); `remember()` `min_predict` 700 → 900.
- [x] T2.7 `SNAPSHOT_UPDATE=1` y revisar el diff: solo cambian los prompts de la Voz. Commit con el diff explicado.
- [x] T2.8 Validar en dev: generar un relato en `storymaker.test` (gemma, ~4–5 min) y mirar el panel: menos oraciones cortadas, sin diálogo.

### S3 — C + E + lo que le llega a la Voz · ✅ 2026-09-30
- [x] T3.1 Esquema: `NarrativeJournal.body_state` / `narrator_traits`; columnas en `init_db()`; `save_journal` / `get_journal` en `story_repository.py`; `is_empty()` las considera. Tests: `test_models.py`, `test_db_connection.py`, repo. `make dev-db` (con `ARGS=--yes` si hace falta).
- [x] T3.2 Memoria: `Memoria.cuerpo` y `Memoria.asi_es`; `outline_journal.md` pide los dos campos y recibe la memoria anterior completa; `outline_journal_system.md` sin cambios de fondo; `mock_structured.py` responde los campos nuevos. Test: el cuerpo del acto anterior llega al prompt de la Memoria; los rasgos se acumulan sin duplicados (tope 12).
- [x] T3.3 Voz: `_already_happened()` desde la escaleta (con caída a `last_events`); sección «CÓMO ESTÁ {NARRADOR} AHORA (no lo contradigas)» con `body_state` + `estado`; «ASÍ ES {NARRADOR} (mantenelo; podés sumar)» cuando hay rasgos; se va la línea «Estado:». Tests en `test_outline_narrator.py` (incluye el caso del vidrio en el oído: el cuerpo del acto 2 aparece en el prompt del acto 3).
- [x] T3.4 Premisa: «LA HISTORIA, PARA QUE CONOZCAS A {NARRADOR} Y SU MUNDO (…)» desde `direction.premise` o `sinopsis`; sin premisa, no hay sección. Test. **Solo la primera oración** (la premisa completa adelantaba hechos, §7).
- [x] T3.5 `_motifs_for()`: «ya usado» sin los motivos que están en los eventos del acto o en la ficha de la amenaza. Test con «ojos brillantes» y «susurros».
- [x] T3.6 `_ending_of()`: último párrafo, tope 120 palabras. Test.
- [x] T3.7 Regenerar un acto: test en `test_regenerate_beat_voz_use_case.py` que verifique «lo que ya pasó» desde la escaleta y el cuerpo de la memoria del acto anterior.
- [x] T3.8 `SNAPSHOT_UPDATE=1` y revisar el diff: Voz y Memoria; asistente igual. Medir el prompt más largo del snapshot (acto 5) contra el presupuesto de §2 (≤ ~3 300 tokens).
- [x] T3.9 Validar en dev: `make dev-db`, importar la historia de prueba (`import-yaml`), generar y leer continuidad y rasgos.

### S4 — Documentación y PR (medición en la Spec-600) · ✅ 2026-09-30
- [→] T4.1 (pasa a Spec-600 S1) `evaluate_voice.py … --label despues-590 --runs 2 --out scripts/research/590/despues` (gemma). Comparar con la base contra los criterios de éxito; lectura: herida, rasgos y contradicciones, adelantos de la premisa, ejemplo copiado. Resultados en §7.
- [→] T4.2 (pasa a Spec-600 S1/S2) Si algún riesgo se dio (§5, Riesgos): ajuste dentro del slice y nueva corrida.
- [→] T4.3 (pasa a Spec-600 S1) (Opcional, con OK) Sonnet: `--profile anthropic-sonnet5` sin `--yes` para estimar; con OK, 1 corrida. Resultados en §7.
- [x] T4.4 `estimated_seconds` (`full_generation`, `regenerate_voz`) con lo medido: `full_generation` 210 → 285 (268 y 302 s en dev); `regenerate_voz` sin corridas medidas, queda igual.
- [x] T4.5 `CLAUDE.md`: qué recibe la Voz (premisa, lo que ya pasó desde la escaleta, cómo está, así es, último párrafo, sin diálogo), la Memoria (`cuerpo`, `asi_es`) y el control de repetición (oraciones cortadas, diálogo); tabla `narrative_journal`.
- [x] T4.6 PR a `development`. La prueba con ellas y el pase a prod quedan en la Spec-600 S3 (con la Voz en Claude; DB nueva por el cambio de esquema, datos descartables).

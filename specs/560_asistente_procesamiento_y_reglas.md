# SPEC-560: Asistente — procesamiento y reglas

**Fecha:** 2026-09-27
**Tipo:** SDD (Spec-Driven Development) — calidad del pipeline del asistente
**Estado:** IMPLEMENT — SPECIFY, PLAN y TASKS aprobados (2026-09-27); plan y tareas conjuntos con la Spec-570
**Rama:** `feat/analisis-asistente-ui-logica`
**Extiende:** Spec-530 (asistente, escaleta y pipeline del relato). La UI del asistente va en Spec-550.

---

## PRINCIPIO

**Máxima del pipeline (2026-09-27):** la Voz recibe un arnés **simple y asertivo**: la escaleta del acto, la memoria y listas cortas de «no repetir»; nunca reglas de continuidad para resolver mientras escribe. Lo conceptual —continuidad, tiempo, lugares, personajes, qué se revela— se resuelve **antes**, en la escaleta: análisis de la IA (Consultor, Planificador, Verificador) y confirmación del autor en la UI (taller y escaleta). Lo que solo aparece en la prosa (repeticiones, clichés, nombres inventados) se **detecta después** y se muestra; **nunca se corrige solo**. Cada campo o chequeo nuevo tiene que prevenir un error que se vio de verdad (para no volver al formulario gigante).

Todas las propuestas de esta spec se juzgan contra este principio.

---

## ASSUMPTIONS

1. Los hallazgos salen de la primera generación con esta versión («La presencia del colectivo», en dev, con `gemma3:12b`).
2. El pipeline es el de Spec-530: Planificador → Verificador → por acto, Voz (`outline_voice*.md`) + Memoria (`outline_journal*.md`). La Voz no ve la prosa de los otros actos: solo la escaleta del acto y la memoria acumulada.
3. Cada cambio de prompt se mide con `scripts/evaluate_voice.py` antes y después, y cambia el snapshot de prompts a propósito (`SNAPSHOT_UPDATE=1`).
4. Cambios de esquema de la DB: sin migraciones; se recrea la DB (dev y prod). **Datos (2026-09-27):** etapa de desarrollo: las historias de prod son descartables. No se valida ni se migra lo que hay en prod; ante un cambio de esquema o de semántica, se recrea la DB.

---

## OBJECTIVE

Que el relato salga **hilado** (sin saltos entre actos), **sin repeticiones** y con **todos los puntos narrativos cubiertos**, y que cada campo del asistente tenga un propósito claro para el autor.

---

## 1. TEMAS

### A1 — Salto entre actos: el Acto 2 no cuenta cómo se llegó desde el Acto 1 · **propuesta a decidir**

**Lo que ve el usuario:** el Acto 2 arranca con «La terminal estaba vacía», sin contar cómo se pasó del final del Acto 1 a ese momento. Propone un campo o una pregunta sobre qué ocurre entre acto y acto, incluso cuánto tiempo pasa.

**Qué recibe hoy la Voz para empezar un acto** (`OutlineNarrator.voice_prompts`, `outline_voice.md`):
- «LO QUE YA PASÓ (no lo vuelvas a contar)»: la memoria, 2–3 frases de **hechos** por acto anterior, y el **estado** del protagonista al final del acto anterior (una frase).
- Los hechos del acto, «AL TERMINAR EL ACTO» (`change_to`) y el escenario.
- **No recibe** «cómo empieza el acto» (`change_from`): el Planificador lo escribe, pero la Voz nunca lo ve.
- **No recibe** cuánto tiempo pasó ni cómo se llegó al lugar: no existe en la escaleta.
- **No recibe** cómo terminó la prosa del acto anterior (su último párrafo): la memoria es un resumen de hechos, no el tono ni la última imagen.
- La instrucción «no lo vuelvas a contar» empuja a saltar directo a los hechos nuevos, sin puente.

**Propuesta:**
1. **Puente en la escaleta** (actos 2–5): «**Cómo llega acá**» — cuánto tiempo pasó y qué pasó entre el final del acto anterior y el primer hecho de este («Esa misma noche, después de dejar el micro en el galpón, José vuelve caminando a la terminal»). Lo propone el Planificador; el autor lo edita.
   - **Opción a (sin cambio de esquema, recomendada):** reusar `change_from` («cómo está la situación al empezar»), que hoy nadie usa en la Voz: el Planificador lo escribe como puente (tiempo + cómo llega) y la UI lo muestra como «Cómo llega acá».
   - **Opción b:** campos nuevos (`bridge`, `time_elapsed`) en `act_outline`: más explícito, pero cambia el esquema (export/import en prod).
2. **La Voz recibe el puente** en una sección «CÓMO SE LLEGA A ESTE ACTO» con la instrucción de **abrir el acto contándolo en pocas líneas** antes de los hechos.
3. **La Voz recibe el final del acto anterior**: sus últimas 2–3 oraciones, textuales («ASÍ TERMINÓ EL ACTO ANTERIOR — seguí desde acá, sin repetirlo»), para continuar la voz y la imagen. Sin llamadas extra al LLM.
4. **El Verificador controla la continuidad:** regla (actos 2–5 sin puente → aviso) y chequeo de la IA («el acto empieza en un lugar o momento que no se explica desde el final del anterior»).

**Costo:** 0 llamadas extra; prompts de la Voz y del Planificador algo más largos.

### A2 — Al regenerar un acto, ¿la Voz sabe qué frases no repetir? · **no; propuesta a decidir**

**Lo que ve el usuario:** el panel del Acto 3 marca frases repetidas. Si lo regenera, ¿al modelo le llega qué no repetir?

**Hoy** (`RegenerateBeatVozUseCase`):
- La Voz recibe la memoria **hasta el acto anterior**, con su lista «YA USADO» (`used_motifs`): imágenes y frases que la Memoria **eligió** como reconocibles. **No** recibe lo que detectó el control de repetición (`repetition_check.py`: las frases de 4 palabras que repite de actos anteriores, los clichés y los nombres inventados). Pueden no coincidir: por eso la repetición se escapa.
- Tampoco sabe qué tenía la versión que se está descartando.
- Después de regenerar, **la memoria de ese acto no se actualiza**: los actos siguientes quedaron escritos con la memoria de la versión vieja (y si se regeneran después, la siguen usando).

**Propuesta:**
1. **Pasarle a la Voz los hallazgos del control de repetición** de ese acto, en una sección «EN LA VERSIÓN ANTERIOR DE ESTE ACTO REPETISTE / USASTE — NO LO VUELVAS A HACER»: frases repetidas (con el acto de origen), clichés y nombres inventados. Es determinístico: 0 llamadas extra.
2. **Actualizar la memoria del acto** después de regenerarlo (1 llamada extra a la Memoria), para que lo que venga después parta de la versión nueva.
3. **Avisar en el panel** que los actos siguientes se escribieron con la versión anterior (sin regenerarlos solos: la IA nunca corre sola).
4. En la generación completa, el control de repetición **no** vuelve a la Voz (no hay versión anterior); la prevención sigue siendo «YA USADO».

### A3 — ¿Hay un proceso que detecte puntos de la narrativa que faltan? · **parcial; propuesta a decidir**

**Pregunta del usuario:** ¿la IA interpreta si faltan beats (puntos de la narrativa) para completar la historia?

**Qué hay hoy:**
- **Estructura fija de 5 actos** (`llm_beats_definition.yaml`): cada acto tiene una función (1 exposición: normalidad + inquietud sutil; 2 acción ascendente: activar el conflicto por una transgresión; 3 clímax: forzar el reconocimiento del horror; 4 acción descendente: colapso y reacción; 5 desenlace). El Planificador llena cada acto con 3–5 hechos siguiendo esa función.
- **Taller** (nivel Dirección): qué busca el protagonista, qué arriesga, qué lo expone, historia secreta, final.
- **Verificador — reglas:** acto sin hechos; acto que termina igual que empieza; persona fuera del elenco; siembra que ningún acto retoma.
- **Verificador — IA:** dónde aparece cada decisión del autor; hechos repetidos o adelantados; lo que se guarda y nunca se revela; personas fuera del elenco.

**Lo que nadie controla:**
- Que **cada acto cumpla su función** (que el Acto 2 tenga de verdad la transgresión, que el 3 sea un clímax y no otra escalada).
- La **continuidad causal y temporal entre actos** (A1).
- Los **criterios de nivel escaleta** que planteaba la Spec-530 (§4: «Cambio», «Revelación»…) quedaron solo como reglas sueltas; no hay taller de escaleta.

**Propuesta:** sumar al Verificador (en la misma llamada, sin costo extra) dos chequeos con aviso por acto:
1. **Función del acto:** «el acto no cumple su función: <función>; falta <qué>».
2. **Continuidad:** «el acto empieza en un lugar o momento que no se explica desde el final del anterior» (A1.4).

Los avisos se ignoran como los demás (Spec-550 H10).

### A4 — «Se guarda para después»: ¿para qué sirve? ¿hace falta? · **propuesta a decidir**

**Pregunta del usuario:** qué objetivo persigue el campo y si es necesario.

**Qué hace hoy (`act_outline.held_back`):**
- Es **lo que el acto sabe pero todavía no cuenta**, para revelarlo en un acto posterior: el suspenso y la revelación (por ejemplo, que la mujer murió en ese micro, o por qué se le aparece a José).
- La **Voz** lo recibe como «NO REVELES TODAVÍA: …» en ese acto.
- El **Verificador** avisa si algo guardado nunca se revela después.
- Lo propone el Planificador («qué información se reserva para un acto posterior»; vacío en el Acto 5).

**Es útil** —en terror, lo que se retiene es la mitad del efecto—, pero hoy no se entiende: el nombre no dice «para quién» ni «hasta cuándo», y se confunde con «siembra/retoma».

**Propuesta:**
- **Mantenerlo y explicarlo:** «**Lo que todavía no se cuenta**» + pista: «La Voz no lo revela en este acto; se tiene que revelar en uno posterior».
- **Mostrar dónde se revela:** «Se revela en el Acto N» (o un aviso si ninguno lo revela), para que se vea el recorrido.
- Diferenciarlo en pantalla de «siembra» (un detalle que se muestra ahora y cobra sentido después) y «retoma».

### A5 — «¿Qué querés que sienta quien lo escuche?» casi no pesa · **decidido: que tenga peso**

**Pregunta del usuario:** ¿qué tan útil es el campo del efecto?

**Hoy:** el efecto llega **solo como una etiqueta** («Efecto que busca el autor: Pavor creciente») a los prompts del Consultor, del Planificador y del Verificador (`context.story_block`). El Consultor lo usa para que sus opciones sean coherentes y el criterio «El final» se evalúa contra él. **La Voz no lo recibe**, y el ritmo de cada acto lo fija la curva de intensidad de los 5 actos (`llm_beats_definition.yaml`), la misma para todos los efectos. Nunca se midió su efecto: dos historias iguales con efectos distintos probablemente salen muy parecidas.

**Cambio (según la máxima: el efecto se resuelve en la escaleta, no en la Voz):**
1. **Cada efecto tiene una receta para el Planificador**, en `config/authoring_options.yaml` (campo nuevo `planificador` por efecto), que llega al prompt como una sección «CÓMO TIENE QUE PEGAR»:

   | Efecto | Receta para la escaleta |
   |---|---|
   | Pavor creciente | La amenaza se acerca de a poco: cada acto, un paso más cerca y más concreta que en el anterior. El Acto 1 solo insinúa; nada se muestra entero antes del Acto 3. |
   | Susto | Al menos dos irrupciones bruscas (Actos 2 y 3), cada una precedida por un momento de calma. Hechos cortos y concretos; el golpe llega sin aviso. |
   | Melancolía inquietante | El miedo nace de una pérdida o una culpa; la amenaza tiene algo humano o triste. El final deja una pena que no se cierra (si el autor decidió el final, manda el suyo). |
   | Horror que se revela | Lo que se guarda en los Actos 1–3 apunta a una verdad que se revela en el Acto 4 y cambia el sentido de lo anterior. Las siembras se cobran en esa revelación. |
   | Otro | El texto que escribió el autor, como objetivo a cumplir. |

2. **El Verificador controla la receta** dentro de la misma revisión (sin llamada extra): un aviso por acto si la escaleta no la cumple («para “Susto” falta una irrupción brusca en el Acto 2»). Se ignora como cualquier aviso (Spec-550 H10).
3. **La Voz no cambia:** recibe la escaleta que ya tiene el efecto adentro.
4. **Medición (condición para quedarse):** la misma historia con dos efectos distintos (p. ej. «Pavor creciente» y «Susto»), 2 corridas cada uno, con `evaluate_voice.py`. Se comparan las escaletas (¿cumplen su receta?) y el usuario lee los relatos sin saber cuál es cuál. **Si no se distinguen, el campo se saca** de la Dirección.

**Costo:** 0 llamadas extra; el prompt del Planificador y el del Verificador, algunas líneas más.

### A6 — Lo detectado no vuelve cuando se rehace · **decidido**

**Pregunta del usuario:** los problemas que se detectan, ¿el proceso apunta a resolverlos, o falta un flujo que los use cuando se vuelve al taller o se vuelve a generar?

**Hoy:**

| Qué se detecta | Dónde se ve | ¿Lo recibe la IA cuando se rehace? |
|---|---|---|
| Criterios del Taller | Taller | Sí: el Consultor recibe respuestas y pendientes en la ronda siguiente |
| Avisos del Verificador | Escaleta | Solo al revisar de nuevo (y respeta lo ignorado, Spec-550 H10). **«Rearmar la escaleta» no los recibe** |
| Frases repetidas, clichés, nombres inventados | Panel del relato | **«Regenerar relato» no recibe nada**; regenerar un acto, recién con A2 |
| Motivos ya usados | interno | Sí, pero solo dentro de una misma generación |

**Cambio (cerrar el circuito; nada automático, solo cuando el autor da la orden):**
1. **Rearmar la escaleta:** el Planificador recibe los avisos **visibles** (no los ignorados) de la escaleta actual como «problemas a resolver en esta versión».
2. **Regenerar el relato completo:** cada acto recibe lo que el control de repetición marcó en ese acto en la última versión (mismo mecanismo que A2).
3. Sin llamadas extra; algunas líneas más en los prompts del Planificador y de la Voz. Va en S5, junto con A2.

---

## 2. DECISIONES

- **A1:** ✅ decidido (2026-09-27) — **campo nuevo** «Cómo llega acá» en los actos 2–5 (columna nueva en `act_outline`; se recrean las DB) y **sí** se le pasan a la Voz las últimas 2–3 oraciones del acto anterior (con la indicación de no repetirlas).
- **A2:** ✅ decidido (2026-09-27) — las tres: pasarle a la Voz lo que marcó el control de repetición, actualizar la memoria del acto regenerado (+1 llamada) y avisar que los actos siguientes se escribieron con la versión vieja.
- **A3:** ✅ decidido (2026-09-27) — se suma solo el chequeo de **continuidad** (regla: actos 2–5 sin «Cómo llega acá»; IA: el acto arranca en un lugar o momento que no se explica desde el anterior). El de **función del acto** queda afuera por ahora.
- **A4:** ✅ decidido (2026-09-27) — mantener y aclarar: «Lo que todavía no se cuenta» + pista + «Se revela en el Acto N» (o aviso si ninguno lo revela).
- **A5:** ✅ decidido (2026-09-27) — que el efecto tenga peso: receta por efecto para el Planificador, control en el Verificador, medición con dos efectos; si no se distinguen, el campo se saca.
- **A6:** ✅ decidido (2026-09-27) — cerrar el circuito: «Rearmar la escaleta» recibe los avisos visibles; «Regenerar relato» recibe lo que el control marcó en cada acto de la última versión. Va en S5.

---

## 3. CÓMO SE MIDE

- «La presencia del colectivo» y las historias de referencia de `evaluate_voice.py`, antes y después: frases repetidas entre actos (4-gramas), clichés, nombres inventados y —nuevo— **aperturas sin puente** (actos 2–5 cuya primera oración no se conecta con el cierre del anterior; revisión manual sobre una muestra).
- Regenerar el Acto 3 de un relato con repeticiones marcadas: la versión nueva no repite las frases señaladas.

---

## 4. PLAN (junto con la Spec-570)

Las dos specs cambian el esquema: van en **una rama** (`feat/spec-560-570`) y en **un pase** a prod, que recrea la DB (datos descartables, 2026-09-27). Primero se ordena el dominio (570) y después se suma lo nuevo (560) sobre el dominio ya limpio. Cada slice cierra con suite en verde, `make dev-db` si cambió el esquema, `make dev-status` y qué mirar en `storymaker.test`.

### S0 — Línea base (sin tocar código)
- `evaluate_voice.py` con el perfil activo (gemma3:12b), 2 corridas, sobre el pipeline actual: frases repetidas, clichés, nombres inventados y, a mano, cómo abren los actos 2–5. Corre en segundo plano (~15 min).
- Script para medir A5: `evaluate_voice.py --effect <id>` (fija el efecto de la historia en la DB temporal).

### S1 — Spec-570: `macro_beat` solo salida · ✅ 2026-09-27 (D2 revisada: `act_outline.draft` y `act_outline.synopsis`; fuera `BeatType` —quedó sin uso— y el `PUT /stories/{id}/beats/{n}`, que editaba el resumen que ya no existe; snapshot: solo suma la sinopsis por acto al Planificador)
- Esquema: fuera `summary`, `synopsis_beat`, `type`, `active_scenario_id`, `active_scenario_description`; modelo y repos.
- Quien las leía, lee la escaleta: la sala (hechos del acto; `GET /beats` sigue devolviendo `summary`, armado desde `act_outline.events`), el tipo de acto sale del número (`get_beat_info`), el export YAML deja de leer `synopsis_beat`.
- `import-yaml`: la sinopsis por acto de los YAML viejos va a la escaleta como primer hecho (D2).
- **Verificación:** snapshot de prompts sin cambios; round-trip de `input_stories/`; E2E de la sala en modo lectura.

### S2 — Spec-570: nombres · ✅ 2026-09-27 (`ActText`, `GenerateStoryUseCase` —y `container.generate_story_use_case`—; `BeatType` ya había salido en S1; la tabla sigue llamándose `macro_beat`)
- `MacroBeat` → `ActText`, `DirectorUseCase` → `GenerateStoryUseCase`, `BeatType` → `ActType`; fuera el alias `Beat`. API (`/beats`), evento `beat_start` y `applies_to_beat` sin cambios (D3).
- **Verificación:** refactor mecánico; suite en verde; `grep` sin los nombres viejos en `src/`.

### S3 — A1 + A3: puente entre actos y continuidad · ✅ 2026-09-27 (snapshot regenerado a propósito: `como_llega` en el Planificador, «Cómo llega» en el Verificador, puente y final anterior en la Voz de los actos 2–5)
- Esquema: `act_outline.bridge` («Cómo llega acá»: tiempo que pasó y cómo se llega).
- Planificador: devuelve `como_llega` para los actos 2–5.
- Escaleta: campo «Cómo llega acá» arriba de los hechos (actos 2–5), editable.
- Voz: secciones «CÓMO SE LLEGA A ESTE ACTO» (con la indicación de abrir contándolo en pocas líneas) y «ASÍ TERMINÓ EL ACTO ANTERIOR» (últimas 2–3 oraciones del acto N−1, con «seguí desde acá, sin repetirlo»); en la generación completa y al regenerar.
- Verificador: regla «sin puente» (actos 2–5) y chequeo de la IA de continuidad (lugar o momento que no se explica desde el acto anterior).
- **Verificación:** snapshot regenerado a propósito (Voz, Planificador, Verificador); pytest de las secciones nuevas; E2E del campo en la Escaleta.

### S4 — A4: «Lo que todavía no se cuenta» · ✅ 2026-09-27 (regla `sin_revelacion`; el Verificador ve «Todavía no se cuenta… (se revela en el acto N)»)
- Esquema: `act_outline.reveal_act` (en qué acto se revela; 0 = ninguno).
- Planificador: devuelve `se_revela_en`; regla del Verificador si algo guardado no se revela en un acto posterior.
- Escaleta: rótulo «Lo que todavía no se cuenta», pista («La Voz no lo revela en este acto; se tiene que revelar en uno posterior») y «Se revela en el Acto N» (elegible).
- **Verificación:** pytest de la regla; E2E del rótulo y del selector.

### S5 — A2 + A6: regenerar sin repetir y cerrar el circuito
- Voz al regenerar: sección con lo que marcó el control de repetición en ese acto (frases repetidas con su acto de origen, clichés, nombres inventados).
- Después de regenerar, la Memoria del acto se actualiza (+1 llamada; el job pasa por la etapa `journal`).
- Esquema: `macro_beat.stale` (se escribió con la memoria de una versión anterior): al regenerar el acto N se marca en los actos > N y se limpia al regenerarlos o al generar todo; el panel del relato lo avisa en esos actos.
- A6: el Planificador recibe los avisos visibles al rearmar; la generación completa recibe, por acto, lo marcado en la última versión.
- **Verificación:** pytest del prompt de regeneración y de la marca; E2E del aviso en el panel; pytest de los prompts de A6.

### S6 — A5: el efecto pesa
- `authoring_options.yaml`: receta `planificador` por efecto; «otro» usa el texto del autor.
- Planificador: sección «CÓMO TIENE QUE PEGAR»; Verificador: aviso si un acto no cumple la receta.
- **Verificación:** snapshot regenerado; pytest de la receta por efecto.

### S7 — Medición, documentación y pase
- `evaluate_voice.py` después de S3–S6 contra la línea base de S0; A5: la misma historia con «Pavor creciente» y «Susto», 2 corridas cada uno → el usuario lee sin saber cuál es cuál. Resultados en esta spec; **si A5 no se distingue, se saca el campo** (decisión del usuario).
- `CLAUDE.md` (pipeline, esquema, escaleta); specs 560 y 570 a DONE; PR a `development`.
- Pase a prod cuando el usuario lo pida: `make deploy` + DB de prod nueva (se avisa que arranca vacía).

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Prompts de la Voz más largos pueden empeorar a gemma3 (va contra la máxima si no ayuda). | S0 mide la base; S7 compara. Si el puente o las últimas oraciones no mejoran las aperturas, se sacan. |
| La Voz repite las últimas oraciones del acto anterior. | Indicación explícita y el control de repetición lo marca; se mide en S7. |
| El refactor de nombres (S2) toca muchos archivos. | Slice propio, mecánico, sin cambios de comportamiento; suite completa. |
| Tres cambios de esquema en la rama. | Una sola recreación de DB por slice en dev; en prod, una sola al final. |

---

## 5. TASKS (junto con la Spec-570)

Cierre de cada slice: ruff + pytest + Vitest + Playwright en verde; si cambió el esquema, `make dev-db ARGS=--yes`; `make dev-status`; al usuario, qué mirar en `storymaker.test`. **Mientras corre una medición no se tocan prompts** (se leen del disco en cada generación).

### S0 — Línea base · ✅ 2026-09-27 — `base-560` (gemma3:12b, «El monte prohibido» con entidades, 2 corridas): clichés 1,0 · parentescos mal 0,5 · narradora en 3.ª persona 0 · frases repetidas 3,5 · 2 187 palabras. Relatos en `scripts/research/560/base/`.
- [x] **T0.1** `evaluate_voice.py --label base-560 --variants con --runs 2 --out scripts/research/560/base` (gemma3:12b, en segundo plano). — *Verify:* `report.json` y los relatos en la carpeta.
- [x] **T0.2** `evaluate_voice.py --effect <id>`: fija el efecto de la historia en la DB temporal. — *Verify:* corrida `--mock` con `--effect susto` deja `direction.effect = susto`. — *Files:* `scripts/evaluate_voice.py`.

### S1 — Spec-570: `macro_beat` solo salida
- [x] **T1.1** Esquema y modelo: fuera `summary`, `synopsis_beat`, `type`, `active_scenario_id`, `active_scenario_description`. — *Files:* `connection.py`, `models.py`, `beat_repository.py`, `story_repository.py`.
- [x] **T1.2** Lectores: `director_use_case` (no escribe esas columnas), `streaming_service` (`beat_start` con el tipo desde el número), `beat_router` (`summary` desde `act_outline.events`), `yaml_exporter` (sin `synopsis_beat`). — *Verify:* snapshot sin cambios; E2E de la sala.
- [x] **T1.3** `import-yaml`: sinopsis por acto → escaleta (primer hecho). — *Verify:* pytest del import de `input_stories/` (escaleta con 5 actos y su sinopsis). — *Files:* `create_story.py`, tests.

### S2 — Spec-570: nombres
- [x] **T2.1** `MacroBeat` → `ActText`, `BeatType` → `ActType`, fuera el alias `Beat`. — *Verify:* `grep` en `src/` sin los nombres viejos; suite.
- [x] **T2.2** `DirectorUseCase` → `GenerateStoryUseCase` (archivo, contenedor DI, routers, CLI, tests). — *Verify:* suite.

### S3 — A1 + A3: puente y continuidad
- [x] **T3.1** Esquema `act_outline.bridge`; `ActOutline.bridge`; `ActForm`; export/import YAML. — *Files:* `connection.py`, `models.py`, `story_repository.py`, schemas, exporter/loader.
- [x] **T3.2** Planificador: `como_llega` (actos 2–5) en el esquema de salida y el prompt.
- [x] **T3.3** Voz: «CÓMO SE LLEGA A ESTE ACTO» + «ASÍ TERMINÓ EL ACTO ANTERIOR» (últimas 2–3 oraciones), en la generación completa y al regenerar. — *Verify:* pytest de las secciones; snapshot regenerado a propósito.
- [x] **T3.4** Verificador: regla `sin_puente` (actos 2–5) y chequeo de continuidad en el prompt. — *Verify:* pytest.
- [x] **T3.5** Escaleta: campo «Cómo llega acá» (actos 2–5). — *Verify:* E2E (se guarda y vuelve).

### S4 — A4: lo que todavía no se cuenta
- [x] **T4.1** Esquema `act_outline.reveal_act`; Planificador `se_revela_en`; regla del Verificador (guardado sin acto posterior que lo revele). — *Verify:* pytest.
- [x] **T4.2** Escaleta: rótulo, pista y «Se revela en el Acto N» (selector). — *Verify:* E2E.

### S5 — A2 + A6: regenerar sin repetir y cerrar el circuito
- [ ] **T5.1** Prompt de regeneración con lo marcado por `repetition_check` en ese acto. — *Verify:* pytest del prompt.
- [ ] **T5.2** Memoria del acto actualizada al regenerar (etapa `journal` en el job). — *Verify:* pytest del use case.
- [ ] **T5.4** A6: Planificador recibe los avisos visibles al rearmar; la generación completa recibe lo marcado por acto en la última versión. — *Verify:* pytest de los dos prompts; snapshot regenerado.
- [ ] **T5.3** Esquema `macro_beat.stale`: se marca en los actos > N, se limpia al regenerarlos o al generar todo; aviso en el panel del relato. — *Verify:* pytest + E2E del aviso.

### S6 — A5: el efecto pesa
- [ ] **T6.1** `authoring_options.yaml`: `planificador` por efecto; `catalog.Option`. — *Verify:* pytest.
- [ ] **T6.2** Planificador «CÓMO TIENE QUE PEGAR» y aviso del Verificador si un acto no cumple la receta. — *Verify:* pytest; snapshot regenerado.

### S7 — Medición, documentación y pase
- [ ] **T7.1** `evaluate_voice.py` después de S3–S6 contra la base; A5: «pavor» y «susto», 2 corridas cada uno, para la lectura a ciegas del usuario. Resultados en esta spec.
- [ ] **T7.2** `CLAUDE.md`; specs 560 y 570 a DONE; PR a `development`.

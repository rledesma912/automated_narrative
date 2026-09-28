# SPEC-580: Un sitio que da ganas de contar — tono de la UI y la historia completa

**Fecha:** 2026-09-28
**Tipo:** SDD (Spec-Driven Development) — experiencia del asistente
**Estado:** SPECIFY — decisiones tomadas (2026-09-28, §6); pendiente el OK para implementar
**Rama:** `feat/spec-580-estructura-taller`
**Extiende:** Spec-530 §4 (criterios del taller), Spec-550 (recorrido de la UI) y Spec-560 A3 (retoma la parte «función del acto», pero antes de la escaleta y no en el Verificador).

---

## PRINCIPIO

**Quién usa la web (2026-09-28):** la esposa y la hija del usuario. No conocen el oficio (nudo, anagnórisis, escaleta, siembra) ni la jerga técnica. Si el sitio les habla como un manual, se frustran y dejan de crear relatos. **Completar el asistente tiene que ser ameno.**

**Máxima del pipeline (2026-09-27):** lo conceptual se resuelve **antes**, en el taller y la escaleta, con análisis de la IA y confirmación de quien escribe. **Cada campo o chequeo nuevo tiene que prevenir un error que se vio de verdad.** Por eso la parte de estructura **empieza midiendo** (S0).

**La teoría diseña los criterios, nunca se muestra ni entra en los prompts** (Spec-530 §1.2): queda en `origen` y en las specs.

---

## ALCANCE

- **Sí:** todo texto que lee quien usa el sitio: pasos, rótulos, pistas, botones, avisos, modales, chips, menú, pie, páginas de inicio, galería, ficha, relatos y sala. Y **lo que la IA le escribe a quien escribe la historia**: las preguntas y opciones del Consultor y los avisos del Verificador.
- **No:** la prosa del relato. Los prompts de la Voz (`outline_voice*.md`, `voice_craft.md`) y de la Memoria (`outline_journal*.md`) no se tocan, y tampoco el contenido de la escaleta que arma el Planificador (hechos, objetivos). El snapshot de prompts de la Voz tiene que quedar igual.
- **No:** las URLs, los ids ni la API (`/asistente/{id}/taller` sigue así). Solo cambia lo que se lee.
- **No:** el contenido de `/debug` (herramienta del usuario). Sale del menú y se llega desde el pie (D6).

---

## ASSUMPTIONS

1. La estructura de 5 actos no cambia (`config/llm_beats_definition.yaml`): 1 exposición (inquietud sutil), 2 acción ascendente (transgresión), 3 clímax (reconocimiento del horror), 4 acción descendente (colapso y reacción), 5 desenlace.
2. Los criterios del taller son datos (`config/workshop_criteria.yaml`): sumar o reescribir uno no cambia el esquema ni el Consultor; la UI los muestra de forma genérica.
3. El Consultor sigue siendo **1 llamada por ronda**: los criterios nuevos van en la misma llamada. El Planificador ya recibe todas las decisiones del taller (`context.decisions_block`).
4. Modelo de referencia: `gemma3:12b`. La prueba con el LLM frontier sigue en pausa.
5. Sin cambio de esquema de la DB. Datos descartables: una historia ya trabajada ve los criterios nuevos «sin evaluar» hasta la próxima ronda.
6. Muchos E2E buscan por texto: cambiar un rótulo obliga a actualizar su test en el mismo slice.

---

## OBJECTIVE

1. **Tono:** que el sitio hable como alguien que te ayuda a contar un cuento en la sobremesa, y que ellas puedan armar un relato **sin ayuda** del usuario.
2. **Historia completa:** que antes de armar la escaleta el taller confirme que la idea alcanza para los cinco actos, y que cuando falte algo **lo pregunte** en lugar de dejar que el Planificador lo invente sin avisar.

**Éxito:**
- Ningún término de oficio ni técnico en las pantallas del asistente ni en las de relatos (glosario de §2.2 aplicado; test que lo verifica).
- Las preguntas del Consultor salen en el tono de la guía (lectura de una muestra en S5).
- En una sinopsis incompleta, el taller pregunta por los momentos que faltan; en una completa («la pena del colectivo»), las preguntas nuevas salen resueltas y no preguntan nada.
- En la escaleta, los actos 2, 3 y 4 cumplen su función con lo que decidió quien escribe, no con algo inventado.
- El Consultor no empeora (JSON válido, tiempo de la ronda).
- **Prueba con ellas:** arman un relato en `storymaker.test` sin ayuda; se anota dónde se trabaron.

---

## PARTE A — EL TONO DEL SITIO

### 2.1 Guía de tono

- **Voseo rioplatense**, como ahora («escribí», «elegí»).
- **Frases cortas.** Una idea por frase. Las pistas, de una o dos líneas.
- **Hablar de su historia:** el nombre del personaje («¿Qué quiere José esa noche?»), no «el protagonista».
- **Hechos concretos, no conceptos:** «¿qué hace José que no tendría que haber hecho?», no «la transgresión».
- **Cómplice, sin exagerar:** un toque cálido está bien («En los cuentos de miedo, casi siempre alguien abre la puerta que no tenía que abrir»); nada de chistes forzados, diminutivos ni signos de exclamación en cadena.
- **La IA es una ayuda, no un examen:** nada es obligatorio y los avisos son sugerencias («Te marco esto por si querés mirarlo»).
- **Botones con verbos de lo que pasa:** «Armar los actos», «Escribir el relato».

### 2.2 Glosario (qué se deja de decir)

Los nombres de los pasos, según D5.

| Hoy | Con el tono nuevo |
|---|---|
| Dirección | Tu idea |
| Taller | Preguntas |
| Escaleta | Los actos |
| Ronda N | *(no se muestra)* |
| Estado de la historia | Cómo viene tu historia |
| Preguntas abiertas | Te falta contarme |
| Ya resuelto | Ya lo tenés |
| cumple / parcial / falta | listo / a medias / falta |
| Analizar mi historia / Analizar de nuevo | Que la IA me pregunte / Preguntame de nuevo |
| Armar la escaleta | Armar los actos |
| Revisión de la IA / Revisar con la IA | Lo que vio la IA / Que la IA lo revise |
| Hilos · Siembra · Retoma | Detalles que vuelven · Aparece acá · Vuelve de antes |
| En escena · elenco | Quiénes están · personajes |
| Lo que todavía no se cuenta | Lo que todavía es secreto |
| «La Voz no lo revela…» | «En este acto no se cuenta; se descubre más adelante.» |
| Galería de historias | Mis historias |
| Sala de Generación · Beat · Despertando al Narrador… | Escribiendo tu relato · Acto · Arrancando… |
| Core API (pie) | *(solo el punto de estado, con «La IA está lista / no responde»)* |
| Inicio: «Anatomía de una Sinopsis Ganadora», «Inyecta densidad sensorial» | Una bienvenida corta que entra entera en la pantalla (D7): qué se puede hacer y el botón «Contar una historia nueva» |
| Ficha: ATMÓSFERA, REGLAS DEL MUNDO, TRAMA | Tipo de horror, Reglas de la historia, De qué trata |

«Acto» se queda: es una palabra conocida y el `.md` para el TTS dice «Acto N».

### 2.3 Lo que escribe la IA para quien escribe

- **Consultor** (`authoring_consultant_system.md`): la regla de estilo pasa de «Español rioplatense, frases simples» a la guía de §2.1, con 2 ejemplos de pregunta en el tono. Las opciones, también en ese tono.
- **Verificador:** los avisos de las reglas (`verifier.py`: `elenco`, `siembra`, `sin_hechos`, `sin_cambio`, `sin_puente`, `sin_revelacion`) se reescriben a mano; los de la IA reciben la misma guía en `authoring_verifier_system.md`.
- Ninguno de los dos recibe teoría. La Voz no cambia.

---

## PARTE B — LA HISTORIA COMPLETA

### 3.1 Qué hay hoy

| Acto | ¿Lo cubre el taller? |
|---|---|
| 1 · Presentación | En parte: el protagonista y qué quiere (`meta`) |
| 2 · Qué rompe la calma | **No** |
| 3 · El momento de entender | **No** (`historia_secreta` dice *qué* se oculta, no *cómo* se descubre) |
| 4 · Qué hace después | **No** (`vulnerabilidad` es el error, no la reacción) |
| 5 · Final | Sí (`final`) |

Cuando falta un momento, el Planificador lo inventa para cumplir la función del acto, y quien escribe recién se entera en la escaleta, si lee con atención.

### 3.2 Las preguntas del taller

Las 5 que hay se reescriben en el tono nuevo y se suman 3 (o 4, según D1), en este orden. Ejemplo con José:

| id | Se ve en la UI | Acto | Estado |
|---|---|---|---|
| `meta` | ¿Qué quiere José esa noche? | 1 | reescrita |
| `inquietud` | ¿Pasa algo raro desde el principio? | 1 | nueva (D1) |
| `en_juego` | ¿Qué puede perder José? | — | reescrita |
| `vulnerabilidad` | ¿En qué se equivoca José? | — | reescrita |
| `transgresion` | ¿Qué hace José que no tendría que haber hecho? | 2 | nueva |
| `historia_secreta` | ¿Qué esconde esta historia? | — | reescrita |
| `descubrimiento` | ¿Qué descubre José que le hace entender todo? | 3 | nueva |
| `reaccion` | ¿Y después qué hace José? | 4 | nueva |
| `final` | ¿Cómo termina? | 5 | reescrita |

- Cada criterio tiene tres textos: `nombre` (la pregunta que se ve), `por_que` (la pista, una o dos líneas en el tono de §2.1; por ejemplo, para `transgresion`: «En los cuentos de miedo, casi siempre alguien abre la puerta que no tenía que abrir. ¿Cuál es la de {protagonista}?») y `pregunta` (lo que evalúa el Consultor, concreto y sin teoría). `origen` queda como documentación.
- **Cómo funciona:** el Consultor lee la sinopsis y marca cada pregunta como resuelta, a medias o pendiente. Si no está resuelta, pregunta sobre esa historia con hasta 3 opciones. Por ejemplo, con «Marta es enfermera de guardia; suena el timbre de una habitación clausurada», puede preguntar «¿Qué hace Marta con el timbre?» con las opciones *entra a la habitación* / *contesta por el intercomunicador* / *busca quién murió ahí*. Lo que elige quien escribe llega al Planificador como una decisión.

### 3.3 Cada decisión sabe a qué acto va (D2)

Campo opcional `acto` en el criterio. El Planificador ve `- [descubrimiento] ¿Qué descubre José…? (va en el acto 3) → Respuesta: …`. Así lo que descubre José no queda en el acto 2 con un acto 3 que es solo más susto. Es una línea más en el prompt del Planificador, que no cambia la prosa.

### 3.4 Lo que no entra

- El chequeo «función del acto» en el Verificador: sigue afuera. Si S5 muestra que no alcanza, otra spec.
- Nombrar la teoría en la UI o en los prompts.

---

## 4. CÓMO SE MIDE

### 4.1 La historia completa

**Material:** 4 historias en `scripts/research/580/`:
- `pena` (Spec-530): sinopsis **completa**, sirve de control.
- `monte` (`input_stories/el_monte_prohibido.yaml`).
- 2 sinopsis **cortas e incompletas** (2–3 líneas, solo la idea y el personaje), D4.

**Corrida:** el camino «asistente» de `evaluate_workshop.py` (ronda del taller con «Decidí vos» → escaleta → revisión), **hasta la escaleta**, sin prosa. 2 corridas por historia → 8 escaletas por variante.

**Grilla por escaleta** (lectura manual, como la de Spec-560 §3.1):

| Acto | ¿Cumple su función? | ¿De dónde sale? |
|---|---|---|
| 2 | Algo rompe la calma y despierta a la amenaza | sinopsis / decisión del taller / **inventado** |
| 3 | El protagonista entiende algo (no es solo más susto) | ídem |
| 4 | El protagonista hace algo con lo que sabe | ídem |

**Umbral (D3):** si en **3 o más de las 8** escaletas de la base algún acto 2–4 no cumple o sale inventado, se suman las preguntas nuevas. Si no, solo se reescriben las 5 que hay (la Parte A sigue igual).

### 4.2 El tono

- Test de vistas que falla si aparece un término del glosario («escaleta», «taller», «siembra», «beat», «ronda»…) en las pantallas de §2.2.
- Lectura de las preguntas y opciones del Consultor en las 8 corridas de S5: ¿siguen la guía?, ¿nombran al personaje?, ¿alguna usa teoría?
- **La prueba que manda:** ellas arman un relato en `storymaker.test`, sin ayuda. El usuario anota dónde dudaron o se trabaron.

---

## 5. PLAN

Cada slice cierra con ruff + pytest + Vitest + Playwright en verde, `make dev-status` y qué mirar en `storymaker.test`. Sin cambio de esquema. **Mientras corre una medición no se tocan prompts ni criterios.**

### S0 — Medición previa de la estructura (sin tocar código de la app)
La corrida base (T0.3) va antes de S1 y S4, para que las preguntas nuevas y el tono del Consultor no se mezclen con la línea base. Espera las sinopsis de D4; mientras tanto se hacen T0.1, S2 y S3 (textos del sitio, que no cambian lo que mide S0).
- `evaluate_workshop.py --hasta-escaleta` y las 2 sinopsis incompletas.
- Corrida base (gemma3:12b, 2 × 4, en segundo plano) → grilla en §7. Decisión con el usuario según el umbral.

### S1 — Las preguntas del taller
- `workshop_criteria.yaml`: las 5 reescritas y las nuevas (según S0 y D1), en el orden de §3.2.
- Si D2: `Criterion.acto` y «(va en el acto N)» en `context.decisions_block`.
- Snapshot regenerado a propósito (Consultor y Planificador; la Voz sin cambios).

### S2 — El asistente en el tono nuevo · ✅ 2026-09-28 (actos con nombres llanos: «Cómo empieza», «Se complica», «El peor momento», «Qué hace después», «Cómo termina»; «intensidad» → «tensión»; el texto de fin del taller también, en `workshop_rules.finish`; test `sin-jerga.view.test.ts`)
- Tu idea, Preguntas y Los actos (`direccion.ejs`, `taller.ejs`, `escaleta.ejs`, `_cabecera.ejs`, `_analizando.ejs`), los mensajes de `asistente.js` y los modales.
- Los avisos de las reglas del Verificador.
- Test del glosario sobre las vistas del asistente; E2E actualizados.

### S3 — El resto del sitio en el tono nuevo · ✅ 2026-09-28 (inicio compacto con los 4 pasos y un consejo; «Mis historias»; pie «La IA está lista / no responde» + enlace a `/debug`; sala «Escribiendo tu relato»; mensajes de etapa del Core y de los scripts: «Escribiendo el acto N», «Repasando lo que pasó», «Juntando el relato»; `sin-jerga` sobre todas las vistas salvo `/debug` y sobre `public/js`)
- Inicio: bienvenida nueva y compacta, entra entera en la pantalla (D7). Menú sin `/debug`; enlace a `/debug` en el pie (D6). Pie, banner de generación, galería, ficha, relatos, panel del relato (control de repetición y aviso de acto desactualizado) y sala.
- Test del glosario sobre todas las vistas salvo `/debug`.

### S4 — Lo que escribe la IA
- Guía de tono en `authoring_consultant_system.md` y `authoring_verifier_system.md`, con ejemplos.
- Snapshot regenerado a propósito (Consultor y Verificador).

### S5 — Medición después y prueba con ellas
- La misma corrida de S0 → grilla, control de `pena`, JSON válido y tiempo del Consultor, lectura del tono de las preguntas. Resultados en §7.
- Prueba en `storymaker.test` con la esposa y la hija; lo que salga se anota en §7 y, si hace falta, se ajusta el texto (un slice corto más).
- **Si las preguntas nuevas no mejoran la grilla o el Consultor empeora**, se sacan (decisión del usuario).

### S6 — Documentación
- `CLAUDE.md` (nombres de los pasos, criterios, guía de tono), spec a DONE, PR a `development`.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Con 8–9 preguntas, gemma3 evalúa peor o tarda más. | S5 mide JSON válido y tiempo; si empeora, las preguntas de estructura pasan a la segunda vuelta o se sacan. |
| Más preguntas = el formulario gigante. | Las que la sinopsis ya resuelve no preguntan (control con `pena`); nada es obligatorio. |
| Pedirle tono al Consultor le quita precisión a las preguntas. | Se mide aparte (S4 va después de S1) y se lee la muestra en S5. |
| Renombrar rótulos rompe E2E que buscan por texto. | Cada slice actualiza sus E2E; el test del glosario evita que vuelva la jerga. |
| «Decidí vos» mide a la IA contestándose sola. | Es para que la medición sea reproducible; la prueba con ellas es la que cuenta. |

---

## 6. DECISIONES

- **D1 — Preguntas:** ✅ (2026-09-28) las de §3.2, **con** la del acto 1 («¿Pasa algo raro desde el principio?»).
- **D2 — Cada decisión sabe a qué acto va:** ✅ sí (`Criterion.acto`).
- **D3 — Umbral de S0:** ✅ 3 de 8 escaletas con algún acto 2–4 que no cumple o sale inventado.
- **D4 — Sinopsis incompletas:** ✅ las traen **la esposa y la hija** del usuario (ideas reales a medio armar): son la mejor referencia. S0 espera a que lleguen; mientras tanto avanzan T0.1 y la Parte A (S2–S3), que no dependen de la medición.
- **D5 — Nombres de los pasos:** ✅ «Tu idea → Preguntas → Los actos».
- **D6 — `/debug`:** ✅ sale del menú lateral; se llega con un enlace discreto en el pie (junto al estado del Core).
- **D7 — Inicio compacto (pedido del usuario):** ✅ hoy tiene fuentes muy grandes y no entra en la pantalla (hay que hacer scroll). La bienvenida nueva entra entera en una pantalla de escritorio (1366×768 y 1920×1080, con el menú abierto): tamaños de letra y márgenes más chicos, sin los bloques explicativos del wizard viejo. Lo verifica un E2E (el alto del contenido no pasa el de la ventana).

---

## 7. RESULTADOS

*(se completa en S0 y S5)*

---

## 8. TASKS

### S0 — Medición previa
- [x] **T0.1** `evaluate_workshop.py --hasta-escaleta` (guarda `escaleta.json` por corrida, sin prosa). — *Verify:* corrida `--mock` deja las escaletas en `--out`. — *Files:* `scripts/evaluate_workshop.py`.
- [ ] **T0.2** 2 sinopsis incompletas (D4) en `scripts/research/580/` y en `STORIES`. — *Verify:* `--mock --stories <nueva>` corre.
- [ ] **T0.3** Corrida base (gemma3:12b, 2 × 4) → `scripts/research/580/base/`; grilla en §7. — *Verify:* 8 escaletas y la grilla.

### S1 — Las preguntas del taller
- [ ] **T1.1** `workshop_criteria.yaml`: reescritas + nuevas, en orden. — *Verify:* pytest del catálogo (`{protagonista}`, orden, ids).
- [ ] **T1.2** (D2) `Criterion.acto` y «(va en el acto N)» en `decisions_block`. — *Verify:* pytest; snapshot regenerado a propósito, la Voz igual. — *Files:* `catalog.py`, `context.py`, `pipeline_prompts.json`.

### S2 — El asistente
- [x] **T2.1** Vistas del asistente, `asistente.js` y modales con la guía y el glosario. — *Files:* `frontend/src/views/asistente/*.ejs`, `public/js/asistente.js`.
- [x] **T2.2** Avisos de las reglas del Verificador reescritos. — *Verify:* pytest de las reglas. — *Files:* `verifier.py`.
- [x] **T2.3** Test del glosario (vistas del asistente) y E2E actualizados. — *Verify:* Vitest + Playwright.

### S3 — El resto del sitio
- [x] **T3.1** Inicio compacto (D7). — *Verify:* E2E a 1366×768 y 1920×1080: sin scroll vertical. — *Files:* `frontend/src/views/home.ejs`.
- [x] **T3.2** Menú sin «API conn» y enlace a `/debug` en el pie (D6). — *Verify:* E2E del menú y del pie. — *Files:* `partials/sidebar.ejs`, `partials/footer.ejs`.
- [x] **T3.3** Pie, banner, galería, ficha, relatos, panel del relato y sala con la guía y el glosario. — *Files:* `frontend/src/views/*.ejs`, `partials/*.ejs`.
- [x] **T3.4** Test del glosario sobre todas las vistas salvo `/debug`; E2E actualizados. — *Verify:* Vitest + Playwright.

### S4 — Lo que escribe la IA
- [ ] **T4.1** Guía de tono en los prompts de sistema del Consultor y del Verificador. — *Verify:* snapshot regenerado a propósito; la Voz y la Memoria sin cambios.

### S5 — Medición después y prueba con ellas
- [ ] **T5.1** Misma corrida que T0.3 → `scripts/research/580/despues/`; grilla, control de `pena`, JSON válido, tiempo y tono en §7.
- [ ] **T5.2** Prueba en `storymaker.test` con la esposa y la hija; notas en §7; ajustes si hacen falta.
- [ ] **T5.3** Decisión con el usuario: las preguntas nuevas se quedan o se sacan.

### S6 — Documentación
- [ ] **T6.1** `CLAUDE.md`, spec a DONE, PR a `development`.

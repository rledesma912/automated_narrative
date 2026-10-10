# SPEC-670: Moldes de historia (forma + efecto + ingrediente)

**Fecha:** 2026-10-10
**Tipo:** SDD — épica (asistente, Planificador, Verificador, Voz, UI)
**Estado:** SPECIFY ✅ (2026-10-10: capas, b + c, D1–D7, catálogo inicial 5 + 6, sin pregunta abierta) · maquetas ✅ (v3, https://claude.ai/artifact/BRfXu1GVCxNSEZcfq5Cupm; el usuario verifica al probar) · PLAN ✅ (OK 2026-10-10, D11–D16) · TASKS ✅ · S1 ✅ (2026-10-10, bdb2e48)
**Rama:** `feat/spec-670-moldes`
**Extiende:** Spec-530 (asistente), Spec-560 A5 (receta del efecto), Spec-580 (criterios en tono coloquial), Spec-650 (estructuras largo/corto).

---

## ASSUMPTIONS

1. El problema que se quiere resolver: los relatos salen «planos, comunes, sin originalidad» (usuario, 2026-10-10). Parte es el modelo del Planificador (gemma; se prueba aparte con dev en todo-Claude), pero la otra parte es el **molde único** del sistema, que ningún modelo puede saltear.
2. La Voz no cambia de registro (Spec-640, pedido de las usuarias): la originalidad tiene que venir de **qué pasa**, es decir, de las preguntas y de «Los actos».
3. Máxima del pipeline: cada pieza nueva previene un error que se vio de verdad; nada de formulario gigante (8–10 preguntas por historia, como hoy).
4. Sin cambio de esquema: la forma y el ingrediente viven en `story.direction` (JSON), como el efecto.
5. Lo de hoy (molde «advertencia») tiene que seguir saliendo **igual**: es el valor por defecto de las historias viejas y de los YAML importados (snapshots idénticos).
6. Textos en `config/` (Spec-620), tono coloquial (Spec-580), sin jerga en pantalla.

---

## OBJECTIVE

Que cada historia se arme con un **molde que le corresponda**, elegido entre muchas combinaciones, en vez del único molde de hoy. El molde decide tres cosas: **qué se pregunta** (criterios), **qué se pide en cada acto** y **qué reglas sigue el Planificador**.

El molde es la suma de capas: **base + forma + efecto + ingrediente + largo**. Unas 18 piezas bien escritas dan más de 100 combinaciones.

La forma la **sugiere la IA** leyendo la idea y la persona la confirma o la cambia (b). El ingrediente se elige o se **sortea** entre los menos usados (c).

---

## 1. Relevamiento (2026-10-10)

### 1.1 Dónde está el molde hoy

| Lugar | Archivo | Qué fija |
|---|---|---|
| Criterios | `config/workshop_criteria.yaml` | 9 criterios con su acto por estructura: meta, inquietud, en_juego, vulnerabilidad, **transgresion**, **historia_secreta** («por qué la amenaza lo busca **a él**»), descubrimiento, reaccion, final |
| Lo que pide cada acto | `config/llm_beats_definition.yaml` (`intent`, `entity_exposure`) | Largo: acto 2 «activar el conflicto mediante **transgresión**»; corto: acto 2 «**romper la regla**…» |
| Reglas del Planificador | `config/prompts_generation/authoring_planner_system.md` | El protagonista siempre HACE algo, cada encuentro más grave, nada se repite, siembras y cobros |
| Código | `planner.py:119` | `historia_secreta` se suma en el acto `revela_secreto`; `final` va al último acto (`planner.py:90`, `verifier.py:83`) |
| Receta del efecto | `authoring_options.yaml` (`efectos[].planificador`) | Ya es una capa: cuándo se muestra la amenaza, qué se guarda |

Es **un solo molde**, el del cuento de advertencia: aviso → no lo toma en serio → rompe una regla → despierta a la amenaza → descubre un secreto que lo involucra → reacciona → marca.

### 1.2 Tus historias contra ese molde

| Historia | Qué forma tiene en realidad | Dónde choca con el molde |
|---|---|---|
| El trabajo de Yadira | Advertencia (brujería) | **Encaja**: las amigas le advierten, ella sigue, la maldición la alcanza |
| NO TE DETENGAS EN EL BOSQUE | Lugar maldito | Secreto: «**No hay conexión. Lo maldito es la zona.**»; transgresión vacía (se rompe el camión, no elige); vulnerabilidad forzada («problemas de respiración») |
| los desconocidos | Visitante que entra a casa | Secreto: «**nada de eso, tal vez una leyenda**»; la transgresión es inventada para cumplir (espiar por la ranura) |
| el engaño del diablo | Señuelo (algo se disfraza de lo que necesitás) | El secreto es del lugar («la salamanca persigue a **cualquiera**»); vulnerabilidad = «ayuda a buscar al niño»: es el señuelo, no un error |
| La laguna oscura (dev) | Asedio (algo viene por nosotros, causa ajena) | **3 de 9 marcados «a propósito»** (en juego, transgresión, descubrimiento); secreto: «**Nada que ver con Tito**»; vulnerabilidad: «**Es al revés**, la criatura los acecha». Claude, con el molde, igual preguntó «¿qué hace Tito que **despierta** a la criatura?» |

**Conclusión:** 4 de 5 historias tienen otra forma. El molde las obliga a inventar una culpa, un secreto personal o un error que no tienen, y el Planificador (acto 2 = transgresión) lo busca aunque la persona lo haya marcado «a propósito».

---

## 2. Qué se construye

### 2.1 Las capas

| Capa | Qué aporta a los 3 lugares | Cuántas al empezar |
|---|---|---|
| **Base** | Criterios: qué quiere, algo raro desde el principio, qué puede perder, qué hace después, cómo termina (5; «qué hace después» es de toda historia y así «Alguien rompe una regla» = las 9 de hoy). Reglas universales (hechos concretos, sin repetir sustos, nada se adelanta) | 1 |
| **Forma** | 3–4 criterios propios, **lo que pide cada acto** (largo y corto) y 1–3 reglas | 5 |
| **Efecto** | Ya existe (pavor, melancolía, revelación…): cuándo se muestra la amenaza y qué se guarda | las de hoy |
| **Ingrediente** | 1 criterio + 1 regla que se cruzan con cualquier forma | 6 |
| **Largo** | Reparte lo que pide la forma entre 3 o 5 actos (Spec-650) | las de hoy |

~~Una pregunta abierta fija («¿Qué tiene tu historia que no tenga otra?»)~~: **descartada** por el usuario (2026-10-10): es genérica. La chispa sale de la forma y del ingrediente.

### 2.2 Las 5 formas iniciales (salen de tus historias)

| Forma (en pantalla) | El arco | Criterios propios (borrador) |
|---|---|---|
| **Alguien rompe una regla** (la de hoy) | Aviso → lo ignora → lo hace igual → castigo | en qué se equivoca, lo que no tendría que haber hecho, lo que esconde la historia, lo que descubre |
| **Un lugar que no hay que pisar** | Llegar o quedar varado → las reglas del lugar → lo que vive ahí → salir (o no) | por qué está ahí, qué tiene de raro el lugar, qué pasó ahí antes, qué no puede hacer ahí |
| **Alguien que llega a casa** | Lo de afuera entra → algo no cuadra → se ve lo que es → echarlo o sobrevivir | quién llega y cómo entra, qué no cuadra, qué es en realidad, qué lo hace irse (o quedarse) |
| **Algo viene por nosotros** | Señales → se acerca → ataca → se entiende por qué → sigue ahí | qué lo empuja (la causa, no la culpa), cómo se acerca, dónde se refugian, qué cambia cuando se entiende |
| **Algo se hace pasar por otra cosa** | Aparece lo que uno necesita → seguirlo → la máscara se cae → escapar del engaño | qué parece y qué es, por qué se lo cree, la primera grieta, qué precio tiene haber caído |

Cada forma trae **lo que pide cada acto** para largo (5) y corto (3), y sus reglas. Ejemplo («Algo viene por nosotros», corto): 1 = la normalidad y las primeras señales, sin culpables; 2 = la amenaza llega y ataca; al final se entiende la causa; 3 = sobrevivir sin resolverlo: la causa sigue ahí. Regla: «Nadie provoca a la amenaza: la causa es de afuera».

Formas para después (fuera del MVP): duelo que no se cierra, transformación, pacto o deuda, persecución. **Decisión del usuario:** se arranca con estas 5 (y los 6 ingredientes) y el catálogo se amplía cuando haya más historias que muestren otras formas.

### 2.3 Los 6 ingredientes iniciales

| Ingrediente (en pantalla) | Criterio que suma | Regla que suma |
|---|---|---|
| La amenaza tiene una regla rara | ¿Qué regla extraña sigue (no cruza el agua, solo de a uno, contesta si la nombran)? | La regla aparece en un acto y decide el final |
| El lugar tiene su propia historia | ¿Qué pasó ahí antes? | Un detalle de esa historia se ve antes de explicarse |
| Lo de todos los días es lo que asusta | ¿Qué objeto o costumbre común se vuelve raro? | El objeto aparece en el acto 1 sin peso y vuelve cambiado |
| Quien cuenta entiende mal algo | ¿Qué cree quien cuenta que no es así? | El oyente lo nota antes que el narrador |
| La víctima no es quien parece | ¿A quién le pasa de verdad? | Se insinúa en un hecho antes de mostrarse |
| Algo se lleva de recuerdo | ¿Qué objeto o marca le queda? | Aparece antes del final, sin importancia |

Cada ingrediente se cruza con la opción «¿Cómo lo cuenta?» y las demás antes de escribirse (memoria: reglas vs opciones de la UI). Ej.: «quien cuenta entiende mal algo» con «Como una crónica seca».

### 2.4 Cómo se elige (b + c)

- En «Tu idea», debajo de la idea: **«¿Qué clase de historia es?»** con las 5 formas (`.opcion-forge`) y el botón **«Que la IA lo sugiera»** (job nuevo `suggest_form`, 1 llamada corta, con modal como los demás).
- **«Un giro»**: elegir un ingrediente, «Sorprendeme» (sortea entre los menos usados en tus historias; se puede volver a sortear) o «Ninguno».
- Las preguntas (`consult`) usan **base + forma + ingrediente**.

### 2.5 Qué se guarda dónde

| Qué | Dónde | Por qué |
|---|---|---|
| **El catálogo** (formas, ingredientes, sus criterios, lo que pide cada acto, reglas, textos) | YAML en `config/` (p. ej. `config/moldes/formas.yaml`, `ingredientes.yaml`), como hoy `workshop_criteria.yaml` y `llm_beats_definition.yaml` | Es contenido del sistema, no de la persona: viaja con el código en git (se revisa en cada PR), lo validan tests de completitud y snapshots, entra en la imagen de prod (Spec-520: prod cambia solo con `make deploy`) y cumple la Spec-620 (textos en `config/`). En la DB necesitaría una pantalla para editarlo, seeds y cambios de esquema (sin migraciones), y los tests no podrían fijarlo |
| **La elección de cada historia** (qué forma e ingrediente usa) | DB: `story.direction` (JSON), columna que ya existe | Es dato de la historia; sin esquema nuevo |
| **Las respuestas** | DB: `story_workshop` (como hoy; el criterio es un texto, entran los nuevos sin cambiar la tabla) | — |
| **«Sorprendeme»** | Cuenta los ingredientes usados leyendo la DB | — |

Si un día las usuarias quieren crear o editar moldes desde la pantalla, ahí conviene pasar el catálogo a la DB (con seeds, como el de géneros). Mientras lo amplíe el desarrollo, YAML es más simple y más seguro. Una historia que apunte a una forma que ya no existe cae a la de hoy (test).

---

## 3. Decisiones (OK del usuario 2026-10-10)

| # | Duda | Recomendación |
|---|---|---|
| D1 | ¿Cuándo sugiere la IA la forma? | Botón propio en «Tu idea» (job `suggest_form`), **no** escondido dentro de la primera ronda de preguntas: las preguntas dependen de la forma; sin forma elegida, «Alguien rompe una regla» (la de hoy) |
| D2 | Si se cambia la forma con preguntas ya respondidas | Las respuestas de criterios que la forma nueva no tiene **no se borran**: se ocultan y vuelven si se vuelve a esa forma. Los actos armados quedan «a revisar» (como al cambiar la dirección) |
| D3 | Historias viejas, YAML importados, export | Sin forma = «Alguien rompe una regla», sin ingrediente: todo sale **igual que hoy**. `export-yaml` / `import-yaml` llevan `forma` e `ingrediente` |
| D4 | Lo especial de hoy en el código (`historia_secreta` en el acto `revela_secreto`, `final` en el último) | Se generaliza: cada forma declara su criterio de **revelación** y en qué acto va; `final` sigue en el último |
| D5 | ¿Dónde se guarda? | `direction.form` y `direction.ingredient` (JSON, sin esquema nuevo). Se editan en «Tu idea», así que viajan con su autoguardado (cuidado de la D9 de la 650) |
| D6 | «Sorprendeme» | Al azar entre los ingredientes menos usados en las historias de la base; se ve cuál salió y se puede cambiar |
| D7 | Medición | La misma sinopsis con 3 moldes distintos (paga, con aviso de costo antes): ¿salen escaletas distintas y menos de manual? Más la lectura de las usuarias (una versión + 1–2 preguntas) |
| D8 | ¿Y si la forma elegida no encaja con la historia (la IA sugirió mal, se eligió rápido, la historia mezcla dos)? Volverían las preguntas inválidas, como hoy («¿qué hace Tito que despierta a la criatura?» cuando nadie la provoca) | Estado nuevo del criterio **«No va en tu historia»** (`no_aplica`): el Consultor lo marca cuando la idea lo contradice, con el motivo en una línea; chip gris, sin pregunta; la persona lo puede reabrir. El Planificador no pide en ningún acto lo que no va (p. ej. «romper la regla»). Si **2 o más** criterios de la forma no van, nota: «Parece que tu historia no es de esta clase. ¿Probamos con otra?» con la sugerencia de la IA. (Agregado 2026-10-10, OK del usuario) |
| D10 | ¿Se entiende? ¿No volvemos al formulario gigante (pedido de hace mucho: no llenar «10.000 preguntas»)? | **Explicaciones en pantalla** donde se usa cada cosa (pistas `.pista-forge`, tono coloquial): qué cambia la forma («de esto depende qué te pregunta la IA y qué pasa en cada acto»), qué es un giro y que es opcional, por qué hay preguntas «de toda historia / de la forma / del giro», qué significa «No va en tu historia», y qué hace «Otra». **Tope de preguntas:** base 5 + forma ≤ 4 = **9 como máximo sin giro** (hoy son 9 fijas); el giro, que es opcional, suma 1 (**10 con giro**). Un test recorre todas las combinaciones del catálogo y falla si alguna pasa de 9 sin giro o de 10 con giro. Las que no van no se preguntan (D8); ninguna es obligatoria. «Tu idea» suma 2 elecciones de un clic (la forma la sugiere la IA; el giro arranca en «Sin giro»). CLAUDE.md documenta el catálogo y cómo ampliarlo. (Agregado 2026-10-10, pedido del usuario) |
| D9 | ¿Y si la historia no tiene ninguna de las formas del catálogo? | Opción **«Otra clase de historia»** (como «Otro» en el efecto): la persona cuenta el arco en una o dos frases. Preguntas: solo la base (+ el giro); el Planificador reparte **esa descripción** entre los actos en vez de lo que pide una forma, con las reglas universales. «Que la IA lo sugiera» puede devolver «Otra» con una descripción propuesta para corregir. Cada «Otra» queda en `direction` y sirve de evidencia para sumar formas al catálogo. (Agregado 2026-10-10) |

---

## 4. SUCCESS CRITERIA

1. Las 5 formas y los 6 ingredientes están completos para largo y corto (test de completitud: criterios, lo que pide cada acto, reglas, textos de pantalla).
2. «Alguien rompe una regla» sin ingrediente = hoy: snapshots `pipeline/voice/assistant` (largo y corto) idénticos.
3. Ningún criterio que contradiga la idea se pregunta: se marca «No va en tu historia» (D8) o no existe en la forma. Con su forma, las historias del §1.2 dejan de chocar: «La laguna oscura» como «Algo viene por nosotros» no recibe preguntas de transgresión ni de un secreto personal, y su acto 2 no pide «romper la regla» (snapshot por forma).
4. Por historia, **9 preguntas como máximo sin giro y 10 con giro** (hoy son 9 fijas), garantizado por un test sobre todas las combinaciones (D10); con «Otra» (D9), 5–6; las que «no van» (D8) no se preguntan.
5. Cada elemento nuevo se explica en pantalla donde se usa (D10).
6. La IA sugiere una forma razonable para las 5 historias del §1.2 (prueba con el modelo del perfil activo; se registra qué sugirió).
7. Medición D7: con la misma sinopsis, 3 moldes dan escaletas distintas entre sí; lectura de las usuarias.
8. Guardianes en verde (`sin-jerga`, `gramatica-visual`, `test_prompts_fuera_del_codigo`, `sin-cinco-actos`…); pytest, Vitest, Playwright; dev con el cambio.

## BOUNDARIES

- **Always:** piezas en `config/`; maquetas antes de la UI; cada pieza con el error real que previene; lo de hoy intacto como valor por defecto.
- **Ask first:** corridas pagas; tocar el registro de la Voz; sumar formas o ingredientes fuera de los 5 + 6.
- **Never:** que la IA elija la forma sin que la persona la vea; migraciones; reglas que contradigan una opción de «¿Cómo lo cuenta?».

## OPEN QUESTIONS

- ¿Los nombres de las formas en pantalla son claros para las usuarias? Se validan con la maqueta.
- La prueba en curso (dev en todo-Claude) dirá si además conviene mover el Planificador (y el Consultor) a Claude; es independiente de esta spec.

---

## 5. PLAN (2026-10-10)

Relevado en `feat/spec-670-moldes`. Principio, como en la 650: **una sola fuente** (el molde de la historia, resuelto desde `config/moldes/`) y lo de hoy como valor por defecto, byte a byte.

### 5.1 Decisiones nuevas que salieron de la revisión

| # | Riesgo encontrado | Decisión recomendada |
|---|---|---|
| D11 | **Respuestas ocultas que se cuelan.** `context.decisions()` toma la respuesta de *cualquier* criterio guardado: al cambiar de forma (D2), las respuestas de la forma anterior llegarían igual al Planificador y al Verificador como «decisiones del autor». | Todo lo que lee el taller pasa por **los criterios activos del molde** (`Molde.criterios`): `initial_items`, `decisions`, `pending_block`, `_state`, el Consultor. Test: una respuesta de otra forma no aparece en ningún prompt. |
| D12 | **Dónde se guarda el motivo de «No va en tu historia» (D8)** sin cambiar el esquema. | Estado nuevo `no_aplica` (la columna `status` no tiene `CHECK`); el motivo va en `question` (con `no_aplica` no hay pregunta) y la UI lo muestra como motivo. `to_evaluate` no lo vuelve a mirar. «Preguntármelo igual» = reabrir **con marca** (`asked` guarda `·no_aplica_rechazado`): en ese criterio la IA ya no puede volver a decir «no va» (si no, reabrir sería un ida y vuelta sin fin). |
| D13 | **El autoguardado de «Tu idea» rearma `Direction` entero** (`_direction(form)`, la misma trampa de la D9 de la 650): borraría lo que puso la IA al sugerir (la forma sugerida y su motivo). | `form`, `ingredient` y `form_other` (el arco de «Otra») viajan en el formulario (los elige la persona). `form_suggested` y `form_reason` (de la IA) los **conserva el servidor** al guardar: `update_direction` los copia de la dirección guardada. Test explícito. |
| D14 | **«Otra clase de historia» con las intenciones de hoy:** el acto 2 diría igual «romper la regla». | «Otra» tiene **intenciones neutras** por acto (las de los nombres de pantalla: cómo empieza · se complica · el peor momento · qué hace después · cómo termina; corto: empieza · qué pasa · termina) y el Planificador recibe el arco del autor en un bloque propio. |
| D15 | El secreto (`historia_secreta`) está atado en el código al acto `revela_secreto` (`planner.py:119`). | Cada forma declara **su criterio de revelación** (`revela: {criterio, texto}`): regla → `historia_secreta` (el fragmento de hoy), asedio → la causa, etc. El acto sigue siendo `revela_secreto` de la estructura. |
| D16 | Una forma o un giro que se borra del catálogo con historias que lo usan. | Cae a «Alguien rompe una regla» / sin giro, con log. Test. |

### 5.2 Núcleo: el molde (S1)

**Nuevo** `src/application/services/authoring/molde.py`: `Molde.for_story(story)` → `criterios` (base + forma + giro, con su acto por estructura), `intencion(n)` (la de la forma o, si la forma no trae, la de `llm_beats_definition.yaml`), `reglas` (las de la forma y el giro para el Planificador), `revela` (D15), `arco` (D14). Carga y valida `config/moldes/formas.yaml` e `ingredientes.yaml` al arrancar (falla temprano si falta un campo), como `Estructura`.

| Lugar | Cambio | Bug que se evita |
|---|---|---|
| `config/moldes/formas.yaml` (nuevo) | Base (5 criterios: los de hoy `meta`, `inquietud`, `en_juego`, `reaccion`, `final`), forma `regla` (= `vulnerabilidad`, `transgresion`, `historia_secreta`, `descubrimiento`, **sin** intenciones propias → las de hoy) y las demás | — |
| `config/workshop_criteria.yaml` | Pasa a ser el **banco de criterios** (todos, con id único); qué criterios usa cada forma lo dice `formas.yaml` | Dos criterios con el mismo id en formas distintas |
| `catalog.py` | `criterion(id)` busca en todo el banco; `direction_criteria()` queda solo para «regla» (compatibilidad) | Un criterio de otra forma «desconocido» → 404 al responder |
| `workshop_rules.initial_items`, `context.decisions/pending_block`, Consultor, `_state` | Por `Molde.criterios` (D11) | Respuestas ocultas en los prompts |
| `planner._acts_block`, `outline_narrator._function` | `Molde.intencion(n)`; secreto según `revela` (D15) | El acto 2 de un asedio pidiendo «romper la regla»; la Voz recibe la intención del acto, así que también cambia ahí |
| `authoring_planner_system.md` | `{reglas_forma}` al final de las reglas; vacío para «regla» sin giro | — |
| `Direction` (dominio) + `DirectionForm` + `_direction` / `_form` | `form`, `ingredient`, `form_other`, `form_suggested`, `form_reason` (D13) | — |
| YAML export / import | Viajan dentro de `direction` (el exportador ya la vuelca entera); un YAML viejo = regla | — |

**Precaución de S1:** con forma «regla» y sin giro, los snapshots `pipeline`, `voice`, `assistant` (largo y corto) quedan **byte a byte iguales**. Snapshots nuevos: `assistant_prompts_asedio.json` y `voice_prompts_asedio.json` (largo y corto) con su test de secciones (no aparece «romper la regla» ni «transgresión»). Tests nuevos: completitud del catálogo (cada forma y giro, en las dos estructuras), **tope de preguntas** (D10: todas las combinaciones ≤ 9 sin giro, ≤ 10 con giro), D11, D16.

### 5.3 Contenido del catálogo (S2)

Las 4 formas nuevas + «Otra» (D14) y los 6 giros, con sus criterios (nombre, pregunta para la IA, «para qué sirve»), lo que pide cada acto (largo y corto) y sus reglas. Cada texto se cruza con «¿Cómo lo cuenta?» y los efectos (memoria: reglas vs opciones). **Te lo paso para leer antes de seguir** (un documento con todo el contenido, sin código): es lo que más pesa en el resultado.

### 5.4 «No va en tu historia» (S3, D8 + D12)

| Lugar | Cambio | Precaución |
|---|---|---|
| `CriterionStatus` | `NO_APLICA = "no_aplica"` | La UI y los tests que recorren estados |
| Consultor: esquema y prompt | `estado` admite `no_aplica` con `motivo`, salvo en los criterios con la marca de rechazo (D12) | Que la IA marque «no va» lo que solo está flojo: el prompt pide que sea **contradicción** con la idea, no falta de datos |
| `merge_round`, `to_evaluate`, `finish` | `no_aplica` no se vuelve a evaluar; `finish` cuenta los de la forma: ≥ 2 → `mal_elegida` (con la sugerencia) | — |
| Planificador / Verificador | Bloque «LO QUE NO VA EN ESTA HISTORIA» (los `no_aplica` con su motivo): no se pide en ningún acto | Que el Planificador meta igual una transgresión |
| `PATCH …/workshop/{c}` `reopen` | Con la marca de D12 | — |

### 5.5 Sugerir la forma (S4, D1)

Job nuevo `suggest_form` (`JobKind`, runner en `authoring_jobs.py`, `estimated_seconds` en los perfiles, `mock_structured`), rol `consultor`. Prompt en `config/prompts_generation/authoring_form_*.md` con las formas del catálogo (nombre + arco) y la idea; salida `{forma, motivo, arco}` (`arco` solo si es «otra»). Guarda `form` (si la persona no eligió una), `form_suggested`, `form_reason` y, para «otra», `form_other`. La sala de la IA es el modal de siempre; al terminar, «Tu idea» se recarga.

### 5.6 La UI (S5)

| Lugar | Cambio |
|---|---|
| «Tu idea» (`direccion.ejs`, `asistente.js`) | «¿Qué clase de historia es?» (6 `.opcion-forge` con su línea) + «Que la IA lo sugiera» (job) + campo de «Otra»; «¿Le sumamos un giro?» (6 + «Sin giro») + «Sorprendeme» (entre los menos usados: `_state` trae cuántas historias usan cada giro); pistas de D10 |
| «Preguntas» (`_taller_contenido.ejs`) | Chips agrupados (de toda historia / de la forma / del giro), `no_aplica` en gris tachado con motivo y «Preguntármelo igual», nota de forma mal elegida, nota de respuestas guardadas de otra forma (D2), pistas de D10 |
| Guardianes | `sin-jerga`, `gramatica-visual`, `no-hardcoded-colors`; fixtures del asistente con `UPDATE_FIXTURES=1` (diff revisado) |
| E2E | Elegir forma y giro, sugerir (con el mock), cambiar de forma sin perder respuestas, «no va» y reabrir |

### 5.7 Cierre (S6)

Medición D7 (con aviso de costo y OK): la misma sinopsis con 3 moldes; las 5 historias del §1.2 con la forma sugerida (criterio 6). CLAUDE.md (el catálogo, cómo ampliarlo, D10), memoria, PR a `development`.

### 5.8 Slices

1. **S1 — El motor** con «regla» (= hoy) y «asedio» (para probar con la laguna). Sin UI: la forma se fija por API/YAML.
2. **S2 — El contenido** del resto del catálogo (documento para tu lectura antes del código).
3. **S3 — «No va en tu historia».**
4. **S4 — La IA sugiere la forma.**
5. **S5 — La UI** de «Tu idea» y «Preguntas».
6. **S6 — Medición y cierre.**

Cada slice cierra con tests en verde y dev mostrando el cambio. Dev sigue en todo-Claude hasta cerrar la prueba de la chispa.

---

## 6. TASKS (2026-10-10)

### S1 — El motor (regla = hoy + asedio)

- **T1.1** `config/moldes/formas.yaml` (base 5 criterios; `regla` sin intenciones propias; `asedio` con sus 4 criterios, intenciones largo/corto, reglas y `revela`) y `ingredientes.yaml` (vacío de contenido salvo uno para el test). `workshop_criteria.yaml` = banco con ids únicos (suma los de `asedio`). **Hecho cuando:** carga validada al arrancar; un campo que falta → error con el nombre del archivo y la pieza.
- **T1.2** `molde.py`: `Molde.for_story(story)` → `criterios`, `intencion(n)`, `reglas`, `revela`, `arco`; fallback D16. **Hecho cuando:** tests unitarios de cada método con regla, asedio, otra y forma inexistente.
- **T1.3** `Direction` (+ `form`, `ingredient`, `form_other`, `form_suggested`, `form_reason`), `DirectionForm`, `_direction` / `_form`, `update_direction` conserva lo de la IA (D13). **Hecho cuando:** test de que el autoguardado no borra `form_suggested` / `form_reason`.
- **T1.4** Taller por molde (D11): `catalog.criterion` sobre el banco, `initial_items`, `to_evaluate`, `context.decisions` / `decisions_block` / `pending_block`, Consultor, `_state`, `PATCH …/workshop/{c}` (criterio fuera del molde → 404). **Hecho cuando:** test: una respuesta de otra forma no aparece en ningún prompt ni en el estado.
- **T1.5** Planificador y Voz por molde: `_acts_block` y `_function` con `Molde.intencion`; secreto según `revela` (D15); `{reglas_forma}` en `authoring_planner_system.md`. **Hecho cuando:** snapshots de hoy **idénticos** (pipeline, voice, assistant; largo y corto) y snapshots nuevos de asedio (largo y corto) con su test de secciones (sin «romper la regla» ni «transgresión»).
- **T1.6** Tests de catálogo: completitud (cada forma/giro en las dos estructuras) y **tope** (D10). YAML round-trip con forma y giro; un YAML viejo = regla.
- **T1.7** Cierre: pytest, Vitest, Playwright, lint; dev: «La laguna oscura» con `form: asedio` puesto por API → «Armar los actos de nuevo» (en todo-Claude) y comparar con `scripts/research/chispa/laguna_gemma.json`.

### S2 — El contenido del catálogo

- **T2.1** Redactar `lugar`, `casa`, `senuelo`, `otra` (D14) y los 6 giros: criterios (nombre, pregunta, para qué sirve, acto), intenciones (largo y corto), reglas, `revela`; cruce con «¿Cómo lo cuenta?» y efectos.
- **T2.2** Documento para tu lectura (artifact) con todo el contenido, sin código. **Hecho cuando:** OK del usuario (o sus cambios).
- **T2.3** Cargarlo en `config/moldes/`; snapshots por forma; tope y completitud en verde.

### S3 — «No va en tu historia» (D8, D12)

- **T3.1** `CriterionStatus.NO_APLICA`; `merge_round` / `to_evaluate` / `finish` (`mal_elegida` con ≥ 2 de la forma).
- **T3.2** Consultor: esquema con `no_aplica` + motivo, salvo criterios con la marca de rechazo; prompt: solo si la idea lo **contradice**. Snapshot.
- **T3.3** `reopen` con marca (D12). Planificador y Verificador: bloque «LO QUE NO VA EN ESTA HISTORIA». Snapshots.
- **T3.4** Tests: no se vuelve a evaluar, reabrir impide otro «no va», `mal_elegida` con 2.

### S4 — La IA sugiere la forma (D1)

- **T4.1** `JobKind.SUGGEST_FORM`, runner, `estimated_seconds` en los 3 perfiles, `mock_structured`, prompt `authoring_form*.md` (+ snapshot).
- **T4.2** Guarda `form` (si no había), `form_suggested`, `form_reason`, `form_other` (si «otra»). **Hecho cuando:** test del runner con mock; prueba con el modelo del perfil activo sobre las 5 historias del §1.2 (se registra qué sugirió; criterio 6).

### S5 — La UI

- **T5.1** «Tu idea»: «¿Qué clase de historia es?» + «Que la IA lo sugiera» + «Otra»; «¿Le sumamos un giro?» + «Sorprendeme» (uso por giro en `_state`) + «Sin giro»; pistas D10.
- **T5.2** «Preguntas»: chips agrupados, `no_aplica` (gris, motivo, «Preguntármelo igual»), notas de forma mal elegida y de respuestas guardadas; pistas D10.
- **T5.3** Tests de vista, guardianes, fixtures (`UPDATE_FIXTURES=1` + diff), E2E (elegir, sugerir con mock, cambiar de forma sin perder respuestas, «no va» y reabrir).

### S6 — Medición y cierre

- **T6.1** Medición D7 (aviso de costo y OK antes).
- **T6.2** CLAUDE.md (catálogo, cómo ampliarlo, D10), memoria, PR a `development`.

## 7. Resultados

### S1 (2026-10-10)

- Forma de siempre: snapshots `pipeline`, `voice`, `assistant` (largo y corto) **idénticos**. Nuevo `moldes_asedio_prompts.json`; tope D10, D11, D13, D16 y YAML con tests.
- Prueba en dev (todo-Claude): copia de «La laguna oscura» con «Algo viene por nosotros» (`df046285…`), las respuestas que aplican copiadas (la del secreto pasó a «qué la empuja a venir»). Comparación con los actos de gemma en `scripts/research/chispa/` (`laguna_gemma.json` tiene hechos del usuario en los actos 2 y 3).
  - **Mejor:** escalada concreta y sin culpa inventada (la orilla → los peces muertos y la fábrica → el patio → rasca las paredes), detalles propios (la gallina más grande, los animales que callan de golpe, los galpones que siguen largando humo), el final abierto que pide la forma. El Verificador en Claude da avisos de continuidad muy precisos (cómo se va la criatura, qué sabe el padre).
  - **Sigue de manual:** «huellas enormes», «el brillo de unos ojos», «una sombra enorme». Es lo que deberían atacar los giros (S2).
  - Inventó personajes (madre, hermana): el Verificador lo marca.

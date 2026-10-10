# SPEC-670: Moldes de historia (forma + efecto + ingrediente)

**Fecha:** 2026-10-10
**Tipo:** SDD — épica (asistente, Planificador, Verificador, Voz, UI)
**Estado:** SPECIFY ✅ (2026-10-10: capas, b + c, D1–D7, catálogo inicial 5 + 6, sin pregunta abierta) · maquetas https://claude.ai/artifact/BRfXu1GVCxNSEZcfq5Cupm (esperando OK)
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
| **Base** | Criterios: qué quiere, algo raro desde el principio, qué puede perder, cómo termina. Reglas universales (hechos concretos, sin repetir sustos, nada se adelanta) | 1 |
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

---

## 4. SUCCESS CRITERIA

1. Las 5 formas y los 6 ingredientes están completos para largo y corto (test de completitud: criterios, lo que pide cada acto, reglas, textos de pantalla).
2. «Alguien rompe una regla» sin ingrediente = hoy: snapshots `pipeline/voice/assistant` (largo y corto) idénticos.
3. Con su forma, las historias del §1.2 dejan de chocar: «La laguna oscura» como «Algo viene por nosotros» no recibe preguntas de transgresión ni de un secreto personal, y su acto 2 no pide «romper la regla» (snapshot por forma).
4. Por historia, entre 7 y 9 preguntas (base + forma + ingrediente).
5. La IA sugiere una forma razonable para las 5 historias del §1.2 (prueba con el modelo del perfil activo; se registra qué sugirió).
6. Medición D7: con la misma sinopsis, 3 moldes dan escaletas distintas entre sí; lectura de las usuarias.
7. Guardianes en verde (`sin-jerga`, `gramatica-visual`, `test_prompts_fuera_del_codigo`, `sin-cinco-actos`…); pytest, Vitest, Playwright; dev con el cambio.

## BOUNDARIES

- **Always:** piezas en `config/`; maquetas antes de la UI; cada pieza con el error real que previene; lo de hoy intacto como valor por defecto.
- **Ask first:** corridas pagas; tocar el registro de la Voz; sumar formas o ingredientes fuera de los 5 + 6.
- **Never:** que la IA elija la forma sin que la persona la vea; migraciones; reglas que contradigan una opción de «¿Cómo lo cuenta?».

## OPEN QUESTIONS

- ¿Los nombres de las formas en pantalla son claros para las usuarias? Se validan con la maqueta.
- La prueba en curso (dev en todo-Claude) dirá si además conviene mover el Planificador (y el Consultor) a Claude; es independiente de esta spec.

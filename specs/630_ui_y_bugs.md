# SPEC-630: UI y bugs — segundo recorrido

**Fecha:** 2026-10-02
**Tipo:** SDD — mejoras de UI y corrección de bugs
**Estado:** SPECIFY — B1–B16 descriptos; D1–D4 y D8–D12 decididos; D5–D7 (visuales) se validan con maqueta
**Rama:** `feat/spec-630-ui-y-bugs` (desde `development`, `453cccb`)
**Extiende:** Spec-530 (asistente), Spec-550 (recorrido de la UI), Spec-580 (tono del sitio).

---

## ASSUMPTIONS

1. Mismo formato que la Spec-550: cada hallazgo entra como **B<n>** con lo que pasa hoy, la decisión (o las opciones, si falta decidir) y cómo se verifica. Las decisiones se toman de a grupos, con recomendación.
2. Datos descartables (2026-09-27): si algún hallazgo toca el esquema, se recrea la DB (`make dev-db`), sin migraciones.
3. El tono visible sigue la Spec-580 (voseo, sin jerga: `sin-jerga.view.test.ts`) y la gramática visual de la Spec-550 H9.
4. Cada checkpoint cierra con tests en verde y dev actualizado (`make dev-status`), con la URL de `storymaker.test` para validar.

---

## OBJECTIVE

Juntar en una spec los arreglos chicos de UI y los bugs que el usuario encuentra recorriendo dev, para implementarlos en slices cortos y llevarlos juntos a prod.

---

## 1. HALLAZGOS

### B1 — «Editar» no lleva siempre al mismo paso · **decidido**

**Qué pasa hoy (medido 2026-10-02):** según desde dónde se entra a editar una historia, se cae en un paso distinto del asistente, y eso confunde:

| Entrada | Archivo | Hoy cae en |
|---|---|---|
| «Editar» en Mis historias (galería) | `frontend/src/views/gallery.ejs:61` | 1 · Tu idea (`/direccion`) |
| «Editar» en la ficha de la historia | `frontend/src/views/historia.ejs:134` | 3 · Los actos (`/escaleta`) |
| Ruta vieja `/generar/cargar/:id` (redirección 301) | `frontend/src/routes/index.ts:26` | 1 · Tu idea (`/direccion`) |

**Decisión:** editar una historia existente **siempre** abre el paso **«3 · Los actos»** (`/asistente/{id}/escaleta`). Desde ahí los pasos de la barra (`_cabecera.ejs`) llevan a «Tu idea» y «Preguntas».

**Fuera de alcance (no cambia):**
- «Nuevo relato» (`/nuevo`) sigue empezando en «Tu idea»: la historia todavía no existe.
- Los pasos de la barra del asistente y el salto al terminar un análisis de la IA (`asistente.js`, `destino`) siguen como están: son navegación dentro del asistente, no «entrar a editar».
- Una historia sin actos (p. ej. recién importada) ya tiene su estado vacío en la escaleta (`escaleta.ejs:47`, «armar los actos»); no se agrega lógica de «caer en otro paso si no hay actos».

**Cómo se verifica:**
- Un único lugar arma la URL de edición (helper en el frontend, p. ej. `editarHref(storyId)`), usado por la galería, la ficha y la redirección de `/generar/cargar/:id`; así no se vuelven a separar.
- Test de vista (Vitest): el «Editar» de la galería y el de la ficha apuntan a `/asistente/{id}/escaleta`.
- Test de ruta: `/generar/cargar/:id` redirige a `/asistente/{id}/escaleta`.
- E2E: desde Mis historias → «Editar» → URL `/asistente/{id}/escaleta$`, con «Los actos» como paso actual.

### Hallazgos de la vista «Los actos» (lista del usuario, 2026-10-02)

Todos son de `frontend/src/views/asistente/escaleta.ejs` + `frontend/public/js/asistente.js`, salvo donde se indica. El usuario marcó en una captura: más ancho hacia la derecha (B3) y más separación entre la columna izquierda y la derecha (B4). Comentarios de Vale (usuaria final) en B9 y B10.

### B2 — «Sumarlo a los personajes» deja el aviso como ignorado · **bug**

**Qué pasa hoy:** el botón (`asistente.js:578`) hace dos llamadas: `POST …/characters` (con `kind: "sin_nombre"`) y `POST …/warnings/dismiss`. El aviso queda en «N avisos ignorados», como si el autor lo hubiera descartado, cuando en realidad **lo resolvió**. Además el personaje sumado **no queda marcado en «Quiénes están»** del acto donde apareció el aviso, y entra como «Sin nombre» aunque tenga nombre («Tío Rubén») y sin «qué es para» quien narra (dato que usa la Voz para los parentescos).

**Propuesta:** aplicar una sugerencia **resuelve** el aviso: se borra de la lista (no pasa a ignorados). El personaje queda en «Quiénes están» de ese acto. Ver D2.
- Backend: `POST …/outline/{n}/warnings/resolve` con `{key}` que quita el aviso (o lo marca `resolved`, sin mostrarse en ignorados). Ignorar sigue igual (Spec-550 H10).

### B3 — La vista de edición es angosta · **UI**

**Qué pasa hoy:** el contenido está limitado a `max-w-5xl` (64rem, `escaleta.ejs:40`) y la columna derecha a `18rem` (`lg:grid-cols-[1fr_18rem]`, `:122`): en una pantalla ancha sobra mucho espacio a la derecha.
**Propuesta:** ver D5.

### B4 — Las dos columnas del acto se pegan · **UI**

**Qué pasa hoy:** la izquierda («Qué quiere…», «Qué pasa», «Qué cambia») y la derecha («Dónde pasa», «Reglas», «Detalles que vuelven», «Lo que todavía es secreto», «Quiénes están») están separadas solo por `gap-6`; los botones «×» de los hechos quedan al lado de «Dónde pasa».
**Propuesta:** más espacio entre columnas (`gap-10`) y una línea divisoria sutil a la izquierda de la columna derecha (`border-l border-forge-border pl-8` en `lg`). La columna derecha con fondo apenas distinto es la alternativa si la línea no alcanza (se decide con la captura).

### B5 — Acciones que recargan la página y mandan el scroll arriba · **bug**

**Qué pasa hoy:** todas las acciones que no son autoguardado pasan por `run()` (`asistente.js:307`) → `reloadKeepingScroll()` → `location.reload()`. Intenta volver al scroll guardado, pero la página parpadea y en la práctica el scroll vuelve arriba. Afecta:

| Acción | Dónde | Línea |
|---|---|---|
| Ignorar / Volver a mostrar un aviso | Los actos | `:585`, `:589` |
| Sumarlo a los personajes | Los actos | `:578` |
| Sumar personaje (formulario) | Los actos | `:569` |
| Responder / decidir / reabrir una pregunta | Preguntas | `:339` |
| Al terminar un análisis de la IA sin cambiar de paso | todos | `:429` |

**Propuesta:** ninguna acción de la vista recarga la página: se actualiza solo la parte que cambió, sin mover el scroll ni el foco. Ver D4 (cómo). Al terminar un análisis de la IA sí se puede recargar (cambia todo y el modal ya tapa la página), pero volviendo al mismo lugar.

### B6 — «+ Lugar» no agrega el lugar a la lista; no se puede agregar más de uno · **bug**

**Qué pasa hoy:** el botón (`asistente.js:557`) muestra un único campo `scenario_new` debajo de la lista. Lo que se escribe se guarda como el lugar del acto (`actPayload`: `scenario: newScenario || value(form, "scenario")`), pero:
- No aparece como opción en la lista hasta recargar la página (la lista sale de `state.scenarios`).
- Hay un solo campo: escribir otro lugar **pisa** el anterior.
- Mientras el campo tenga texto, **gana siempre** sobre la opción elegida: elegir otro lugar de la lista no se guarda.
- El lugar nuevo no entra a `story.scenarios`: solo existe porque algún acto lo usa (`authoring_router._state`, `scenarios`), y desaparece si ningún acto lo elige.

**Propuesta:** «+ Lugar» abre un campo con «Agregar»; al confirmar (botón o Enter) el lugar se suma a la historia (`story.scenarios`, endpoint nuevo `POST …/scenarios`), aparece como opción **en todos los actos**, queda elegido en este y el campo se vacía para sumar otro.

### B7 — Poder borrar lugares, reglas y personajes · **UI**

**Qué pasa hoy:**
- **Reglas:** ya tienen «×» (`escaleta.ejs:174`) y se guardan al quitarlas. Se verifica que funcione y que se vea (con la lista vacía no hay ninguna «×» a la vista).
- **Lugares:** no hay forma de borrarlos.
- **Quiénes están:** no hay forma de borrar un personaje del elenco (solo desmarcarlo del acto).

**Propuesta:** cada lugar y cada personaje tiene un «×» chico al lado (no adentro de la opción, para no elegirla sin querer). Borrar pide confirmación con `ForgeConfirm` y dice en qué actos se usa; al borrar se quita de esos actos. Quien narra no se puede borrar. Ver D3.

### B8 — Agrupar «Lo que todavía es secreto» con «Se descubre en» · **UI**

**Qué pasa hoy:** el secreto (`:191`) y el combo «Se descubre en» (`:195`) van uno debajo del otro, con el mismo peso que el resto de la columna.
**Propuesta:** los dos dentro de una caja propia (borde y fondo suave, como el formulario de «+ Personaje»), con el combo en la misma línea del título de la caja: «Se descubre en [el Acto 4 ▾]».

### B9 — «Qué cambia» no se entiende · **UI** (comentario de Vale)

**Qué pasa hoy:** el título es «Qué cambia» y los dos campos no tienen rótulo visible (`aria-label` «Al empezar» / «Al terminar»): no se sabe qué hay que poner ni que es un antes → después.
**Datos:** `change_from` / `change_to` es cómo está el protagonista al empezar y al terminar el acto (la Voz recibe `change_to` como «cambio», el Verificador marca `sin_cambio` si son iguales).
**Propuesta (textos para aprobar, D6):**
- Título: «Cómo cambia {protagonista} en este acto».
- Pista: «Cómo está al empezar el acto y cómo queda al terminar: con miedo → decidida a volver».
- Rótulos visibles sobre cada campo: «Al empezar» y «Al terminar».

### B10 — Las opciones se confunden con los botones · **UI** (comentario de Vale)

**Qué pasa hoy:** las opciones compactas («Dónde pasa», «Quiénes están»; `.opcion-forge--compacta`) y los botones («+ Lugar», «+ Regla») tienen la misma forma: rectángulo con bordes redondeados. Aunque el color cambie, Vale los confunde.
**Propuesta:** las opciones compactas pasan a **píldora** (`rounded-full`), con borde y la marca de radio/casilla que ya tienen. Se distinguen de los botones (rectángulo) y de los chips de estado (píldora **sin borde** y sin marca). Actualiza la gramática visual de la Spec-550 H9 y su test (`gramatica-visual.view.test.ts`). Las tarjetas grandes de opción (Preguntas, Tu idea) quedan como están salvo que D7 diga otra cosa.

### B11 — Que todo lo que se edita en «Los actos» se guarde y llegue a la IA · **auditoría**

**Revisión inicial (2026-10-02, a completar en el slice):**

| Dato del acto | Se guarda | Planificador | Verificador | Voz |
|---|---|---|---|---|
| Cómo llega acá (`bridge`) | sí | — (lo genera) | sí | sí |
| Qué quiere (`goal`) | sí | — | sí | sí |
| Qué pasa (`events`) | sí | — | sí | sí |
| Qué cambia (`change_from/to`) | sí | — | **no** (solo la regla `sin_cambio`) | solo `change_to` |
| Dónde pasa (`scenario`) | sí, pero ver B6 | solo los de `story.scenarios` | sí (nombre) | sí (con descripción si la tiene) |
| Reglas del acto (`rule.applies_to_beat`) | sí | **no** | **no** | sí |
| Lo que todavía es secreto + se descubre en | sí | — | sí | solo el secreto |
| Quiénes están (`on_stage`) | sí | — | **solo la regla de elenco** (el LLM no lo ve) | sí |
| Personaje nuevo (nombre, qué es, tipo) | sí | sí (si hay más de uno) | elenco (nombres) | sí (parentescos) |
| Lugar nuevo | **a medias** (B6) | **no** (no está en `story.scenarios`) | — | sin descripción |

Huecos que hay que decidir (D8): las reglas del acto no llegan al Planificador ni al Verificador; el Verificador no ve «Qué cambia» ni «Quiénes están»; los lugares nuevos no llegan al Planificador. Según la máxima del pipeline, cada dato nuevo para la IA tiene que prevenir un error que se vio. Los que importan: rearmar los actos ignora las reglas que escribió el autor, y la revisión no puede avisar que una regla del acto se contradice con lo que pasa.

**Cómo se verifica:** un test por fila (integración del router + snapshot de prompts `assistant_prompts.json` para lo que se suma), y un E2E que edita cada campo de un acto, recarga y comprueba que quedó.

### B12 — «Vista» no suma: se va la ficha de la historia · **UI** (pedido del usuario)

**Qué pasa hoy:** «Vista» en Mis historias (`gallery.ejs:50`) abre la ficha (`/historia/{id}`, `historia.ejs`): un resumen de solo lectura (tipo de horror, quién lo cuenta, personajes, lugares, reglas, de qué trata) con los mismos botones que ya tiene la tarjeta de la galería. «Editar» alcanza. Otros accesos a la ficha:

| Acceso | Archivo |
|---|---|
| «Vista» en Mis historias | `frontend/src/views/gallery.ejs:50` |
| «Ver historia» en la sala de generación | `frontend/src/views/streaming-room.ejs:75` |
| «Ver Historia Completa» al terminar un relato | `frontend/src/views/partials/streaming_done_panel.ejs:9` |
| «Ver historia» al cancelar un relato | `frontend/public/js/streaming-room.js:286` |
| La banda de generación cuando un job falla | `frontend/public/js/generation-banner.js:104` |

**Decisión (D9):** la ficha **se va del todo**.
- Se borran `historia.ejs` y su controlador de página (quedan `POST /historia/{id}/generar`, `/historia/{id}/relatos/…` y el borrado).
- `GET /historia/{id}` **redirige**: a «Los actos» (el helper de B1) o, si hay un relato escribiéndose, a la sala (`/generar/stream/{id}`), para que los links viejos sigan andando.
- «Vista» sale de la galería.
- «Ver Historia Completa» (relato terminado) → **«Ver relato»** (`/historia/{id}/relatos`).
- «Ver historia» de la sala y del cancelar, y la banda cuando falla → **«Editar»** (helper de B1).
- B1 queda con dos entradas de edición (galería y la ruta vieja `/generar/cargar/:id`), más la redirección de `/historia/{id}`.

**Cómo se verifica:** test de vista (ningún link a `/historia/{id}` a secas en vistas ni en `public/js`), test de ruta de la redirección (con y sin job activo), y se ajustan los E2E que pasaban por la ficha (`generation-guard`, `generation-banner`, `estimates`, `streaming-room`, `visual-snapshots`…).

### B13 — Las pestañas de versiones repiten el nombre de la historia · **UI**

**Qué pasa hoy:** en «El relato» (`/historia/{id}/relatos`, `relatos.ejs:28`) cada pestaña de versión muestra el título del relato (el de la historia) y abajo la fecha; el panel repite el título como encabezado (`relato_panel.ejs:41`). Todas dicen lo mismo y el título ya está arriba de la página («Relatos de …»).
**Decisión (D10):** la pestaña dice solo **«Versión del dd/mm/yyyy hh:mm»** (hora de Buenos Aires, como hoy). El encabezado del panel se va: las acciones suben (B15) y el panel queda con la prosa.

### B14 — Mis historias no dispara generaciones · **UI**

**Qué pasa hoy:** cada tarjeta de Mis historias (`gallery.ejs:67–104`) tiene «Regenerar» (relato terminado), «Reintentar» (falló) y «Generar relato» (borrador). Escribir desde ahí es a ciegas: quien arma la historia siempre quiere repasar los actos antes.
**Decisión (D11):** salen **los tres**. La tarjeta queda para entrar: «Editar», «Ver relato», «Para el video», «Ver avance» (en curso o fallido) y «Borrar». Se escribe desde «Los actos» («Escribir el relato») o desde «El relato» («Escribir de nuevo», B15). `POST /historia/{id}/generar` queda solo si lo usa otra vista; si no, se borra.
**Cómo se verifica:** test de vista de la galería (ningún `data-generation-trigger` en las tarjetas) y ajuste de los E2E que generaban desde la galería (`generation-guard`, `estimates`…).

### B15 — Las acciones del relato, agrupadas arriba · **UI**

**Qué pasa hoy:** «Descargar .md», «Corregir el relato», «Armar el guion para el video» / «Para el video» y «Copiar Relato» están dentro del panel de cada versión (`relato_panel.ejs:42–84`), mezcladas con la prosa y dentro del scroll del panel. No hay forma de escribir la historia completa de nuevo desde esta vista.
**Decisión (D12):** un **panel de acciones arriba de todo**, entre el título de la página y las pestañas de versiones, con todo agrupado:
- **«Escribir de nuevo la historia completa»** (job `full_generation`, crea una versión nueva): confirmación con `ForgeConfirm` y el tiempo estimado (`estimate.ejs`).
- De la **versión elegida**: «Corregir el relato», «Armar el guion para el video» / «Para el video», «Descargar .md» y «Copiar relato». Cambian al cambiar de pestaña (`relatos.js`) y se deshabilitan mientras se regenera un acto de esa versión, como hoy.
- «Regenerar» de cada acto **queda como está**, al lado del título del acto.
- La barra fija arriba tiene solo los pasos (B16).

### B16 — «El relato» no deja volver a los pasos anteriores · **bug**

**Qué pasa hoy:** «Tu idea», «Preguntas» y «Los actos» tienen la barra fija con los cuatro pasos (`_cabecera.ejs`), y el 4 («El relato») lleva a `/historia/{id}/relatos`. Pero esa vista no tiene la barra: solo «Volver a Galería» (`relatos.ejs:12`). Se entra al paso 4 y no se puede volver al 3.
**Decisión:** «El relato» lleva la misma barra fija (`.asistente-barra` + `_cabecera.ejs` con `pasoActual: 'relato'`), con los pasos 1–3 como links. «Volver a Galería» se va (Mis historias está en el menú). «Corregir el relato» y «Para el video» siguen con su «Volver a los relatos».
**Cómo se verifica:** test de vista (la barra con los cuatro pasos y «El relato» actual) y E2E: desde «El relato» → «Los actos».

---

## 2. DECISIONES

| # | Decisión | Estado | Fecha |
|---|---|---|---|
| D1 | B1: editar una historia existente abre siempre «3 · Los actos» (`/escaleta`), desde cualquier entrada | decidido | 2026-10-02 |
| D2 | B2: «Sumarlo a los personajes» es **un clic**: suma el personaje (tipo «Con nombre», sin «qué es para»; se completa después si hace falta), lo marca en «Quiénes están» del acto y el aviso se borra (no pasa a ignorados) | decidido | 2026-10-02 |
| D3 | B7: se puede borrar **cualquier** lugar o personaje (hoy no se distingue quién lo sumó), con `ForgeConfirm` que dice en qué actos se usa; al borrar se quita de esos actos. Quien narra no se borra | decidido | 2026-10-02 |
| D4 | B5: sin recargar → el Express renderiza la tarjeta de un acto como fragmento (`_acto.ejs`, ruta interna) y `asistente.js` reemplaza solo esa tarjeta; las opciones compartidas (lugares, personajes) se actualizan en las otras tarjetas sin tocar sus campos. En Preguntas, lo mismo con la tarjeta de la pregunta | decidido | 2026-10-02 |
| D5 | B3: ancho → **recomendado:** usar todo el ancho disponible hasta ~96rem (`max-w-screen-2xl`), columna derecha de `24rem`; los textos largos (encabezado) siguen en `max-w-3xl` para leerse bien | a decidir | |
| D6 | B9: textos de «Qué cambia» | a aprobar | |
| D7 | B10: píldora con borde → **recomendado:** solo opciones compactas; las tarjetas grandes de Preguntas y Tu idea quedan | a decidir | |
| D9 | B12: la ficha de la historia se va del todo; `/historia/{id}` redirige a «Los actos» (o a la sala con un relato en curso); los «Ver historia» pasan a «Editar» y el del relato terminado a «Ver relato» | decidido | 2026-10-02 |
| D10 | B13: la pestaña de cada versión dice «Versión del dd/mm/yyyy hh:mm»; el panel pierde el encabezado | decidido | 2026-10-02 |
| D11 | B14: Mis historias no dispara generaciones: salen «Regenerar», «Reintentar» y «Generar relato» | decidido | 2026-10-02 |
| D12 | B15: panel de acciones arriba de las versiones (no en la barra fija): «Escribir de nuevo la historia completa» + las de la versión elegida; «Regenerar» por acto queda igual. B16: la barra fija con los pasos también en «El relato» | decidido | 2026-10-02 |
| D8 | B11: se llenan los tres huecos: reglas del acto al Planificador (al rearmar) y al Verificador; «Qué cambia» y «Quiénes están» al Verificador; lugares nuevos al Planificador (por B6 quedan en `story.scenarios`). Snapshot `assistant_prompts.json` actualizado a propósito, con test por sección nueva | decidido | 2026-10-02 |

---

## 3. CRITERIOS DE ÉXITO

- [ ] B1: las tres entradas de edición llevan a `/asistente/{id}/escaleta`, armadas desde un solo helper.
- [ ] B2: aplicar «Sumarlo a los personajes» no deja el aviso en ignorados y marca al personaje en el acto.
- [ ] B5: ninguna acción de «Los actos» ni de «Preguntas» recarga la página; el scroll y el foco quedan donde estaban (E2E que mide `scrollTop` antes y después).
- [ ] B6/B7: se suman varios lugares seguidos y aparecen en todos los actos; lugares, reglas y personajes se pueden borrar.
- [ ] B3/B4/B8/B9/B10: validado con capturas en `storymaker.test` (las dos paletas; `palette-contrast` y `gramatica-visual` en verde).
- [ ] B11: tabla completa, cada fila con su test; snapshots actualizados a propósito.
- [ ] B12: no queda ningún acceso a la ficha; `/historia/{id}` redirige.
- [ ] B13–B16: pestañas «Versión del …»; la galería sin botones de generar; acciones del relato arriba; desde «El relato» se vuelve a los pasos 1–3.
- [ ] Tests en verde (`make lint`, `make test`, `cd frontend && npm test`, Playwright) y dev reflejando los cambios.

---

## 4. PLAN

*(Se arma con las decisiones D2–D8.)*

## 5. TASKS

*(Después del OK del plan.)*

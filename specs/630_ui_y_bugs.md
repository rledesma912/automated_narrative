# SPEC-630: UI y bugs — segundo recorrido

**Fecha:** 2026-10-02
**Tipo:** SDD — mejoras de UI y corrección de bugs
**Estado:** IMPLEMENT — S1 y S2 ✅ (2026-10-02); sigue S3. Plan aprobado sin maqueta (D5–D7 con lo recomendado)
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
- **«Escribir de nuevo la historia completa»** (job `full_generation`, crea una versión nueva): lleva a la sala con `?regenerate=1`, que ya pide confirmación con el tiempo estimado (Spec-219), igual que «Escribir el relato» de «Los actos».
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
| D5 | B3: todo el ancho disponible hasta `max-w-screen-2xl` (96rem), columna derecha de `24rem`; el encabezado sigue en `max-w-3xl`. B4: `lg:gap-10` + línea divisoria (`border-l`) a la izquierda de la columna derecha. B8: caja con borde y fondo suave | decidido (sin maqueta, a pedido del usuario) | 2026-10-02 |
| D6 | B9: título «Cómo cambia {protagonista} en este acto», pista «Cómo está al empezar el acto y cómo queda al terminar: con miedo → decidida a volver» y rótulos visibles «Al empezar» / «Al terminar» | decidido | 2026-10-02 |
| D7 | B10: píldora con borde solo en las opciones compactas; las tarjetas grandes de Preguntas y Tu idea quedan | decidido | 2026-10-02 |
| D9 | B12: la ficha de la historia se va del todo; `/historia/{id}` redirige a «Los actos» (o a la sala con un relato en curso); los «Ver historia» pasan a «Editar» y el del relato terminado a «Ver relato» | decidido | 2026-10-02 |
| D10 | B13: la pestaña de cada versión dice «Versión del dd/mm/yyyy hh:mm»; el panel pierde el encabezado | decidido | 2026-10-02 |
| D11 | B14: Mis historias no dispara generaciones: salen «Regenerar», «Reintentar» y «Generar relato» | decidido | 2026-10-02 |
| D12 | B15: panel de acciones arriba de las versiones (no en la barra fija): «Escribir de nuevo la historia completa» (va a la sala, que ya confirma con el tiempo estimado) + las de la versión elegida; «Regenerar» por acto queda igual. B16: la barra fija con los pasos también en «El relato» | decidido | 2026-10-02 |
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

Siete slices. Cada uno cierra con tests en verde (`make lint`, `make test`, `cd frontend && npm test`, los E2E que toca) y dev actualizado (`make dev-status`), con la URL de `storymaker.test` y qué mirar. Sin cambios de esquema: `story.scenarios`, `personajes_full`, `rule` y `act_outline.warnings` ya existen (no hace falta `make dev-db`).

**Orden y por qué:**

```
S0 maqueta ─────────────────────────────┐ (cierra D5–D7, B4, B8, B15 visual)
S1 navegación (B1 B12 B13 B14 B16) ─────┤ independiente
S2 tarjeta del acto sin recargar (B5) ──┼─→ S3 personajes, lugares, avisos (B2 B6 B7)
                                        ├─→ S4 aspecto de «Los actos» (B3 B4 B8 B9 B10)  ← S0
S5 acciones del relato (B15) ← S0, S1 ──┤
S6 datos a la IA (B11) ← S3 ────────────┘
```

S2 va antes que S3 y S4 porque extrae la tarjeta a un partial: S3 la vuelve a pedir después de cada acción y S4 cambia su aspecto en un solo lugar. S6 va después de S3 porque los lugares nuevos recién llegan a `story.scenarios` con B6.

### S0 — Maqueta visual · **descartado** (2026-10-02: el usuario no necesita validar maquetas; D5–D7 con lo recomendado)

Una maqueta interactiva (artifact HTML, `<meta charset="utf-8">`, las dos paletas «Papel» y «Latte» con los tokens reales de `theme.css`) con:
- una tarjeta de acto real (datos de «Susana» de la captura) en dos anchos (D5: `max-w-screen-2xl` + columna derecha `24rem` contra el actual);
- la separación entre columnas (B4: línea divisoria contra fondo distinto);
- la caja del secreto con «Se descubre en» (B8);
- «Cómo cambia Susana en este acto» con rótulos y pista (B9, D6);
- opciones compactas en píldora con borde, junto a botones y chips (B10, D7);
- el panel de acciones de «El relato» y las pestañas «Versión del …» (B13, B15).

**Sale:** D5, D6 y D7 decididos; B4, B8 y B15 con la variante elegida. Sin código del repo.

### S1 — Navegación: editar, la ficha, Mis historias y los pasos del relato (B1, B12, B13, B14, B16)

Todo en el frontend (Express + EJS), sin tocar el Core.
- **Helper de rutas** `frontend/src/utils/rutas.ts`: `editarHref(storyId)` → `/asistente/{id}/escaleta`. Se expone a las vistas en `app.locals.rutas` (`src/app.ts`, como `assetVersion`), y `public/js` arma la misma URL (un comentario apunta al helper; lo cubre el E2E).
- **B1:** `gallery.ejs` «Editar» → `rutas.editarHref(s.id)`; `/generar/cargar/:id` → 301 a `editarHref`.
- **B12:** se borran `views/historia.ejs`, `historiaPage` y `tests/unit/views/historia.view.test.ts`. `GET /historia/:storyId` pasa a `historiaRedirect` (`historia.controller.ts`): pregunta al Core `GET /api/v1/stories/{id}/jobs/active`; con un `full_generation` activo → `/generar/stream/{id}`, si no → `editarHref` (si el Core no responde, `editarHref`). Links: «Ver historia» de `streaming-room.ejs:75` y de `streaming-room.js:286` → «Editar»; «Ver Historia Completa» de `streaming_done_panel.ejs:9` → «Ver relato» (`/historia/{id}/relatos`); la banda (`generation-banner.js:104`) en estado fallido → `/asistente/{id}/escaleta`. «Vista» sale de `gallery.ejs:50`.
- **B13:** `relatos.ejs:28–40`: la pestaña dice «Versión del {fecha}»; se borra el `<h3>` de `relato_panel.ejs:41` (y `displayTitle`).
- **B14:** `gallery.ejs`: salen los tres `<form action="/historia/{id}/generar">`. `POST /historia/:id/generar` queda: lo usa la sala (`streaming-room.ejs:83`, «Regenerar» de un relato fallido).
- **B16:** `relatos.ejs` suma la barra fija (`.asistente-barra` + `include('asistente/_cabecera')` con `state: { story_id, status }` y `pasoActual: 'relato'`); `relatosPage` pasa `status`. Sale «Volver a Galería».

### S2 — La tarjeta del acto y la pregunta, sin recargar (B5, D4)

- **Partials:** la tarjeta de un acto sale de `escaleta.ejs` a `views/asistente/_acto.ejs` (entrada: `a`, `state`, `narrador`); la tarjeta de una pregunta de `taller.ejs` a `views/asistente/_pregunta.ejs`. Las vistas las incluyen igual que hoy: el HTML inicial no cambia (lo cubre un test de vista que compara contra el render actual).
- **Fragmentos (Express):** `GET /asistente/:storyId/fragmento/actos?n=2,3` (las tarjetas pedidas, o todas sin `n`) y `GET /asistente/:storyId/fragmento/taller` (el contenido del taller: preguntas abiertas y «Ya resuelto», porque responder mueve una pregunta de lugar). Los dos leen el estado del Core (`GET /api/v1/authoring/stories/{id}`) y responden HTML sin layout (`asistente.controller.ts`).
- **Cliente (`asistente.js`):** `run(action, { actos })` deja de recargar: `flushAll()` → `action()` → `refresh()`. `refresh` pide el fragmento, reemplaza el `<li>` de cada acto (`data-acto="{n}"`) y **ancla el scroll**: guarda el `getBoundingClientRect().top` de la tarjeta donde se hizo clic antes de reemplazar y corrige el `scrollTop` del contenedor después (sin salto ni parpadeo). El foco vuelve al control equivalente (por `data-*`) o, si ya no existe (un aviso resuelto), a la tarjeta (`tabindex="-1"`). `lucide.createIcons()` y `ForgeAsistente.init` sobre lo nuevo.
- **Cuáles se refrescan:** el acto del clic siempre; **todos** cuando cambia algo compartido (un personaje o un lugar que se suma o se borra). Como antes de cada acción corre `flushAll()`, reemplazar los otros actos no pierde lo escrito.
- **Al terminar un análisis de la IA** (`modal.done`, `:429`) sí se recarga (cambia todo), pero con el scroll bien restaurado: se diagnostica por qué hoy `restoreScroll` no vuelve (contenedor de scroll real; restaurar después del layout, en `requestAnimationFrame`) y se arregla.

### S3 — Personajes, lugares y avisos (B2, B6, B7, D2, D3)

**Core (`authoring_router.py`, cuerpo JSON como `warnings/dismiss`; 409 con un job activo, como el resto):**
- `POST …/outline/{n}/warnings/resolve` `{key}`: **quita** el aviso del acto (no pasa a ignorados); 404 si no existe.
- `POST …/characters` suma `act` opcional: además de agregar al elenco, lo marca en `on_stage` de ese acto (sin pisar el resto del acto).
- `POST …/characters/remove` `{name}`: lo saca de `personajes_full` y de `on_stage` de todos los actos; 422 si es quien narra; 404 si no está.
- `POST …/scenarios` `{name}`: lo suma a `story.scenarios` (sin duplicar, sin importar mayúsculas; `order_index` al final) y, con `act` opcional, lo deja elegido en ese acto.
- `POST …/scenarios/remove` `{name}`: lo saca de `story.scenarios` y vacía `scenario` en los actos que lo usan; 404 si no está.
- `_state` suma, para la confirmación, en qué actos se usa cada personaje y cada lugar (`characters[].acts`, `scenarios` como `[{name, acts}]`).
- Mensajes nuevos (si los hay) en `config/core_messages.yaml`, área `api` (Spec-620).

**Frontend (`_acto.ejs` + `asistente.js`):**
- **B2:** «Sumarlo a los personajes» = un clic: `POST …/characters {name, kind: "persona", act: n}` → `POST …/warnings/resolve {key}` → refresca todos los actos.
- **B6:** «+ Lugar» muestra un campo con botón «Agregar» (y Enter); `scenario_new` sale de `actPayload` (el lugar se elige siempre con la opción). Al agregar: `POST …/scenarios {name, act: n}` → refresca todos; el campo queda vacío y abierto para sumar otro.
- **B7:** un «×» chico (`.btn-forge-icono`, fuera de la `.opcion-forge`) al lado de cada lugar y de cada personaje (no en quien narra), con `ForgeConfirm.ask` («Se quita de los actos 1 y 3»); al confirmar, `…/remove` → refresca todos. Las reglas mantienen su «×».

### S4 — Aspecto de «Los actos» (B3, B4, B8, B9, B10) · según S0

- `escaleta.ejs` / `_acto.ejs`: ancho (D5), grilla `lg:grid-cols-[1fr_24rem] lg:gap-10` y separación de B4, caja del secreto (B8), «Cómo cambia {protagonista} en este acto» con pista y rótulos visibles `<label for>` (B9).
- `globals.css`: `.opcion-forge--compacta .opcion-forge__caja { rounded-full }` (B10); se actualiza el comentario de la gramática (Spec-550 H9) y el bloque «Gramática visual» de `CLAUDE.md`.

### S5 — Acciones del relato agrupadas arriba (B15, D12)

- `relatos.ejs`: un panel de acciones (`card-forge`) entre el título y las pestañas:
  - «Escribir de nuevo la historia completa» → `/generar/stream/{id}?regenerate=1` (el mismo camino que «Escribir el relato» de «Los actos»: la sala ya pide confirmación con el tiempo estimado, Spec-219), con `data-generation-trigger` para que se deshabilite si hay un job.
  - Un grupo por versión (`data-acciones-version="{id}"`, se ve solo el de la pestaña activa): «Corregir el relato», «Armar el guion para el video» / «Para el video», «Descargar .md», «Copiar relato».
- `relato_panel.ejs`: salen esas acciones (queda la prosa, los avisos y «Regenerar» por acto). Al regenerar un acto, la respuesta del panel trae el grupo de acciones de esa versión con `hx-swap-oob` (deshabilitado mientras se regenera, habilitado al terminar).
- `relatos.js`: `selectRelato` muestra el grupo de la versión; `copyRelatoContent` sigue copiando solo `[data-copy-part]` del panel de esa versión.

### S6 — Que todo llegue a la IA (B11, D8)

- **Verificador** (`verifier._act_text`, fragmentos nuevos en `fragments/asistente/verificador/acto/`): `cambia.md` («Cómo cambia: {de} → {a}»), `en_escena.md` («En escena: …»), `reglas.md` («Reglas de este acto: …»). `authoring_verifier.md`: una línea para que avise si un hecho contradice una regla del acto.
- **Planificador** (`planner._prompt`): `{reglas}` nuevo en `authoring_planner.md` con `fragments/asistente/planificador/reglas.md` (las reglas por acto que puso el autor, para respetarlas al rearmar). Los lugares nuevos ya llegan por `{escenarios}` desde S3.
- `fragments/README.md`: qué fragmento llena cada hueco nuevo.
- Snapshot `assistant_prompts.json` regenerado a propósito (`SNAPSHOT_UPDATE=1`), y `test_el_snapshot_cubre_todas_las_secciones` con los marcadores nuevos. `pipeline_prompts.json` y `voice_prompts.json` **no cambian** (la Voz no se toca).
- **Auditoría de persistencia:** un E2E que edita cada campo de un acto (puente, qué quiere, hechos, cómo cambia, lugar, reglas, secreto + se descubre en, quiénes están), recarga y comprueba cada valor.

### Cierre

- `CLAUDE.md`: B1 (editar → «Los actos»), B12 (sin ficha), B14, B15/B16 en «Web & Streaming»; endpoints nuevos en «API Endpoints»; gramática de B10.
- Spec en DONE, PR a `development` (no a `main`).

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Reemplazar una tarjeta pisa un guardado pendiente | `flushAll()` antes de cada acción (ya lo hace `run`); los E2E esperan `data-pendiente` |
| El scroll igual salta al cambiar el alto de una tarjeta de arriba | se ancla en la tarjeta del clic, no en el `scrollTop` absoluto; E2E que mide la posición de la tarjeta antes y después |
| Borrar un lugar o personaje que usa otro acto sin que se note | la confirmación dice en qué actos; se quita de esos actos en la misma llamada |
| Los E2E que pasaban por la ficha o generaban desde la galería se rompen | se ajustan en S1 (lista en T1.7) |
| El Verificador marca más avisos con más datos | tope de 3 visibles por acto (ya existe); se mira con `evaluate_workshop.py --mock` y una corrida real en dev |

---

## 5. TASKS

Convención de tests: **pytest** en `tests/` (Core), **Vitest** en `frontend/tests/unit/`, **Playwright** en `frontend/tests/e2e/`.

### S0 — Maqueta
- [x] ~~T0.1–T0.2~~ descartadas: D5–D7 decididos con lo recomendado.

### S1 — Navegación · ✅ 2026-10-02

**Hallazgo al implementar (B14):** en un borrador, «Escribir el relato» de «Los actos» llevaba a la sala en modo lectura, sin botón para empezar; solo andaba porque los borradores se lanzaban desde la galería o la ficha. Ahora la sala acepta `?escribir=1` (`stream.controller.ts`: `startMode` para borrador o fallido, `regenerateMode` para terminado; `?regenerate=1` sigue andando) y en modo lectura un borrador ofrece «Escribir el relato». «Escribir el relato» de «Los actos» y «Regenerar» de la sala usan `?escribir=1`. La banda de un job fallido dice «Editar» (antes «Ver detalle», que abría la ficha).

- [x] T1.1 `utils/rutas.ts` con `editarHref`, expuesto en `app.locals.rutas`. **Test:** `tests/unit/utils/rutas.test.ts` (devuelve `/asistente/{id}/escaleta`).
- [x] T1.2 B1: «Editar» de la galería y la 301 de `/generar/cargar/:id`. **Tests:** `gallery.view.test.ts` («Editar» → `/escaleta`); `tests/unit/routes/editar.test.ts` (la 301 → `/asistente/{id}/escaleta`, con supertest como `generar-relato-retirado.test.ts`).
- [x] T1.3 B12: se borran `historia.ejs`, `historiaPage` y `historia.view.test.ts`; `historiaRedirect`. **Tests:** `tests/unit/routes/historia-redirect.test.ts` (sin job → `/escaleta`; con `full_generation` activo → `/generar/stream/{id}`; Core caído → `/escaleta`).
- [x] T1.4 B12: links de la sala, el panel de terminado, el cancelar y la banda. **Tests:** `tests/unit/views/sin-ficha.view.test.ts` (ningún `href="/historia/{id}"` a secas en `src/views` ni en `public/js`, como recorre `sin-jerga`); `streaming_done_panel` dice «Ver relato» → `/relatos`.
- [x] T1.5 B13 y B16: pestañas «Versión del …» y la barra con los pasos en `relatos.ejs`. **Tests:** `relatos.view.test.ts` (la pestaña no trae el título y sí «Versión del 02/10/2026 14:30»; la barra tiene los cuatro pasos, «El relato» con `aria-current="step"` y 1–3 como links; no hay «Volver a Galería»).
- [x] T1.6 B14: sin botones de generar en la galería. **Test:** `gallery.view.test.ts` (ninguna tarjeta, en ningún estado, trae `data-generation-trigger` ni `action="/historia/…/generar"`; reemplaza el caso de «Vista»).
- [x] T1.7 Ajustar E2E: `generation-guard`, `relatos`, `visual-snapshots` (pasaban por la ficha o «Vista»), `estimates`, `streaming-room`, `corregir-relato`, `relatos-regenerar` (los que generaban desde la galería: pasan a lanzar por la sala o por «Los actos»). **E2E nuevo** en `asistente.spec.ts`: Mis historias → «Editar» → `/asistente/{id}/escaleta$` con «Los actos» actual; desde «El relato» → paso 3 → «Los actos».
- [x] T1.8 Checkpoint: `make dev-status`; URLs para mirar (Mis historias, «El relato» de una historia con dos versiones).

### S2 — Sin recargar · ✅ 2026-10-02

**Cómo quedó (ajustes al plan):**
- Partials: `_acto.ejs` (la tarjeta), `_escaleta_contenido.ejs` (resumen + tarjetas) y `_taller_contenido.ejs` (todo el contenido de «Preguntas»: responder mueve la pregunta de sección, así que no alcanza con la tarjeta; en vez de `_pregunta.ejs`).
- Una sola ruta: `GET /asistente/:id/fragmento/(escaleta|taller)`, sin layout, `no-store`; 404 / 502.
- `asistente.js`: `run(action, { error, paso, actos, anclas, foco })` → `refresh()`. En «Preguntas» la pantalla se ancla en la pregunta que sigue (la respondida baja a «Ya lo tenés») y se conserva lo escrito sin mandar en las otras. Si la estructura cambió (p. ej. no había actos), cae a recargar.
- **Causa del scroll que volvía arriba** (medido en dev): `restoreScroll` corría con la página a medio armar y el navegador recortaba el `scrollTop` (se pedía 1480, quedaba en 475). Ahora se aplica en `load` + `requestAnimationFrame`; solo se usa al terminar un análisis de la IA.
- Ganchos: `data-acto` + `tabindex="-1"` en cada tarjeta, `data-resumen-actos`, `data-preguntas-contenido` (no `data-taller-…`: lo marca `sin-jerga`).

- [x] T2.1 Extraer `_acto.ejs` y `_pregunta.ejs`. **Test:** `tests/unit/views/asistente-partials.view.test.ts` (el render de `escaleta.ejs` y `taller.ejs` con un estado fijo es igual antes y después: se guarda el HTML actual como fixture en el primer commit del slice).
- [x] T2.2 Rutas de fragmento en `asistente.controller.ts`. **Tests:** `tests/unit/controllers/asistente.controller.test.ts` (devuelve solo los actos pedidos, sin layout; 404 si la historia no existe; el del taller trae abiertas y «Ya resuelto»).
- [x] T2.3 `run()` + `refresh()` con anclaje de scroll y foco en `asistente.js`; `data-acto` en cada `<li>`.
- [x] T2.4 Scroll al terminar un análisis de la IA (`restoreScroll` después del layout).
- [x] T2.5 **E2E** `tests/e2e/asistente-sin-recargar.spec.ts`: en el acto 4, «Ignorar», «Volver a mostrar» y «Sumar personaje» no navegan (`page.on('framenavigated')` no dispara) y la tarjeta queda a la misma altura (±4 px); en Preguntas, responder una pregunta no navega; después de un análisis con el mock, el scroll vuelve a donde estaba.
- [x] T2.6 Checkpoint en dev.

### S3 — Personajes, lugares y avisos
- [ ] T3.1 `warnings/resolve`. **Test:** `test_authoring_api.py::test_resolver_un_aviso_lo_quita` (desaparece, no queda `dismissed`; 404 con clave inexistente; 409 con job activo).
- [ ] T3.2 `characters` con `act` y `characters/remove`. **Tests:** `test_sumar_personaje_lo_marca_en_el_acto` (queda en `on_stage` del acto pedido, los otros no cambian); `test_borrar_personaje_lo_saca_de_los_actos` (sale del elenco y de todo `on_stage`; 422 con quien narra; 404 si no está).
- [ ] T3.3 `scenarios` y `scenarios/remove`. **Tests:** `test_sumar_lugares_varios` (dos seguidos quedan en `story.scenarios` y en `state.scenarios`; sin duplicar por mayúsculas; con `act` queda elegido); `test_borrar_lugar_vacia_los_actos` (sale de `story.scenarios` y del `scenario` de los actos que lo usaban); `_state` trae en qué actos se usa cada uno.
- [ ] T3.4 Frontend B2, B6, B7 en `_acto.ejs` + `asistente.js`. **Tests:** `tests/unit/views/escaleta.view.test.ts` (el «×» está al lado de cada lugar y personaje, no adentro de la opción, y no está en quien narra; no hay `scenario_new` en el payload: `actPayload` se prueba exportándolo en `window.ForgeAsistente` como `eta.js`).
- [ ] T3.5 **E2E** en `asistente.spec.ts`: «Sumarlo a los personajes» → el aviso no está ni visible ni en ignorados y el personaje queda marcado en ese acto; sumar dos lugares seguidos → aparecen en los cinco actos y el segundo queda elegido; elegir otro lugar de la lista se guarda; borrar un lugar y un personaje con confirmación → desaparecen de todos los actos; borrar una regla.
- [ ] T3.6 Checkpoint en dev.

### S4 — Aspecto de «Los actos»
- [ ] T4.1 Ancho, columnas y caja del secreto según S0.
- [ ] T4.2 «Cómo cambia {protagonista} en este acto», pista y rótulos visibles. **Test:** `escaleta.view.test.ts` (título con el nombre; `<label for="change-from-{n}">Al empezar</label>` y «Al terminar»).
- [ ] T4.3 Opciones compactas en píldora. **Test:** `gramatica-visual.view.test.ts` (la opción compacta es `rounded-full` con borde y marca; el chip sigue sin borde; el botón no es píldora).
- [ ] T4.4 `sin-jerga`, `no-hardcoded-colors` y `palette-contrast` en verde; capturas `CAPTURAS=630 npx playwright test visual-snapshots` en las dos paletas.
- [ ] T4.5 Checkpoint en dev con las capturas.

### S5 — Acciones del relato
- [ ] T5.1 Panel de acciones en `relatos.ejs` y salida de las acciones de `relato_panel.ejs`. **Tests:** `relatos.view.test.ts` (el panel está antes de las pestañas; un grupo por versión, visible solo el primero; «Escribir de nuevo la historia completa» → `/generar/stream/{id}?regenerate=1` con `data-generation-trigger`; el panel de la versión no trae Descargar/Corregir/Copiar y sí «Regenerar» por acto).
- [ ] T5.2 `hx-swap-oob` del grupo al regenerar un acto. **Test:** `relatos.controller.test.ts` (el fragmento del panel trae el grupo de esa versión, deshabilitado con `regenerating`).
- [ ] T5.3 `relatos.js`: cambiar de pestaña cambia el grupo. **E2E** en `relatos-switcher.spec.ts`: con dos versiones, pasar a la segunda muestra sus acciones y «Copiar relato» copia la segunda; `paquete-video.spec.ts` y `corregir-relato.spec.ts` entran por el panel nuevo.
- [ ] T5.4 Checkpoint en dev.

### S6 — Datos a la IA
- [ ] T6.1 Fragmentos del Verificador y línea de reglas en `authoring_verifier.md`. **Test:** `test_planner_verifier.py` (el acto en el prompt trae «Cómo cambia», «En escena» y las reglas del acto; sin datos, no aparecen las líneas).
- [ ] T6.2 `{reglas}` del Planificador. **Test:** `test_planner_verifier.py` (las reglas por acto llegan al prompt; sin reglas, la sección no aparece; un lugar sumado por `POST …/scenarios` llega en `{escenarios}`).
- [ ] T6.3 `SNAPSHOT_UPDATE=1` de `assistant_prompts.json` y marcadores nuevos en `test_el_snapshot_cubre_todas_las_secciones`; `pipeline_prompts.json` y `voice_prompts.json` sin cambios; `test_prompts_fuera_del_codigo.py` en verde.
- [ ] T6.4 **E2E** `tests/e2e/escaleta-persistencia.spec.ts`: cada campo del acto, recarga y comprobación.
- [ ] T6.5 Una corrida real de «Que la IA lo revise» en dev con una historia con reglas, para ver que los avisos nuevos tienen sentido (sin costo: el Verificador es local).
- [ ] T6.6 Checkpoint en dev.

### Cierre
- [ ] T7.1 `CLAUDE.md` y `fragments/README.md`.
- [ ] T7.2 Suite completa en verde + `make dev-status`; spec en DONE; PR a `development`.

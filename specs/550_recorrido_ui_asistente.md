# SPEC-550: Recorrido de la UI — mejoras del asistente y del marco

**Fecha:** 2026-09-27
**Tipo:** SDD (Spec-Driven Development) — mejoras de UI
**Estado:** SPECIFY — H1–H10 decididos (2026-09-27); abierta a nuevos hallazgos; PLAN cuando el usuario cierre el recorrido
**Rama:** `feat/analisis-asistente-ui-logica`
**Extiende:** Spec-530 (asistente), Spec-531 (tema), Spec-540 (tema de dev).

---

## ASSUMPTIONS

1. El usuario recorre la UI en dev (`storymaker.test`, tema «Latte») y anota lo que quiere cambiar; cada hallazgo entra acá con su decisión (o como pendiente).
2. Los cambios de tema se hacen con los tokens `--forge-*` de `theme.css` y valen para **los dos temas** (confirmado): donde el usuario ve violeta (Latte, dev), en prod se ve el acento de «Papel» (rojo óxido). Ver D2.
3. Nada de colores fijos en vistas (tests `no-hardcoded-colors` y `palette-contrast`, ambas paletas AA ≥ 4,5:1).
4. Escala: 1–2 usuarios, escritorio; la UI tiene que seguir usable en una ventana angosta.

---

## OBJECTIVE

Juntar en un solo lugar las mejoras de UI que surgen del recorrido del usuario, decidir cada una y después implementarlas en slices.

---

## 1. HALLAZGOS

### H1 — «¿Cómo termina?» parece repetir «¿De qué trata?» · **decidido: opción 2**

**Lo que ve el usuario:** si la sinopsis ya cuenta el final, ¿para qué otro campo?

**Lo que hace hoy:** el campo, con «Es así a propósito» marcado, es un **candado**: el criterio «El final» del taller queda resuelto (`workshop_rules.py:44`), el Planificador reemplaza la función del Acto 5 por «cerrar la historia con el final que decidió el autor» (`planner.py:102`), el Verificador lo fuerza en el Acto 5 (`verifier.py:74`) y la Voz del Acto 5 lo recibe textual (`outline_narrator.py:126`). Sin el candado, el Acto 5 sigue la definición genérica («escape incompleto y secuela») y la IA tiende a volver inquietante un final en paz (Spec-530: 4 de 4 corridas). La sinopsis no tiene ese efecto: es material que la IA interpreta.

**Opciones:**
1. Explicarlo en pantalla («¿El final ya está decidido?» + qué pasa si lo escribís o lo dejás vacío).
2. **Escribirlo = decidirlo** (recomendada): sin casilla; con texto, el final está decidido; vacío, lo propone la IA.
3. Detectarlo en la sinopsis con la IA y confirmarlo con el usuario.

### H2 — Las opciones seleccionadas no se distinguen bien · **decidido**

**Lo que ve el usuario:** en las tarjetas de opción, la seleccionada apenas se diferencia (hoy: borde de acento y fondo de acento al 5 %).

**Cambio:** la opción seleccionada va con **fondo del acento y texto blanco** (`bg-forge-accent`, `text-forge-on-accent`), incluido el texto secundario de la tarjeta (descripción, ejemplo), que hoy es `text-forge-muted` y sobre el acento no se leería.

**Alcance** (todos los `peer-checked` de tarjetas; hoy 6 grupos):
- Dirección: efecto buscado y «¿cómo lo cuenta?».
- Taller: opciones de cada pregunta y «Escribir la mía» (con su campo de texto legible encima del acento).
- Escaleta: escenario y «en escena» (el escenario ya usa acento lleno; se unifica el estilo).

**Detalles:**
- Una clase compartida en `globals.css` (p. ej. `.opcion-forge`) en lugar de repetir las utilidades en cada vista.
- El foco con teclado sigue visible sobre la tarjeta seleccionada (anillo con separación: `ring-offset`).
- Hover de las no seleccionadas: borde de acento, sin llenar.

### H3 — Menú lateral más angosto y colapsable · **decidido**

**Lo que ve el usuario:** el menú ocupa mucho (hoy `--sidebar-width: 16rem`).

**Cambio:**
- **Más angosto:** `--sidebar-width` de 16rem a **13rem** (valor a ajustar con capturas).
- **Colapsable:** un botón en el menú lo reduce a una **tira de íconos** (~3.5rem): solo los íconos de navegación, con su nombre como `title`/`aria-label`; la marca queda en una inicial y la etiqueta DEV en un punto. Se vuelve a abrir con el mismo botón.
- **Recuerda el estado** por navegador (`localStorage`, envuelto en `try/catch`): conveniencia por usuario, no dato compartido. Se aplica antes de pintar (atributo en `<html>` desde un script chico en `<head>`) para que no parpadee al navegar con `hx-boost`.
- Un solo token manda el ancho: `--sidebar-width` (abierto) / `--sidebar-width-collapsed`; el menú y todo lo que depende de él lo leen de ahí.

**Hallazgo relacionado:** el pie de actividad está fijo con `left-56` (14rem) mientras el menú mide 16rem: se superpone 2rem sobre el menú y tapa su pie («DEV · rama · commit»). Pasa a usar `left-[var(--sidebar-width)]`, y así también acompaña al colapsar.

### H4 — Ficha de la historia: «Regenerar» y «Generar Relato» juntos · **decidido**

**Lo que ve el usuario:** en la ficha (`/historia/{id}`) de una historia con relato aparecen «Regenerar» y «Generar Relato», que parecen hacer lo mismo. Con un relato creado, solo debe verse **«Regenerar»**.

**Lo que hace hoy cada uno** (`historia.ejs:136–151`, solo con `status = completed`):
- **Regenerar** → job `full_generation`: la IA escribe los 5 actos de nuevo y guarda una **variante nueva** del relato (Spec-460).
- **Generar Relato** → `POST /historia/{id}/generar-relato` → `generate-narrative` del Core (`generate_from_existing_beats`): **no llama a la IA**; junta los actos ya escritos en otra variante titulada «Relato <fecha>». Como cada generación ya guarda su variante, el resultado es un **duplicado** de la última. Es un resto de antes de la Spec-460.

Como «Generar Relato» solo aparece cuando ya hay relato, la regla del usuario equivale a **sacarlo de la ficha**.

**Cambio:**
- Ficha: botones según el estado, excluyentes:

  | Estado | Botón principal |
  |---|---|
  | sin relato (`draft`, `pending`) | **Generar relato** |
  | falló (`failed`) | **Reintentar** |
  | con relato (`completed`) | **Regenerar** (+ «Ver Relatos» y «Editar», como hoy) |
  | generando (`processing`) | «Generando…» + «Ver progreso» (como hoy) |

- Se quitan del frontend el botón, la ruta `POST /historia/:id/generar-relato`, su handler (`generateNarrativeHandler`) y `generateNarrative()` de `core_api.service.ts` (no la usa nadie).
- El endpoint del Core `generate-narrative` **se queda**: lo usa el E2E de relatos para sembrar variantes (`relatos.spec.ts:18`).
- Texto: hoy el botón de una historia sin relato dice «Generar historia»; pasa a **«Generar relato»**, igual que en la Escaleta («Generar relato»).

### H5 — «Ver Relatos» en plural · **decidido**

**Lo que ve el usuario:** el botón de la ficha lleva al relato generado: tiene que ir en singular.

**Hoy:** la ficha dice «Ver Relatos» (`historia.ejs:155`) y la galería, para el mismo destino, «Ver Relato» (`gallery.ejs:75`). Los dos llevan a `/historia/{id}/relatos`, que muestra el relato (y, si se regeneró, sus otras versiones como pestañas, con la primera abierta).

**Cambio:** «**Ver relato**» en la ficha y en la galería (mismo texto en los dos lugares). La página de destino no cambia.

### H6 — El aviso de guardado: parpadear y desaparecer · **decidido**

**Lo que ve el usuario:** el aviso de la barra de arriba queda fijo («✓ Guardado hace un momento» / «Todo guardado»). Quiere que, al guardar, **parpadee unos instantes y después desaparezca**.

**Hoy:** `status()` de `asistente.js` reescribe `[data-guardado]` con tres estados: guardando (loader), ok («Guardado hace un momento») y error; el texto queda hasta el próximo cambio. Al cargar la página dice «Todo guardado» (o, en `/nuevo`, «Se guarda solo cuando escribas el título»).

**Cambio:**
- **Guardando…**: visible mientras dura el guardado, sin parpadeo.
- **Guardado**: aparece, **parpadea ~1,5 s** (2–3 pulsos de opacidad) y **se desvanece** (~0,5 s). Si llega otro guardado mientras tanto, la animación vuelve a empezar.
- **Error**: **no desaparece** (y no parpadea): queda hasta que un guardado salga bien. Perder un error de guardado sería peor que el ruido.
- **Al cargar:** sin aviso («Todo guardado» sobra: no pasó nada todavía). En `/nuevo` se mantiene «Se guarda solo cuando escribas el título» hasta el primer guardado, porque explica por qué no se guarda.
- **Sin saltos:** el aviso reserva su lugar (se oculta con opacidad, no con `display: none`), así los botones de la barra no se mueven.
- **Movimiento reducido:** con `prefers-reduced-motion`, sin parpadeo: aparece y se desvanece.
- **Accesibilidad:** sigue `aria-live="polite"`: el lector de pantalla anuncia «Guardado» aunque después se oculte.
- Animación con clases de `globals.css` (keyframes), sin colores nuevos.

**Tests:** los E2E que esperan «Guardado hace un momento» siguen valiendo (el texto queda en el DOM, oculto con opacidad); se agrega uno que verifica que tras unos segundos el aviso queda transparente y otro que un error queda visible.

### H7 — Taller: «Qué quiere» no dice de quién ni para qué · **decidido (textos aprobados)**

**Lo que ve el usuario:** el criterio «QUÉ QUIERE» no se entiende: no dice a quién se refiere ni qué objetivo cubre.

**Hoy** (`config/workshop_criteria.yaml`, la UI muestra `nombre` y `por_que`):
- Los nombres no tienen sujeto: «Qué quiere», «Qué está en juego», «Qué lo expone». El sujeto es el protagonista, pero no se dice.
- El «por qué importa» está en jerga («Una meta concreta le da a la amenaza algo que frustrar») y **solo** aparece en las preguntas abiertas: en «Ya resuelto» y en los chips del estado se ve el nombre suelto.
- Un criterio marcado «a propósito» sin respuesta muestra «Sin pregunta por ahora.», que no explica nada. (En «La presencia del colectivo», en dev, «Qué quiere» quedó así.)
- La pregunta que escribe la IA puede no nombrar al protagonista: el prompt pide preguntas «sobre esta historia», pero no que lo nombre.

**Cambio:**
1. **Nombres con sujeto**, usando el nombre del protagonista de la Dirección (si no hay, «el protagonista»):

   | Criterio | Hoy | Propuesto |
   |---|---|---|
   | `meta` | Qué quiere | **Qué busca José** |
   | `en_juego` | Qué está en juego | **Qué arriesga José** |
   | `vulnerabilidad` | Qué lo expone | **Qué expone a José** |
   | `historia_secreta` | La historia secreta | La historia secreta |
   | `final` | El final | El final |

2. **«Para qué sirve» en lenguaje llano, con ejemplos**, visible en las preguntas abiertas, en «Ya resuelto» y como `title` de los chips:

   | Criterio | Texto propuesto |
   |---|---|
   | `meta` | Lo que José quiere conseguir en esta historia: llegar a destino, cobrar el viaje, proteger a alguien. El miedo crece cuando la amenaza se interpone en eso. |
   | `en_juego` | Lo que José pierde si la amenaza gana: el trabajo, la cordura, a alguien querido. Si no arriesga nada, quien escucha no teme por él. |
   | `vulnerabilidad` | Algo que José hace o cree que lo deja a merced de la amenaza. Si le pasa por algo suyo, el miedo pesa más que si le pasa por azar. |
   | `historia_secreta` | Lo que no se ve al principio y explica por qué le pasa a José: un vínculo, una culpa, un secreto. |
   | `final` | Si el final deja en quien escucha la marca que buscás (el efecto de la Dirección). |

   En el YAML, `nombre` y `por_que` llevan `{protagonista}`, que la vista reemplaza.
3. **«A propósito» sin respuesta** dice «Lo dejaste así a propósito: la IA no lo va a preguntar.» en vez de «Sin pregunta por ahora.».
4. **Consultor:** una regla más en `authoring_consultant_system.md`: la pregunta nombra al protagonista por su nombre. Cambia el snapshot de prompts (`SNAPSHOT_UPDATE=1`, a propósito).

### H8 — Confirmaciones con el diálogo nativo del navegador · **decidido**

**Lo que ve el usuario:** al rearmar la escaleta aparece el `confirm()` del navegador («storymaker.test dice…»), fuera del tema. Lo quiere como componente de la UI, con el tema.

**Hoy hay dos confirmaciones nativas:**
- **Rearmar la escaleta** (Taller): `data-confirmar` → `window.confirm()` en `asistente.js:422`.
- **Regenerar un acto** (panel del relato): `hx-confirm` en `relato_panel.ejs:96`; HTMX usa `window.confirm()` por defecto.

Ya existe un modal con el tema, pero solo para borrar historias (`partials/modal_confirm.ejs`, servido por HTMX).

**Cambio:**
- **Un componente de confirmación** con el tema: partial en el layout + `public/js/confirm-dialog.js` (`window.ForgeConfirm.ask({ title, message, confirmLabel, tone }) → Promise<boolean>`, UMD testeable en Vitest como `eta.js`).
  - Sobre `<dialog>` nativo con `showModal()`: foco atrapado, `Esc` cancela, velo `--forge-overlay`, `aria-labelledby`/`aria-describedby`.
  - Tarjeta como el modal de borrar: ícono, título, mensaje, «Cancelar» y el botón de la acción («Rearmar la escaleta», «Regenerar el acto»). Tono `warning` para acciones que reemplazan contenido.
  - El foco arranca en «Cancelar» (lo seguro); al cerrar vuelve al botón que lo abrió.
- **Rearmar la escaleta:** `data-confirmar` usa `ForgeConfirm.ask`.
- **Regenerar un acto:** se intercepta `htmx:confirm` (`preventDefault` + `ask` + `issueRequest(true)`), así cualquier `hx-confirm` futuro usa el componente sin tocarlo.
- Nada de `window.confirm`/`alert`/`prompt` en el frontend: un test lo verifica (como `no-hardcoded-colors`).
- El modal de borrar historia queda como está (ya tiene el tema); unificarlo es opcional.

### H9 — No se distingue qué es chip, qué es botón y qué es nota · **decidido (se valida con capturas)**

**Lo que ve el usuario:** chips, botones y notas se confunden: no se sabe qué se puede tocar y qué solo informa.

**Por qué pasa:** casi todo es un **rectángulo recto con borde de 1 px**, y lo que cambia es poco y no es consistente:
- Los **botones secundarios** (`btn-forge-outline(-sm)`: «Decidí vos», «Es así a propósito», «Analizar de nuevo», «Editar») tienen borde gris y texto gris: se ven apagados, como una etiqueta.
- Los **chips de estado** (semáforo del Taller: «Qué quiere», «Falta», «A medias»; estado en la Galería: «Borrador», «Completada») son rectángulos con borde y fondo de color: se parecen a botones.
- Las **notas** usan tres formatos distintos: texto con 💡 (pistas de la Dirección y del Taller), texto con ⓘ («Quedan 4 preguntas abiertas»), y cajas con borde y fondo de aviso (avisos del Verificador en la Escaleta, «Repite 1 frase» en el relato —que además se despliega—, aviso de la sala).
- Las **tarjetas de opción** (radios) también son rectángulos con borde.

**Cambio — una gramática visual con tres familias, cada una con forma propia** (en `globals.css`, para los dos temas):

| Familia | Qué es | Forma | Color | Interacción |
|---|---|---|---|---|
| **Botón** | hace algo | rectángulo con **esquinas redondeadas** (`rounded-md`), alto fijo, ícono + verbo, MAYÚSCULAS como hoy | primario: **acento lleno**; secundario: **borde y texto de acento** (no gris); peligro: error lleno | cursor mano, hover y foco visibles, `active:scale` |
| **Chip** | dice un estado o una categoría | **píldora** (`rounded-full`), chica, texto normal (sin mayúsculas), punto de color del estado | fondo pálido del estado, **sin borde** | ninguna: sin hover, cursor normal; nunca es `<button>` |
| **Nota** | explica o avisa | **sin caja**: barra de color a la izquierda (`border-l-4`) + fondo pálido + ícono del tono; las pistas (💡) solo texto gris con ícono | tono `info` / `warning` / `error` / `pista` | ninguna; si tiene detalle desplegable, el que se toca es un **link** «Ver detalle», no la caja |

Las **tarjetas de opción** (radios) quedan como su propia cuarta forma: tarjeta con un **círculo de radio** visible a la izquierda (hoy solo lo tienen las del Taller) y seleccionada con el acento lleno (H2). Los **campos** siguen con borde y fondo de campo.

**Clases compartidas:** `.btn-forge*` (revisadas), `.chip-forge` + `--cumple|--parcial|--falta|--intencional|--info`, `.nota-forge` + `--info|--warning|--error`, `.pista-forge`. Las vistas dejan de armar estos estilos a mano (hoy: `taller.ejs:9–12` y `:68/:83`, `gallery.ejs:5–11`, `escaleta.ejs:96`, `relato_panel.ejs:106`, `streaming-room.ejs:156`, `debug.ejs:22–24`, las pistas de `direccion.ejs` y `taller.ejs:86`).

**Inventario a convertir:**

| Pantalla | Chips | Notas | Botones secundarios |
|---|---|---|---|
| Dirección | — | 5 pistas 💡 | — |
| Taller | semáforo del estado, estado de cada pregunta | «Quedan N preguntas» (ⓘ), pistas 💡 | Decidí vos, Es así a propósito, Analizar de nuevo, Cambiar, Que la IA lo vuelva a preguntar |
| Escaleta | «a revisar» / decisiones por acto | avisos del Verificador | Revisar con la IA, Descartar avisos, Sumar personaje |
| Ficha / Galería | estado de la historia | — | Editar, Ver relato, Eliminar |
| Relato | — | «Repite N frases» (con «Ver detalle») | Regenerar, Descargar .md, Copiar |
| Sala / Debug | ONLINE / OFFLINE | aviso de la sala, panel de error | Cancelar |

**Validación:** con capturas de las pantallas reales (Taller y Escaleta primero, en los dos temas) antes de convertir el resto. El catálogo `/componentes` se descartó (2026-09-27).

### H10 — Los avisos ignorados vuelven a aparecer al revisar de nuevo · **decidido**

**Lo que ve el usuario:** en la Escaleta, un aviso marcado «Ignorar» reaparece cuando se vuelve a revisar con la IA. Ignorado tiene que quedar ignorado.

**Por qué pasa:**
- «Ignorar» (`POST …/outline/{n}/warnings/dismiss`, `authoring_router.py:184`) **borra** el texto de `act_outline.warnings`; no queda registro de que el autor lo descartó.
- Cada revisión (`OutlineVerifier.verify`) **reescribe** la lista entera del acto: las reglas determinísticas (`rule_warnings`: siembras que nadie retoma, personajes fuera del elenco) vuelven a dar el mismo aviso, y el LLM vuelve a señalar lo mismo, a veces con otras palabras.

**Cambio:**
1. **Se guarda qué descartó el autor**, por acto. Sin cambio de esquema: la columna JSON `act_outline.warnings` pasa de lista de textos a lista de objetos `{text, key, source: "regla"|"ia", dismissed}` (se siguen leyendo los textos sueltos de hoy). Así no hace falta migrar la DB de prod.
2. **Avisos de regla:** cada uno lleva una clave estable por tema (p. ej. `siembra:<texto de la siembra>`, `elenco:<nombre>`). Un aviso descartado no vuelve mientras su clave siga igual. Si un aviso junta varias siembras, se arma solo con las que no se descartaron.
3. **Avisos de la IA:** el Verificador recibe los que el autor descartó en ese acto («el autor ya descartó estos avisos: no los repitas ni los reformules») —el mismo criterio que usa el Consultor con las preguntas ya hechas—, y además se filtran los que coincidan con uno descartado (texto normalizado).
4. **Se puede deshacer:** si un acto tiene avisos ignorados, un link discreto «N ignorados» los muestra (atenuados) con «Volver a mostrar».
5. **Cuándo se olvidan:** al **rearmar la escaleta** (actos nuevos, contenido nuevo) los descartes se borran; editar un acto o volver a revisar **no** los borra.
6. El máximo de avisos por acto (`MAX_WARNINGS_PER_ACT`) cuenta solo los visibles.

**Tests:** revisar dos veces con un aviso de regla descartado → no vuelve; con uno de la IA descartado → el prompt lo incluye y un aviso igual se filtra; «Volver a mostrar» lo restaura; rearmar la escaleta limpia los descartes; lectura de la lista vieja (solo textos). Cambia el snapshot de prompts (`SNAPSHOT_UPDATE=1`, a propósito).

---

## 2. DECISIONES

- **D1 (H1):** ✅ decidido (2026-09-27) — **escribirlo = decidirlo**: se quita la casilla «Es así a propósito»; con texto, el final queda fijo (`ending_intentional` se deriva de que haya texto); vacío, lo propone la IA. Las historias que hoy tienen final escrito sin la casilla pasan a tenerlo fijo (se avisa en el pase).
- **D2 (H2):** «fondo violeta con letras blancas» = **fondo del acento del tema + `on-accent`**: violeta en dev (Latte) y rojo óxido en prod (Papel). Confirmado por el usuario (2026-09-27): todos los cambios de UI de esta spec aplican a los dos temas, cada uno con sus colores.
- **D3 (H3):** ancho abierto 13rem, colapsado a íconos, estado recordado por navegador.
- **D4 (H4):** en la ficha, un solo botón de generación según el estado; «Generar Relato» (duplicaba la última variante sin IA) se quita del frontend; el endpoint del Core queda para los E2E.
- **D5 (H5):** «Ver relato» en singular, igual en ficha y galería.
- **D6 (H6):** el aviso «Guardado» parpadea ~1,5 s y se desvanece; «Guardando…» visible mientras dura; los errores quedan fijos; al cargar, sin aviso (salvo la ayuda de `/nuevo`).
- **D7 (H7):** ✅ decidido (2026-09-27) — criterios del taller con sujeto y «para qué sirve» en lenguaje llano, visibles en todos lados; **textos de las tablas de H7 aprobados** tal como están.
- **D8 (H8):** confirmaciones con un componente propio (`<dialog>` con el tema) para «Rearmar la escaleta» y todo `hx-confirm` (regenerar acto); sin diálogos nativos del navegador.
- **D9 (H9):** tres familias con forma propia — botón (redondeado, acento), chip (píldora, sin borde, sin interacción), nota (barra lateral de color, sin caja) — más tarjetas de opción con radio visible; clases compartidas en `globals.css`. Se valida con capturas de las pantallas reales antes de convertir todas las vistas; sin catálogo `/componentes`.
- **D10 (H10):** los avisos ignorados quedan ignorados al volver a revisar (claves estables para los de regla; los de la IA se le pasan al Verificador y se filtran); se pueden volver a mostrar; se olvidan solo al rearmar la escaleta. Sin cambio de esquema (JSON de `act_outline.warnings`).

---

## 3. CRITERIOS DE ÉXITO (parciales, se completan al cerrar el recorrido)

1. **H2:** en las 6 tarjetas, la opción elegida se ve con fondo de acento y todo su texto en `on-accent`; contraste ≥ 4,5:1 en Papel y Latte (texto principal y secundario); el foco con teclado se ve sobre una tarjeta elegida.
2. **H3:** el menú abierto mide 13rem; colapsado muestra solo íconos con nombre accesible; el estado sobrevive a recargar y a navegar (sin parpadeo); el pie de actividad arranca donde termina el menú, abierto o colapsado; nada del contenido queda tapado.
3. **H4:** una historia con relato muestra «Regenerar» y no «Generar Relato»; sin relato, «Generar relato»; fallida, «Reintentar»; `POST /historia/:id/generar-relato` ya no existe (404).
4. **H5:** ficha y galería dicen «Ver relato».
5. **H6:** al guardar, el aviso parpadea y a los ~2 s queda transparente sin mover la barra; un error de guardado queda visible; con movimiento reducido no parpadea.
6. **H7:** en el Taller, cada criterio dice de quién habla (nombre del protagonista) y para qué sirve, en las preguntas abiertas, en «Ya resuelto» y en los chips; las preguntas nuevas de la IA nombran al protagonista.
7. **H8:** rearmar la escaleta y regenerar un acto piden confirmación con el diálogo del tema (Papel y Latte); «Cancelar» y `Esc` no hacen nada; confirmar sigue el flujo de hoy; no queda `window.confirm`/`alert`/`prompt` en el frontend.
8. **H9:** en todas las pantallas del inventario, los botones, chips y notas usan las clases compartidas; ningún chip ni nota tiene hover ni es `<button>`; los botones secundarios usan el acento; capturas antes/después en los dos temas.
9. **H10:** un aviso ignorado no reaparece tras «Revisar con la IA» (ni de regla ni de la IA); «N ignorados → Volver a mostrar» lo restaura; rearmar la escaleta los limpia; las escaletas guardadas con el formato viejo se siguen leyendo.
10. Suite completa en verde y dev (`storymaker.test`) reflejando cada cambio (Spec-540 §2.5).

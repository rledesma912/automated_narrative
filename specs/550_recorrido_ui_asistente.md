# SPEC-550: Recorrido de la UI — mejoras del asistente y del marco

**Fecha:** 2026-09-27
**Tipo:** SDD (Spec-Driven Development) — mejoras de UI
**Estado:** SPECIFY — recorrido en curso: se van sumando hallazgos; PLAN cuando el usuario cierre el recorrido
**Rama:** `feat/analisis-asistente-ui-logica`
**Extiende:** Spec-530 (asistente), Spec-531 (tema), Spec-540 (tema de dev).

---

## ASSUMPTIONS

1. El usuario recorre la UI en dev (`storymaker.test`, tema «Latte») y anota lo que quiere cambiar; cada hallazgo entra acá con su decisión (o como pendiente).
2. Los cambios de tema se hacen con los tokens `--forge-*` de `theme.css` y valen para **los dos temas**: donde el usuario ve violeta (Latte, dev), en prod se ve el acento de «Papel» (rojo óxido). Ver D2.
3. Nada de colores fijos en vistas (tests `no-hardcoded-colors` y `palette-contrast`, ambas paletas AA ≥ 4,5:1).
4. Escala: 1–2 usuarios, escritorio; la UI tiene que seguir usable en una ventana angosta.

---

## OBJECTIVE

Juntar en un solo lugar las mejoras de UI que surgen del recorrido del usuario, decidir cada una y después implementarlas en slices.

---

## 1. HALLAZGOS

### H1 — «¿Cómo termina?» parece repetir «¿De qué trata?» · **pendiente** (el usuario lo deja para después)

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

---

## 2. DECISIONES

- **D1 (H1):** pendiente; el usuario lo retoma después. Recomendación: opción 2.
- **D2 (H2):** «fondo violeta con letras blancas» = **fondo del acento del tema + `on-accent`**. En dev (Latte) es violeta; en prod (Papel) es el rojo óxido. *A confirmar por el usuario:* ¿o quiere violeta también en prod?
- **D3 (H3):** ancho abierto 13rem, colapsado a íconos, estado recordado por navegador.
- **D4 (H4):** en la ficha, un solo botón de generación según el estado; «Generar Relato» (duplicaba la última variante sin IA) se quita del frontend; el endpoint del Core queda para los E2E.
- **D5 (H5):** «Ver relato» en singular, igual en ficha y galería.
- **D6 (H6):** el aviso «Guardado» parpadea ~1,5 s y se desvanece; «Guardando…» visible mientras dura; los errores quedan fijos; al cargar, sin aviso (salvo la ayuda de `/nuevo`).

---

## 3. CRITERIOS DE ÉXITO (parciales, se completan al cerrar el recorrido)

1. **H2:** en las 6 tarjetas, la opción elegida se ve con fondo de acento y todo su texto en `on-accent`; contraste ≥ 4,5:1 en Papel y Latte (texto principal y secundario); el foco con teclado se ve sobre una tarjeta elegida.
2. **H3:** el menú abierto mide 13rem; colapsado muestra solo íconos con nombre accesible; el estado sobrevive a recargar y a navegar (sin parpadeo); el pie de actividad arranca donde termina el menú, abierto o colapsado; nada del contenido queda tapado.
3. **H4:** una historia con relato muestra «Regenerar» y no «Generar Relato»; sin relato, «Generar relato»; fallida, «Reintentar»; `POST /historia/:id/generar-relato` ya no existe (404).
4. **H5:** ficha y galería dicen «Ver relato».
5. **H6:** al guardar, el aviso parpadea y a los ~2 s queda transparente sin mover la barra; un error de guardado queda visible; con movimiento reducido no parpadea.
6. Suite completa en verde y dev (`storymaker.test`) reflejando cada cambio (Spec-540 §2.5).

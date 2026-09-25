# SPEC-531: Tema claro único y favicon

**Fecha:** 2026-09-25
**Tipo:** SDD (Spec-Driven Development)
**Estado:** SPECIFY — borrador para revisar con el usuario
**Relación:** independiente de la Spec-530; conviene hacerla antes, porque las vistas nuevas del asistente se diseñan directamente sobre este tema.

---

## ASSUMPTIONS

1. **Se queda un solo tema, claro, diseñado para leer relatos largos.** Se descartan los oscuros porque no suman (pedido del usuario). Con un solo tema, el selector, la cookie `nf_theme` y `POST /theme` se eliminan.
2. **Los temas claros actuales (`earthy`, `light-contrast`) no se conservan como opciones.** El tema nuevo toma lo que sirva de ellos. Ver la pregunta abierta 1.
3. **El sistema de variables CSS (`--forge-*`) se mantiene.** Todo el frontend ya las consume vía Tailwind (`forge.bg`, `forge.text`…), así que cambiar el tema es sobre todo cambiar valores.
4. **Sin dependencias nuevas.** El favicon es un SVG hecho a mano, con PNG de respaldo generado una sola vez.

---

## OBJECTIVE

Que el sitio tenga **identidad propia en la pestaña del navegador** (favicon) y **un único tema claro, cálido y legible**, cómodo para leer relatos de ~2.500 palabras y para completar el asistente de autoría. Sin combinaciones de colores rotas en ninguna pantalla.

**Éxito:** todas las páginas se ven con el tema claro, sin restos oscuros; los textos cumplen contraste WCAG AA; el favicon aparece en la pestaña, en los marcadores y en el acceso directo del celular.

---

## 1. HALLAZGOS

| Hallazgo | Consecuencia |
|---|---|
| 3 temas en `frontend/config/themes.json`: `horror` (oscuro, **default**), `earthy` y `light-contrast` (claros). | Se reemplaza por un solo tema claro. |
| Selector de tema en `sidebar.ejs`, cookie `nf_theme` (`theme.middleware.ts`), `POST /theme` (`theme.controller.ts`), `theme.service.ts`. | Se simplifica: el tema es fijo y ya no hace falta servicio, cookie ni ruta. |
| `src/styles/theme.css` trae fallbacks oscuros y reglas `prefers-color-scheme` / `data-theme` (claro y oscuro). | Se deja una sola definición en `:root`, sin variantes oscuras. |
| 55 colores fijos fuera de las variables: `theme.css` (33), `guia.ejs` (13), `globals.css` (6), `home.ejs` (3), `modal_confirm.ejs`, `streaming_error_panel.ejs`, `wizard.ejs` (1 cada uno). | Se revisan uno por uno: pasan a variables o se justifican. `guia.ejs` tiene su propio tema oscuro embebido. |
| Cada tema define su fuente (`mono` en `horror`). | La fuente pasa a ser fija: ver §2.2. |
| No hay favicon (no hay `rel="icon"` ni archivo). | Se agrega. |

---

## 2. CAMBIOS PROPUESTOS

### 2.1 Paleta «Papel» (propuesta inicial, se ajusta con capturas)

| Variable | Valor | Uso |
|---|---|---|
| `--forge-bg` | `#f7f3ec` | Fondo: papel cálido, no blanco puro (cansa menos en lecturas largas). |
| `--forge-surface` | `#fffdf8` | Tarjetas y paneles. |
| `--forge-border` | `#e2d9c8` | Bordes suaves. |
| `--forge-text` | `#2b2620` | Texto: tinta (13,6:1 sobre el fondo). |
| `--forge-muted` | `#6f6454` | Texto secundario (5,2:1). |
| `--forge-accent` | `#8a2b1f` | Acento: rojo óxido, guiño al horror sin ser sangre (7,8:1; texto blanco sobre el acento: 8,6:1). |
| `--forge-error` / `-bg` / `-border` | `#a3261a` / `#f8e3df` / `#d9958a` | Errores. |
| Semáforo (Spec-530) | verde `#3f6b3a`, ámbar `#8a5d0f`, rojo = error, gris = muted | Se definen ya para que el asistente los use. |

### 2.2 Tipografía

- **Prosa de los relatos:** serif (Georgia, la que ya existe), 1,125 rem e interlineado 1,7.
- **UI** (menús, formularios, botones): sans del sistema.
- Se abandona `Courier New` como fuente general. Queda solo para bloques de código o de depuración.

### 2.3 Qué se quita

- `themes.json` queda con una entrada, o se elimina y los valores pasan a `theme.css`. Propuesta: **eliminarlo**, porque el tema deja de ser configurable.
- `theme.service.ts`, `theme.middleware.ts`, `theme.controller.ts`, la ruta `POST /theme`, el selector del sidebar y la cookie `nf_theme`.
- Las variantes `prefers-color-scheme: dark` y `html[data-theme=…]` de `theme.css`.
- El tema oscuro embebido en `guia.ejs`, que pasa a las variables. La Spec-530 puede rediseñar la guía después.

### 2.4 Favicon

- `frontend/public/favicon.svg` (un solo color de acento sobre transparente, legible a 16 px) más `favicon-32.png` y `apple-touch-icon.png` (180 px) generados una vez.
- En `layout.ejs`: `<link rel="icon" href="/favicon.svg" type="image/svg+xml">`, el PNG de respaldo, `apple-touch-icon` y `<meta name="theme-color" content="#f7f3ec">`.
- Motivo: ver la pregunta abierta 2.

---

## BOUNDARIES

- **Siempre:** usar solo las variables `--forge-*` en vistas y estilos (ningún color fijo nuevo); contraste AA verificado; capturas de todas las páginas antes y después.
- **Preguntar antes:** cambiar tamaños de fuente o el layout (esta spec es de color, tipografía e ícono).
- **Nunca:** dependencias nuevas; volver a introducir un tema oscuro por la puerta de atrás (p. ej. con `prefers-color-scheme`).

---

## TESTING

- **Vitest:** los tests de `css-architecture` (`styles-render`, `cutover-no-cdn`) y `relatos.controller.test.ts`, que referencian el sistema de temas, se actualizan. Un test nuevo verifica que el layout incluye el favicon y que no quedan `themeCssVars` ni el selector.
- **Test de colores fijos:** recorre `src/views` y `src/styles` y falla si aparece un color hexadecimal fuera de `theme.css`, salvo una lista explícita de excepciones justificadas.
- **Contraste:** script o test que calcula el contraste de cada par texto/fondo de la paleta (≥ 4,5:1).
- **E2E (Playwright):** recorre home, galería, ficha, wizard, sala y relatos; toma capturas; verifica que el favicon responde 200.

---

## SUCCESS CRITERIA

1. Un solo tema claro en todas las páginas, sin selector ni restos oscuros (incluida la guía).
2. Ningún color fijo fuera de `theme.css`, salvo las excepciones listadas.
3. Todos los pares texto/fondo ≥ 4,5:1.
4. El favicon se ve en la pestaña (SVG) y en iOS (apple-touch).
5. `npm test` y Playwright en verde; revisión visual del usuario sobre las capturas.

---

## PREGUNTAS ABIERTAS

1. **¿Se conserva `light-contrast` como opción de accesibilidad** (fondo blanco puro, más contraste), o un solo tema y listo? Propuesta: uno solo; si hace falta, el tema «Papel» ya cumple AA.
2. **Motivo del favicon:** ¿pluma, vela, libro abierto, un ojo, la inicial «N» de NarrativeForge? Propuesta: una vela, que se lee bien a 16 px y sugiere «historia contada de noche».
3. **Nombre en la pestaña:** hoy «NarrativeForge — …» y en prod el sitio es `storymaker.test`. ¿Se unifica el nombre?

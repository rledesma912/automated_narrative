# SPEC-531: Tema claro único y favicon

**Fecha:** 2026-09-25
**Tipo:** SDD (Spec-Driven Development)
**Estado:** IMPLEMENT — PLAN aprobado 2026-09-25 (un solo tema, favicon: vela)
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

---

## PLAN

**Estado:** aprobado (2026-09-25): un solo tema, sin `light-contrast`; favicon: vela.

### Estrategia

Primero la red de seguridad: capturas «antes» y tests que fallan con colores fijos. Después el tema, los colores fijos, la tipografía y el favicon, en ese orden. Cada slice deja la app andando y con los tests en verde.

### Hallazgos del relevamiento (complementan §1)

- **`guia.ejs` es huérfana:** ninguna ruta la sirve. Tiene su propio tema oscuro y un `<link>` a un `/css/style.css` que no existe.
- **Colores fijos por tipo:**
  - superposiciones `bg-black/60–80` (`modal_confirm.ejs`, `wizard.ejs`);
  - secciones oscuras `bg-black/30–50` y `border-white/5–10` en `home.ejs`;
  - `text-white` sobre el acento en 4 botones de `globals.css` y en el hover de error de `streaming_error_panel.ejs`;
  - `orange-*` de Tailwind en la advertencia de la sala (`streaming-room.ejs:156-158`), con las variables `--orange-*` de `theme.css` y `colors.orange` en `tailwind.config.js`;
  - `#b91c1c` en `globals.css:102-103`.
- **Tests atados al sistema de temas:**
  - `theme-vars.test.ts` recorre los 3 temas de `themes.json`;
  - `cutover-no-cdn.test.ts` exige `<%- themeCssVars %>` en el layout;
  - `styles-render.test.ts` y `relatos.controller.test.ts` pasan `themeCssVars` y `themeFont` como locals;
  - `build-succeeds.test.ts` y `config-loads.test.ts` verifican `colors.orange`.
- **Fuentes:** `themeFont` pone la fuente del `<body>` (hoy `mono` por el tema `horror`); los títulos ya usan `font-serif`.
- **Herramientas para los PNG del favicon:** Playwright ya está en el proyecto y puede renderizar el SVG, así que no hace falta nada nuevo. `convert` e `inkscape` existen en esta máquina, pero no en la imagen ni en CI.

### Decisiones técnicas

1. **La paleta vive solo en `src/styles/theme.css` (`:root`)**, compilada en `public/styles.css`. `layout.ejs` deja de inyectar variables: el `<style>` del head queda solo con lo que no es color (`--sidebar-width`, scrollbar con variables).
2. **Variables nuevas** para lo que hoy está fijo:
   - `--forge-overlay`: tinta al 55 %, para los modales;
   - `--forge-on-accent`: texto sobre el acento (`#ffffff`, 8,6:1);
   - `--forge-warning` y `--forge-warning-bg`: ámbar, para advertencias y el semáforo;
   - `--forge-success`: verde del semáforo.

   Se exponen en Tailwind como `forge.overlay`, `forge.on-accent`, etc.
3. **`colors.orange` y `--orange-*` se eliminan.** La advertencia de la sala pasa a `forge.warning`.
4. **Se elimina el sistema de temas:** `config/themes.json`, `theme.service.ts`, `theme.middleware.ts`, `theme.controller.ts`, la ruta `POST /theme`, el selector del sidebar y los locals `themeCssVars`, `themeFont`, `themeName`, `activeTheme` y `allThemes`. La cookie `nf_theme` que ya tengan los navegadores queda sin efecto; no hace falta borrarla.
5. **`guia.ejs` se elimina**, porque es código muerto. Si la Spec-530 necesita una guía, se diseña de cero sobre el tema.
6. **Tipografía:** `<body>` en sans del sistema (`font-sans`), títulos en serif como hoy, y la prosa de los relatos en serif con `leading-[1.7]` (`streaming-room.ejs` y `relato_panel.ejs`). `font-mono` queda solo en `debug.ejs`, en la terminal de la sala y en `home.ejs`, a revisar con las capturas.
7. **Favicon:**
   - `public/favicon.svg`, escrito a mano;
   - `scripts/build-favicons.ts` renderiza con Playwright `favicon-32.png` y `apple-touch-icon.png` (180 px, con fondo `--forge-bg`);
   - los PNG se commitean y el script queda para regenerarlos.
8. **Test de colores fijos (Vitest):** recorre `src/views/**/*.ejs`, `src/styles/*.css` y `public/js/*.js`. Falla ante `#hex`, `rgb(`, `bg-black`, `bg-white`, `text-white`, `border-white` y paletas de Tailwind (`orange-`, `gray-`, `red-`…) fuera de `theme.css`, salvo una lista de excepciones en el propio test, cada una con su motivo.
9. **Test de contraste (Vitest):** lee las variables de `theme.css` y verifica ≥ 4,5:1 para los pares texto/fondo que se usan (text, muted, accent, error, warning y success sobre bg y surface; on-accent sobre accent).

### Slices

#### S0 — Red de seguridad
- Script de capturas con Playwright (`tests/e2e/visual-snapshots.spec.ts`, no forma parte de la suite normal: se corre con `--grep @capturas`) sobre home, galería, ficha, wizard (paso 1 y paso 4), sala, relatos y el modal de confirmación. Genera las capturas «antes» en `test-results/531/antes/`.
- Tests de colores fijos y de contraste, **en rojo** (documentan lo que falta).
- **Verificación:** capturas generadas; los dos tests fallan por los motivos esperados.

#### S1 — Tema único «Papel»
- `theme.css`: paleta en `:root` (§2.1 + variables nuevas); se eliminan las variantes oscuras, `prefers-color-scheme` y `data-theme`.
- Se elimina el sistema de temas (decisión 4) y se ajusta `layout.ejs`.
- Tests: `theme-vars.test.ts` → reemplazado por el de contraste; `cutover-no-cdn`, `styles-render` y `relatos.controller` sin los locals de tema.
- **Verificación:** test de contraste en verde; `npm test` en verde, salvo el de colores fijos; capturas intermedias.

#### S2 — Colores fijos a variables
- Modales → `forge.overlay`; `home.ejs` → surface/border; `text-white` → `forge.on-accent`; advertencia de la sala → `forge.warning`; `#b91c1c` → `--forge-error`; se eliminan `colors.orange` y `--orange-*` (se actualizan `build-succeeds` y `config-loads`); se borra `guia.ejs`.
- **Verificación:** test de colores fijos en verde; `npm test` en verde.

#### S3 — Tipografía
- Body sans, prosa en serif con interlineado 1,7, y revisión de `font-mono` (decisión 6).
- **Verificación:** capturas; ninguna página con `Courier New` como fuente del cuerpo.

#### S4 — Favicon
- `favicon.svg`, script de PNG, `<link>` y `<meta name="theme-color">` en `layout.ejs`.
- Test: el layout incluye los `<link>`. E2E: `/favicon.svg`, `/favicon-32.png` y `/apple-touch-icon.png` responden 200 con el tipo correcto.
- **Verificación:** el favicon se ve en la pestaña (captura del navegador).

#### S5 — Cierre
- Capturas «después» y comparación lado a lado para el usuario.
- `make lint`, pytest, `npm test` y Playwright en verde.
- `CLAUDE.md` (tema único y favicon) y estado de la spec.
- El pase a prod queda para cuando el usuario lo pida (`make deploy` desde `main`).

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Algún contraste queda mal en una combinación que no está en el test (p. ej. texto muted sobre `error-bg`). | Capturas de todas las pantallas en S0 y S5, y revisión del usuario. |
| Clases armadas en JS (`public/js`) con colores fijos que el test no ve como texto literal. | El test también recorre `public/js`; la `safelist` de Tailwind se revisa. |
| Estilos del `hover:` de los botones de error pensados para fondo oscuro. | Se revisan en las capturas del panel de error de la sala. |
| La cookie `nf_theme` vieja. | No tiene efecto: ya nadie la lee. |

### Preguntas abiertas que bloquean slices

- **S1:** pregunta abierta 1 (¿`light-contrast` como opción?). Si la respuesta es sí, la decisión 4 cambia: se conserva un selector mínimo de 2 temas.
- **S4:** pregunta abierta 2 (el dibujo del favicon). Si no hay respuesta, va la vela.
- **S5:** pregunta abierta 3 (el nombre en la pestaña). No bloquea: se puede cambiar después.

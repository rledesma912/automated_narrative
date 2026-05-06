# Spec-318: Sistema de Diseño Centralizado y Componentización UI

**Fecha:** 5 de mayo de 2026  
**Estado:** Draft / Specifying  
**Prioridad:** Media-Alta  
**Metodología:** SDD (Specify → Plan → Tasks → Implement)

---

## 1. Objetivo

Centralizar y normalizar el lenguaje visual de **NarrativeForge** eliminando la duplicación masiva de clases Tailwind (DRY) y extrayendo componentes reutilizables (SOLID/DIP). Se busca pasar de estilos "inline" dispersos a una arquitectura de diseño basada en componentes `@layer` y partials EJS, sin romper la compatibilidad con el sistema de temas dinámicos.

### Principios Guía:
- **No Breaking Changes:** El look & feel debe permanecer idéntico o mejorar levemente; la estructura de datos no cambia.
- **SOLID/DIP:** El HTML no debe depender de la implementación visual detallada, sino de abstracciones (ej. `.btn-forge`).
- **DRY:** Centralizar patrones repetitivos identificados en `home.ejs`, `gallery.ejs` y `wizard.ejs`.
- **KISS:** No sobre-abstraer; mantener Tailwind para layouts únicos.
- **UX:** Mejorar la consistencia de espaciados, estados hover y legibilidad tipográfica.

---

## 2. Componentes a Centralizar (Capa @layer components)

Se crearán las siguientes clases semánticas en `frontend/src/styles/globals.css`:

| Clase | Descripción | Comportamiento |
|---|---|---|
| `.btn-forge` | Botón primario de acción (estilo "Skull") | Tracking ancho, hover scale, sombra de acento. |
| `.btn-forge-outline` | Botón secundario para acciones de lista | Borde sutil, hover con opacidad. |
| `.card-forge` | Contenedor base de información | Fondo surface, borde variable, transición de color. |
| `.card-forge-active` | Estado activo/destacado de un card | Anillo de acento, elevación extra. |
| `.heading-forge-xl` | Títulos principales (Hero) | Fuente serif, tracking-tighter, color acento. |
| `.heading-forge-lg` | Títulos de sección | Fuente serif, borde inferior sutil. |
| `.badge-forge` | Etiquetas de estado (Generando, Error, OK) | Texto XS, tracking-widest, background semitransparente. |
| `.text-forge-body` | Cuerpo de texto normalizado | Interlineado relajado, color text variable. |

---

## 3. Arquitectura de Temas (Revisión)

Se mantiene el flujo actual pero se asegura la compatibilidad:
1. `themes.json` → Fuente de verdad de valores hexadecimales.
2. `ThemeService.toCssVars()` → Inyecta en `:root` del `layout.ejs`.
3. `tailwind.config.js` → Mapea `forge-*` a `var(--forge-*)`.
4. **Mejora:** Normalizar el uso de `--font-serif` y `--font-mono` para que cambien según el tema (Noir vs Horror).

---

## 4. Plan de Implementación (Slices)

### Slice 1: Infraestructura y CSS Base
- [x] **1.1** Actualizar `frontend/src/styles/globals.css` con las definiciones de `@layer components`.
- [x] **1.2** Asegurar que `tailwind.config.js` tenga todos los mapeos necesarios (especialmente espaciados y sombras).
- [x] **1.3** Test de compilación: `npm run build:css`.

### Slice 2: Refactor de Componentes Atómicos (Layout & Sidebar)
- [x] **2.1** Limpiar `sidebar.ejs`: usar `.nav-link-forge` (nueva abstracción).
- [x] **2.2** Limpiar `footer.ejs`: normalizar estados de conexión.
- [x] **2.3** Validar visualmente la consistencia del "chrome" de la aplicación.

### Slice 3: Refactor de Vistas de Contenido (Home & Gallery)
- [x] **3.1** Refactorizar `home.ejs`: aplicar `.heading-forge-xl` y `.card-forge`.
- [x] **3.2** Refactorizar `gallery.ejs`: aplicar `.card-forge` a los items de historia y `.badge-forge` a los estados.
- [x] **3.3** Refactorizar `wizard.ejs` y `generate.ejs`: normalizar inputs y botones.

### Slice 4: Mejoras de UX y Feedback
- [x] **4.1** Implementar transiciones globales de opacidad para cargas de página (HTMX).
- [x] **4.2** Normalizar el `modal_confirm.ejs` con los nuevos estilos de componentes.
- [x] **4.3** Asegurar accesibilidad (contraste base en todos los temas).

---

## 5. Checklist de Verificación (Validation)

- [ ] `npm run build:css` genera el bundle sin warnings.
- [ ] Las vistas renderizan exactamente igual (o más consistentes) que antes.
- [ ] El cambio de tema en la sidebar actualiza correctamente todos los nuevos componentes `.forge-*`.
- [ ] No hay estilos "hardcoded" de colores hexadecimales fuera de `themes.json`.
- [ ] Verificación de responsividad en componentes centralizados.

---

## 6. Riesgos y Mitigación

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Especificidad de CSS | Medio | Usar `@layer components` para que las utilidades de Tailwind sigan pudiendo sobreescribir casos puntuales. |
| Romper temas dinámicos | Alto | Mantener siempre la referencia a `var(--forge-*)` y nunca a colores estáticos. |
| Regresión visual | Bajo | Capturas de pantalla previas al refactor para comparación manual. |

---

## 7. Referencias

- Spec-315: CSS Architecture (CLI vs CDN)
- Spec-301: Limpieza UI
- `CLAUDE.md`: CSS_ARCHITECTURE section

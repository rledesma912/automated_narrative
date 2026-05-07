# Spec-315: Arquitectura Frontend, CSS y Diseño

**Estado:** Vivo / Estándar
**Prioridad:** Alta
**Metodología:** PostCSS + Tailwind CLI

## 1. Arquitectura CSS

NarrativeForge utiliza un pipeline de compilación para CSS basado en **Tailwind CLI**, eliminando la dependencia de CDNs externas.

### 1.1 Pipeline de Build
- **Entrada:** `frontend/src/styles/globals.css` (Directivas `@tailwind` + componentes `@layer`).
- **Salida:** `frontend/public/styles.css` (Generado por `npm run build:css`).
- **Configuración:** `tailwind.config.js` mapea las variables de tema (`--forge-*`) a clases utilitarias.

### 1.2 Sistema de Temas Dinámicos
Los colores y fuentes se definen en `frontend/config/themes.json`. El `ThemeService` traduce estos valores a variables CSS inyectadas en el `:root` de la aplicación, permitiendo cambios de tema en tiempo real sin recompilar el frontend.

## 2. Sistema de Diseño (Componentización)

Para mantener el principio DRY, se utilizan clases semánticas centralizadas en `@layer components`:

| Clase | Uso |
|---|---|
| `.btn-forge` | Botón primario de acción. |
| `.btn-forge-outline` | Botón secundario/de lista. |
| `.btn-forge-danger` | Acciones destructivas (Eliminar). |
| `.card-forge` | Contenedor base para historias y paneles. |
| `.heading-forge-xl` | Títulos principales de página. |
| `.badge-forge` | Etiquetas de estado (Generando, OK, Error). |

### 2.1 Colores de Error
Los estados de error están centralizados mediante variables `--forge-error*`, evitando el uso de clases hardcodeadas como `red-500` en los templates EJS.

## 3. Estándares de UX y UI

### 3.1 Navegación y Chrome
- **Sidebar y Footer:** Todas las páginas deben renderizarse a través de `renderPage()` para asegurar la presencia del sidebar lateral y el footer global de estado.
- **Transiciones:** Se utilizan estados de carga y transiciones de opacidad para mejorar la percepción de fluidez en navegaciones HTMX.

### 3.2 Visualización de Contenido
- **Scroll Interno:** Los paneles de lectura (ej. relatos) deben tener scroll interno (`overflow-y-auto`) con una altura máxima calculada (`max-h-[calc(100vh-X)]`) para que el header de la página y los tabs permanezcan fijos.
- **Feedback de Copiado:** El botón "Copiar" debe proveer feedback visual inmediato y contar con un fallback para contextos no seguros (no-HTTPS).

### 3.3 Wizard de Generación
- **Auto-guardado:** Los cambios en los campos del wizard se persisten automáticamente en el evento `blur` o `change`, mostrando un indicador de "✓ Guardado" en el footer.
- **Navegación Segura:** Los botones "Anterior" deben ejecutar un guardado del paso actual antes de realizar la transición de página.

## 4. Organización de Vistas (Partials)

Para reducir la complejidad de los archivos EJS, se extraen bloques repetitivos a partials:
- `wizard_card_list.ejs`: Gestiona listas dinámicas de personajes, escenarios y reglas.
- `streaming_done_panel.ejs` / `streaming_error_panel.ejs`: Desacoplan los estados finales de la sala de generación.
- **Scripts Externos:** La lógica JS compleja se extrae a `/public/js/` (ej. `streaming-room.js`, `wizard.js`) para facilitar el mantenimiento y evitar "bloat" en los templates.

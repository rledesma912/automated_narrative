# Spec-315: CSS Architecture Refactor (PostCSS + Tailwind CLI)

**Fecha:** 5 de mayo de 2026  
**Estado:** En progreso  
**Prioridad:** Alta  
**Rama:** `feature/css-refactor-parallel`  

---

## 1. Objetivo

Migrar de **Tailwind CDN** a **Tailwind CLI compilado** para:

1. ✅ Eliminar dependencia de CDN (sin internet = funciona)
2. ✅ Centralizar configuración de diseño en `tailwind.config.js` + archivos CSS
3. ✅ Permitir tunear temas por ambiente sin recompilación de frontend
4. ✅ Optimizar bundle (tree-shaking, purging CSS no usado)
5. ✅ Mantener compatibilidad con sistema de variables CSS (themes dinámicos del backend)

**Restricción crítica:** Sin breaking changes. El frontend sigue funcionando idénticamente; solo cambia la forma en que se entrega el CSS.

---

## 2. Contexto Actual

**Arquitectura actual (CDN):**
- Tailwind cargado desde CDN en `layout.ejs`
- Configuración inline en `<script>` dentro del HTML
- Variables CSS inyectadas desde backend (`themeCssVars`)
- Sin compilación: CSS generado on-demand en navegador

**Problemas:**
- ❌ Requiere internet para cargar estilos
- ❌ Configuración dispersa entre backend + template HTML
- ❌ No hay purging automático de CSS no usado
- ❌ Cambios de tema requieren intervención del backend

---

## 3. Arquitectura Destino

```
frontend/
├── tailwind.config.js          # Configuración centralizada (PostCSS)
├── postcss.config.js           # Pipeline PostCSS
├── src/
│   ├── styles/
│   │   ├── globals.css         # Directives @tailwind + componentes custom
│   │   ├── theme.css           # Variables CSS (centralizado, sin CDN)
│   │   └── utilities.css       # (opcional) Utilities custom no-Tailwind
│   ├── views/
│   │   └── partials/
│   │       └── layout.ejs      # ❌ CDN removed, ✅ link to styles.css
│   └── server.ts               # Express server
├── public/
│   └── styles.css              # OUTPUT compilado (git-ignore)
├── package.json                # Scripts nuevos: build:css, watch:css
└── scripts/
    └── bash/
        └── build-css.sh        # Helper para build
```

---

## 4. Componentes a Refactorizar

| Componente | Ubicación | Estado Actual | Estado Final | Cambios |
|---|---|---|---|---|
| **Config Tailwind** | `layout.ejs` inline | Script embed | `tailwind.config.js` file | Extraer config de HTML |
| **CSS entry point** | N/A | N/A | `src/styles/globals.css` | ✨ Nuevo |
| **Variables tema** | Backend `themeCssVars` | Mixto | `src/styles/theme.css` | Centralizar CSS vars |
| **PostCSS config** | N/A | N/A | `postcss.config.js` | ✨ Nuevo |
| **Layout template** | `layout.ejs` | CDN + inline | Link a stylesheet | ❌ Eliminar CDN + script |
| **Build scripts** | `package.json` | Mínimos | `build:css`, `watch:css`, `prestart` | Agregar 3 scripts |
| **Build output** | N/A | N/A | `public/styles.css` | Artefacto compilado |
| **Helper bash** | N/A | N/A | `scripts/bash/build-css.sh` | ✨ Nuevo |

---

## 5. Checklist de Tasks

### Fase 1: Preparación (SIN CAMBIOS EN PROD)

- [x] **1.1** Crear `tailwind.config.js` en raíz frontend
- [x] **1.2** Crear `postcss.config.js` en raíz frontend
- [x] **1.3** Crear `src/styles/globals.css`
- [x] **1.4** Crear `src/styles/theme.css`
- [x] **1.5** Actualizar `package.json`: agregar scripts
- [x] **1.6** Actualizar `.gitignore`: ignorar `public/styles.css`
- [x] **1.7** Crear `scripts/bash/build-css.sh`
- [x] **1.8** Verificar que `npm run build:css` genera `public/styles.css` sin errores
- [x] **1.9** Crear tests unitarios: config carga correctamente

### Fase 2: Migración Segura (MODO PARALELO: CDN + CLI)

- [x] **2.1** Compilar CSS con `npm run build:css`
- [x] **2.2** En layout.ejs: agregar `<link rel="stylesheet" href="/styles.css">`
- [x] **2.3** En layout.ejs: **mantener CDN + config inline** (fallback)
- [x] **2.4** Tests E2E: renderizar página → estilos desde CLI
- [x] **2.5** Comparar visually: screenshot CDN vs CLI (idénticas)

### Fase 3: Cutover (ELIMINAR CDN)

- [ ] **3.1** En layout.ejs: eliminar `<script src="cdn.tailwindcss.com">`
- [ ] **3.2** En layout.ejs: eliminar `<script> tailwind.config = {...}`
- [ ] **3.3** Tests E2E: renderizar todas las páginas
- [ ] **3.4** Tests offline: desabilitar internet → estilos siguen cargando

### Fase 4: Optimización

- [ ] **4.1** Production build: `npm run build:css -- minify`
- [ ] **4.2** Medir bundle size: CSS antes vs después
- [ ] **4.3** Validar purging: clases no usadas fueron eliminadas

### Fase 5: Documentación + Deployment

- [ ] **5.1** Crear `docs/CSS_ARCHITECTURE.md`
- [ ] **5.2** Actualizar `frontend/README.md`
- [ ] **5.3** Commit + PR
- [ ] **5.4** Deploy a staging
- [ ] **5.5** Merge a `main`

---

## 6. Slices Incrementales

### Slice 1: Configuración Base (Fase 1)
**Archivos:** `tailwind.config.js`, `postcss.config.js`, `globals.css`, `theme.css`, updates en `package.json` + `.gitignore`  
**Resultado:** CSS compilado en `public/styles.css`, sin cambios visibles aún  
**Riesgo:** Bajo (no toca template)

### Slice 2: Modo Paralelo (Fase 2)
**Cambios:** layout.ejs carga ambos CDN + CLI  
**Resultado:** CSS duplicado pero funcionando
**Riesgo:** Bajo (fallback a CDN si CLI falla)

### Slice 3: Cutover (Fase 3)
**Cambios:** Eliminar CDN de layout.ejs  
**Resultado:** Solo CSS compilado  
**Riesgo:** Medio (pero cubierto por slice 2 testing)

### Slice 4: Optimización (Fase 4)
**Cambios:** Production build, minify  
**Resultado:** CSS optimizado  
**Riesgo:** Bajo (solo builds, sin runtime changes)

### Slice 5: Documentación (Fase 5)
**Cambios:** Docs nuevas  
**Resultado:** Proyecto documentado  
**Riesgo:** Ninguno

---

## 7. Breaking Changes Analysis

**❌ NINGÚN breaking change:**
- Template HTML sigue importando CSS igual (solo fuente cambia)
- Variables CSS persistten (`--forge-bg`, `--forge-accent`, etc.)
- Clases Tailwind siguen siendo idénticas
- Backend no necesita cambios (`themeCssVars` sigue funcionando)
- Sistema de temas dinámicos se mantiene

---

## 8. Test Strategy

### Unitarios (Slice 1)
```javascript
// test/css-architecture/config-loads.test.js
test('tailwind.config.js carga sin errores', () => {
  const config = require('../../frontend/tailwind.config.js');
  expect(config.content).toBeDefined();
  expect(config.theme.extend.colors.forge).toBeDefined();
});
```

### Build (Slice 1/2)
```javascript
// test/css-architecture/build-succeeds.test.js
test('npm run build:css genera public/styles.css', () => {
  execSync('npm run build:css', { cwd: 'frontend' });
  expect(fs.existsSync('frontend/public/styles.css')).toBe(true);
  expect(fs.statSync('frontend/public/styles.css').size > 0).toBe(true);
});
```

### E2E (Slice 2/3)
```javascript
// test/css-architecture/visual-parity.test.js
test('Estilos visualmente idénticos (CDN vs CLI)', async () => {
  const pageWithCDN = await renderWith('cdn');
  const pageWithCLI = await renderWith('cli');
  
  const diffPixels = visualDiff(pageWithCDN, pageWithCLI);
  expect(diffPixels).toBeLessThan(10);
});

// test/css-architecture/offline-mode.test.js
test('Página funciona sin internet', async () => {
  disableInternet();
  const page = await renderPage();
  expect(getComputedStyle(page, '.text-forge-text')).toMatch('rgb');
  enableInternet();
});
```

---

## 9. Definiciones Críticas (SDD Compliance)

Enlazar a `specs/001_marco_sdd.md` para:
- **Naming:** `tailwind.config.js` (CamelCase + . → minúsculas standard)
- **Carpeta estructura:** Respetar Clean Architecture
- **CSS variables:** PascalCase bloques (`{{ --forge-bg }}` respeta naming DB singular)
- **Testing:** pytest-asyncio no aplica (frontend = vitest/playwright)
- **Linting:** Usar ESLint + Prettier en `frontend/`

---

## 10. Dependencias nuevas (package.json)

```json
{
  "devDependencies": {
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.31",
    "autoprefixer": "^10.4.16"
  }
}
```

---

## 11. Variables de entorno

**No hay cambios en `.env`.**  
Tailwind CLI lee config desde `tailwind.config.js` (no necesita env vars).

---

## 12. Referencias

- Spec-001: Marco SDD
- Spec-220: Monitor mode (streaming-room.ejs)
- Spec-219: Regenerate mode
- CLAUDE.md: CSS_ARCHITECTURE

---

## 13. Historja de cambios

| Fecha | Acción | Estado |
|---|---|---|
| 2026-05-05 | Spec creado (Slice 1: Fase 1 - Preparación) | ✅ En progreso |

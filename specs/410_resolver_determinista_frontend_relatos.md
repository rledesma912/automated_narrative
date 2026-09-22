# SPEC-410: Resolver Determinístico + Frontend Relatos y Themes

**Fecha:** 2026-05-18
**Tipo:** SDD (Spec-Driven Development)
**Estado:** DONE

---

## ASSUMPTIONS

1. Los escenarios de una historia tienen `order_index` secuencial (0, 1, 2...)
2. La distribución de escenarios a beats sigue el orden de `order_index`
3. La paleta de "Earthy Tones" se infiere de archivos .png (tonos tierra: marrones, ocres, verdes musgo)
4. La vista de relatos actual muestra el título del beat + sinopsis del acto (formato `## Beat N - summary\n\nprosa`)
5. Se desea cambiar a título "Acto N" sin beat summary visible

---

## OBJECTIVE

Implementar cuatro cambios independientes:

1. **Eliminar llamada LLM del Resolver** → distribución determinística basada en `order_index`
2. **Relatos cards resaltados** → el relato activo en la vista relatos tiene borde/acento diferenciado
3. **Nuevo tema Earthy Tones** → reemplazar "Noir Urbano" con paleta de tonos tierra
4. **Vista relatos simplificada** → mostrar "Acto N" en vez de "Beat N - summary"

---

## COMMANDS

```bash
make lint
make test
```

---

## PROJECT STRUCTURE

### Backend (Resolución determinística)

```
src/
├── application/services/
│   └── scenario_resolver_service.py  # Refactorizar a determinístico
├── application/use_cases/
│   └── director_use_case.py         # Ajustar flujo (sin await resolve_distribution)
```

### Frontend (Themes, Relatos)

```
frontend/
├── config/
│   └── themes.json                   # Earthy Tones reemplaza noir
├── src/views/
│   ├── relatos.ejs                   # Título Acto N + cards resaltados
│   └── gallery.ejs                    # Cards con borde activo (si aplica)
```

---

## 1. RESOLVER DETERMINÍSTICO (Eliminar LLM)

### Código estilo

**Antes (LLM):**
```python
async def resolve_distribution(self, story, anchors=None) -> dict:
    response = await self.llm.generate(prompt=...)
    distribution = self._parse_distribution(response.text, story)
    return distribution
```

**Después (determinístico):**
```python
def resolve_distribution(self, story: "Story") -> dict:
    """Distribuye escenarios por orden_index de forma determinística."""
    scenarios = story.scenarios or []
    num_beats = self.prompt_builder.num_beats  # 5

    if not scenarios:
        return {str(i): {"scenario_index": None} for i in range(1, num_beats + 1)}

    distribution = {}
    for i in range(1, num_beats + 1):
        scenario_idx = min(i - 1, len(scenarios) - 1)
        distribution[str(i)] = {"scenario_index": scenario_idx}

    return distribution
```

### Reglas de distribución

| Beats | Escenarios | Distribución |
|-------|------------|--------------|
| 5 | 3 | Acto1→S0, Acto2→S1, Acto3→S2, Acto4→S2, Acto5→S2 |
| 5 | 5 | Acto1→S0, Acto2→S1, Acto3→S2, Acto4→S3, Acto5→S4 |
| 5 | 1 | Todos los actos → S0 |

### Archivos a modificar

- `src/application/services/scenario_resolver_service.py` (eliminar async, quitar LLM, añadir método síncrono)
- `src/application/use_cases/director_use_case.py` (cambiar llamadas)

---

## 2. RELATOS CARDS RESALTADOS

### Requisito

El relato activo (seleccionado en tabs) debe tener un borde visible más grueso y/o sombra para diferenciarlo.

### Implementación

En `relatos.ejs`, la sección `<section data-relato-panel>` tiene clase `card-forge`. Agregar clase condicional para estado activo.

```css
/* Tema activos en CSS */
.relato-panel.active {
  border-color: var(--forge-accent) !important;
  box-shadow: 0 0 0 1px var(--forge-accent), 0 4px 12px rgba(0,0,0,0.3);
}
```

```ejs
<section
  id="relato-panel-<%= relato.id %>"
  data-relato-panel="<%= relato.id %>"
  class="relato-panel card-forge !p-8 ... <%= index === 0 ? 'active' : '' %>"
>
```

En `relatos.js`, actualizar clase `active` al hacer click en tab.

---

## 3. TEMA EARTHY TONES (Reemplazar Noir Urbano)

### Colores inferidos de "Earthy Tones"

Basado en paleta de tonos tierra (marrones, verdes musgo, ocres):

```json
{
  "earthy": {
    "name": "Earthy Tones",
    "bg": "#1a1814",
    "surface": "#242220",
    "border": "#3a3830",
    "accent": "#8b7355",
    "muted": "#7a7060",
    "text": "#d4cfc5",
    "error": "#c45c4a",
    "error-bg": "#3f2420",
    "error-border": "#5e3a30",
    "font": "serif"
  }
}
```

### Archivos a modificar

- `frontend/config/themes.json` → eliminar entrada `noir`, agregar `earthy`
- Verificar que el frontend no tenga hardcodeado `noir` en otro lugar

---

## 4. VISTA RELATOS - TÍTULO "ACTO N"

### Cambio

**Antes:**
```
## Beat 1 - Resonancia Inicial
[prosa del beat]

## Beat 2 - Confrontación
[prosa del beat]
```

**Después:**
```
## Acto 1
[prosa del beat 1]

## Acto 2
[prosa del beat 2]
```

### Implementación

En `relatos.ejs`, cambiar el parseo del split:

```ejs
<%
  const sections = (relato.content || '').split(/^## (.+)$/m);
  const preamble = (sections[0] || '').trim();

  // Mapear títulos de beat a "Acto N"
  function mapBeatTitle(title) {
    const match = title.match(/Beat\s*(\d+)/i);
    if (match) return `Acto ${match[1]}`;
    return title;
  }
%>

<% for (let i = 1; i < sections.length; i += 2) { %>
  <h3 class="heading-forge-lg ..."><%= mapBeatTitle(sections[i]) %></h3>
  ...
<% } %>
```

---

## PLAN

### Hito 1: Backend - Resolver Determinístico
1. Refactorizar `ScenarioResolverService` para eliminar llamada LLM
2. Implementar distribución determinística por `order_index`
3. Actualizar `DirectorUseCase` para usar método síncrono
4. Verificar que tests existentes pasen

### Hito 2: Frontend - Theme Earthy Tones
5. Eliminar entrada `noir` de `themes.json`
6. Agregar entrada `earthy` con paleta inferida

### Hito 3: Frontend - Relatos Cards Resaltados
7. Agregar CSS para `.relato-panel.active` en `styles.css`
8. Agregar clase condicional `active` en `relatos.ejs`
9. Actualizar `relatos.js` para sincronizar clase activa en tabs

### Hito 4: Frontend - Vista Relatos Simplificada
10. Modificar parseo en `relatos.ejs` para mostrar "Acto N" en vez de "Beat N - summary"

---

## TASKS

- [x] **T1:** Refactorizar `ScenarioResolverService.resolve_distribution()` a método síncrono sin LLM
  - Acceptance: Método síncrono, retorna dict con distribución determinística
  - Verify: `make test` pasa
  - Files: `src/application/services/scenario_resolver_service.py`

- [x] **T2:** Actualizar `DirectorUseCase` para remover await de `resolve_distribution`
  - Acceptance: No se pasa LLM a ScenarioResolverService
  - Verify: `make test` pasa
  - Files: `src/application/use_cases/director_use_case.py`

- [x] **T3:** Reemplazar tema `noir` por `earthy` en `themes.json`
  - Acceptance: Entrada `earthy` existe, `noir` no existe
  - Verify: Revisar JSON manualmente
  - Files: `frontend/config/themes.json`

- [x] **T4:** Agregar CSS para `.relato-panel.active`
  - Acceptance: Borde accent visible en panel activo
  - Verify: Inspeccionar en navegador
  - Files: `frontend/src/styles/globals.css`

- [x] **T5:** Agregar clase `active` condicional en `relato_panel.ejs`
  - Acceptance: Primer panel tiene clase `active`
  - Verify: Revisar HTML generado
  - Files: `frontend/src/views/partials/relato_panel.ejs`

- [x] **T6:** Actualizar `relatos.js` para sincronizar clase activa en tabs
  - Acceptance: Al clickear tab, clase `active` se mueve al panel correcto
  - Verify: Probar clicks en tabs (e2e `relatos.spec.ts`)
  - Files: `frontend/public/js/relatos.js`

- [x] **T7:** Modificar parseo en `relato_panel.ejs` para mostrar "Acto N"
  - Acceptance: Títulos muestran "Acto 1", "Acto 2" etc.
  - Verify: Revisar contenido de relato renderizado
  - Files: `frontend/src/views/partials/relato_panel.ejs`

1. **Resolver:**
   - [x] `ScenarioResolverService.resolve_distribution()` es síncrono
   - [x] No se llama LLM para distribución de escenarios
   - [x] La distribución sigue `min(beat - 1, num_scenarios - 1)`
   - [x] Tests existentes pasan (195 passed)

2. **Relatos cards:**
   - [x] El panel activo tiene borde `accent` visible
   - [x] Al cambiar de tab, el nuevo panel se resalta

3. **Theme:**
   - [x] `themes.json` tiene entrada `earthy` con paleta de tonos tierra (inferida del PNG real, no de la hipótesis del spec)
   - [x] No existe entrada `noir` ("Noir Urbano" eliminado)
   - [x] El theme aplica correctamente (bg, text, accent visibles) — validado visualmente

4. **Vista relatos:**
   - [x] Los títulos muestran "Acto 1", "Acto 2", etc.
   - [x] No se muestra el summary del beat

---

## BOUNDARIES

- **Always:** Correr `make lint` después de cambios
- **Ask first:** Cambios en más de 5 archivos o schema DB
- **Never:** Hacer commit con tests fallando

---

## OPEN QUESTIONS

→ RESUELTO: Usar paleta inferida de imagen para Earthy Tones.
→ RESUELTO: Cards resaltadas solo en vista relatos (tabs). No aplicar a galería.
# Spec-204: Wizard Interactivo — Listas Dinámicas y 5 Actos

## 1. Objetivo
Mejorar la UX del wizard con:
1. **Listas dinámicas** para escenarios y protagonistas (agregar/eliminar)
2. **5 actos estructurados** basados en la Pirámide de Freytag

## 2. Contexto

### 2.1 Estado Actual
- Escenarios: 4 campos fijos (scenario_1 a scenario_4)
- Protagonistas: 3 campos fijos (protagonista_1 a protagonista_3)
- step_plot: 1 textarea libre para sinopsis

### 2.2 Estado Objetivo
- **Listas dinámicas**: empieza con 1, botón agregar (hasta 5), botón eliminar con popup
- **5 actos**: campos estructurados con guía basas en Freytag

## 3. Diseño de Listas Dinámicas

### 3.1 Protagonistas (step_config_personajes)

**Comportamiento:**
- inicial: 1 protagonista visible
- Botón "Agregar personaje" → agrega otro hasta max 5
- Cada protagonista tiene botón "Eliminar" (icono papelera)
- Popup de confirmación antes de eliminar

**UI Visual:**
```
┌─────────────────────────────────────────────────────────┐
│ PERSONAJE 1                                    🗑️ │
│ ──────────────────────────────────────────────────── │
│ Nombre: [____________]                             │
│ Rol:   [_________________________________________]   │
│ Traits: [☑] religioso  [ ] protector  [ ] ...]    │
└─────────────────────────────────────────────────────────┘

[+ Agregar personaje]        (máximo 5)
```

**Popup de confirmación (al eliminar):**
```
┌─────────────────────────────────────────┐
│ ¿Eliminar este personaje?                  │
│                                   │
│ Se borrará "<nombre>" definitivament. │
│                                   │
│    [Cancelar]  [Eliminar]       │
└─────────────────────────────────────────┘
```

### 3.2 Escenarios (step_world)

**Comportamiento:**
- inicial: 1 escenario visible
- Botón "Agregar escenario" → agrega otro hasta max 4
- Cada escenario tiene botón "Eliminar" (icono papelera)
- Popup de confirmación antes de eliminar

**Campos por escenario:**
- nombre (text, required)
- descripción (textarea rows=2, optional)

## 4. Diseño de 5 Actos (Basado en Freytag)

### 4.1 Pirámide de Freytag

| Acto | nombre | Etapa Freytag | Descripción |
|-----|--------|--------------|------------|
| 1 | Exposición | Setup | Presentación del mundo, personajes y conflicto inicial |
| 2 | Acción Ascendente | Rising Action | Complicaciones que llevan al clímax |
| 3 | Clímax | Climax | Punto de mayor tensión o revelación |
| 4 | Acción Descendente | Falling Action | Consecuencias del clímax |
| 5 | Desenlace | Dénouement | Resolución y nueva normalidad |

### 4.2 Campos por Acto

```yaml
- name: acto_1_exposicion
  type: textarea
  label: "Acto 1: Exposición"
  subtitle: "Presentá el mundo, los personajes y el conflicto inicial"
  hint: "Quién es el protagonista, dónde está, qué problema enfrent o qué lo motiva"
  rows: 4
  group: "actos"
  required: true

- name:acto_2_accion
  type: textarea
  label: "Acto 2: Acción Ascendente"
  subtitle: "Las complicaciones que llevan al momento más intenso"
  hint: "Qué obstáculos aparecen, qué decisiones debe tomar el protagonista"
  rows: 4
  group: "actos"
  required: true

- name: acto_3_climax
  type: textarea
  label: "Acto 3: Clímax"
  subtitle: "El momento de mayor tensión o revelación"
  hint: "Qué descubrimiento o evento cambia todo"
  rows: 4
  group: "actos"
  required: true

- name: acto_4_accion
  type: textarea
  label: "Acto 4: Acción Descendente"
  subtitle: "Las consecuencias del momento más intenso"
  hint: "Cómo cambian las reglas del mundo después del clímax"
  rows: 4
  group: "actos"
  required: true

- name: acto_5_desenlace
  type: textarea
  label: "Acto 5: Desenlace"
  subtitle: "La resolución y la nueva normalidad"
  hint: "Cómo queda el mundo después de la historia"
  rows: 4
  group: "actos"
  required: true
```

### 4.3 UI Visual

```
┌─────────────────────────────────────────────────────────┐
│ ACTO 1: EXPOSICIÓN                                🗑️ │
│ ──────────────────────────────────────────────────── │
│ Presentá el mundo, los personajes y el conflicto inicial   │
│                                                     │
│ ┌───────────────────────────────────────────────┐   │
│ │ Quién es el protagonista, dónde está, qué       │   │
│ │ problema enfrenta o qué lo motiva           │   │
│ │                                           │   │
│ │                                           │   │
│ └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 5. Mapeo a Input Story

```typescript
function buildActos(wizard: WizardData): Synopsis {
  const plot = wizard.step_plot;
  return {
    act_1: {
      type: "exposicion",
      text: plot.acto_1_exposicion,
    },
    act_2: {
      type: "accion_ascendente",
      text: plot.acto_2_accion,
    },
    act_3: {
      type: "climax",
      text: plot.acto_3_climax,
    },
    act_4: {
      type: "accion_descendente",
      text: plot.acto_4_accion,
    },
    act_5: {
      type: "desenlace",
      text: plot.acto_5_desenlace,
    },
  };
}
```

## 6. Slices de Implementación

### Slice A: UI Wizard - Listas Dinámicas
- **Meta:** Componente de lista dinámica con agregar/eliminar
- **QA Check:** Agregar hasta 5, eliminar con popup

### Slice B: UI Wizard - 5 Actos
- **Meta:** 5 campos textarea con subtitles
- **QA Check:** Labels y subtitles visibles

### Slice C: generate.controller.ts
- **Meta:** Build actos desde wizard data
- **QA Check:** JSON con estructura act_1...act_5

### Slice D: Tests E2E
- **Meta:** Crear historia con lista dinámica
- **QA Check:** Verificar en /galeria

## 7. Tareas

### Slice A: Listas Dinámicas
- [ ] Modificar ui_definitions.yaml para protagonists con inicial=1
- [ ] Modificar ui_definitions.yaml para escenarios con inicial=1
- [ ] Componente JavaScript para agregar elemento
- [ ] Componente JavaScript para eliminar con popup
- [ ] Popup de confirmación (modal)
- [ ] Test: agregar 5 personajes
- [ ] Test: eliminar personaje con popup

### Slice B: 5 Actos
- [ ] Reemplazar step_plot actual por 5 actos
- [ ] Agregar subtitles por cada acto
- [ ] Labels: "Acto 1: Exposición", etc.
- [ ] Mostrar hints debajo de cada campo
- [ ] Test: 5 actos visibles

### Slice C: generate.controller.ts
- [ ] Función buildActos()
- [ ] Integrar en buildStoryPayload()
- [ ] Test: POST genera JSON correcto

### Slice D: Tests
- [ ] Test lista dinámica (agregar/eliminar)
- [ ] Test popup de confirmación
- [ ] Test 5 actos
- [ ] Verificar en /galeria

## 8. QA Checklist

- [ ] Protagonista comienza con 1 visible
- [ ] Botón "Agregar personaje" funciona
- [ ] Hasta 5 protagonistas permitidos
- [ ] Popup de confirmación al eliminar
- [ ] Escenario comienza con 1 visible
- [ ] Botón "Agregar escenario" funciona
- [ ] Hasta 4 escenarios permitidos
- [ ] 5 acto con subtitles visibles
- [ ] Labels correctos: Exposición, Acción Ascendente, Clímax, etc.
- [ ] JSON final tiene act_1 a act_5

## 10. Guardar Historia Sin Generar (Nueva Feature)

### 10.1 Problema
Si la generación falla después de loader tous los datos del wizard, se pierden.

### 10.2 Solución
Separación de la creación (guardado) de la generación:

**Flujo Propuesto:**
```
Wizard Confirmar → [Guardar] → [Generar]
                        ↓                 ↓
                   Historia guardada   Generación
                   (status: draft)    (status: processing)
```

### 10.3 Diseño

**Página de Confirmar (wizard-confirm.ejs)**

| Botón | Acción | Estado result |
|------|--------|-------------|
| **Guardar** | Guarda datos, no genera | Historia en /galeria (draft) |
| **Generar** | Guarda + inicia SSE | Historia en generación |

**Botón Guardar:**
```html
<button type="submit" name="action" value="save" class="...">
  <i data-lucide="save" class="w-4 h-4"></i> Guardar
</button>
```

**Botón Generar:**
```html
<button type="submit" name="action" value="generate" class="...">
  <i data-lucide="zap" class="w-4 h-4"></i> Generar historia
</button>
```

### 10.4 UI en Galería

**Historia guardada (draft):**
```
┌─────────────────────────────────────────┐
│ [Título de historia]                    │
│ Estado: 📝 Borrador                    │
│                                         │
│ [Ver] [Generar] [Eliminar]           │
└─────────────────────────────────────────┘
```

**Acciones disponibles:**
- **Ver**: Muestra los datos completos (revisión)
- **Generar**: Inicia la generación SSE
- **Editar**: Vuelve al wizard con datos cargados
- **Eliminar**: Borra la historia

### 10.5 Diseño de la Página de Ver/Revisar

**Ruta:** `/historia/:id/ver`

```
┌────────────────────────────────────────────────────────┐
│ [Título de historia]                            🔄    │
│ Estado: 📝 Borrador                       📅 28/04/2026 │
├────────────────────────────────────────────────────────┤
│                                                    
│ ATMÓSFERA                                          
│ Terror Psicológico (psicologico) - creciente_opresivo   
│                                                    
│ NARRADOR                                          
│ Irene (Protagonista 1)                             │
│ Voz: intimista                                    
│                                                    
│ PERSONAJES                                        
│ - Irene: Narradora y protagonista...               
│ - Ricardo: Esposo de Irene...                   
│                                                    
│ ESCENARIOS                                       
│ - Casa de María                              
│ - Monte de los Espinillos                    
│                                                    
│ REGLAS                                          
│ - María no advierte con miedo... (psicologica)    
│                                                    
│ ACTO 1: EXPOSICIÓN                              
│ Irene y su familia llegan...                  
│                                                    
│ ... (todos los actos)                          
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ ACCIONES                                           │
│                                                    │
│ [ ← Volver]  [Editar]  [Generar →]                │
└────────────────────────────────────────────────────────┘
```

### 10.6 Estados de Historia

| Estado | Significado | Acciones disponibles |
|--------|-------------|-------------------|
| `draft` | Guardada, sin generar | Ver, Generar, Editar, Eliminar |
| `processing` | Generando actualmente | Ver (solo lectura) |
| `completed` | Generada exitosamente | Ver, Regenerar, Eliminar |
| `failed` | Error en generación | Ver, Reintentar, Eliminar |

### 10.7 API Endpoints

```python
# POST /stories (guardar sin generar)
@router.post("/stories")
async def create_story(
    request: StoryCreateRequest,
    action: str = "save"  # "save" o "generate"
):
    # Guarda la historia
    story = await use_case.execute(request)
    
    if action == "generate":
        # Inicia streaming
        return {"story_id": str(story.id), "status": "processing"}
    else:
        # Solo guarda
        return {"story_id": str(story.id), "status": "draft"}

# GET /historia/{id}/ver
@router.get("/historia/{story_id}/ver")
async def view_story(story_id: str):
    # Devuelve datos completos para revisión
    return story_with_all_data

# POST /historia/{id}/generar
@router.post("/historia/{story_id}/generar")
async def generate_from_draft(story_id: str):
    # Inicia generación desde draft
    return {"status": "processing"}
```

### 10.8 Tareas

- [ ] Modificar wizard-confirm.ejs con botón Guardar
- [ ] Agregar campo "action" al form (save/generate)
- [ ] Endpoint POST /stories acepta action
- [ ] Guardar historia con status="draft"
- [ ] Galería muestra historias por estado
- [ ] Página /historia/{id}/ver
- [ ] Botón Generar en página de ver
- [ ] Botón Editar en página de ver
- [ ] Estados: draft, processing, completed, failed

### 10.9 UX Checklist

- [ ] Botón "Guardar" visible en wizard-confirm
- [ ] Guardar crea historia en /galeria
- [ ] Historia guardada muestra "Borrador"
- [ ] Click en historia muestra datos completos
- [ ] Botón "Generar" en página de ver
- [ ] Botón "Editar" en página de ver
- [ ] Estados actualizan correctamente

```bash
# Test UI
cd frontend && npm run dev
# Navegar a /generar/paso/2 (personajes)
# Click "Agregar personaje" hasta 5
# Click eliminar en personaje 3
# Confirmar popup
# Navegar a /generar/paso/5 (trama)
# Verificar 5 actos visibles
```
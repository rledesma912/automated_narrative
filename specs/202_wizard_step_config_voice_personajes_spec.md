# Spec-202: Mejora Step Configuración — Elenco y Voz Narradora

## 1. Objetivo
Expandir el step_config del Wizard para capturar:
1. Elenco de personajes (protagonistas)
2. Selección del narrador (storyteller)
3. Configuración de estilo de voz con valores por defecto y guías tipadas

## 2. Contexto del Código Existente

### 2.1 Archivos Actuales
| Archivo | Ubicación | Estado |
|---------|----------|--------|
| ui_definitions.yaml | `frontend/config/` | 4 steps actuales |
| wizard.service.ts | `frontend/src/services/` | Interface WizardField limitada |
| form_renderer.service.ts | `frontend/src/services/` | Parser básico |
| wizard.ejs | `frontend/src/views/` | Solo text/textarea/select |

### 2.2 Interfaces Actuales (referencia)

**WizardField actual (wizard.service.ts:4-13):**
```typescript
export interface WizardField {
  name: string;
  label: string;
  type: "text" | "textarea" | "select";  // FALTA: radio, multi-select
  required: boolean;
  placeholder?: string;
  rows?: number;
  hint?: string;
  options?: string[];
}
```

**RawField actual (form_renderer.service.ts:8-17):**
```typescript
interface RawField {
  name: string;
  type: "text" | "textarea" | "select";  // FALTA: radio, multi-select
  label: string;
  placeholder?: string;
  required?: boolean;
  rows?: number;
  hint?: string;
  options?: string[];
}
```

**ui_definitions.yaml actual:**
- step_config: title, atmosfera, relator (texto libre)
- step_protagonist: nombre, rasgo, miedo, motivacion
- step_world: ubicacion, clima, regla_paranormal
- step_plot: sinopsis

### 2.3 Valores por Defecto Implícitos

- `voice.person`: primera
- `voice.tense`: pasado

### 2.4 Backend: Core API Payload

El Core actual espera en POST /stories (src/presentation/schemas/request.py:18):

```python
class CreateStoryRequest(BaseModel):
    title: str
    protagonista: str
    relator: str | None = None
    atmosfera: str
    sinopsis: str
    escenarios: str | None = None
    reglas: list[str] | None = None
    protagonists: list[dict] | None = None      # FALTA en current
    storyteller: dict | None = None             # FALTA en current
    storyteller_config: dict | None = None      # FALTA en current
```

**El frontend debe transformar los datos del wizard al formato que el Core espera.**

## 3. Nuevo Flujo del Step Configuración

### 3.1 Estructura Propuesta

| Sub-step | Campos | Notas |
|---------|--------|-------|
| config_title | title, atmosfera | Existe |
| config_personajes | elenco + relator | **NUEVO**: personajes con role/traits |
| config_voz | perception, knowledge, language, bias | **NUEVO**: configuración avanzada |

### 3.2 Guías y Descripciones por Campo/Grupo

Cada campo o grupo debe incluir:
- **subtitle** (opcional): Descripción breve del grupo
- **note** (opcional): Nota explicativa o ejemplo concreto

```yaml
- name: field_name
  type: text|select|multi-select
  label: "Label formal"
  subtitle: "Descripción breve para el usuario"    # 1-2 líneas
  note: "Ejemplo: ..."                # Ejemplo concreto opcional
  hint: "Tooltip adicional"           # Mantener si ya existía
  group: "nombre_grupo"            # Agrupación visual
```

### 3.3 Diseño Visual (UI Layout)

**Principios:**
- **Ancho:** Utilizar 80-90% del viewport ancho
- **Fuentes:** 
  - Labels: 18-20px (antes ~14px)
  - Subtitles: 16px
  - Input text: 18px
- **Grupos visuales:** Cards o secciones con border sutil
- **Tono de labels:** Informal y orientador

**Ejemplo de label informal transformada:**
| Label formal | Label informal |
|-----------|-------------|
| Storyteller (narrador) | Aquí va quien cuenta la historia |
| Protagonista 1 - Nombre | El nombre de tu personaje |
| Perception Reliability | ¿Qué tan confiable es lo que ve/oye el narrador? |
| Distortion Level | ¿Cuánto distorsiona la realidad cuando tiene miedo? |

### 3.2 Detalle de Campos

#### Sub-step: Personajes (config_personajes)

Grupo visual: "Personajes de la historia" (card con border)

**Protagonistas (lista dinámica, hasta 5):**
```
- name: protagonista_N_name
  type: text
  label: "El nombre de tu personaje"
  subtitle: "Nombre del personaje"
  placeholder: "Ej: Irene, Ricardo, María..."
  group: "elenco"
  required: true

- name: protagonista_N_role  
  type: text
  label: "Qué papel cumple"
  subtitle: "Rol o relación con otros"
  placeholder: "Ej: Narradora y protagonista; nuera de María"
  group: "elenco"
  required: true

- name: protagonista_N_traits
  type: multi-select
  label: "Cómo es su personalidad"
  subtitle: "Traits que lo definen (selecciona los que aplica)"
  group: "elenco"
  options:
    - religioso
    - protector
    - observador
    - escéptico
    - pragmático
    - terco
    - bondadoso
    - portador_folklore
    - sereno
    - callado
```

**Storyteller (selector):**
```
- name: storyteller_id
  type: select
  label: "Aqui va quien cuenta la historia"
  subtitle: "Seleccioná el personaje que narra"
  note: "Uno de los personajes que definiste arriba"
  group: "narrador"
  required: true

- name: voice_style
  type: select
  label: "Con qué tono de voz"
  subtitle: "Cómo sonar la historia"
  options:
    - "intimista: Como un diario personal, cámara cerca"
    - "omnisciente: Un narrador que todo lo ve y todo lo sabe"
    - "dramático: Escenas con tensión y revelaciones"
    - "contemplativo: Ritmo lento, descripción rica"
    - "poético: Lenguaje evocador y metafórico"
  group: "narrador"
```
- name: string (requerido)
- role: string (placeholder: "Protagonista principal...", requerido)
- traits: multiselect/array (opcional, ejemplos: ["religioso", "protector", "observador", "escéptico", "pragmático", "terco", "bondadoso", "portador de folklore"])
```

**Storyteller (selector):**
```
- storyteller_id: select (opciones = ids de protagonistas definidos)
- voice_style: select (opciones con ejemplos):
  - "intimista" → "Diario personal, cámara close"
  - "omnisciente" → "Narrador externo que todo lo ve"
  - "dramático" → "Escenas con tensión y reveal"
  - "contemplativo" → "Ritmo lento, descripción rica"
```

#### Sub-step: Voz (config_voz)

Grupo visual: "Cómo suena la historia" (card)

**Percepción ( defecto implícito = subjetiva):**
```
- name: perception_reliability
  type: select
  label: "Qué tan confiable es lo que ve/oye el narrador"
  subtitle: "¿Percibe la realidad tal cual o distorted?"
  group: "percepcion"
  default: "subjetiva"
  options:
    - subjetiva
    - objetiva
    - poco_confiable

- name: distortion_level
  type: select
  label: "Cuánto distorsiona la realidad"
  subtitle: "¿Cuánto se diferencia lo que ve del mundo real?"
  group: "percepcion"
  default: "media"
  options:
    - minima
    - baja
    - media
    - alta
    - critica
  note: "Nivel de distorsión bajo miedo o estrés"

- name: distortion_triggers
  type: multi-select
  label: "Qué le hace perder la realidad"
  subtitle: "¿Qué situaciones distorsionan su percepción?"
  group: "percepcion"
  options:
    - miedo
    - oscuridad
    - fatiga
    - trauma
    - sustancia
    - paranoia
```

**Conocimiento:**
```
- name: paranormal_knowledge
  type: select
  label: "Qué tanto sabe de lo oculto"
  subtitle: "Conocimiento sobre fenómenos paranormales"
  group: "conocimiento"
  default: "medio"
  options:
    - nulo
    - bajo
    - medio
    - alto
    - experto

- name: religioso_knowledge
  type: select
  label: "Qué tanto sabe de lo sagrado"
  subtitle: "Conocimiento religioso/espiritual"
  group: "conocimiento"
  default: "medio"
  options:
    - nulo
    - bajo
    - medio
    - alto
    - experto

- name: interpretation_style
  type: select
  label: "Cómo interpreta lo extraño"
  subtitle: "Cuando ve algo incontrolable, ¿cómo lo entiende?"
  group: "conocimiento"
  options:
    - literal: "Lo ve tal cual, sin interpretación"
    - simbolica: "Busca significados ocultos"
    - mitologica: "Lo conecta con mitos y leyendas"
    - cientifica: "Busca explicaciones racionales"
    - supersticiosa: "Le teme, lo evita, lo respeta"
```

**Lenguaje:**
```
- name: language_register
  type: select
  label: "Cómo habla el narrador"
  subtitle: "Registro lingüístico"
  group: "lenguaje"
  options:
    - formal: "Educado, correcto"
    - coloquial: "Natural, diario"
    - rural_tradicional: "Campo, tradicional"
    - arcaico: "Antiguo, desactualizado"
    - poético: "Evocador, metafórico"

- name: figurative_density
  type: select
  label: "Cuánto usa figuras retóricas"
  subtitle: "Metáforas, comparaciones, descripciones"
  group: "lenguaje"
  default: "media"
  options:
    - minima
    - baja
    - media
    - alta
    - maxima
```

**Sesgos (bias):**
```
- name: fear_focus
  type: multi-select
  label: "De qué tiene más miedo"
  subtitle: "Qué activa su miedo automáticamente"
  group: "sesgos"
  options:
    - proteccion_de_hijos
    - supervivencia
    - perdida
    - traicion
    - corrupcion
    - lo_desconocido
    - aislamiento

- name: attention_focus
  type: multi-select
  label: "En qué presta más atención"
  subtitle: "A qué le dedica más energía mental"
  group: "sesgos"
  options:
    - sonidos
    - sombras
    - naturaleza
    - tecnologia
    - rostros
    - espacios_cerrados
    - detalles_fisicos
```

## 4. Cambios en ui_definitions.yaml

```yaml
steps:
  - id: step_config_title
    title: "Título y Atmósfera"
    subtitle: "El nombre de tu historia y el tipo de horror"
    fields:
      - name: title
        type: text
        label: "Título de la historia"
        subtitle: "El nombre de tu historia"
        placeholder: "Ej: La Casa del Umbral"
        required: true
      - name: atmosfera
        type: select
        label: "Qué tipo de horror"
        subtitle: "El género de terror que más usa"
        required: true
        options:
          - "Terror Psicológico"
          - "Horror Cósmico"
          - "Terror Gótico"
          - "Body Horror"
          - "Paranormal"
          - "Folk Horror"
          - "Suspenso"
          - "Terror Supervivencia"

  - id: step_config_personajes
    title: "Personajes"
    subtitle: "Quiénes son y quién cuenta la historia"
    fields:
      # Protagonista 1
      - name: protagonista_1_name
        type: text
        label: "Personaje 1 - Nombre"
        subtitle: "El nombre de tu personaje"
        placeholder: "Ej: Irene"
        group: "elenco"
        required: true
      - name: protagonista_1_role
        type: text
        label: "Personaje 1 - Qué hace"
        subtitle: "Su rol o relación con otros"
        placeholder: "Ej: Narradora y protagonista; nuera de María"
        group: "elenco"
        required: true
      - name: protagonista_1_traits
        type: multi-select
        label: "Personaje 1 - Cómo es"
        subtitle: "Traits de personalidad (selecciona los que aplican)"
        group: "elenco"
        options:
          - religioso
          - protector
          - observador
          - escéptico
          - pragmático
          - terco
          - bondadoso
          - portador_folklore
          - sereno
          - callado

      # Protagonista 2 (opcional)
      - name: protagonista_2_name
        type: text
        label: "Personaje 2 - Nombre"
        subtitle: "Otro personaje"
        placeholder: "Ej: Ricardo"
        group: "elenco"
      - name: protagonista_2_role
        type: text
        label: "Personaje 2 - Qué hace"
        placeholder: "Ej: Esposo de Irene; hijo de María"
        group: "elenco"
      - name: protagonista_2_traits
        type: multi-select
        label: "Personaje 2 - Cómo es"
        group: "elenco"
        options:
          - religioso
          - protector
          - observador
          - escéptico
          - pragmático
          - terco
          - bondadoso
          - portador_folklore

      # ... Similar hasta protagonista_5

      # Narrador
      - name: storyteller_id
        type: select
        label: "Aquí va quien cuenta la historia"
        subtitle: "Seleccioná el personaje que narra"
        note: "Elegí uno de los personajes que definiste arriba"
        group: "narrador"
        required: true

      - name: voice_style
        type: select
        label: "Con qué tono de voz"
        subtitle: "Cómo suena la historia"
        group: "narrador"
        options:
          - "intimista: Como un diario personal, cámara cerca"
          - "omnisciente: Un narrador que todo lo ve y todo lo sabe"
          - "dramático: Escenas con tensión y revelaciones"
          - "contemplativo: Ritmo lento, descripción rica"
          - "poético: Lenguaje evocador y metafórico"

  - id: step_config_voz
    title: "Cómo suena la historia"
    subtitle: "Cómo percibe, piensa y habla el narrador"
    fields:
      # Percepción
      - name: perception_reliability
        type: select
        label: "Qué tan confiable es lo que ve/oye"
        subtitle: "¿Percibe la realidad tal cual?"
        group: "percepcion"
        default: "subjetiva"
        options:
          - subjetiva
          - objetiva
          - poco_confiable
      - name: distortion_level
        type: radio
        label: "Cuánto distorsiona la realidad"
        subtitle: "¿Cuánto se diferencia lo que ve del mundo real?"
        group: "percepcion"
        default: "media"
        options:
          - minima
          - baja
          - media
          - alta
          - critica
      - name: distortion_triggers
        type: multi-select
        label: "Qué le hace perder la realidad"
        subtitle: "¿Qué situaciones distorsionan su percepción?"
        group: "percepcion"
        options:
          - miedo
          - oscuridad
          - fatiga
          - trauma

      # Conocimiento
      - name: paranormal_knowledge
        type: select
        label: "Qué tanto sabe de lo oculto"
        subtitle: "Conocimiento sobre fenómenos paranormales"
        group: "conocimiento"
        default: "medio"
        options:
          - nulo
          - bajo
          - medio
          - alto
          - experto
      - name: religioso_knowledge
        type: select
        label: "Qué tanto sabe de lo sagrado"
        subtitle: "Conocimiento religioso/espiritual"
        group: "conocimiento"
        default: "medio"
        options:
          - nulo
          - bajo
          - medio
          - alto
          - experto
      - name: interpretation_style
        type: select
        label: "Cómo interpreta lo extraño"
        subtitle: "Cuando ve algo incontrolable, ¿cómo lo entiende?"
        group: "conocimiento"
        options:
          - literal
          - simbolica
          - mitologica
          - cientifica
          - supersticiosa

      # Lenguaje
      - name: language_register
        type: radio
        label: "Cómo habla el narrador"
        subtitle: "Registro lingüístico"
        group: "lenguaje"
        options:
          - formal
          - coloquial
          - rural_tradicional
          - arcaico
          - poético
      - name: figurative_density
        type: select
        label: "Cuánto usa figuras retóricas"
        subtitle: "Metáforas, comparaciones, descripciones"
        group: "lenguaje"
        default: "media"
        options:
          - minima
          - baja
          - media
          - alta
          - maxima

      # Sesgos
      - name: fear_focus
        type: multi-select
        label: "De qué tiene más miedo"
        subtitle: "Qué activa su miedo automáticamente"
        group: "sesgos"
        options:
          - proteccion_de_hijos
          - supervivencia
          - perdida
          - traicion
          - corrupcion
          - lo_desconocido
      - name: attention_focus
        type: multi-select
        label: "En qué presta más atención"
        subtitle: "A qué le dedica más energía mental"
        group: "sesgos"
        options:
          - sonidos
          - sombras
          - naturaleza
          - tecnologia
          - paisajes
          - rostros
```

## 5. Mapeo a Input Story (Core)

El frontend debe construir el JSON equivalente:

```json
{
  "story": {
    "title": "..."
  },
  "protagonists": [
    {"id": "P1", "name": "...", "role": "...", "traits": ["..."]},
    ...
  ],
  "storyteller": {"id": "P1"},
  "storyteller_config": {
    "perception": {
      "reliability": "subjetiva",
      "distortion": {"level": "media", "triggers": ["miedo"]}
    },
    "knowledge": {
      "domain": {"paranormal": "medio", "religioso": "medio"},
      "interpretation_style": "simbolica"
    },
    "voice": {"person": "primera", "tense": "pasado", "style": "intimista"},
    "language": {"register": "rural_tradicional", "figurative_density": "media"},
    "bias": {"fear_focus": [], "attention_focus": []}
  }
}
```

## 6. Defaults Implícitos

| Campo | Default en UI | Valor enviado |
|-------|---------------|--------------|
| voice.person | (no mostrar) | "primera" |
| voice.tense | (no mostrar) | "pasado" |
| perception.reliability | "subjetiva" | (seleccionado) |
| distortion_level | "media" | (seleccionado) |

## 7. UX — Guías, Helpers y Diseño Visual

### 7.1 Campos con Descripción

Cada campo puede incluir:

- **label:** Título formal del campo
- **subtitle:** Descripción breve (1-2 líneas) para el usuario entender qué completar
- **note:** Texto adicional con ejemplo concreto o resultado esperado
- **placeholder:** Ejemplo orientado
- **hint:** Tooltip opcional
- **group:** Agrupación visual (card/sección)

### 7.2 Diseño Visual (UI Layout)

**Principios:**
- **Ancho del contenedor:** 80-90% del viewport (`w-[85vw]` o `max-w-5xl`)
- **Fuentes:** 
  - Labels: 18-20px, font-semibold
  - Subtitles: 14-16px, text-muted
  - Input text: 18px
  - Notes: 13px, italic
- **Grupos visuales:** Cards con borde sutil (`border-forge-border`, `bg-forge-surface`)
- **Spacing:** `gap-6` entre grupos, `gap-4` entre campos
- **Tono de labels:** Informal y orientador

### 7.3 Estructura de Grupos por Campo

| group | Título Card | Subtítulo Card |
|-------|-----------|-------------|
| "elenco" | PERSONAJES | "Quiénes son en la historia" |
| "narrador" | NARRADOR | "Aquí va quien cuenta la historia, su nombre y su tono de voz" |
| "percepcion" | PERCEPCIÓN | "Qué tan confiable es lo que ve, oye y siente" |
| "conocimiento" | CONOCIMIENTO | "Qué sabe de lo oculto y lo sagrado" |
| "lenguaje" | LENGUAJE | "Cómo habla y escribe el narrador" |
| "sesgos" | SESGOS | "Qué le da miedo y en qué presta atención" |

**Componentes por tipo:**
| Tipo | Componente UI |
|------|------------|
| text | Input text (`w-full`, `text-lg`) |
| select | Combo dropdown (`text-lg`) |
| multi-select | Checkbox grid (2-3 columnas) |
| radio | Radio button list (vertical) |

### 7.4 Ejemplo Visual por Grupo

```
┌─────────────────────────────────────────────────────────────┐
│ PERSONAJES DE LA HISTORIA                                    │
│ Quiénes son y quién cuenta la historia                      │
├─────────────────────────────────────────────────────────────┤
│ │ El nombre de tu personaje                                  │
│ │ ██████████████████████████████████████  (input text)       │
│ │                                                             │
│ │ Su rol o relación con otros                                │
│ │ ██████████████████████████████████████  (input text)       │
│ │                                                             │
│ │ Traits de personalidad (selecciona)                        │
│ │ [✓] religioso  [ ] protector  [ ] escéptico  [...]        │
│                                                             │
│ │ ... (repeticón para más personajes)                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ NARRADOR                                                    │
│ Aquí va quien cuenta la historia, su nombre y tono de voz    │
├─────────────────────────────────────────────────────────────┤
│ │ Seleccioná el personaje que narra                        │
│ │ [▼ Irene                                                  │
│ │ Elegí uno de los personajes que definiste arriba         │
│ │                                                             │
│ │ Con qué tono de voz                                       │
│ │ ( ) intimista: Como un diario personal, cámara cerca     │
│ │ ( ) omnisciente: Un narrador que todo lo ve                │
│ │ ( ) dramático: Escenas con tensión                     │
│ [ ] contemplativo                                         │
└─────────────────────────────────────────────────────────────┘
```

**Componentes por tipo de campo:**
| Tipo | Componente UI |
|------|------------|
| text | Input text (w-full) |
| select | Combo box dropdown |
| multi-select | Checkbox grid (2-3 columns) |
| radio | Radio button list (vertical) |

## 8. Slices de Implementación (QA-Oriented)

### Slice A: Extensión ui_definitions.yaml
- **Meta:** Definir estructura YAML con nuevos campos, groups, subtitles, notes
- **QA Check:** YAML parsea correctamente con loadSteps()
- **Entregable:** ui_definitions.yaml actualizado

### Slice B: wizard.service.ts — Soporte nuevos tipos
- **Meta:** Cargar y guardar multi-select, radio, groups, notes
- **QA Check:** Campo con grupo se asocia correctamente
- **Entregable:** WizardField con todos los campos nuevos

### Slice C: form_renderer.service.ts — Renderizado groups/cards
- **Meta:** renderField soporta multi-select (checkbox grid), radio, renderiza groups como cards
- **QA Check:** Campo en grupo "elenco" renderiza en card titled "PERSONAJES"
- **Entregable:** Función renderGroup() y renderField() actualizados

### Slice D: wizard.ejs — Nuevo layout visual
- **Meta:** Layout ancho (85vw), fuentes 18-20px, cards por grupo
- **QA Check:** Labels visibles con subtítulos, notas debajo de campos
- **Entregable:** Template wizard.ejs con nuevos estilos

### Slice E: generate.controller.ts — Construcción JSON completo
- **Meta:** Construir objeto story con protagonists[], storyteller, storyteller_config
- **QA Check:** POST a /stories recibe JSON equivalente a input_stories/*.md
- **Entregable:** Endpoint generar historia funcional

### Slice F: Integración Core API
- **Meta:** Frontend envía a Core y recibe story_id
- **QA Check:** Story creada en DB con todos los campos
- **Entregable:** Flujo completo generar → guardar → verificar en /galeria

### Slice G: Tests End-to-End
- **Meta:** Verificar flujo completo con Playwright
- **QA Check:** Crear historia completa y verificar en streaming
- **Entregable:** Spec test_e2e_wizard_spec.md

## 9. Orden de Implementación

| # | Slice | Archivo | Depende de |
|---|-------|---------|-----------|
| 1 | A | ui_definitions.yaml | - | - |
| 2 | B | wizard.service.ts | 4-13 | A |
| 3 | C | form_renderer.service.ts, wizard.ejs | 29-40 | B |
| 4 | D | generate.controller.ts | - | C |
| 5 | E | core_api.service.ts | - | D |
| 6 | F | tests/ | - | E |
| 7 | G | Playwright | - | F |

## 10. Validación QA (Checklist)

- [ ] ui_definitions.yaml parsea sin errores
- [ ] Campo multi-select devuelve array (no string)
- [ ] Campo radio devuelve valor seleccionado
- [ ] Grupo "elenco" renderiza en card titled "PERSONAJES"
- [ ] Grupo "narrador" renderiza en card titled "NARRADOR"
- [ ] Labels con subtítulos se muestran correctamente
- [ ] Notes aparecen debajo del campo
- [ ] Layout ancho 85vw visible en pantalla
- [ ] Fuentes labels 18-20px, inputs 18px
- [ ] Wizard completa 3 sub-steps de configuración
- [ ] Elenco de 1-5 personajes se guarda en sesión
- [ ] Storyteller selecciona de personajes definidos
- [ ] Campos con defaults se envían correctamente
- [ ] JSON salida mapea exactamente a estructura input_stories/el_monte_prohibido.md
- [ ] Historia creada visible en /galeria

## 11. Tareas (Tasks) por Slice

### Slice A: ui_definitions.yaml
- [ ] Reemplazar steps actuales por 3 nuevos steps
- [ ] Agregar campo `subtitle` a cada step
- [ ] Definir step_config_title con title, atmosfera
- [ ] Definir step_config_personajes (elenco: 5人物的 × name, role, traits + storyteller_id, voice_style)
- [ ] Definir step_config_voz (percepcion: 3 campos, conocimiento: 3 campos, lenguaje: 2 campos, sesgos: 2 campos)
- [ ] Agregar campo `type: radio` para distortion_level, language_register
- [ ] Agregar campo `type: multi-select` para traits, triggers, fear_focus, attention_focus
- [ ] Agregar campo `group` en todos los campos (elenco, narrador, percepcion, conocimiento, lenguaje, sesgos)
- [ ] Agregar campo `note` en storyteller_id y otros campos clave
- [ ] Probar con: `cd frontend && npx ts-node -e "import('./src/services/form_renderer.service').then(m => console.log(JSON.stringify(m.loadSteps())))"`

### Slice B: wizard.service.ts
- [ ] Extender WizardField (línea 4-13) con:
  ```typescript
  type: "text" | "textarea" | "select" | "radio" | "multi-select"
  subtitle?: string;
  note?: string;
  group?: string;
  default?: string;
  ```
- [ ] Extender RawField en form_renderer.service.ts con mismos campos
- [ ] Test: `npm run dev` y verificar no hay errores de tipos

### Slice C: form_renderer.service.ts
- [ ] Actualizar parseField() (línea 29-40) para incluir subtitle, note, group, default
- [ ] Test: loadSteps() devuelve los nuevos campos

### Slice D: wizard.ejs
- [ ] Cambiar container max-w-2xl → max-w-[85vw] o w-[85vw]
- [ ] Agregar renderizado de groups como cards (title + subtitle del group)
- [ ] Implementar renderizado para tipo `radio` (<input type="radio">)
- [ ] Implementar renderizado para tipo `multi-select` (checkbox grid)
- [ ] Agregar subtítulo debajo de cada label
- [ ] Agregar note debajo del campo cuando existe
- [ ] Aumentar fuentes: label text-lg-semibold, input text-lg
- [ ] Test: Visually verificar layout

### Slice E: generate.controller.ts
- [ ] Importar WizardData desde wizard.service
- [ ] Función buildProtagonists() que parsea session.wizard.step_config_personajes → protagonists[]
- [ ] Función buildStoryteller() que selecciona storyteller_id
- [ ] Función buildStorytellerConfig() que parsea session.wizard.step_config_voz
- [ ] Constructor buildStoryPayload() que ensambla todo
- [ ] Aplicar defaults implícitos: voice.person="primera", voice.tense="pasado"
- [ ] POST a /stories con payload completo
- [ ] Test: Crear historia y verificar JSON en response

### Slice F: core_api.service.ts
- [ ] Verificar endpoint POST /stories existente
- [ ] Agregar manejo de errores (connection refused, timeout)
- [ ] Test: POST genera historia visible en /galeria

### Slice G: Tests Playwright
- [ ] Spec test_wizard_personajes_voz.spec.ts
- [ ] Test flujo completo wizard pasos 1-3
- [ ] Test multi-select checkboxes funcionan
- [ ] Test radio buttons funcionan
- [ ] Test groups renderizan como cards
- [ ] Test historia aparece en /galeria

## 12. Comandos de Testing

```bash
#Slice A - Validar YAML
cd frontend && npx ts-node -e "import('./src/services/form_renderer.service').then(m => console.log(JSON.stringify(m.loadSteps())))"

# Slice B - Verificar tipos
cd frontend && npx tsc --noEmit

# Slice D - Dev server con hot-reload
cd frontend && npm run dev

# Slice E/F - Crear historia
# Navegar a http://localhost:3000/generar/paso/1
# Completar los 3 pasos
# Verificar en /galeria

# E2E
cd frontend && npx playwright test
```
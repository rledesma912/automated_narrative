# Spec-203: Mejora Steps — Atmósfera, Escenarios y Reglas

## 1. Objetivo
Completar la captura de datos para que el wizard genere JSON equivalente a input_stories/el_monte_prohibido.md:

1. **Atmosphere**: genre + subgenre + tone
2. **Scenarios**: Array de locations con name + description + order
3. **Rules**: Array de reglas del mundo

## 2. Contexto del Código Existente

### 2.1 Steps Actuales en ui_definitions.yaml (al 28/04/2026)

| Step ID | Campos actuales | Status |
|--------|---------------|--------|
| step_config_title | title, atmosfera | ❌ Faltan subgenre, tone |
| step_config_personajes | protagonista_1/2/3 (name, role, traits), storyteller_id, voice_style | ✅ Spec-202 |
| step_config_voz | perception, knowledge, language, bias | ✅ Spec-202 |
| step_world | ubicacion, clima, regla_paranormal | ❌ No mapea a scenarios/rules |
| step_plot | sinopsis | ✓ OK |

### 2.2 Mapeo Actual vs Target (el_monte_prohibido.md)

| Campo UI actual | Campo target | Mapeo |
|----------------|------------|-------|
| title | story.title | ✓ directo |
| atmosfera | atmosphere.genre | ✓ directo |
| step_config_personajes | protagonists[] | ✓ Spec-202 |
| storyteller_id | storyteller.id | ✓ Spec-202 |
| step_config_voz | storyteller_config | ✓ Spec-202 |
| **ubicacion** | scenarios[].name | ❌ solo 1 texto |
| **clima** | atmosphere.tone | ❌ incorrecto |
| **regla_paranormal** | rules[].text | ❌ solo 1 texto |
| sinopsis | synopsis | ✓ directo |

## 3. Nuevo Flujo Propuesto

### 3.1 Steps con Cambios

| Step | Cambios |
|------|--------|
| step_config_title | + **atmosphere_subgenre** + **atmosphere_tone** |
| step_config_personajes | YA IMPLEMENTADO (Spec-202) |
| step_config_voz | YA IMPLEMENTADO (Spec-202) |
| **step_world** | **REEMPLAZAR**: 4 escenarios + 5 reglas |
| step_plot | OK (sin cambios) |

## 4. Diseño de Campos

### 4.1 Atmosphere (step_config_title)

**YA EXISTE:** atmosphere (genre)
**AGREGAR:**

```yaml
- name: atmosphere_subgenre
  type: select
  label: "Qué estilo de horror"
  subtitle: "El subgénero o estilo específico"
  group: "atmosphere"
  options:
    - rural_folklore
    - gotico
    - urbano_moderno
    - historico
    - sci_fi
    - psicologico
    - sobrenatural
    - otro

- name: atmosphere_tone
  type: radio
  label: "Cómo sube la tensión"
  subtitle: "El tono de la historia"
  group: "atmosphere"
  options:
    - creciente_opresivo
    - constante
    - descendente
    - quebrado
    - ambiguo
```

### 4.2 Escenarios (step_world)

**REEMPLAZAR** ubicacion, clima, regla_paranormal POR:

```yaml
- name: scenario_1_name
  type: text
  label: "Escenario 1"
  subtitle: "El primer lugar de la historia"
  placeholder: "Ej: La casa de la abuela"
  group: "escenarios"
  required: true

- name: scenario_1_description
  type: textarea
  label: "Descripción del escenario 1"
  subtitle: "Cómo es este lugar"
  placeholder: "Una casa antigua en el campo..."
  rows: 2
  group: "escenarios"

# Opcionales: scenario_2 a scenario_4
- name: scenario_2_name
- name: scenario_2_description
- name: scenario_3_name
- name: scenario_3_description
- name: scenario_4_name
- name: scenario_4_description
```

### 4.3 Reglas (step_world)

```yaml
- name: rule_1_text
  type: textarea
  label: "Regla 1 del mundo"
  subtitle: "Una ley que rige este mundo"
  placeholder: "Los espejos muestran el pasado..."
  rows: 2
  group: "reglas"
  required: true

- name: rule_1_type
  type: select
  label: "Tipo de regla"
  group: "reglas"
  options:
    - entorno
    - psicologica
    - paranormal
    - evento
    - social

# Opcionales: rule_2 a rule_5
- name: rule_2_text
- name: rule_2_type
# ... hasta rule_5
```

## 5. Mapeo a Input Story

```typescript
interface WizardData {
  step_config_title: Record<string, string>;
  step_config_personajes: Record<string, string>;
  step_config_voz: Record<string, string>;
  step_world: Record<string, string>;
  step_plot: Record<string, string>;
}

interface Atmosphere {
  genre: string;
  subgenre: string;
  tone: string;
}

interface Scenario {
  id: string;
  order: number;
  name: string;
  description: string;
}

interface Rule {
  id: string;
  text: string;
  type: string;
}

interface Protagonist {
  id: string;
  name: string;
  role: string;
  traits: string[];
}

function buildAtmosphere(wizard: WizardData): Atmosphere {
  const t = wizard.step_config_title;
  return {
    genre: t.atmosphere,
    subgenre: t.atmosphere_subgenre || "",
    tone: t.atmosphere_tone || "",
  };
}

function buildProtagonists(wizard: WizardData): Protagonist[] {
  const p = wizard.step_config_personajes;
  const list: Protagonist[] = [];
  
  for (let i = 1; i <= 3; i++) {
    const name = p[`protagonista_${i}_name`];
    const role = p[`protagonista_${i}_role`];
    const traits = p[`protagonista_${i}_traits`];
    if (name) {
      list.push({
        id: `P${i}`,
        name,
        role: role || "",
        traits: parseMultiSelect(traits),
      });
    }
  }
  return list;
}

function buildScenarios(wizard: WizardData): Scenario[] {
  const w = wizard.step_world;
  const scenarios: Scenario[] = [];
  
  for (let i = 1; i <= 4; i++) {
    const name = w[`scenario_${i}_name`];
    const desc = w[`scenario_${i}_description`];
    if (name) {
      scenarios.push({ id: `S${i}`, order: i, name, description: desc || "" });
    }
  }
  return scenarios;
}

function buildRules(wizard: WizardData): Rule[] {
  const w = wizard.step_world;
  const rules: Rule[] = [];
  
  for (let i = 1; i <= 5; i++) {
    const text = w[`rule_${i}_text`];
    const type = w[`rule_${i}_type`];
    if (text) {
      rules.push({ id: `R${i}`, text, type: type || "entorno" });
    }
  }
  return rules;
}

function buildStoryteller(wizard: WizardData): { id: string } {
  const p = wizard.step_config_personajes;
  const id = p.storyteller_id?.replace("protagonista_", "P") || "P1";
  return { id };
}

function parseMultiSelect(value: string | string[] | undefined): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return String(value).split(",").map(s => s.trim()).filter(Boolean);
}

function buildStoryPayload(wizard: WizardData) {
  return {
    story: {
      title: wizard.step_config_title.title,
    },
    atmosphere: buildAtmosphere(wizard),
    protagonists: buildProtagonists(wizard),
    storyteller: buildStoryteller(wizard),
    scenarios: buildScenarios(wizard),
    rules: buildRules(wizard),
    synopsis: wizard.step_plot.sinopsis,
  };
}
```

## 5.1 Arquitectura de Transformación (CRÍTICO)

### 5.1.1 Flujo de Datos

```
Wizard UI (datos atómicos)
       ↓
Template de Transformación (frontend/config/story_templates/)
       ↓
Strings Formateados (parametría para API Core)
       ↓
API Core (POST /stories)
```

### 5.1.2 Capa de Transformación

El frontend debe tener una **capa de transformación configurable** que convierte los datos atómicos del wizard en strings descriptivos. Esta capa NO debe estar hardcodeada en código.

**Template de transformación ubicado en:** `frontend/config/story_templates/default.yaml`

```yaml
# Templates de transformación para la API
# Estos valores se construyen desde los datos atómicos del wizard

protagonista_template: "{{name}} es {{role}}{{#if traits}}, caracterizado por {{traits}}{{/if}}"

relator_template: "Narración en {{voice_style}}{{#if person}} persona{{/if}}, {{tense}}"

escenarios_template: "{{#each scenarios}}{{name}}{{#if description}}: {{description}}{{/if}}{{#unless @last}}; {{/unless}}{{/each}}"

atmosfera_template: "{{genre}}{{#if subgenre}} ({{subgenre}}){{/if}} - {{tone}}"

reglas_template: "{{#each rules}}{{text}}{{#unless @last}}; {{/unless}}{{/each}}"

personajes_full_template: |
  {{#each protagonists}}
  - {{id}}: {{name}}
    role: {{role}}
    {{#if traits}}traits: [{{traits}}]{{/if}}
  {{/each}}

storyteller_config_template: |
  perception:
    reliability: {{perception.reliability}}
    {{#if perception.distortion_level}}
    distortion:
      level: {{perception.distortion_level}}
      triggers: [{{perception.distortion_triggers}}]
    {{/if}}
  knowledge:
    domain:
      paranormal: {{knowledge.paranormal_knowledge}}
      religioso: {{knowledge.religioso_knowledge}}
    interpretation_style: {{knowledge.interpretation_style}}
  voice:
    {{#if voice_style}}style: {{voice_style}}{{/if}}
  language:
    register: {{language.language_register}}
    figurative_density: {{language.figurative_density}}
  bias:
    fear_focus: [{{bias.fear_focus}}]
    attention_focus: [{{bias.attention_focus}}]
```

### 5.1.3 Archivo Maestro de Template

**Nuevo archivo:** `frontend/config/story_templates/template_completo.yaml`

Este archivo es la **fuente de verdad** que:
1. Define la estructura de datos que la UI debe capturar
2. Define los templates de transformación para la API
3. Sirve como referencia para generar el ui_definitions.yaml

```yaml
# Template Completo para Historia de Horror
# Versión: 1.0.0
# Fecha: 2026-04-28

# ============================================
# SECCIÓN 1: CONFIGURACIÓN BÁSICA
# ============================================
story:
  title_template: "{{title}}"

atmosphere:
  genre_options:
    - terror_psicologico
    - horror_cosmico
    - terror_gotico
    - body_horror
    - paranormal
    - folk_horror
    - suspenso
    - terror_supervivencia
  
  subgenre_options:
    - rural_folklore
    - gotico
    - urbano_moderno
    - historico
    - sci_fi
    - psicologico
    - sobrenatural
    - otro
  
  tone_options:
    - creciente_opresivo
    - constante
    - descendente
    - quebrado
    - ambiguo

# ============================================
# SECCIÓN 2: PERSONAJES
# ============================================
protagonists:
  max_count: 5
  
  field_prefix: "protagonista"
  
  fields:
    - name: "{{prefix}}_name"
      label: "Nombre del personaje"
      type: text
      required: true
    
    - name: "{{prefix}}_role"
      label: "Rol o relación"
      type: text
      required: true
    
    - name: "{{prefix}}_traits"
      label: "Traits de personalidad"
      type: multi-select
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

storyteller:
  source_field: "storyteller_id"
  format: "P{n}"  # transforma "protagonista_1" → "P1"

voice_style_options:
  - intimista
  - omnisciente
  - dramático
  - contemplativo
  - poético

# ============================================
# SECCIÓN 3: VOZ NARRADORA
# ============================================
storyteller_config:
  perception:
    reliability_options:
      - subjetiva
      - objetiva
      - poco_confiable
    
    distortion_level_options:
      - minima
      - baja
      - media
      - alta
      - critica
    
    distortion_triggers_options:
      - miedo
      - oscuridad
      - fatiga
      - trauma
      - sustancia
      - paranoia
  
  knowledge:
    level_options:
      - nulo
      - bajo
      - medio
      - alto
      - experto
    
    interpretation_style_options:
      - literal
      - simbolica
      - mitologica
      - cientifica
      - supersticiosa
  
  language:
    register_options:
      - formal
      - coloquial
      - rural_tradicional
      - arcaico
      - poético
    
    density_options:
      - minima
      - baja
      - media
      - alta
      - maxima
  
  bias:
    fear_focus_options:
      - proteccion_de_hijos
      - supervivencia
      - perdida
      - traicion
      - corrupcion
      - lo_desconocido
      - aislamiento
    
    attention_focus_options:
      - sonidos
      - sombras
      - naturaleza
      - tecnologia
      - rostros
      - espacios_cerrados
      - detalles_fisicos

# ============================================
# SECCIÓN 4: ESCENARIOS
# ============================================
scenarios:
  max_count: 4
  min_count: 1
  field_prefix: "scenario"
  
  fields:
    - name: "{{prefix}}_{{n}}_name"
      label: "Nombre del escenario"
      type: text
      required: true
    
    - name: "{{prefix}}_{{n}}_description"
      label: "Descripción"
      type: textarea
      rows: 2
      required: false

# ============================================
# SECCIÓN 5: REGLAS
# ============================================
rules:
  max_count: 5
  min_count: 1
  field_prefix: "rule"
  
  fields:
    - name: "{{prefix}}_{{n}}_text"
      label: "Texto de la regla"
      type: textarea
      rows: 2
      required: true
    
    - name: "{{prefix}}_{{n}}_type"
      label: "Tipo de regla"
      type: select
      options:
        - entorno
        - psicologica
        - paranormal
        - evento
        - social

# ============================================
# SECCIÓN 6: TRAMA
# ============================================
synopsis:
  field_name: "sinopsis"
  label: "Sinopsis de la historia"
  type: textarea
  rows: 10
  hint: "Esbozo libre. El sistema extrae los beats automáticamente"

# ============================================
# SECCIÓN 7: MAPEO A API CORE
# ============================================
# Estos son los campos que se envían al endpoint POST /stories

api_payload:
  title:
    source: "step_config_title.title"
  
  protagonista:
    source: "step_config_personajes.protagonista_1_name"
    template: "{{name}} es el protagon {{#if role}} - {{role}}{{/if}}"
  
  relator:
    source: "step_config_personajes.voice_style"
    template: "Narración en {{voice_style}}"
  
  atmosfera:
    source: "step_config_title"
    template: "{{atmosphere}}{{#if atmosphere_subgenre}} ({{atmosphere_subgenre}}){{/if}} - {{atmosphere_tone}}"
  
  escenarios:
    source: "step_world"
    template: "{{scenario_1_name}}{{#if scenario_2_name}}; {{scenario_2_name}}{{/if}}{{#if scenario_3_name}}; {{scenario_3_name}}{{/if}}"
  
  reglas:
    source: "step_world"
    template: "{{rule_1_text}}{{#if rule_2_text}}; {{rule_2_text}}{{/if}}"
  
  personajes_full:
    source: "step_config_personajes"
    template: "generado desde array protagonists"
  
  storyteller_config:
    source: "step_config_voz + step_config_personajes"
    template: "generado desde estructura"
```

## 5.2 Estrategia de Implementación (RESUMEN)

1. **UI captura datos atómicos** → Se almacenan en sesión como `Record<string, string>`

2. **Capa de transformación** → Lee `template_completo.yaml` y construye los strings

3. **API recibe strings formateados** → Mapeo a StoryCreateRequest

4. **_CORE procesa** → El parser del Core maneja el resto (si viene en formato YAML)

**El archivo `template_completo.yaml` es la fuente de verdad.**

## 6. Slices de Implementación

### Slice A: ui_definitions.yaml - Atmosphere
- **Meta:** Agregar atmosphere_subgenre y atmosphere_tone al step_config_title
- **QA Check:** Dropdown subgenre tiene opciones, radio tone tiene opciones

### Slice B: ui_definitions.yaml - Scenarios
- **Meta:** REEMPLAZAR ubicacion/clima/regla_paranormal por 4 escenarios
- **QA Check:** 4 escenarios con name + description

### Slice C: ui_definitions.yaml - Rules
- **Meta:** Agregar 5 reglas con text + type
- **QA Check:** 5 reglas visibles

### Slice D: generate.controller.ts
- **Meta:** Build atmosphere, scenarios, rules desde wizard data
- **QA Check:** JSON equivalente a el_monte_prohibido.md

### Slice E: Tests E2E
- **Meta:** Crear historia con escenarios y reglas
- **QA Check:** Historia visible con datos completos

## 7. Orden de Implementación

| # | Slice | Depende de |
|---|-------|-----------|
| 1 | A: atmosphere (subgenre, tone) | - |
| 2 | B: escenarios (4) | 1 |
| 3 | C: reglas (5) | 2 |
| 4 | D: generate.controller.ts | A+B+C |
| 5 | E: Tests | D |

## 8. QA Checklist

- [ ] atmosphere_subgenre tiene opciones válidas
- [ ] atmosphere_tone tiene opciones
- [ ] Campos scenario_1_name hasta scenario_4_name existen
- [ ] Campos scenario_1_description hasta scenario_4_description existen
- [ ] Campos rule_1_text hasta rule_5_text existen
- [ ] Campos rule_1_type hasta rule_5_type existen
- [ ] Group "escenarios" renderiza como card
- [ ] Group "reglas" renderiza como card
- [ ] JSON final tiene atmosphere con subgenre y tone
- [ ] JSON final tiene scenarios[] con order
- [ ] JSON final tiene rules[] con type
- [ ] Historia visible en /galeria

## 9. Tareas por Slice

### Slice A: Atmosphere (step_config_title)
- [ ] Agregar campo atmosphere_subgenre al step_config_title
- [ ] Agregar campo atmosphere_tone al step_config_title
- [ ] group: "atmosphere" en ambos
- [ ] Probar renderizado en wizard

### Slice B: Scenarios (step_world)
- [ ] REMOVER: ubicacion, clima, regla_paranormal
- [ ] AGREGAR: scenario_1_name, scenario_1_description (required)
- [ ] AGREGAR: scenario_2_name, scenario_2_description
- [ ] AGREGAR: scenario_3_name, scenario_3_description
- [ ] AGREGAR: scenario_4_name, scenario_4_description
- [ ] group: "escenarios" en todos

### Slice C: Rules (step_world)
- [ ] AGREGAR: rule_1_text, rule_1_type (required)
- [ ] AGREGAR: rule_2_text, rule_2_type
- [ ] AGREGAR: rule_3_text, rule_3_type
- [ ] AGREGAR: rule_4_text, rule_4_type
- [ ] AGREGAR: rule_5_text, rule_5_type
- [ ] group: "reglas" en todos
- [ ] Opciones rule_type: entorno, psicologica, paranormal, evento, social

### Slice D: generate.controller.ts
- [ ] Importar WizardData
- [ ] Función buildAtmosphere()
- [ ] Función buildProtagonists()
- [ ] Función buildScenarios()
- [ ] Función buildRules()
- [ ] Función buildStoryteller()
- [ ] Función buildStoryPayload()
- [ ] Test: POST genera JSON correcto

### Slice E: Tests
- [ ] Crear historia con 3 escenarios
- [ ] Crear historia con 3 reglas
- [ ] Verificar en /galeria
- [ ] Verificar datos en DB

## 10. Comandos de Testing

```bash
# Validar YAML
cd frontend && npx ts-node -e "import('./src/services/form_renderer.service').then(m => console.log(JSON.stringify(m.loadSteps())))"

# Test integración
curl -X POST http://localhost:3000/generar/paso/1 \
  -d "title=Test&atmosphere=terror_paranormal&..."

# Ver historia creada
curl http://localhost:8010/stories
```

## 11. Dependencias

**Este spec requiere:**
- Spec-202 IMPLEMENTADO (step_config_personajes, step_config_voz)
- **ARCHIVO: `frontend/config/story_template.yaml`** — Este archivo es la fuente de verdad

**Orden:**
1. Spec-202 → implementado ✅
2. Spec-203 → este spec
3. `story_template.yaml` → fuente de verdad

## 12. Archivo Template Maestro (FUENTE DE VERDAD)

El archivo `frontend/config/story_template.yaml` contiene:

1. Opciones para todos los campos (genre_options, subgenre_options, etc.)
2. Templates de transformación para la API Core
3. Defaults implícitos (voice.person=primera, voice.tense=pasado)
4. Mapeo de campos wizard → api_payload

Este archivo DEBE actualizarse para cambiar la parametría, NO el código.

## 13. Comando de Verificación

```bash
# Verificar que el template existe
ls -la frontend/config/story_template.yaml

# Verificar que ui_definitions.yaml genera los campos correctos
cd frontend && npx ts-node -e "import('./src/services/form_renderer.service').then(m => console.log(JSON.stringify(m.loadSteps())))"
```
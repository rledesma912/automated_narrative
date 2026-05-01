# SPEC-217: YAML bidireccional CLI ↔ Wizard

## Estado
APROBADO — recomendaciones de preguntas 1/2/3 aceptadas. En IMPLEMENT.

---

## Contexto

Hoy existen dos puntos de entrada para crear historias:
- **Frontend (wizard 5 pasos)** → POST `/stories` → `_request_to_dto` → `CreateStoryUseCase`
- **CLI** (`python -m src generate ...`) → flags + opcional `--input <md>` → `MarkdownStoryParser` → `CreateStoryUseCase`

Ambos caminos convergen en `StoryCreateDTO` y persisten un `Story` con un campo `storyteller_config: dict` que es el contrato semántico rico del wizard (perception, knowledge, language, bias, atmosphere, voice, actos, scenarios, rules).

**El problema:** la estructura del `storyteller_config` que produce el parser actual NO coincide al 100% con la que `mapStoryToWizard()` (frontend) espera para rehidratar el wizard. Concretamente, falta o difiere:

| Campo esperado por wizard | Estado actual del parser |
|---|---|
| `storyteller_config.storyteller_id` (P1..P5) | Ausente |
| `storyteller_config.storyteller_name` | Ausente |
| `storyteller_config.voice_style` | Ausente |
| `storyteller_config.atmosphere.{genre, subgenre, tone}` | Solo `tone` y `genre` parciales |
| `storyteller_config.actos.act_N.{type, text}` | Hoy queda en `structured_synopsis`, no en `actos` |
| `storyteller_config.rules[].text` (no `content`) | Inconsistente (parser usa `text`, repo usa `content`) |
| `storyteller_config.scenarios[].{id, order, name, description}` | Hoy se persiste `name` solo en tabla `scenario`, no en config |

Resultado: si una historia se genera vía CLI y luego se intenta editar en el wizard (`/generar/cargar/:storyId`), varios campos llegan vacíos o desalineados.

**Lo que se busca:**
1. Establecer un **formato YAML canónico** que sea espejo exacto del `storyteller_config` que el wizard consume y produce.
2. Refactor del `MarkdownStoryParser` para que persista un `storyteller_config` completo y consistente con `mapStoryToWizard()`.
3. Nuevo comando CLI `export-yaml <story_id>` que vuelca cualquier historia de la DB a YAML editable, y ese YAML es válido como input para `generate --input` (bidireccionalidad).
4. Como verificación concreta: generar el YAML de "El monte prohibido" (story_id `92c1aec4-1de2-47ba-b8d1-bc374cbaddc9`) con el comando nuevo, y confirmar que al cargarlo de vuelta el wizard rehidrata 100% sus 5 pasos.

---

## Decisiones confirmadas

| # | Decisión | Justificación |
|---|---------|---------------|
| D1 | Origen del YAML de "El monte prohibido": exportarlo desde la DB actual usando el nuevo comando `export-yaml` | La DB ya tiene `storyteller_config` completo y validado; usarlo como ground truth garantiza fidelidad. |
| D2 | Formato YAML bidireccional: el output de `export-yaml` debe ser input válido de `generate --input` | Permite migrar/clonar/respaldar historias y compartir fixtures sin pasar por DB. |
| D3 | Cubrir el gap parser↔wizard arreglando el parser, no el wizard | El wizard ya define el contrato esperado (es el consumidor canónico). El parser es la pieza desactualizada. |
| D4 | El YAML refleja la estructura interna del `storyteller_config`, no una vista "humana" alternativa | Simétrico con `mapWizardToCore` y `mapStoryToWizard`. Sin transformaciones extra. |

---

## Formato YAML canónico

```yaml
---
title: "El monte prohibido"

# Top-level: estos campos van a Story directamente (no a storyteller_config)
personajes_full:
  - id: P1
    name: "Irene"
    role: "Narradora y protagonista; nuera de María"
    traits: ["observador", "sociable", "protector"]
  - id: P2
    name: "Ricardo"
    role: "Esposo de Irene; hijo de María"
    traits: ["escéptico", "pragmático", "protector"]
  # ... hasta P5

# Strings backward-compat — derivables de storyteller_config si faltan
protagonista: "Irene: Narradora y protagonista; nuera de María [observador, sociable, protector]; ..."
relator: "Primera persona en pasado. Narrador: Irene. Tono: intimista. Registro: coloquial."
escenarios: "Casa de María; Estancia de la fiesta; Monte de los Espinillos; Casa de María (regreso)"
atmosfera: "folk_horror (rural) - quebrado"
sinopsis: |
  [composición de los 5 actos en prosa, derivable de storyteller_config.actos]
reglas:
  - "La tecnología de celulares no existe en este tiempo."
  - "..."

# Estructura rica — la fuente de verdad para el wizard
storyteller_config:
  storyteller_id: P1
  storyteller_name: "Irene"
  voice_style: intimista

  voice:
    person: primera
    tense: pasado
    style: intimista

  atmosphere:
    genre: folk_horror
    subgenre: rural
    tone: quebrado

  scenarios:
    - id: S1
      order: 1
      name: "Casa de María"
      description: "Vivienda rural antigua, aislada de la modernidad"
    - id: S2
      order: 2
      name: "Estancia de la fiesta"
      description: "Casco de estancia donde se realiza el festejo familiar."
    # ... S3, S4

  rules:
    - id: R1
      text: "La tecnología de celulares no existe en este tiempo."
      type: social
    - id: R2
      text: "María no advierte con miedo, sino compartiendo leyendas..."
      type: psicologica
    # ... R3, R4, R5

  actos:
    act_1:
      type: exposicion
      text: |
        Irene y su familia llegan al amanecer a la casa de María en un taxi...
    act_2:
      type: accion_ascendente
      text: |
        La fiesta es alegre...
    act_3:
      type: climax
      text: |
        Dentro del monte...
    act_4:
      type: accion_descendente
      text: |
        Ricardo azota las riendas...
    act_5:
      type: desenlace
      text: |
        Ya dentro de la casa...

  perception:
    reliability: subjetiva
    distortion:
      level: baja
      triggers: ["oscuridad", "panico"]

  knowledge:
    domain:
      paranormal: bajo
      religioso: alto
    interpretation_style: mitologica

  language:
    register: coloquial
    figurative_density: baja

  bias:
    fear_focus: ["perdida", "desconocido"]
    attention_focus: ["sonidos", "sombras", "naturaleza"]
---
```

**Reglas de simetría con el wizard:**
- Toda key dentro de `storyteller_config` corresponde 1:1 a lo que `mapWizardToCore()` produce y `mapStoryToWizard()` consume.
- `personajes_full` es top-level de `Story` (NO va dentro de `storyteller_config`).
- Los strings `protagonista`, `relator`, `escenarios`, `atmosfera`, `sinopsis`, `reglas` son **derivados backward-compat** que `export-yaml` regenera y que el parser usa como fallback si la sección rica no existe.
- IDs `P1..P5`, `S1..S4`, `R1..R7` son convención del wizard (no UUIDs).

---

## Solución — 3 Slices

### Slice A — Refactor del MarkdownStoryParser

**Archivo:** `src/infrastructure/parsers/markdown_parser.py`

Cambios:
1. La extracción de `storyteller_config` debe poblar TODAS las keys del contrato (storyteller_id, storyteller_name, voice_style, voice, atmosphere completo, actos, scenarios con id/order/description, rules con id/text/type).
2. Si el YAML de input ya trae `storyteller_config:` como bloque rico (formato canónico nuevo), pasarlo directo sin re-derivar (preserva fidelidad).
3. Si solo trae el formato viejo (`atmosphere.tone`, `synopsis.act_N`, `protagonists`, `rules`), reconstruir el `storyteller_config` canónico aplicando las mismas reglas que `mapWizardToCore()` (simetría).
4. `personajes_full` se construye desde `protagonists:` o desde `storyteller_config.personajes_full` (preferir el rico si existe).
5. Mantener compatibilidad con el `el_monte_prohibido.md` actual (formato viejo) — debe seguir generando un Story funcional.

**Fixture de test:** parsear el YAML canónico nuevo y verificar que `storyteller_config` resultante tiene todos los campos que `mapStoryToWizard()` espera.

---

### Slice B — Comando CLI `export-yaml`

**Archivos:** `src/cli/runner.py`, `src/cli/commands.py`, opcionalmente `src/infrastructure/exporters/yaml_exporter.py` (nuevo)

1. Agregar subcomando `python -m src export-yaml <story_id> [--output <path>]`:
   - Carga la historia desde el repositorio (`SQLStoryRepository.get_by_id`).
   - Construye un dict YAML según el formato canónico, derivando los strings backward-compat desde `storyteller_config`.
   - Escribe a `input_stories/<slug>.yaml` por defecto, o al path indicado.
   - Imprime path resultante y confirma OK.

2. El YAML generado DEBE ser válido como `--input` del comando `generate`. (Round-trip test).

**Edge cases:**
- Historia sin `storyteller_config` (legacy): generar YAML solo con strings backward-compat + warning.
- Historia con beats generados: el export NO incluye los beats narrados (es solo el input/config, no el output narrativo).

---

### Slice C — Generación del fixture "El monte prohibido"

1. Ejecutar `python -m src export-yaml 92c1aec4-1de2-47ba-b8d1-bc374cbaddc9 --output input_stories/el_monte_prohibido.yaml`.
2. Inspeccionar el archivo generado (revisión visual).
3. (Opcional) reemplazar el `input_stories/el_monte_prohibido.md` viejo por el `.yaml` nuevo, o mantener ambos con extensiones distintas.
4. Smoke test e2e:
   - `python -m src generate --input input_stories/el_monte_prohibido.yaml --hasta analyst --mock` (no genera prosa, solo verifica parseo + persistencia).
   - Iniciar frontend, ir a `/generar/cargar/<id_nuevo>`, verificar que los 5 pasos del wizard se rehidratan completos.

---

## Criterios de Aceptación

| # | Criterio | Forma de verificar |
|---|----------|----------------|
| CA1 | Parser produce `storyteller_config` con todas las keys del contrato wizard | Test unitario: cargar YAML canónico, assert keys presentes |
| CA2 | Comando `export-yaml <id>` genera archivo en `input_stories/` | Smoke test CLI |
| CA3 | YAML exportado es input válido de `generate --input` (round-trip) | Test e2e: export → import → diff |
| CA4 | Cargar historia regenerada en wizard rehidrata los 5 pasos sin campos vacíos | Verificación visual en `/generar/cargar/:id` |
| CA5 | YAML de "El monte prohibido" generado y commiteado en `input_stories/` | Inspección del repo |
| CA6 | El `el_monte_prohibido.md` legacy sigue funcionando con `--input` | Test de regresión sobre tests existentes |

---

## Scope vs No-Scope

| SI es scope | NO es scope |
|-------------|------------|
| Refactor `MarkdownStoryParser` para `storyteller_config` completo | Cambios al schema de DB |
| Comando `export-yaml` en CLI | Endpoint HTTP de export |
| Fixture YAML de "El monte prohibido" | Re-generación de la historia (ya existe) |
| Tests unitarios del parser y exporter | Tests e2e completos del frontend |
| Compatibilidad con formato viejo (lectura) | Migración masiva de historias viejas |

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `src/infrastructure/parsers/markdown_parser.py` | Refactor: producir `storyteller_config` canónico completo |
| `src/cli/runner.py` | Registrar subcomando `export-yaml` |
| `src/cli/commands.py` | Handler `export_yaml(story_id, output)` |
| `src/infrastructure/exporters/yaml_exporter.py` (nuevo) | Lógica de Story → dict YAML canónico |
| `input_stories/el_monte_prohibido.yaml` (nuevo) | Fixture generado |
| `tests/unit/infrastructure/test_yaml_exporter.py` (nuevo) | Tests del exporter |
| `tests/unit/infrastructure/test_markdown_parser.py` | Extender tests con formato canónico nuevo |

---

## Preguntas abiertas

1. ¿El exporter incluye los actos como `act_N: {type, text}` (formato wizard) o también como `acto_N_exposicion` (formato sesión wizard)? **Recomiendo: solo `act_N`** porque es el formato del API/dominio; el wizard hace la traducción.
2. ¿Mantener `el_monte_prohibido.md` legacy o reemplazarlo por el `.yaml` nuevo? **Recomiendo: mantener ambos** durante la transición; el `.md` queda como referencia del formato viejo.
3. ¿El YAML usa extensión `.yaml` o sigue como `.md` con frontmatter? **Recomiendo: `.yaml` puro** — es 100% YAML, no necesita el wrapper markdown. El parser detecta extensión.

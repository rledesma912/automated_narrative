# Spec 044: ResponseNormalizer — Definición Canónica de Scope

## Estado

IMPLEMENTADO

---

## Contexto y motivación

El `ResponseNormalizer` fue creado en Spec 026 para limpiar el output raw de los LLMs antes
de persistirlo o usarlo. Con el tiempo acumuló dos responsabilidades distintas:

1. **Ruido de modelo** (lo que debe hacer): bloques `<think>`, `<reasoning>`, `<thought>` que
   algunos modelos razonadores emiten como parte de su proceso interno, junto con frases de
   relleno conversacional ("Aquí tienes", "Por supuesto").

2. **Estructura Markdown** (lo que **no** debe hacer): headers (`# ## ###`), separadores `---`,
   bloques de código ` ``` `. Estos elementos son Markdown válido que forman parte de la
   respuesta real — tanto para su uso en el pipeline como para la lectura humana del output.

**El problema concreto**: `strip_line_patterns` en `llm_core_definitions.yaml` contiene
`^#{1,6}\s` y `^---+\s*$`, que eliminan estructura Markdown legítima del output narrativo.

---

## Definición canónica del Normalizer

> **El `ResponseNormalizer` actúa solo cuando la respuesta del LLM contiene ruido de proceso
> — contenido que el modelo genera como parte de su razonamiento interno y que no es parte
> de la respuesta real. No altera el Markdown que el LLM produce como output útil.**

### Qué elimina (en scope)

| Categoría | Ejemplos | Mecanismo |
|---|---|---|
| Bloques de razonamiento | `<think>...</think>`, `<reasoning>...`, `<thought>...` | `thinking_tags` en YAML |
| Relleno conversacional | "Aquí tienes", "Por supuesto", "Espero que te guste" | `strip_line_patterns` en YAML |
| Espacios en blanco excesivos | 3+ líneas vacías consecutivas | `_clean_whitespace()` |

### Qué no elimina (fuera de scope)

| Categoría | Razón |
|---|---|
| Headers Markdown (`# ## ###`) | Pueden ser parte de la respuesta narrativa o estructurada |
| Separadores `---` | Markdown válido en salidas narrativas |
| Bloques de código ` ``` ` | El pipeline JSON los stripea localmente donde corresponde |
| Cualquier contenido narrativo | El Normalizer no tiene lógica de dominio |

> **Nota sobre JSON**: los parsers que consumen respuestas JSON (`_parse_distribution`,
> `_parse_anchors`, etc.) se encargan localmente de limpiar los delimitadores ` ```json ``` `.
> Eso es responsabilidad del parser, no del Normalizer.

---

## Terminología

El componente se llama **Normalizer** (`ResponseNormalizer`). En conversaciones anteriores
se usó el término "Parser" informalmente para referirse a él — esa nomenclatura queda
descontinuada. Los documentos que digan "el Parser limpia el output LLM" deben actualizarse
a "el Normalizer limpia el output LLM".

> No confundir con `MarkdownParser` (`src/infrastructure/parsers/markdown_parser.py`), que
> es el lector de archivos de input. Son componentes distintos con nombres correctos propios.

---

## Cambios de implementación

### A — YAML `config/llm_core_definitions.yaml`

**Eliminar** de `strip_line_patterns`:

```yaml
# ELIMINAR — no son ruido de modelo, son Markdown válido
- "^#{1,6}\\s"       # headers
- "^---+\\s*$"       # separadores horizontales
- "^```"             # bloques de código
- "^INSTRUCCIONES"   # defensa innecesaria — los prompts no deben aparecer en respuestas
```

**Conservar** en `strip_line_patterns`:

```yaml
strip_line_patterns:
  - "^Aquí tienes"
  - "^A continuación"
  - "^Espero que te guste"
  - "^Por supuesto"
  - "^Claro[,!.]"
```

**Eliminar** de `model_overrides.natsumura`:

```yaml
# ELIMINAR — strip de headers ya no aplica a ningún modelo
natsumura:
  strip_line_patterns_extra:
    - "^### "
    - "^## "
    - "^# "
```

Si el nodo `natsumura` queda vacío en `model_overrides`, eliminarlo también.

### B — Tests `tests/unit/infrastructure/test_response_normalizer.py`

**Eliminar** tests que verifican el strip de Markdown (comportamiento ya no soportado):

- `test_strips_markdown_headers`
- `test_strips_horizontal_rules`
- `test_model_override_applied_when_model_name_matches` (verifica strip de `### Apertura`)
- `test_model_override_skipped_when_model_name_differs` (misma lógica)

**Agregar** tests que verifican que Markdown se **preserva**:

- `test_preserves_markdown_headers` — un header `##` en el output llega intacto
- `test_preserves_horizontal_rules` — un `---` en el output llega intacto
- `test_preserves_code_fences` — un bloque ` ``` ` llega intacto

**Conservar** sin cambios:

- `test_strips_thinking_tag_block`
- `test_strips_multiple_thinking_tags_case_insensitive`
- `test_strips_preamble_lines`
- `test_preserves_paragraph_breaks`
- `test_collapses_three_or_more_blank_lines`
- `test_compact_mode_drops_blank_lines`
- `test_empty_config_returns_text_unchanged`
- `test_trailing_whitespace_cleaned`

**Actualizar** `_config()` en el fixture: eliminar `^#{1,6}\s` y `^---+\s*$` del
`strip_line_patterns` base; eliminar el nodo `model_overrides.natsumura`.

### C — Spec 001 `specs/001_marco_sdd.md`

Actualizar la tabla de componentes (línea ~30):

```markdown
# ANTES
| **Normalizer** | Post-procesamiento. Elimina ruido LLM (thinking tags, headers, frases de asistente). | `ResponseNormalizer` |

# DESPUÉS
| **Normalizer** | Elimina ruido de proceso LLM: bloques de razonamiento (`<think>`) y relleno conversacional. No altera Markdown válido del output. | `ResponseNormalizer` |
```

### D — Destino de Spec 026

Spec 026 permanece como referencia histórica de la arquitectura de configuración YAML
(`llm_core_definitions.yaml` como fuente de verdad). Agregar al inicio del archivo:

```markdown
> **Nota (Spec 044):** La sección de normalización (Hitos 3–4) queda supersedida por
> `specs/044_response_normalizer_scope.md`, que redefine el scope del `ResponseNormalizer`.
> La arquitectura YAML de config LLM (Hitos 1–2) sigue vigente.
```

No se elimina Spec 026 porque documenta decisiones de diseño de config que no están en
otro lugar.

---

## Archivos involucrados

| Archivo | Operación |
|---|---|
| `config/llm_core_definitions.yaml` | Limpiar `strip_line_patterns` y `model_overrides.natsumura` |
| `tests/unit/infrastructure/test_response_normalizer.py` | Eliminar tests de headers; agregar tests de preservación |
| `specs/001_marco_sdd.md` | Actualizar descripción del Normalizer en tabla de componentes |
| `specs/026_llm_core_definitions_spec.md` | Agregar nota de superseded en sección Normalizer |

---

## Criterios de aceptación

- `pytest tests/unit/infrastructure/test_response_normalizer.py -v` — todos pasan
- Un output narrativo con headers `##` llega a `beat.content` sin modificaciones
- Un bloque `<think>...</think>` NO llega a `beat.content`
- Una frase "Aquí tienes el relato:" NO llega a `beat.content`
- El YAML no tiene `^#{1,6}` ni `^---+` en ningún `strip_line_patterns`

---

## Relaciones con otros specs

| Spec | Relación |
|---|---|
| 026 — LLM Core Definitions | Supersede la sección de normalización (Hitos 3–4). Config YAML vigente. |
| 001 — Marco SDD | Actualizar tabla de componentes (descripción del Normalizer) |
| 031 — Prompts Compact | Prompts compactos generan Markdown — el Normalizer debe respetarlo |

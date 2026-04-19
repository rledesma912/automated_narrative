# Spec 029: Prompt Variants — `compact` y `frontier`

## Objetivo

Introducir dos variantes de prompt estructuralmente distintas para los roles
`director` y `voz`, seleccionables por perfil en `llm_core_definitions.yaml`.

| Variante | Para qué modelo | Filosofía |
|---|---|---|
| `frontier` | Claude, Gemini Pro, GPT-4 (instruction-following potente) | Prompt estructurado, secciones nombradas, instrucciones complejas, sinopsis completa |
| `compact` | llama3.1:8b, mistral local, modelos RP pequeños | Prompt mínimo, beat_summary al final como tarea explícita, sin instrucciones negativas, contexto como texto directo |

### Diagnóstico que motiva este spec

Con `ollama-natsumura` (y posiblemente con otros modelos locales pequeños) el modelo
ignora el `beat_summary` aunque llegue correctamente. Causa: el beat_summary está
enterrado al 25% de un prompt de ~1400 tokens. Los modelos locales pequeños son
*completion models* — responden mejor a "continuar desde aquí" que a "seguir estas
instrucciones en 8 secciones". Evidencia:

- Con beats correctos del Director (confirmado en log post Spec 028), la Voz sigue
  generando la misma apertura en todos los actos ignorando el resumen.
- El prior del modelo ("familia viaja en coche bajo la lluvia") domina sobre cualquier
  instrucción cuando el prompt es demasiado largo.

---

## Diseño

### 1. Campo `prompt_variant` en el perfil

```yaml
profiles:
  ollama-llama31:
    prompt_variant: compact      # ← nuevo campo
    provider: ollama
    ...

  anthropic-sonnet:
    prompt_variant: frontier     # ← nuevo campo
    provider: anthropic
    ...
```

- Si el campo no existe → default `frontier` (backwards compatible).
- El `PromptBuilder` lee `settings.active_profile_config().get("prompt_variant", "frontier")`.
- La variante aplica a todos los roles del perfil (`director`, `voz`).
  El rol `journal` usa siempre su template existente (sin variante, es JSON estructurado).

### 2. Archivos de prompt

```
config/prompts_generation/
  planner.md            → variante frontier (existente, sin cambios)
  planner_compact.md    → variante compact  (NUEVO)
  voice.md              → variante frontier (existente, sin cambios)
  voice_compact.md      → variante compact  (NUEVO)
  system.md             → solo para frontier (compact no usa system separado)
  journal.md            → sin variante (igual para ambos)
```

### 3. Diseño de `planner_compact.md`

Principios:
- Prompt total < 600 tokens.
- Ejemplo concreto del formato al final (few-shot inmediato antes de la respuesta).
- Sin secciones nombradas con `##` — el modelo responde al ejemplo, no a la instrucción.

```markdown
Eres el director de "{title}". Tu tarea: escribir exactamente {num_beats} líneas,
una por acto, describiendo qué ocurre en esa escena de esta historia específica.

Historia: {sinopsis}
Protagonistas: {protagonistas}
Atmósfera: {atmosfera}
Reglas: {reglas}

Estructura de actos que debes seguir:
{beats_spec}

Formato — escribe solo estas {num_beats} líneas y nada más:
1. [qué ocurre concreto en este acto]
2. [qué ocurre concreto en este acto]
```

### 4. Diseño de `voice_compact.md`

Principios:
- El beat_summary va **al final**, como la última instrucción antes de generar.
- Sin instrucciones negativas ("NUNCA...", "NO...") — confunden a modelos pequeños.
- `previous_context` como texto directo del último beat (no resumen de 150 chars).
- Prompt total < 500 tokens (excluida la sinopsis/contexto).
- Termina con una línea de apertura parcial para anclar el estilo de generación.

```markdown
Narrador: {relator} — primera persona, español.
Estilo: {atmosphere}
Historia: {title}
Personajes: {protagonistas}
Escenarios: {escenarios}
Reglas activas: {reglas}

--- LO QUE PASÓ ANTES ---
{previous_context}

--- ESTADO ACTUAL (journal) ---
{journal_context}

--- TU TAREA ---
Escribe el Acto {beat_number} de {total_beats} en 150-250 palabras.
Escena: {beat_summary}
Sinopsis de apoyo: {sinopsis}

Escribe prosa continua en español, sin títulos. Continúa:
```

**Por qué funciona para modelos pequeños:**
- La línea `Continúa:` es el ancla de completion — el modelo la interpreta como
  "completa esta frase iniciada" y genera prosa directamente.
- El beat_summary es lo ÚLTIMO que ve antes de generar → máxima influencia.
- Sin las 8 secciones de `##INSTRUCCIONES` que diluyen el foco.

### 5. `previous_context` ampliado para compact

Para la variante `compact`, `_build_previous_context()` devuelve los últimos
**500 chars** del beat anterior (no 150) sin truncamiento artificial. Para frontier
se mantienen 150 chars como resumen compacto.

La selección ocurre en `PromptBuilder.build_beat_prompt()`:

```python
variant = self._get_prompt_variant()
max_ctx = 500 if variant == "compact" else 150
previous_context = self._build_previous_context(previous_beats, max_chars=max_ctx)
```

### 6. Resolución en `PromptBuilder`

```python
def _get_prompt_variant(self) -> str:
    return settings.active_profile_config().get("prompt_variant", "frontier")

def _planner_template_path(self) -> str:
    variant = self._get_prompt_variant()
    return "planner_compact.md" if variant == "compact" else settings.prompt_file_planner

def _voice_template_path(self) -> str:
    variant = self._get_prompt_variant()
    return "voice_compact.md" if variant == "compact" else settings.prompt_file_voice
```

El template se carga lazy (primera llamada) y se cachea. Si el archivo de la variante
no existe, fallback al template frontier con warning.

---

## Hitos

### Hito 1 — Campo `prompt_variant` en perfiles YAML y resolución en `Settings`

- Agregar `prompt_variant: compact|frontier` a los perfiles en `llm_core_definitions.yaml`.
- Agregar método `active_profile_config() -> dict` a `Settings` que devuelve el bloque
  completo del perfil activo (incluyendo `prompt_variant`, `provider`, etc.).
- Perfiles con variante:
  - `ollama-llama31` → `compact`
  - `ollama-mistral` → `compact`
  - `anthropic-sonnet` → `frontier`
  - `gemini-cli` → `frontier`

### Hito 2 — `planner_compact.md`

- Crear `config/prompts_generation/planner_compact.md` siguiendo el diseño de §3.
- Variables requeridas: `{title}`, `{sinopsis}`, `{protagonistas}`, `{atmosfera}`,
  `{reglas}`, `{num_beats}`, `{beats_spec}`.

### Hito 3 — `voice_compact.md`

- Crear `config/prompts_generation/voice_compact.md` siguiendo el diseño de §4.
- Variables requeridas: `{relator}`, `{atmosphere}`, `{title}`, `{protagonistas}`,
  `{escenarios}`, `{reglas}`, `{previous_context}`, `{journal_context}`,
  `{beat_number}`, `{total_beats}`, `{beat_summary}`, `{sinopsis}`.

### Hito 4 — `PromptBuilder` con selección de variante

- Método `_get_prompt_variant() -> str`.
- Métodos `_planner_template_path()` y `_voice_template_path()` que devuelven el
  filename correcto según variante.
- `_build_previous_context()` acepta parámetro `max_chars: int`; el caller pasa
  500 para compact, 150 para frontier.
- `build_beat_prompt()` pasa `system_prompt=None` cuando la variante es `compact`
  (el template compact ya incluye todo; no se necesita system.md separado).
  Esto evita que OllamaAdapter concatene system.md + voice_compact.md duplicando
  el contexto.
- Templates lazy-cacheados por variante (no invalidar cache si se llama con distintas variantes).

### Hito 5 — `VozUseCase`: no pasar system_prompt en compact

En `VozUseCase.execute()`, la llamada a `build_voice_prompt()` genera el system.md.
Para la variante compact, ese system prompt no debe enviarse:

```python
variant = self.prompt_builder._get_prompt_variant()
system_prompt = None if variant == "compact" else self.prompt_builder.build_voice_prompt(story)
```

Esto se puede hacer en `VozUseCase` o delegar al `PromptBuilder` con un método
`build_system_prompt_for_voz(story) -> str | None`.

### Hito 6 — Tests

`tests/unit/application/test_prompt_builder.py` (agregar):

- `test_compact_variant_loads_compact_templates` — con perfil compact, los métodos
  de path devuelven `planner_compact.md` / `voice_compact.md`.
- `test_frontier_variant_loads_standard_templates` — con perfil frontier (o default),
  devuelve los templates estándar.
- `test_compact_previous_context_max_500` — `_build_previous_context` con variant=compact
  devuelve hasta 500 chars.
- `test_frontier_previous_context_max_150` — idem con frontier → 150 chars.
- `test_compact_voice_prompt_ends_with_continua` — el prompt generado termina con
  `Continúa:` (ancla de completion).
- `test_compact_beat_summary_is_last_content` — el beat_summary aparece en la
  segunda mitad del prompt (no enterrado al inicio).

`tests/unit/test_config_profiles.py` (agregar):

- `test_active_profile_config_returns_full_block` — `settings.active_profile_config()`
  devuelve el dict completo del perfil (incluyendo `prompt_variant`).

---

## Archivos involucrados

| Archivo | Hito | Operación |
|---|---|---|
| `config/llm_core_definitions.yaml` | 1 | Agregar `prompt_variant` a perfiles |
| `src/config.py` | 1 | Agregar `active_profile_config()` |
| `config/prompts_generation/planner_compact.md` | 2 | Crear |
| `config/prompts_generation/voice_compact.md` | 3 | Crear |
| `src/application/services/prompt_builder.py` | 4 | Selección de variante + max_chars |
| `src/application/use_cases/voz_use_case.py` | 5 | No pasar system_prompt en compact |
| `tests/unit/application/test_prompt_builder.py` | 6 | Tests de variante |
| `tests/unit/test_config_profiles.py` | 6 | Test `active_profile_config()` |

---

## Criterios de aceptación

- [ ] `pytest tests/ -q` — sin FAILED
- [ ] Con `ollama-llama31` (compact): el prompt de Voz termina con `Continúa:` y tiene
  el beat_summary en la última sección antes de generar
- [ ] Con `anthropic-sonnet` (frontier): el prompt de Voz usa `voice.md` sin cambios
- [ ] El system.md NO se concatena cuando la variante es compact
- [ ] Con compact, `previous_context` tiene hasta 500 chars (no truncado a 150)

---

## Fuera de alcance

- Variante `compact` para el rol `journal` — el journal ya responde bien porque
  su prompt pide JSON estructurado, que todos los modelos siguen correctamente.
- Variante `ultra_compact` para modelos de menos de 7B parámetros.
- Selección de variante por rol (distinto para director vs. voz) — si hiciera falta,
  puede extenderse el campo `prompt_variant` al nivel de rol en lugar del perfil.

---

## Relación con specs previos

- **Spec 026/027**: el campo `prompt_variant` se agrega al bloque de perfil en el mismo
  YAML. No rompe la estructura existente (campo opcional con default `frontier`).
- **Spec 028**: el parser robusto ya funciona. Este spec no toca el parser.
- **Spec 014**: los templates frontier (`planner.md`, `voice.md`) no se modifican.
  Este spec solo agrega los templates compact paralelos.

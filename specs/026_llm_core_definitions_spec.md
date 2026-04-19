# Spec 026: llm_core_definitions — Configuración SDD de Proveedores LLM + Pipeline de Normalización

## Objetivo

Establecer `config/llm_core_definitions.yaml` como **fuente de verdad única** para toda la
configuración de LLM (proveedor, modelos, temperaturas, context size, stop sequences y filtros
de respuesta), reemplazando las variables dispersas en `.env`. Simultáneamente, completar el
pipeline de normalización que existe definido pero no está conectado al flujo de generación.

### Resultado objetivo

```yaml
# config/llm_core_definitions.yaml — todo el comportamiento LLM en un solo lugar
provider: ollama

roles:
  director:
    model: Tohur/natsumura-storytelling-rp-llama-3.1:8b
    temperature: 0.4
    ...
  voz:
    ...
  journal:
    model: mistral:latest
    ...

response_filters:
  thinking_tags: [think, thought, reasoning]
  strip_markdown_headers: true
  ...
```

```bash
# El .env queda solo para secretos y paths
ANTHROPIC_API_KEY=...
DATABASE_URL=...
```

---

## Diagnóstico del sistema actual

| Componente | Estado | Problema |
|---|---|---|
| `config.py` (`Settings`) | LLM config en `.env` + defaults hardcodeados | Disperso, difícil de versionar, no soporta configs por rol |
| `llm_response_filters.yaml` | Existe en `config/` | **Nunca se lee desde Python** — código muerto |
| `ResponseNormalizer` | Existe en `infrastructure/normalizers/` | **Nunca se llama en el pipeline** — orphaned |
| `ResponseNormalizer.normalize()` | Hardcodea sus propias listas | Ignora el YAML, viola DRY; además colapsa párrafos de prosa (bug) |
| `voice.md` | Usa `### Apertura / Desarrollo / Cierre` | Modelos pequeños los reproducen literalmente en el output |
| Sinopsis en Voz | Sinopsis completa en cada beat prompt | Modelos pequeños anticipan beats futuros al leer el plot completo |

---

## Arquitectura de la solución

### Archivos nuevos / modificados

```
config/
  llm_core_definitions.yaml           ← NUEVO — fuente de verdad LLM
  llm_response_filters.yaml           ← ELIMINAR (migrado al anterior)
  prompts_generation/
    voice.md                          ← FIX — reemplazar ### por instrucciones en prosa

src/
  config.py                           ← REFACTOR — carga YAML, expone LLMCoreSettings
  infrastructure/
    normalizers/
      response_normalizer.py          ← REFACTOR — lee YAML, fix prose bug, agrega strip ###
  application/
    use_cases/
      director_use_case.py            ← FIX — aplicar normalización post-LLM
      voz_use_case.py                 ← FIX — aplicar normalización + ajustar sinopsis
    services/
      prompt_builder.py               ← FIX — sinopsis condicional por beat

.env / .env.sample                    ← LIMPIEZA — sacar vars LLM, dejar solo secretos/paths

CLAUDE.md                             ← ACTUALIZAR — nueva arquitectura de config
specs/001_marco_sdd.md                ← ACTUALIZAR — diagrama + tabla de componentes
```

### Flujo con el pipeline completo

```
StoryRunner
  └── DirectorUseCase.execute(story)
        ├── PromptBuilder.build_planner_prompt(story)
        ├── LLMProvider.generate(prompt, ...)        ← raw response
        ├── ResponseNormalizer.normalize(text, role="director")  ← NUEVO
        └── _parse_beats(clean_text)

  └── VozUseCase.execute(story, beat, ...)
        ├── PromptBuilder.build_beat_prompt(...)     ← sinopsis acotada por beat
        ├── LLMProvider.generate(prompt, ...)        ← raw response
        ├── ResponseNormalizer.normalize(text, role="voz")       ← NUEVO
        └── beat.content = clean_text
```

### Jerarquía de configuración

```
config/llm_core_definitions.yaml   → Toda la configuración LLM
.env                               → Secretos (API keys) + Paths del sistema
src/config.py (Settings)           → Carga ambos y expone objetos tipados
```

---

## Especificación: `config/llm_core_definitions.yaml`

```yaml
# config/llm_core_definitions.yaml
version: "1.0"

# Proveedor activo: ollama | gemini | anthropic | mock
provider: ollama

# Configuración Ollama
ollama:
  host: "http://localhost:11434"

# Configuración Gemini CLI
gemini:
  cli_command: gemini
  model: gemini-1.5-pro-latest

# Configuración Anthropic
anthropic:
  model: claude-sonnet-4-6

# Configuración por rol narrativo
roles:
  director:
    model: Tohur/natsumura-storytelling-rp-llama-3.1:8b
    temperature: 0.4
    num_ctx: 4096
    num_predict: 512
    stop: ["###", "---\n", "```"]

  voz:
    model: Tohur/natsumura-storytelling-rp-llama-3.1:8b
    temperature: 0.6
    num_ctx: 4096
    num_predict: 800
    stop: ["###", "---\n", "```", "INSTRUCCIONES", "## "]
    # Estrategia de inyección de sinopsis en el prompt de cada beat:
    #   full       → sinopsis completa (modelos potentes que saben ignorar beats futuros)
    #   beat_slice → segmento proporcional al beat actual (recomendado por defecto)
    #   none       → sin sinopsis (solo beat_summary + previous_context + journal)
    context_strategy: beat_slice

  journal:
    model: mistral:latest
    temperature: 0.3
    num_ctx: 2048
    num_predict: 256
    stop: []

# Filtros de respuesta (aplicados después de cada llamada LLM)
response_filters:
  # Tags de "pensamiento interno" a eliminar (con contenido entre tags)
  thinking_tags:
    - think
    - thought
    - reasoning

  # Patrones de líneas completas a eliminar (regex, aplicado línea por línea)
  strip_line_patterns:
    - "^#{1,6}\\s"           # headers markdown (# ## ### etc.)
    - "^---+$"               # separadores horizontales
    - "^```"                 # bloques de código
    - "^Aquí tienes.*:"      # frases de asistente
    - "^Espero que te guste"
    - "^Por supuesto"
    - "^Claro"

  # Preservar saltos de párrafo (líneas vacías entre párrafos)
  preserve_paragraph_breaks: true

  # Overrides por modelo (identificado por substring del nombre)
  model_overrides:
    deepseek-r1:
      strip_thinking: true
    qwen2.5:
      strip_thinking: false
    natsumura:
      strip_thinking: false
      strip_line_patterns_extra:
        - "^### "
        - "^## "
        - "^# "
```

---

## Hito 1 — `llm_core_definitions.yaml`

**Criterio de aceptación:**
- El archivo existe en `config/llm_core_definitions.yaml` con la estructura definida arriba
- El archivo tiene valores funcionales que replican el comportamiento actual del sistema
- `llm_response_filters.yaml` queda marcado como deprecado (o eliminado después de Hito 2)

**Tareas:**

- [x] **1.1** — Crear `config/llm_core_definitions.yaml` con la estructura especificada.
  - Verify: `python -c "import yaml; yaml.safe_load(open('config/llm_core_definitions.yaml'))"`

---

## Hito 2 — Refactor `Settings` en `config.py`

**Criterio de aceptación:**
- `Settings` carga `llm_core_definitions.yaml` y expone sub-objetos tipados: `llm_provider`, `llm_roles`, `llm_response_filters`
- Los adaptadores (`OllamaAdapter`, `GeminiCLIAdapter`, `AnthropicAdapter`) leen su config desde `settings.llm_roles.<rol>`
- Las variables LLM que estaban en `.env` se eliminan de `.env.sample` (con nota de migración)
- Las vars de secretos y paths permanecen en `.env`
- `settings.llm_model`, `settings.director_temperature`, etc. siguen existiendo como propiedades para backwards compatibility con el código existente, delegando al YAML

**Tareas:**

- [x] **2.1** — Agregar método `_load_llm_core()` a `Settings` que carga el YAML.
  - Archivo: `src/config.py`
  - Si el archivo no existe, loguea warning y usa defaults hardcodeados
  - Expone:
    - `settings.llm_provider` → `data["provider"]`
    - `settings.llm_role_config(role: str)` → dict con model/temp/num_ctx/num_predict/stop
    - `settings.llm_response_filter_config` → dict de filtros
  - Verify: `python -c "from src.config import settings; print(settings.llm_provider)"`

- [x] **2.2** — Actualizar `OllamaAdapter` para leer `num_ctx`, `num_predict`, `stop` del YAML via settings.
  - Archivo: `src/infrastructure/adapters/ollama_adapter.py`
  - Recibir el `role` como parámetro opcional en `generate()` o como config del adapter
  - Verify: `pytest tests/unit/infrastructure/test_ollama_adapter.py -v` (si existe)

- [x] **2.3** — Limpiar `.env.sample`: eliminar vars LLM movidas al YAML, agregar comentario de migración.
  - Variables a eliminar: `LLM_MODEL`, `LLM_MODEL_TEMPERATURE`, `DIRECTOR_TEMPERATURE`,
    `VOZ_TEMPERATURE`, `STATE_EXTRACTOR_MODEL`, `STATE_EXTRACTOR_TEMPERATURE`,
    `OLLAMA_HOST`, `GEMINI_CLI_COMMAND`, `GEMINI_MODEL_NAME`, `ANTHROPIC_MODEL`
  - Variables a conservar: `LLM_PROVIDER` (override de emergencia), `ANTHROPIC_API_KEY` (secreto)
  - Agregar comentario: `# LLM config moved to config/llm_core_definitions.yaml`
  - Verify: `.env.sample` tiene solo secretos + paths + override de proveedor

---

## Hito 3 — Refactor `ResponseNormalizer`

**Criterio de aceptación:**
- Lee la configuración de filtros desde `settings.llm_response_filter_config` (que viene del YAML)
- `normalize(text, role=None, model_name=None)` aplica filtros base + overrides por modelo
- **No colapsa párrafos** — las líneas vacías entre párrafos se preservan cuando `preserve_paragraph_breaks: true`
- Elimina headers markdown (`###`, `##`, `#`) del output narrativo
- Elimina thinking tags con su contenido
- Elimina líneas de "ruido de asistente"
- La clase sigue siendo stateless para su lógica de filtrado; recibe config en `__init__`

**Diseño:**

```python
class ResponseNormalizer:
    def __init__(self, config: dict | None = None):
        cfg = config or settings.llm_response_filter_config
        self._thinking_tags: list[str] = cfg.get("thinking_tags", [])
        self._strip_patterns: list[str] = cfg.get("strip_line_patterns", [])
        self._preserve_paragraphs: bool = cfg.get("preserve_paragraph_breaks", True)
        self._model_overrides: dict = cfg.get("model_overrides", {})

    def normalize(self, text: str, model_name: str = "") -> str:
        result = self._strip_thinking_tags(text)
        result = self._strip_noisy_lines(result, model_name)
        result = self._clean_whitespace(result)
        return result.strip()

    def _strip_thinking_tags(self, text: str) -> str: ...
    def _strip_noisy_lines(self, text: str, model_name: str) -> str: ...
    def _clean_whitespace(self, text: str) -> str:
        # Preserva líneas vacías entre párrafos si preserve_paragraph_breaks=True
        ...
```

**Tareas:**

- [x] **3.1** — Reescribir `ResponseNormalizer` según el diseño.
  - Archivo: `src/infrastructure/normalizers/response_normalizer.py`
  - Inyección de config via `__init__` (SOLID: DI, OCP)
  - No hardcodear ninguna lista — todo viene de `cfg`
  - Verify: unit tests (Hito 5)

---

## Hito 4 — Wiring del normalizer en el pipeline

**Criterio de aceptación:**
- `DirectorUseCase` normaliza la respuesta del LLM antes de pasarla a `_parse_beats()`
- `VozUseCase` normaliza la respuesta antes de asignar a `beat.content`
- El normalizer se inyecta en ambos use cases (no se instancia internamente)
- `StoryRunner` instancia y pasa el normalizer
- `SilentNormalizer` no-op para tests que no quieran testear normalización

**Diseño (inyección):**

```python
# StoryRunner.__init__
self.normalizer = ResponseNormalizer()

# DirectorUseCase.__init__
def __init__(self, llm, prompt_builder, normalizer=None):
    self.normalizer = normalizer or ResponseNormalizer()

# VozUseCase.__init__
def __init__(self, llm, memory_journalist=None, prompt_builder=None, normalizer=None):
    self.normalizer = normalizer or ResponseNormalizer()
```

**Sinopsis en Voz — ajuste de contexto:**

El beat prompt de Voz actualmente inyecta la sinopsis completa. Para modelos pequeños esto
causa anticipación de beats futuros. Se agrega un modo `sinopsis_hint` que inyecta solo
la parte relevante al beat actual:

```python
# PromptBuilder.build_beat_prompt()
# En lugar de sinopsis completa, inyectar un hint acotado:
sinopsis_hint = self._get_beat_sinopsis_hint(story.sinopsis, beat.number, total_beats)
```

`_get_beat_sinopsis_hint()` divide la sinopsis en `total_beats` segmentos aproximados y
retorna solo el segmento correspondiente al beat actual. Si la sinopsis no tiene suficiente
contenido para dividir limpiamente, retorna las primeras 2 oraciones como contexto general.

**Tareas:**

- [x] **4.1** — Inyectar `normalizer` en `DirectorUseCase` y aplicar post-LLM.
  - Archivo: `src/application/use_cases/director_use_case.py`
  - `clean_text = self.normalizer.normalize(response.text, model_name=settings.llm_model)`
  - `beats = self._parse_beats(clean_text, ...)`

- [x] **4.2** — Inyectar `normalizer` en `VozUseCase` y aplicar post-LLM.
  - Archivo: `src/application/use_cases/voz_use_case.py`
  - `clean_text = self.normalizer.normalize(response.text, model_name=settings.llm_model)`
  - `beat.content = clean_text`

- [x] **4.3** — Pasar `normalizer` desde `StoryRunner`.
  - Archivo: `src/core/orchestrator.py`
  - Instanciar `ResponseNormalizer()` en `__init__` y pasarlo a DirectorUseCase y VozUseCase

- [x] **4.4** — Implementar `context_strategy` en `PromptBuilder`.
  - Archivo: `src/application/services/prompt_builder.py`
  - `build_beat_prompt()` lee `settings.llm_role_config("voz")["context_strategy"]`
  - `"full"` → inyecta `story.sinopsis` completa (comportamiento actual)
  - `"beat_slice"` → llama `_get_beat_sinopsis_hint(sinopsis, beat.number, total_beats)` que divide la sinopsis en `total_beats` segmentos y retorna el correspondiente. Si la sinopsis tiene < 3 oraciones, retorna la sinopsis completa.
  - `"none"` → no inyecta sinopsis (el modelo trabaja solo con beat_summary + contexto)
  - La estrategia es config pura: cambiar de `full` a `beat_slice` en el YAML cambia el comportamiento sin tocar código.

---

## Hito 5 — Fix `voice.md`

**Criterio de aceptación:**
- Las instrucciones de estructura del beat no usan `### Apertura / Desarrollo / Cierre`
- Se reemplazan por instrucciones en prosa que no se filtran al output
- El resto del template no cambia

**Cambio concreto:**

```markdown
# ANTES (produce headers en output de modelos pequeños):
### Estructura del Beat
- Apertura: conexión con beat anterior
- Desarrollo: lo que ocurre en este beat
- Cierre: cliffhanger o transición

# DESPUÉS (instrucciones en prosa):
### Estructura del Beat
Comenzá conectando con lo último que ocurrió (1-2 oraciones). Luego desarrollá
la acción central de este beat. Cerrá con una imagen o frase que genere tensión
o anticipe el siguiente momento, sin resolver nada.
```

**Tareas:**

- [x] **5.1** — Editar `config/prompts_generation/voice.md`.
  - Reemplazar la lista `Apertura / Desarrollo / Cierre` por instrucciones en prosa
  - Verify: correr generación con Tohur y confirmar que `###` no aparece en el output

---

## Hito 6 — Tests

**Criterio de aceptación:**
- `ResponseNormalizer` tiene tests unitarios cubriendo cada tipo de filtro
- Los use cases tienen tests que verifican que el normalizer se aplica (mock del normalizer)
- La suite completa pasa: `pytest tests -v`

**Tareas:**

- [x] **6.1** — Crear `tests/unit/infrastructure/test_response_normalizer.py`.
  - Test: elimina `<think>` tags con contenido
  - Test: elimina líneas que empiezan con `###`, `##`, `#`
  - Test: elimina líneas `---`
  - Test: elimina frases de asistente ("Aquí tienes", "Por supuesto")
  - Test: **preserva** líneas vacías entre párrafos
  - Test: config custom via `__init__` (no depende de settings global)
  - Test: `model_overrides` activa filtros adicionales según `model_name`

- [x] **6.2** — Actualizar tests de `DirectorUseCase` y `VozUseCase`.
  - Inyectar normalizer mock para tests existentes (no romper tests de parsing/lógica)
  - Agregar test: el normalizer se llama con el texto raw del LLM

- [x] **6.3** — Tests de `context_strategy` en `PromptBuilder`.
  - Test: `beat_slice` — beat 1/5 recibe el segmento inicial, beat 5/5 recibe el final
  - Test: `beat_slice` — sinopsis corta (< 3 oraciones) retorna sinopsis completa sin dividir
  - Test: `full` — el prompt contiene la sinopsis completa
  - Test: `none` — el prompt no contiene ninguna referencia a la sinopsis

---

## Hito 7 — Documentación

**Criterio de aceptación:**
- `CLAUDE.md` refleja la nueva arquitectura de configuración
- `specs/001_marco_sdd.md` actualiza el diagrama de componentes
- `.env.sample` limpio y comentado

**Tareas:**

- [x] **7.1** — Actualizar `CLAUDE.md`.
  - Sección "Key Environment Variables": reemplazar vars LLM por referencia al YAML
  - Agregar sección "LLM Configuration": explica `llm_core_definitions.yaml`
  - Agregar sección "Response Pipeline": describe el flujo con normalizador

- [x] **7.2** — Actualizar `specs/001_marco_sdd.md`.
  - Agregar `ResponseNormalizer` al diagrama de arquitectura
  - Actualizar tabla de modelos de referencia
  - Agregar nota sobre `llm_core_definitions.yaml` como fuente de verdad

- [x] **7.3** — Limpiar `config/llm_response_filters.yaml`.
  - Agregar comentario `# DEPRECATED: migrado a llm_core_definitions.yaml`
  - (Eliminación física en una release posterior, para no romper git history)

---

## Orden de implementación

```
Hito 1 (YAML base)
  → Hito 2 (Settings + limpieza .env)
    → Hito 3 (ResponseNormalizer refactor)
      → Hito 4 (Wiring en pipeline + sinopsis hint)
        → Hito 5 (voice.md fix)
          → Hito 6 (Tests)
            → Hito 7 (Documentación)
```

---

## Boundaries

- **Always do:** `pytest tests -v` al cerrar cada hito.
- **Always do:** mantener backwards compatibility en `Settings` — propiedades existentes siguen funcionando.
- **Never do:** cambiar la firma del Protocol `LLMProvider`.
- **Never do:** que `ResponseNormalizer` tenga lógica narrativa — solo limpieza estructural/técnica.
- **Ask first:** cualquier cambio al esquema de la DB.
- **Ask first:** si se elimina físicamente `llm_response_filters.yaml`.

---

## Archivos involucrados

| Archivo | Hito | Operación |
|---|---|---|
| `config/llm_core_definitions.yaml` | 1.1 | Crear |
| `src/config.py` | 2.1 | Refactor |
| `src/infrastructure/adapters/ollama_adapter.py` | 2.2 | Actualizar |
| `.env.sample` | 2.3 | Limpiar |
| `src/infrastructure/normalizers/response_normalizer.py` | 3.1 | Reescribir |
| `src/application/use_cases/director_use_case.py` | 4.1 | Fix |
| `src/application/use_cases/voz_use_case.py` | 4.2 | Fix |
| `src/core/orchestrator.py` | 4.3 | Fix |
| `src/application/services/prompt_builder.py` | 4.4 | Fix |
| `config/prompts_generation/voice.md` | 5.1 | Fix |
| `tests/unit/infrastructure/test_response_normalizer.py` | 6.1 | Crear |
| `tests/unit/application/test_director_use_case.py` | 6.2 | Actualizar |
| `tests/unit/application/test_voz_use_case.py` | 6.2 | Actualizar |
| `CLAUDE.md` | 7.1 | Actualizar |
| `specs/001_marco_sdd.md` | 7.2 | Actualizar |
| `config/llm_response_filters.yaml` | 7.3 | Deprecar |

---

## Nota — Evolución posterior (Spec 027)

El shape descripto en este spec (`provider:` + `roles:` a nivel top) fue **reemplazado** por un shape de perfiles pre-configurados. Ver `specs/027_llm_profiles_spec.md` para el formato actual: `active_profile:` + `profiles:` con múltiples perfiles autocontenidos (cada uno con provider + roles completos) y override por `LLM_PROFILE`. Los mecanismos de este spec (normalizer pipeline, context_strategy, DI en use cases, response_filters con model_overrides) siguen vigentes sin cambios — el nuevo shape solo reorganiza cómo se expresa la config de provider/roles.

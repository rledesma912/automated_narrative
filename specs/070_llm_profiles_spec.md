# Spec 027: Perfiles de LLM pre-configurados

## Objetivo

Extender `config/llm_core_definitions.yaml` (Spec 026) con una capa de **perfiles
pre-configurados**. En lugar de un único bloque `provider:` + `roles:`, la YAML
pasa a contener varios perfiles nombrados (cada uno con su provider y sus 3
roles completamente definidos). Se cambia de perfil con una sola variable
(`active_profile:` en la YAML, o env `LLM_PROFILE` como override).

### Resultado objetivo

```yaml
version: "1.1"
active_profile: ollama-natsumura       # override: env LLM_PROFILE

profiles:
  ollama-natsumura:    { provider: ollama,    ollama: {...},    roles: {...} }
  ollama-llama31:      { provider: ollama,    ollama: {...},    roles: {...} }
  ollama-mistral:      { provider: ollama,    ollama: {...},    roles: {...} }
  anthropic-sonnet:    { provider: anthropic, anthropic: {...}, roles: {...} }
  anthropic-opus-voz:  { provider: anthropic, anthropic: {...}, roles: {...} }  # híbrido: voz=Opus 4.7, resto=Sonnet 4.6
  gemini-pro:          { provider: gemini,    gemini: {...},    roles: {...} }
  gemini-mixto:        { provider: gemini,    gemini: {...},    roles: {...} }

response_filters:
  thinking_tags: [...]
  strip_line_patterns: [...]
  model_overrides: {...}
```

---

## Motivación

Spec 026 centralizó toda la config LLM en un YAML pero todavía requiere editar
2-3 líneas cuando se quiere probar otro modelo (cambiar `roles.*.model`,
ajustar `stop`/`num_predict`/`context_strategy` específicos). No es un flujo
cómodo para experimentación rápida entre `llama3.1:8b`, `Tohur/natsumura`,
`mistral:latest`, o saltar a Anthropic/Gemini.

Con perfiles el cambio es **una línea**.

---

## Decisiones de diseño

1. **Perfil = provider + roles** (autocontenido por provider). Un perfil puede
   saltar de Ollama a Anthropic sin tocar nada más. Cada perfil trae su propio
   bloque adapter-specific (`ollama`/`anthropic`/`gemini`).
2. **Sin herencia**. Cada perfil define todos sus campos (model, temperature,
   num_ctx, num_predict, stop, context_strategy). Más verboso pero sin
   indirección ni capas default.
3. **Migración dura**. El shape plano `provider:`/`roles:` del Spec 026
   desaparece. La YAML solo entiende el shape nuevo. `response_filters` sigue
   a nivel top (transversales a todos los modelos, con `model_overrides` para
   lo específico por modelo).
4. **Convención model-por-rol**. El `model` de la llamada siempre vive en
   `profiles.<perfil>.roles.<rol>.model`. El bloque adapter-specific
   (`ollama.host`, `anthropic.model`, `gemini.model`) solo aporta settings de
   transporte o default de fallback. Esto permite mezclar modelos dentro de
   un mismo perfil (ej. `gemini-mixto`: Pro para narrativa, Flash para journal).

### Precedencia de resolución

1. Variable de entorno `LLM_PROFILE` (si está seteada y existe el perfil).
2. `active_profile:` de la YAML.
3. Fallback `ollama-natsumura` si no existe ninguno — con warning.

---

## Shape completo

```yaml
version: "1.1"
active_profile: ollama-natsumura

profiles:
  ollama-natsumura:
    provider: ollama
    ollama: { host: "http://localhost:11434" }
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
        stop: ["###", "---\n", "```", "## ", "INSTRUCCIONES"]
        context_strategy: beat_slice
      journal:
        model: mistral:latest
        temperature: 0.3
        num_ctx: 2048
        num_predict: 256
        stop: []

  ollama-llama31:
    provider: ollama
    ollama: { host: "http://localhost:11434" }
    roles:
      director: { model: llama3.1:8b, temperature: 0.4, num_ctx: 4096, num_predict: 512, stop: ["###", "---\n"] }
      voz:      { model: llama3.1:8b, temperature: 0.6, num_ctx: 4096, num_predict: 800, stop: ["###", "---\n"], context_strategy: full }
      journal:  { model: mistral:latest, temperature: 0.3, num_ctx: 2048, num_predict: 256, stop: [] }

  ollama-mistral:
    provider: ollama
    ollama: { host: "http://localhost:11434" }
    roles:
      director: { model: mistral:latest, temperature: 0.4, num_ctx: 4096, num_predict: 512, stop: [] }
      voz:      { model: mistral:latest, temperature: 0.6, num_ctx: 4096, num_predict: 800, stop: [], context_strategy: full }
      journal:  { model: mistral:latest, temperature: 0.3, num_ctx: 2048, num_predict: 256, stop: [] }

  anthropic-sonnet:
    provider: anthropic
    anthropic: { model: claude-sonnet-4-6 }
    roles:
      director: { model: claude-sonnet-4-6, temperature: 0.4 }
      voz:      { model: claude-sonnet-4-6, temperature: 0.6, context_strategy: full }
      journal:  { model: claude-sonnet-4-6, temperature: 0.3 }

  gemini-pro:
    provider: gemini
    gemini: { cli_command: gemini, model: gemini-1.5-pro-latest }
    roles:
      director: { model: gemini-1.5-pro-latest, temperature: 0.4 }
      voz:      { model: gemini-1.5-pro-latest, temperature: 0.6, context_strategy: full }
      journal:  { model: gemini-1.5-pro-latest, temperature: 0.3 }

  gemini-mixto:
    # Pro para narrativa (calidad), Flash para journal (coste/velocidad)
    provider: gemini
    gemini: { cli_command: gemini, model: gemini-1.5-pro-latest }
    roles:
      director: { model: gemini-1.5-pro-latest,   temperature: 0.4 }
      voz:      { model: gemini-1.5-pro-latest,   temperature: 0.6, context_strategy: full }
      journal:  { model: gemini-1.5-flash-latest, temperature: 0.3 }

response_filters:
  thinking_tags: [think, thought, reasoning]
  strip_line_patterns:
    - "^#{1,6}\\s"
    - "^---+\\s*$"
    - "^```"
    - "^Aquí tienes"
    - "^Espero que te guste"
    - "^Por supuesto"
    - "^Claro[,!.]"
    - "^INSTRUCCIONES"
  preserve_paragraph_breaks: true
  model_overrides:
    natsumura: { strip_line_patterns_extra: ["^### ", "^## ", "^# "] }
    deepseek-r1: { strip_thinking: true }
    qwen2.5: { strip_thinking: false }
```

---

## Hitos

### Hito 1 — Reescribir YAML al nuevo shape

- Migrar `config/llm_core_definitions.yaml` al shape con `active_profile:` +
  `profiles:`.
- Incluir los 6 perfiles iniciales listados arriba.
- Subir `version:` a `"1.1"`.

### Hito 2 — Resolver de perfil en `src/config.py`

- Nueva función pura `_resolve_active_profile(core: dict, env_override: str | None) -> tuple[str, dict]`
  que devuelve `(nombre_perfil, bloque_perfil)` aplicando precedencia.
- Loggear con claridad qué perfil se activó (`[CONFIG] perfil activo: <nombre>`)
  y si se activó por env.
- Recablear properties:
  - `llm_provider` → `profile["provider"]`
  - `ollama_host` → `profile.get("ollama", {}).get("host", ...)`
  - `anthropic_model` → `profile.get("anthropic", {}).get("model", ...)`
  - `gemini_cli_command`, `gemini_model_name` → del bloque `profile.get("gemini", ...)`
  - `role_config(role)` → `profile.get("roles", {}).get(role, {})`
- Añadir campo `llm_profile: str = ""` a `Settings` para captura del env var.
- `llm_response_filter_config` **no cambia** — sigue leyendo
  `_llm_core.get("response_filters", {})` (es top-level).

### Hito 3 — `.env.sample`

- Reemplazar la sección `LLM_PROVIDER` por `LLM_PROFILE`:
  ```
  # LLM_PROFILE=ollama-llama31
  ```
  Cada perfil ya trae su provider — el env override pisa el perfil completo.

### Hito 4 — Tests

`tests/unit/test_config_profiles.py` (nuevo):

- `test_active_profile_from_yaml` — sin env, usa `active_profile:` de la YAML.
- `test_env_override_wins` — `LLM_PROFILE=otro` pisa el YAML.
- `test_unknown_profile_falls_back_to_default` — con warning, sin romper.
- `test_role_config_reflects_active_profile` — cambiar de perfil cambia el modelo devuelto.
- `test_llm_provider_reflects_active_profile` — perfil anthropic → provider anthropic.

### Hito 5 — Documentación

- Crear este archivo (027).
- Actualizar sección "LLM Configuration" de `CLAUDE.md` con el nuevo shape y
  cómo añadir un perfil.
- Añadir nota al final de `specs/026_llm_core_definitions_spec.md` apuntando a 027.

---

## Out of scope

- No se agrega herencia de defaults (`defaults.roles.*`) — si aparece mucha
  duplicación en perfiles del mismo provider, se evalúa en un spec futuro.
- No se agrega CLI flag `--profile <nombre>` — por ahora solo env var + YAML.
  Puede sumarse como hito menor si hace falta.

---

## Relación con specs previos

- **Spec 026**: consolidó config LLM en YAML. Este spec extiende ese YAML con
  una capa de presets. El shape plano de 026 deja de ser válido.
- **Spec 001**: SDD / Clean Architecture — este cambio es puramente de
  infraestructura (`config.py`) y YAML; no toca domain ni application.

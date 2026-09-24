# Spec 020: Anthropic API Provider

> **Estado:** implementado. Claude Opus 4.7 está en uso productivo vía el perfil
> híbrido `anthropic-opus-voz` (rol `voz` con `claude-opus-4-7`, resto de roles
> con `claude-sonnet-4-6`). Ver `config/llm_core_definitions.yaml` y Spec-070.
> El `AnthropicAdapter` omite `temperature` para modelos con prefijo
> `claude-opus-4` (`_NO_SAMPLING_PREFIXES`).

## Objetivo

Incorporar Anthropic API (claude-opus-4-7 u otros modelos cloud de Anthropic) como
cuarto proveedor de LLM, junto a Ollama, Gemini CLI y Mock. La integración debe ser
quirúrgica: solo afecta la capa de infraestructura y configuración, sin tocar dominio,
casos de uso, ni el orquestador.

### Resultado objetivo

```bash
# Usar Anthropic desde CLI
python -m src generate --provider anthropic --input el_monte_prohibido.md

# O configurar como proveedor por defecto en .env
LLM_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-opus-4-7
```

---

## Diagnóstico del sistema actual

| Componente | Estado |
|---|---|
| `LLMProvider` Protocol | `generate(prompt, *, system_prompt, model, temperature) -> LLMResponse` |
| `LLMFactory` | Registra: `"ollama"` (default), `"gemini"`, `"mock"` |
| `Settings` (config.py) | No tiene `anthropic_api_key` ni `anthropic_model` |
| `LLMResponse` | `text: str`, `context: list[int] | None`, `word_count: int` |
| `OllamaAdapter` | Modelo de referencia: acepta `system_prompt`, `model`, `temperature` |

**Diferencias clave de la API de Anthropic vs Ollama:**

1. `system` es un parámetro de primer nivel en `messages.create()`, no se concatena al prompt.
2. `claude-opus-4-7` **no acepta** `temperature`, `top_p`, ni `top_k`. Pasarlos causa `BadRequestError 400`.
3. Los errores son tipados: `anthropic.AuthenticationError`, `anthropic.RateLimitError`, `anthropic.BadRequestError`.
4. El SDK es `anthropic` (PyPI), clase `AsyncAnthropic`.

---

## Arquitectura de la solución

### Sin cambios a: domain, application, core, cli (excepto CLI flag si aplica)

```
src/
  config.py                          ← +anthropic_api_key, +anthropic_model
  infrastructure/
    adapters/
      anthropic_adapter.py           ← nuevo
      __init__.py                    ← +AnthropicAdapter
    factories.py                     ← +"anthropic" case
```

### Flujo de datos

```
LLMFactory.get_provider(provider="anthropic")
    └── AnthropicAdapter(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

AnthropicAdapter.generate(prompt, *, system_prompt, model, temperature)
    └── AsyncAnthropic().messages.create(
            model=model or self.default_model,
            max_tokens=4096,
            system=system_prompt,        # primer nivel
            messages=[{"role":"user","content":prompt}]
            # SIN temperature para Opus 4.7
        )
    └── retorna LLMResponse(text=response.content[0].text)
```

---

## Hitos y tareas

### Hito 1 — Configuración

**Criterio de aceptación:**
- `Settings` expone `anthropic_api_key: str = ""` y `anthropic_model: str = "claude-opus-4-7"`
- Los valores se leen del `.env` (o variables de entorno)
- No rompe nada si las claves están vacías (la validación ocurre al instanciar el adapter)

**Tareas:**

- [ ] **1.1** — Agregar campos a `Settings`.
  - Archivo: `src/config.py`
  - Añadir bajo el bloque `# Gemini CLI`:
    ```python
    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"
    ```
  - Verify: `python -c "from src.config import settings; print(settings.anthropic_model)"`

- [ ] **1.2** — Agregar `anthropic` a dependencias del proyecto.
  - Archivo: `pyproject.toml`
  - Añadir `"anthropic>=0.40.0"` a `dependencies`
  - Verify: `pip install -e .` sin errores (o confirmar que ya está instalado)

---

### Hito 2 — AnthropicAdapter

**Criterio de aceptación:**
- `AnthropicAdapter.generate()` cumple la firma del Protocol `LLMProvider`
- Para modelos Opus 4.x (`claude-opus-*`): no envía `temperature` en el request
- Para otros modelos: sí envía `temperature` si se especifica
- Maneja `AuthenticationError`, `RateLimitError`, `BadRequestError` con mensajes claros
- `close()` es no-op (el cliente Anthropic no mantiene conexión persistente)

**Tareas:**

- [ ] **2.1** — Crear `src/infrastructure/adapters/anthropic_adapter.py`.

  ```python
  """Anthropic API adapter."""
  import logging
  import anthropic
  from src.config import settings
  from src.domain.interfaces import LLMResponse

  logger = logging.getLogger(__name__)

  _NO_SAMPLING_MODELS = ("claude-opus-4",)  # prefijos que no aceptan temperature


  class AnthropicAdapter:
      def __init__(self, api_key: str | None = None, default_model: str | None = None):
          key = api_key or settings.anthropic_api_key
          if not key:
              raise ValueError(
                  "ANTHROPIC_API_KEY no configurada. "
                  "Agrégala al .env o exporta la variable de entorno."
              )
          self._client = anthropic.AsyncAnthropic(api_key=key)
          self.default_model = default_model or settings.anthropic_model

      async def generate(
          self,
          prompt: str,
          *,
          system_prompt: str | None = None,
          model: str | None = None,
          temperature: float | None = None,
      ) -> LLMResponse:
          model_name = model or self.default_model
          kwargs: dict = {
              "model": model_name,
              "max_tokens": 4096,
              "messages": [{"role": "user", "content": prompt}],
          }
          if system_prompt:
              kwargs["system"] = system_prompt

          # Opus 4.x no acepta parámetros de sampling
          uses_sampling = not any(model_name.startswith(p) for p in _NO_SAMPLING_MODELS)
          if uses_sampling and temperature is not None:
              kwargs["temperature"] = temperature

          logger.debug(f"[ANTHROPIC] model={model_name}")
          logger.debug(f"[ANTHROPIC] prompt (primeros 500):\n{prompt[:500]}")

          try:
              response = await self._client.messages.create(**kwargs)
          except anthropic.AuthenticationError as e:
              raise RuntimeError(f"[ANTHROPIC] API key inválida: {e}") from e
          except anthropic.RateLimitError as e:
              raise RuntimeError(f"[ANTHROPIC] Rate limit alcanzado: {e}") from e
          except anthropic.BadRequestError as e:
              raise RuntimeError(f"[ANTHROPIC] Request inválido: {e}") from e

          text = response.content[0].text
          logger.debug(f"[ANTHROPIC] respuesta (primeros 300):\n{text[:300]}")
          return LLMResponse(text=text)

      async def close(self) -> None:
          pass
  ```
  - Verify: importación sin errores `python -c "from src.infrastructure.adapters.anthropic_adapter import AnthropicAdapter"`

- [ ] **2.2** — Exportar desde `src/infrastructure/adapters/__init__.py`.
  - Agregar `from src.infrastructure.adapters.anthropic_adapter import AnthropicAdapter`
  - Verify: `python -c "from src.infrastructure.adapters import AnthropicAdapter"`

---

### Hito 3 — Registro en LLMFactory

**Criterio de aceptación:**
- `LLMFactory.get_provider(provider="anthropic")` retorna `AnthropicAdapter`
- El proveedor por defecto sigue siendo `"ollama"` si `llm_provider` no cambia
- `settings.llm_provider = "anthropic"` en `.env` activa Anthropic automáticamente

**Tareas:**

- [ ] **3.1** — Agregar caso `"anthropic"` en `LLMFactory`.
  - Archivo: `src/infrastructure/factories.py`
  - Agregar import: `from src.infrastructure.adapters import AnthropicAdapter`
  - Agregar bloque antes del default `OllamaAdapter`:
    ```python
    if selected_provider == "anthropic":
        logger.info(
            f"[FACTORY] Instanciando proveedor Anthropic ({settings.anthropic_model})",
            module="llm_factory",
        )
        return AnthropicAdapter()
    ```
  - Verify: `pytest tests/unit/infrastructure/test_llm_factory.py -v` (si existe) o crear el test

---

### Hito 4 — Tests

**Criterio de aceptación:**
- Test unitario de `AnthropicAdapter` con cliente mock (sin llamadas reales a la API)
- Test de `LLMFactory` verificando que `provider="anthropic"` retorna `AnthropicAdapter`
- La suite completa sigue pasando: `pytest tests/unit/ -q --ignore=tests/unit/core/`

**Tareas:**

- [ ] **4.1** — Crear `tests/unit/infrastructure/test_anthropic_adapter.py`.
  - Mockear `anthropic.AsyncAnthropic` con `unittest.mock.AsyncMock`
  - Test: `generate()` retorna `LLMResponse` con el texto correcto
  - Test: sin `ANTHROPIC_API_KEY`, lanza `ValueError` en `__init__`
  - Test: `AuthenticationError` del cliente se convierte en `RuntimeError`
  - Test: para modelos `claude-opus-*`, `temperature` NO está en el payload enviado
  - Test: `close()` es no-op (no lanza)

- [ ] **4.2** — Test de factory en `tests/unit/infrastructure/test_llm_factory.py`.
  - Crear o agregar al archivo existente
  - Verificar que `LLMFactory.get_provider(provider="anthropic")` retorna instancia de `AnthropicAdapter`
  - Mockear `settings.anthropic_api_key = "test-key"` para evitar `ValueError`

---

## Orden de implementación

```
Hito 1 (config)
  → Hito 2 (adapter)
    → Hito 3 (factory)
      → Hito 4 (tests)
```

---

## Boundaries

- **Always do:** `pytest tests/unit/ -q --ignore=tests/unit/core/` al cerrar cada hito.
- **Never do:** modificar `LLMProvider` Protocol, `LLMResponse`, use cases, orchestrator.
- **Never do:** llamadas reales a la API en tests — siempre mockear `anthropic.AsyncAnthropic`.
- **Ask first:** si se necesitan cambios en el CLI `--provider` flag (actualmente ya acepta string libre).

---

## Archivos involucrados

| Archivo | Hito |
|---|---|
| `src/config.py` | 1.1 |
| `pyproject.toml` | 1.2 |
| `src/infrastructure/adapters/anthropic_adapter.py` | 2.1 |
| `src/infrastructure/adapters/__init__.py` | 2.2 |
| `src/infrastructure/factories.py` | 3.1 |
| `tests/unit/infrastructure/test_anthropic_adapter.py` | 4.1 |
| `tests/unit/infrastructure/test_llm_factory.py` | 4.2 |

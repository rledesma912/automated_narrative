# SPEC-480: La Voz en Anthropic (EV-2)

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development)
**Estado:** DONE (2026-09-24) — integración completa y desplegada; el perfil híbrido no está activo; la evaluación con Claude queda pendiente de presupuesto
**Roadmap:** EV-2. Sigue a Spec-470 (EV-3), que dejó como techo del modelo local la gramática torpe y los errores de continuidad.

---

## ASSUMPTIONS

1. **Solo la Voz** pasa a Claude; Analyst, Mapper y Journal siguen en Ollama (`gemma3:12b`). La Voz es donde se nota la prosa y son 5 de las 16 llamadas.
2. El resto del pipeline, los prompts de Spec-470 (compact) y las entidades de Spec-450 no cambian. La Voz en Claude usa la variante de prompt **compact**, la misma que hoy, para comparar solo el modelo.
3. Se usa el SDK oficial `anthropic` (ya es dependencia, 0.96.0) y la `ANTHROPIC_API_KEY` del `.env`.
4. El perfil local actual (`ollama-gemma3-12b`) sigue siendo el activo hasta que la evaluación muestre que vale la pena; el cambio de perfil activo en prod se decide con los números.
5. Cada relato generado con Claude cuesta dinero: **toda corrida de evaluación se aprueba antes** con su costo estimado.
6. **Esta spec no gasta dinero** (decisión 2026-09-24): se desarrolla y se prueba la integración con el SDK simulado; **ninguna llamada real a la API**. La evaluación con Claude queda preparada y pendiente de presupuesto.

---

## OBJECTIVE

Mejorar la calidad de la prosa (lo que las relatoras notan) donde el modelo local ya no da más: frases mal armadas («El taxi toco la puerta de barro», «Alargar la manta sobre los chiquitos, sentí algo áspero»), formas no rioplatenses («Rezad»), errores de continuidad («conversando con su madre» en el sulki, cuando María quedó en la casa) y el esquive de la lista de clichés con variantes («me heló el alma»).

**Éxito:** en la evaluación de Spec-470 (`scripts/evaluate_voice.py`), la Voz en Claude mantiene o mejora las métricas (clichés ≤ 1, parentescos 0, narradora en 3ra persona 0, frases repetidas ≤ 2) y la lectura manual confirma menos errores de gramática y continuidad, con un **costo por relato** conocido y aceptado.

---

## 1. HALLAZGOS EN EL CÓDIGO

| Hallazgo | Consecuencia |
|---|---|
| `LLMFactory.get_provider()` crea **un solo adapter** para todo el pipeline, según `provider` del perfil. | El perfil híbrido `anthropic-opus-voz` no funciona: el Mapper y el Journal piden `qwen2.5:14b` y la llamada iría a la API de Anthropic. |
| `AnthropicAdapter` manda `temperature` salvo a `claude-opus-4*`. | Claude Opus 5 y Sonnet 5 **rechazan** los parámetros de sampling (400). |
| Lee `response.content[0].text`. | En Opus 5 el pensamiento adaptativo viene activo por defecto: el primer bloque puede ser de razonamiento, no el texto. |
| No mira `stop_reason`. | Un `refusal` (clasificadores de seguridad) o un corte por `max_tokens` pasarían como prosa vacía o truncada. |
| El perfil usa `claude-opus-4-7` / `claude-sonnet-4-6`. | Generación anterior; los vigentes son Claude Opus 5 y Sonnet 5. |

---

## 2. CAMBIOS PROPUESTOS

### 2.1 Proveedor por rol

- Cada rol de un perfil puede declarar su `provider` (`roles.voz.provider: anthropic`); si no lo declara, usa el del perfil.
- Un adapter enrutador (`RoleRoutingAdapter`) implementa `LLMProvider` y despacha cada llamada al adapter del rol (todas las llamadas ya pasan `role`, incluido el Journal desde el arreglo de Spec-450 S3). `LLMFactory` lo usa cuando el perfil mezcla proveedores; con un solo proveedor, nada cambia.

### 2.2 `AnthropicAdapter` al día

- Sin `temperature` / `top_p` / `top_k` para los modelos que no los aceptan (Opus 5, Sonnet 5, Opus 4.7+).
- `thinking` y `effort` configurables por rol en el perfil (`thinking: adaptive|disabled`, `effort: low|medium|high`).
- El texto se arma con **los bloques `text`** de la respuesta, no con `content[0]`.
- `stop_reason`: `refusal` → error claro (con la categoría); `max_tokens` → error claro (no se persiste un acto truncado).
- `max_tokens` desde `num_predict` del rol (hoy fijo en 4096).
- Uso de tokens (`usage`) registrado en el log y en el debug collector, para medir el costo real.

### 2.3 Perfil híbrido

Perfil nuevo (o `anthropic-opus-voz` corregido): los roles de `ollama-gemma3-12b` para Analyst, Mapper y Journal, y la Voz en Claude. **No se activa en prod** hasta decidirlo con la evaluación.

### 2.4 Evaluación

`scripts/evaluate_voice.py` suma `--profile <perfil>` y reporta el **costo por relato** (tokens de entrada/salida de la Voz × precio del modelo).

---

## 3. COSTO ESTIMADO

Base: medición de Spec-470 (la Voz recibe ~1900–2900 tokens por llamada según las entidades; escribe ~450–530 palabras ≈ 700–900 tokens), 5 llamadas por relato. El tokenizer de Claude puede contar hasta ~1,35× más que el de gemma; se toma el peor caso.

| Modelo | Precio (entrada / salida, US$ por millón) | Sin pensamiento | Con pensamiento adaptativo (+~1000 tokens de salida por acto) |
|---|---|---|---|
| **Claude Opus 5** (`claude-opus-5`) | 5 / 25 | ~US$ 0,20 por relato | ~US$ 0,33 por relato |
| **Claude Sonnet 5** (`claude-sonnet-5`) | 2 / 10 | ~US$ 0,08 por relato | ~US$ 0,13 por relato |

Cuenta por relato: entrada ~2400 tokens (gemma) × 1,35 ≈ 3240 por acto → ~16.200; salida ~700 × 1,35 ≈ 950 por acto → ~4.750; el pensamiento suma ~5000 de salida. En Claude Opus 5 el pensamiento adaptativo está **activo por defecto**.

La evaluación completa (2 corridas × sin/con entidades = 4 relatos) costaría **~US$ 0,80–1,30 con Opus 5** o **~US$ 0,30–0,55 con Sonnet 5**, más una corrida corta de prueba. Los costos reales se miden en la evaluación (§2.4).

---

## BOUNDARIES

- **Siempre:** aprobar el costo de cada corrida de evaluación antes de lanzarla; medir con el mismo arnés de Spec-470; tests con el SDK simulado (sin llamadas reales).
- **Consultar antes:** activar el perfil híbrido en prod; cambiar de modelo.
- **Nunca:** mandar datos de las historias a otro proveedor que no sea el elegido; hardcodear la API key.

---

## DECISIONES (2026-09-24)

1. **Modelo de la Voz:** Claude Sonnet 5 (`claude-sonnet-5`).
2. **Pensamiento:** configurable por rol (`thinking: adaptive` / `disabled`), para comparar con y sin cuando se evalúe. En Sonnet 5, **omitir** `thinking` corre adaptativo: «sin pensamiento» manda `{"type": "disabled"}` explícito.
3. **Presupuesto:** ninguno por ahora. Solo integración, probada con el SDK simulado; sin llamadas reales. La evaluación (`evaluate_voice.py --profile …`) queda lista para cuando haya presupuesto.
4. **Prod:** el perfil híbrido queda definido pero **no se activa**; se decide después de evaluar.

---

## PLAN

### Estrategia

Primero el ruteo por rol (sin él, ningún perfil mixto funciona), después el adapter de Anthropic al día, y al final el perfil híbrido y el arnés de evaluación. **Todo se prueba con el SDK simulado**: los tests reemplazan el cliente de Anthropic por un doble que devuelve respuestas armadas a mano (bloques `thinking` + `text`, `usage`, `stop_reason`), así se verifica exactamente qué se envía y cómo se lee lo que vuelve, sin gastar.

```
S0 Proveedor por rol ─▶ S1 AnthropicAdapter al día ─▶ S2 Perfil híbrido + health + evaluación preparada ─▶ S3 Docs + DONE
```

### Decisiones técnicas

1. **`RoleRoutingAdapter`** (`src/infrastructure/adapters/role_routing_adapter.py`): implementa `LLMProvider`; recibe `{rol: adapter}` y un adapter por defecto; en `generate(..., role=...)` despacha al del rol (sin rol o rol desconocido → el por defecto). `close()` cierra cada adapter una vez. Los adapters se crean **una vez por proveedor** (si dos roles usan Ollama, comparten el adapter).
2. **Config:** `roles.<rol>.provider` opcional en `llm_core_definitions.yaml`; `settings.role_provider(rol)` devuelve el del rol o el del perfil. `settings.llm_providers` (conjunto de proveedores en uso) para el health check y `/config/active-profile`.
3. **`LLMFactory.get_provider()`**: si todos los roles usan el mismo proveedor, devuelve ese adapter como hoy (cero cambio para los perfiles actuales); si mezclan, arma el `RoleRoutingAdapter`. `--mock` y `provider=` explícito siguen igual.
4. **`AnthropicAdapter`**:
   - Modelos sin sampling: `claude-opus-4-7`/`4-8`, `claude-opus-5*`, `claude-sonnet-5*`, `claude-fable-*` (lista de prefijos; ninguno recibe `temperature`/`top_p`/`top_k`).
   - `thinking` del rol: `adaptive` → `{"type": "adaptive"}`; `disabled` → `{"type": "disabled"}` (en Sonnet 5 omitirlo **no** lo apaga); sin valor → no se manda. `effort` → `output_config={"effort": …}`.
   - `max_tokens` = `num_predict` del rol (o el recibido); con pensamiento, mínimo 16000 para que el razonamiento no se coma el acto.
   - Texto = concatenación de los bloques `text`; `stop_reason == "refusal"` → `LLMRefusalError` con la categoría de `stop_details`; `stop_reason == "max_tokens"` → error (un acto truncado no se persiste).
   - `LLMResponse` suma `input_tokens` / `output_tokens` opcionales (el resto de los adapters no cambia).
   - Errores del SDK con la cadena específica (`RateLimitError`, `APIStatusError`, `APIConnectionError`), sin reintentos propios: el SDK ya reintenta 429/5xx.
5. **Perfil `ollama-gemma3-12b-voz-sonnet5`**: copia de los roles de `ollama-gemma3-12b` (Analyst, Mapper, Journal en Ollama) y `voz: {provider: anthropic, model: claude-sonnet-5, num_predict: …, thinking: …}`; variante de prompt compact (igual que hoy). El perfil viejo `anthropic-opus-voz` (roto) se elimina. **No se activa**.
6. **Health check** (`/health`): verifica cada proveedor en uso (Ollama responde; Anthropic tiene key); `/config/active-profile` muestra el proveedor de cada rol.
7. **`evaluate_voice.py`**: `--profile <nombre>` (cambia el perfil solo dentro del proceso) y costo por relato cuando la Voz es de Anthropic (suma `input_tokens`/`output_tokens` de las llamadas de la Voz × precio de Sonnet 5, US$ 2 / 10 por millón). Pide confirmación explícita (`--yes`) antes de llamar a una API paga.

### S0 — Proveedor por rol
- `role_provider()`, `RoleRoutingAdapter`, `LLMFactory`; tests: perfil de un proveedor → mismo adapter que hoy; perfil mixto → cada rol a su adapter; `close()` una vez por adapter.

### S1 — AnthropicAdapter al día
- §4 completo, con un cliente de Anthropic simulado en los tests: sin `temperature` para Sonnet 5; `thinking` adaptive/disabled; texto desde bloques `text` aunque el primero sea `thinking`; refusal y `max_tokens` como error; `usage` en `LLMResponse`.

### S2 — Perfil híbrido, health y evaluación preparada
- Perfil nuevo (sin activar), borrar `anthropic-opus-voz`; health y `/config/active-profile` por rol; `evaluate_voice.py --profile` + costo + `--yes`. Prueba de punta a punta con el pipeline completo, el perfil híbrido y el cliente de Anthropic simulado (la Voz va al doble; Analyst/Mapper/Journal al mock local).

### S3 — Documentación y cierre
- `CLAUDE.md` (LLM Provider Abstraction / LLM Configuration: proveedor por rol, perfil híbrido, cómo evaluarlo con costo), nota en Spec-060/070, Spec-480 → DONE (la evaluación real queda como pendiente con su costo estimado). Deploy del backend (con OK): no cambia el comportamiento en prod porque el perfil activo sigue siendo el local.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| El doble del SDK no se parece a la API real | Se arma con los tipos del SDK instalado (`anthropic.types.Message`, `TextBlock`, `ThinkingBlock`, `Usage`) en vez de dicts sueltos; la primera corrida real (cuando haya presupuesto) arranca con una prueba corta. |
| La versión 0.96 del SDK no acepta algún parámetro nuevo | Los parámetros que el SDK no tipa (`output_config`) van por `extra_body`, verificado en el test. |
| El ruteo rompe perfiles existentes | Con un solo proveedor, `LLMFactory` devuelve exactamente el mismo adapter que hoy (test). |
| Un gasto accidental | El perfil híbrido no se activa; `evaluate_voice.py` exige `--yes` con un proveedor pago; los tests nunca crean un cliente real. |

---

## TASKS

Formato: **Acceptance** / **Verify** / **Files**. Checkpoint por slice: lint + pytest (+ Playwright en S2, que toca endpoints que usa el frontend) en verde → commit con tu OK. **Ninguna tarea hace llamadas reales a la API de Anthropic.**

### S0 — Proveedor por rol

- [x] **T0.1:** Config por rol.
  - Acceptance: `settings.role_provider(rol)` → `roles.<rol>.provider` o el `provider` del perfil; `settings.llm_providers` → conjunto de proveedores en uso por los 4 roles.
  - Verify: pytest con un `llm_core_definitions` de prueba (perfil de un proveedor; perfil mixto).
  - Files: `src/config.py`, `tests/unit/test_config_profiles.py`
- [x] **T0.2:** `RoleRoutingAdapter`.
  - Acceptance: despacha por `role` (sin rol / rol desconocido → por defecto), pasa todos los argumentos tal cual, `close()` una vez por adapter distinto.
  - Verify: pytest con adapters falsos que registran las llamadas.
  - Files: `src/infrastructure/adapters/role_routing_adapter.py`, `src/infrastructure/adapters/__init__.py`, `tests/unit/infrastructure/test_role_routing_adapter.py`
- [x] **T0.3:** `LLMFactory`.
  - Acceptance: un solo proveedor → el mismo tipo de adapter que hoy; mezcla → `RoleRoutingAdapter` con un adapter por proveedor (compartido entre roles); `use_mock` y `provider=` explícito sin cambios.
  - Verify: pytest (`tests/unit/infrastructure/test_llm_factory.py`), sin crear clientes reales (Anthropic con key falsa, sin requests).
  - Files: `src/infrastructure/factories.py`
- [x] **Checkpoint S0:** lint + pytest → commit.

### S1 — AnthropicAdapter al día

- [x] **T1.1:** Cliente simulado para tests.
  - Acceptance: un doble de `AsyncAnthropic().messages.create` que registra los kwargs y devuelve un `anthropic.types.Message` real (bloques `ThinkingBlock`/`TextBlock`, `Usage`, `stop_reason`, `stop_details`).
  - Files: `tests/support/fake_anthropic.py`
- [x] **T1.2:** Request.
  - Acceptance: sin `temperature` para los modelos sin sampling (Sonnet 5, Opus 5, Opus 4.7/4.8, Fable); `thinking` según el rol (`adaptive` / `disabled` explícito / sin valor → no se manda); `effort` → `output_config` (por `extra_body` si el SDK 0.96 no lo tipa); `max_tokens` = `num_predict` del rol (mínimo 16000 con pensamiento adaptativo); modelo del rol.
  - Verify: pytest sobre los kwargs registrados por el doble.
  - Files: `src/infrastructure/adapters/anthropic_adapter.py`, `tests/unit/infrastructure/test_anthropic_adapter.py`
- [x] **T1.3:** Respuesta.
  - Acceptance: texto = bloques `text` concatenados (aunque el primero sea `thinking`); `refusal` → `LLMRefusalError` con la categoría; `max_tokens` → error; `LLMResponse.input_tokens` / `output_tokens` desde `usage`; errores del SDK con cadena específica.
  - Verify: pytest con respuestas simuladas de cada caso.
  - Files: `src/infrastructure/adapters/anthropic_adapter.py`, `src/domain/interfaces.py`, `src/domain/exceptions.py`
- [x] **Notas de S1 (2026-09-24):**
  - El SDK 0.96 ya tipa `thinking` (adaptive/disabled), `output_config.effort` y `stop_details`: no hizo falta `extra_body`.
  - El doble del SDK usa los tipos reales (`Message`, `TextBlock`, `ThinkingBlock`, `Usage`, `RefusalStopDetails`) y ya atrapó un error del test: el SDK 0.96 solo tipa las categorías de rechazo `cyber` y `bio`.
  - `max_tokens`: piso de 16000 salvo `thinking: disabled` (Sonnet 5 / Opus 5 piensan por defecto y el razonamiento sale del mismo tope).
  - `close()` ahora cierra el cliente HTTP del SDK (antes era un no-op).
- [x] **Checkpoint S1:** lint + pytest → commit.

### S2 — Perfil híbrido, health y evaluación preparada

- [x] **T2.1:** Perfil `ollama-gemma3-12b-voz-sonnet5` (sin activar) y baja de `anthropic-opus-voz`.
  - Verify: pytest (el perfil carga; la Voz es `anthropic`/`claude-sonnet-5`, el resto `ollama`; `active_profile` sigue siendo `ollama-gemma3-12b`).
  - Files: `config/llm_core_definitions.yaml`
- [x] **T2.2:** `/health` y `/config/active-profile` por rol.
  - Acceptance: health verifica cada proveedor en uso (Ollama responde, Anthropic tiene key); active-profile muestra `provider` por rol.
  - Verify: pytest de los endpoints con el perfil local y con el híbrido.
  - Files: `src/presentation/routers/stream_router.py`
- [x] **T2.3:** Pipeline completo con el perfil híbrido.
  - Acceptance: un job con el perfil híbrido manda las 5 llamadas de la Voz al cliente de Anthropic simulado (con el system prompt compact de Spec-470) y el resto al mock local; el relato se consolida.
  - Verify: pytest de integración (`tests/integration/test_hybrid_profile.py`).
- [x] **T2.4:** `evaluate_voice.py --profile … --yes`.
  - Acceptance: `--profile` cambia el perfil solo dentro del proceso; con un proveedor pago y sin `--yes`, termina sin generar y muestra el costo estimado; con `--yes`, reporta el costo real por relato (`usage` de la Voz × US$ 2 / 10 por millón).
  - Verify: pytest con el cliente simulado (costo calculado a partir del `usage` simulado); sin corrida real.
  - Files: `scripts/evaluate_voice.py`, `tests/unit/scripts/test_evaluate_voice.py`
- [x] **Notas de S2 (2026-09-24):**
  - **Health (bug previo):** el chequeo de Anthropic miraba `os.getenv("ANTHROPIC_API_KEY")`, pero la clave vive en `.env` y la lee `settings`: con el proceso levantado así la reportaba faltante. Ahora usa `settings.anthropic_api_key`. El health es `degraded` si falta algún proveedor en uso.
  - **Evaluación preparada, sin gastar:** con el perfil híbrido y sin `--yes`, `evaluate_voice.py` muestra «El perfil usa un proveedor pago para ['voz']: costo estimado ~US$ 0.32 (4 relatos)» y no genera nada (verificado con el script real). El costo real se mide con un contador que envuelve al proveedor (`TokenMeter`).
  - **Pipeline completo** con el perfil híbrido y el cliente simulado: las 5 llamadas de la Voz van a Claude (`claude-sonnet-5`, `thinking: disabled`, sin `temperature`, prompt compact de Spec-470); Analyst, Mapper y Journal al modelo local.
- [x] **Checkpoint S2:** lint + pytest + Playwright → commit.

### S3 — Documentación y cierre

- [x] **T3.1:** `CLAUDE.md` (proveedor por rol, perfil híbrido, evaluación con costo y `--yes`), notas en Spec-060/070, Spec-480 → DONE con la evaluación real como pendiente (costo estimado).
- [x] **T3.2:** Deploy del backend (con tu OK) y verificación de que el perfil activo sigue siendo el local (`/config/active-profile`).

## PENDIENTES

- **Evaluación con Claude** (cuando haya presupuesto): `uv run python scripts/evaluate_voice.py --label sonnet5 --profile ollama-gemma3-12b-voz-sonnet5 --runs 2 --out <dir> --yes` (~US$ 0,32 los 4 relatos sin pensamiento; cambiar `thinking: adaptive` en el perfil para la variante con pensamiento, ~US$ 0,52). Arrancar con `--runs 1 --variants con` como prueba corta.
- **Hallazgo del deploy (EV-8, previo):** prod genera con `ollama-llama31` (`llama3.1:8b`): `LLM_PROFILE=ollama-llama31` en `.env.prod` (y en `.env`) pisa el `active_profile: ollama-gemma3-12b` del YAML. `config.py` lee `LLM_PROFILE` con `os.getenv` (no del `.env`), así que los scripts y tests locales —y las evaluaciones de Spec-450 S5 y Spec-470— corrieron con `gemma3:12b`. Decidir qué modelo local usa prod y alinear `.env`/`.env.prod`/YAML.
- **Medición del perfil de prod (`ollama-llama31`, 2026-09-24), con el arnés de Spec-470:**

| | `llama3.1:8b` (prod) | `gemma3:12b` (evaluado) |
|---|---|---|
| Clichés sin / con entidades | 1 / 1 | 0,5 / 0,5 |
| Parentescos mal / 3ra persona | 0 / 0,25 | 0 / 0 |
| Palabras por relato | ~1450–1950 | ~2050–2200 |
| Tiempo por relato | ~2 min | ~3,7 min |
| Contexto (`num_ctx`) | **el Analyst desborda siempre** (−292 tokens sin entidades, −1353 con 3); con 3 entidades también la Voz (−272) y el Journal en `mistral` (−755): Ollama recorta el prompt en silencio | todos los roles entran (margen mínimo ~1000) |

  - **Lectura manual (llama3.1, con entidades):** el acto 2 no narra sus eventos (Irene «se acuesta en la cama»; María, que quedó en su casa, aparece en la fiesta preparando una ensalada y dice «¡Venid todos! ¡Es hora de rezar!»); el acto 3 salta de «me quedé dormida… en la casa» al sulki; tiempos verbales mezclados, «Me levantó» por «me levanté», «no estaba seguro» en una narradora; mitología inventada; los actos 4–5 repiten la sinopsis en presente. Las métricas automáticas no captan la incoherencia.
  - Con `gemma3:12b` (Spec-470 S2) los actos narran sus eventos, en orden y con continuidad.
- **Decisión (2026-09-24): el modelo local es `gemma3:12b`** (perfil `ollama-gemma3-12b`) en prod y en dev. `LLM_PROFILE` pasó de `ollama-llama31` a `ollama-gemma3-12b` en `.env.prod` y `.env` (no versionados; backups `.env*.bak-20260924`); backend recreado y verificado (`/config/active-profile`: los 4 roles en `gemma3:12b`; `/health` ok). Resuelve el hallazgo EV-8.


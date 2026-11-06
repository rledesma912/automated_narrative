# SPEC-740: FreeLLMAPI como proveedor y qué IA escribió cada relato

**Fecha:** 2026-11-05
**Tipo:** SDD: proveedores LLM (adapter + perfil), registro de llamadas, «El relato» (UI)
**Estado:** S1 hecho (af75ffe). **Enfoque cambiado el 2026-11-06** (§0): FreeLLMAPI para el relato corto. Plan y tareas reescritos (§9, §10), con OK del usuario (2026-11-06). Hechas S1, S2, S4, S5 y S6; S3 midiendo. **Parte F (OpenAI, D9) sumada el 2026-11-06**; S8 hecha salvo T8.6 (con clave).
**Rama:** `feat/spec-740-freellmapi` (desde `origin/development`)
**Extiende:** Spec-480 (proveedor por rol), Spec-530 (salida estructurada), Spec-600 D3 (la Voz sin respaldo), Spec-620 (mensajes fuera del código), Spec-720 D6 (`respaldo`, `respaldos`).

---

## ASSUMPTIONS

1. FreeLLMAPI (v0.16.19, imagen del 2026-11-04) corre en esta máquina y queda para uso propio. Es un gateway self-hosted: unifica las capas gratuitas de varios proveedores detrás de una API compatible con OpenAI, con cadena de fallback.
2. Es un proveedor **más**, elegible por rol como Anthropic u Ollama. No reemplaza a nadie hasta que una medición lo justifique (como las Spec-600, 700 y 720).
3. Prod sigue con `hibrido-sonnet55` hasta que el usuario decida otra cosa. **Hoy no hay crédito en Anthropic** (dicho por el usuario, 2026-11-05): la Voz, que no tiene respaldo, no puede escribir hasta recargar o cambiar de perfil; el Planificador y el Verificador caen a gemma (Spec-720).
4. «Las chicas» quieren ver, en cada relato, qué IA lo escribió. Es información: no cambia nada del pipeline.
5. El registro sirve para **todos** los proveedores (Claude y gemma también), no solo para FreeLLMAPI. Si no, una historia escrita con Sonnet no diría nada.
6. Los relatos ya escritos no tienen el dato y no se infiere: el perfil activo de entonces no prueba quién respondió cada llamada.

---

## §0. Cambio de enfoque (2026-11-06)

Lo pidió el usuario después de T1.9 (§8): FreeLLMAPI le sirve sobre todo al **relato corto**. No porque escriba mejor, sino porque se expone menos a los límites gratis: 8 llamadas contra 12, ~18 000 tokens contra ~30 000, y en la prueba un solo modelo sin esperas, contra tres modelos y dos esperas en el largo. Además, el corto es lo que más se usa (prod: 11 historias cortas y 5 largas).

Decisiones del usuario: el **largo va con Sonnet** (perfil con Claude), y **mientras no haya crédito queda deshabilitado** (D6). La medición es **solo de cortos** (D7).

## OBJECTIVE

1. Que el **relato corto** se escriba con FreeLLMAPI (perfil `freellmapi-libre`, S1), y el **largo** con otro perfil, Sonnet, o que quede **deshabilitado** con una nota clara mientras no haya crédito.
2. Que cada llamada a una IA deje registrado qué modelo respondió **de verdad**, y que cada versión de un relato lo muestre.

**Éxito:**
- Un corto sale completo con FreeLLMAPI.
- Con el largo deshabilitado, nadie puede lanzar IA sobre una historia larga y la pantalla dice por qué, sin jerga.
- Al volver el crédito, alcanza con cambiar una variable para que el largo vuelva con Sonnet.
- Cada versión dice qué IA la escribió; los relatos viejos no dicen nada.
- La medición de cortos dice cuántos entran por día y si la lectura a ciegas los acepta.

---

## 1. Relevamiento (2026-11-05)

Verificado en el código de **la versión instalada** (`server/dist` del contenedor), salvo donde se aclara. Sin clave no se pudo hacer ninguna llamada real: ver S0.

| Tema | Qué hay | Consecuencia |
|---|---|---|
| API | `POST /v1/chat/completions`, `GET /v1/models`, `Authorization: Bearer` (sin clave: 401) | Alcanza `httpx`, que ya es dependencia. Sin SDK nuevo, y los headers quedan a mano |
| Modelo usado | El campo `model` trae el id que usó la ruta, **no** lo pedido (pedí `auto` → `gemini-3.1-flash-lite-preview`; pedí `gpt-oss-120b` → `openai/gpt-oss-120b`). `X-Routed-Via` = `plataforma/modelo` (`groq/openai/gpt-oss-120b`) | Se puede registrar sin adivinar: se guarda `X-Routed-Via` tal cual. El modelo interno del upstream (`upstreamModel`) no sale en la respuesta |
| Fallback | Ante 429/5xx rota de clave y modelo. Si hubo fallos: `X-Fallback-Attempts` y `X-Fallback-Trail` (`plataforma/modelo keyN=causa`) | También queda registrado por qué no respondió el primero |
| Elegir modelo | `auto` (cadena activa), `auto:smart\|fast\|…`, `auto:<perfil>` (cadena con nombre; si no existe, 400), o un id fijo | Cada rol puede tener su `model` en el YAML |
| Sesión | `X-Session-Id` mantiene el modelo ~30 min (según la documentación). Sin ese header, la clave sale del primer mensaje de usuario, que cambia en cada acto | Sin header, cada acto puede caer en otro modelo. Con el id del job como sesión, el relato tiende a quedar en uno |
| Salida estructurada | `response_format` con `json_schema` pasa la validación y el router saltea las plataformas que lo descartan (`platformDropsResponseFormat`) | `response_schema` tiene adónde ir. Falta medir qué tan bien lo cumple cada modelo; `generate_structured` valida igual |
| Caché | Desactivada salvo que se configure; `X-FreeLLM-Cache: off` la saltea en cada pedido. Un acierto devuelve `X-Routed-Via: cache` | Se manda siempre `off`: regenerar un acto tiene que escribir de nuevo, y un acierto no diría qué modelo respondió |
| Corte | `finish_reason` `length` y `content_filter` llegan al cliente en texto puro | Se mapean a lo que ya existe: truncado → `LLMResponseError`, filtro → `LLMRefusalError` |
| Errores | Vistos en S0: 401; 429 `rate_limit_exceeded` con `retryAtMs`; 502 `upstream_failed` (503 o timeout de 60 s del upstream); 413 `context_length_exceeded`; 404 `model_not_found` (también en un modelo que `/v1/models` da como disponible). Documentados y sin ver: 429 `quota_exceeded`, 503 `no_providers_configured` | Se mapean a `LLMUnavailableError`, con su mensaje coloquial. Ver A8 |
| Red | Desde `narrative-api-dev`: `host.docker.internal:3001` y `freellmapi:3001` → **no llegan** (el puerto está en 127.0.0.1 y otra red). `host.docker.internal:80` con `Host: freellmapi.test` → **llega** (401). nginx: `proxy_read_timeout 3600s` | Alcanza con `extra_hosts: freellmapi.test:host-gateway` en los dos compose, por HTTP |
| Hoy, en el sistema | `LLMResponse` no trae modelo ni proveedor. `generated_narrative` y `macro_beat` tampoco. `RoleRoutingAdapter.respaldos` solo anota qué roles cayeron al respaldo, sin guardarlo por llamada | No hay de dónde sacar el dato: hay que registrarlo |
| Adapter de Claude | `model` por rol, `response_schema`, `LLMUnavailableError`, `LLMRefusalError`. `LLMFactory._single()` elige por nombre | El adapter nuevo calza en la misma forma; `RoleRoutingAdapter` y `respaldo` funcionan sin tocarlos |

**Lo que dice el propio proyecto** (README y arquitectura, sin verificar por separado):
- «Intelligence degrades as the day progresses»: los mejores modelos agotan la cuota diaria y el router baja a otros hasta la medianoche UTC.
- «Free tiers can change without notice», «No SLA», «Latency is highly variable».
- «no sharing your endpoint with other humans», uso personal y de experimentación. Su tabla de términos marca Cohere como «Avoid», y Gemini, NVIDIA y Z.ai como «Caution».
- Los prompts van directo de esta máquina a los proveedores habilitados, y varias capas gratuitas pueden usarlos según sus términos. Ver §6 D5.

---

## 2. Parte A: el proveedor

- **A1. `FreeLLMAPIAdapter`** (`src/infrastructure/adapters/freellmapi_adapter.py`), con `httpx`. Cumple `LLMProvider`. `response_schema` → `response_format: {type: json_schema, json_schema: {name, schema}}`. Manda siempre `X-FreeLLM-Cache: off` y `X-FreeLLM-Compress: off` (S0: el gateway viene con compresión `aggressive` de los prompts; lo que le decimos a la IA no se toca sin que lo sepamos). Sin soporte de streaming: el pipeline no lo usa.
- **A2. Configuración.** `FREELLMAPI_URL` y `FREELLMAPI_API_KEY` por entorno (`.env`, `.env.prod`), `extra_hosts` en los dos compose. El modelo por rol vive donde siempre: `roles.<rol>.{provider: freellmapi, model, temperature, num_predict}`.
- **A3. Sesión por job.** `X-Session-Id` = id del job, para que un relato tienda a quedar en un solo modelo. No lo garantiza: si el modelo agota la cuota, sigue otro, y queda registrado.
- **A4. Errores.** 401/403 → `clave`; 429 y cuota → `saturada`; 5xx → `saturada`; sin red → `sin_conexion`; sin modelos disponibles → causa nueva con su mensaje en `core_messages.yaml` (Spec-620). Los mensajes existentes se revisan: pueden hablar de crédito o de Anthropic.
- **A5. Filtros de respuesta.** `ResponseNormalizer` elige `model_overrides` por substring del modelo. Con `auto` el nombre configurado no dice nada, así que tiene que aplicar el modelo que respondió. Un `<think>` en la prosa de un modelo razonador es el error que previene.
- **A6. `/health` y `/config/active-profile`.** Verifican FreeLLMAPI como a cada proveedor en uso. La disponibilidad se mira con `GET /v1/models`, que no gasta cuota.
- **A7. Perfil de prueba.** `freellmapi-libre`, no activo: **todos los roles** en FreeLLMAPI (D1), con `estimated_seconds` propios y `max_tokens` ajustado por rol. S0 mostró que pedir de más también cuenta contra la cuota por minuto (4000 dio 413 y 2000 pasó), y que un modelo que razona puede gastarlo todo sin escribir (`dots3`: `length` con 67 palabras).
- **A8. Esperar antes de rendirse (nuevo, por S0).** Si la cadena entera está en cooldown (429 con `retryAtMs`), el adapter espera hasta esa hora y reintenta, con un tope por llamada (propuesta: 2 min) y sin pasarse de las esperas que no sirven (`quota_exceeded` falla enseguida). Recién ahí aplica D3. Las cuotas de estas capas se miden **por minuto**: un job escribe más rápido de lo que dejan. La espera es solo por cooldown informado; un error de otra clase no se reintenta.

---

## 3. Parte B: el registro

- **B1. `LLMResponse`** suma `provider`, `model` y `fallback_attempts`, más `fallback_trail` opcional. Lo llena cada adapter con lo que informó el proveedor. Sin ese dato (Gemini CLI, por ejemplo), con el modelo pedido.
- **B2. Tabla `llm_call`:** `id, story_id, job_id, narrative_id (NULL hasta que exista), role, act (NULL fuera de los actos), provider, model, via (`X-Routed-Via`, NULL en otros proveedores), fallback_attempts, fallback_trail, respaldo (0/1), input_tokens, output_tokens, elapsed_s, created_at`. Es una tabla nueva: sin `ALTER` ni export/import. `init_db()` corre al arrancar (`src/main.py:28`), así que la tabla aparece sola en prod con el deploy.
- **B3. Quién anota.** Un envoltorio de `LLMProvider` por job, en un solo lugar, para no tocar cada caso de uso. Recibe todas las llamadas, también los reintentos de `generate_structured`, y funciona con cualquier adapter o respaldo. El acto llega por un contexto del pipeline, sin cambiar la firma de `generate`.
- **B4. Si anotar falla, el relato no se pierde.** El registro se loguea y el job sigue: es información, no parte de la generación.
- **B5. Qué vale para una versión.** Por acto, la **última** llamada `voz` de ese relato. Regenerar un acto reemplaza su dato, igual que reemplaza su texto. Corregirlo a mano no cambia el dato.
- **B6. Sin dato → sin línea.** Los relatos viejos no muestran nada; nunca «desconocido» ni el perfil de entonces.
- **B7. Borrado.** Las filas se van con el relato o la historia (`ON DELETE CASCADE`). Ningún dato de `llm_call` llega a un prompt ni al `.md` de `audiogen`.

---

## 4. Parte C: lo que ven las chicas

- **C1. API.** `GET /generated-narratives/{id}/ia` → resumen por versión, y por acto si cambió.
- **C2. «El relato».** En el panel de cada versión, en tono del sitio (Spec-580):
  - Un solo modelo: «Lo escribió **Claude Sonnet 5.5**».
  - Más de uno: «Lo escribieron **Gemini 2.5 Flash** (actos 1 a 3) y **Llama 3.3** (actos 4 y 5)».
  - Junto a cada acto, solo si la versión tiene más de un modelo.
- **C3. El resto del trabajo, plegado.** «Ver qué IA hizo cada cosa»: preguntas, actos, revisión, memoria y guion, sin tokens ni costos.
- **C4. Nombres.** Se muestra el id del modelo con un nombre lindo si está en `config/`; si no, el id tal cual. Un modelo nuevo nunca rompe la pantalla.
- **C5. Textos** en `core_messages.yaml` o en las vistas según corresponda (Spec-620), y pasan `sin-jerga.view.test.ts`. «Fallback» no se ve; si hace falta decirlo: «el primero no estaba disponible».

- **C6. El largo deshabilitado (D6).** En «Tu idea», «¿Qué tan largo?» muestra el largo apagado con una nota de información: «Por ahora solo se pueden escribir relatos cortos». Una historia larga que ya existe muestra la misma nota arriba, en la barra del asistente, y sus botones de IA (preguntas, armar, revisar, escribir, regenerar, guion) no se pueden tocar. La nota ofrece pasarla a corto con el cambio de largo que ya existe (Spec-650: borra los actos, con confirmación). Leer, corregir a mano y descargar siguen andando.

---

## 4b. Parte D: un perfil por largo (D6)

- **D1. Configuración.** `LLM_PROFILE` sigue siendo el perfil de siempre: el del corto y el de lo que no tiene historia. `LLM_PROFILE_LARGO` (nuevo, en `.env`) es el del largo: vacío = el mismo que `LLM_PROFILE` (nada cambia para quien no lo usa); `off` = largo deshabilitado; el nombre de un perfil = ese perfil. Se cambia sin deploy: está en `.env.prod`, fuera de la imagen, y alcanza con reiniciar la API.
- **D2. Cada job usa el perfil de su historia.** El `ContextVar` de S1 (`llm_context`) suma el perfil: `JobManager` lo fija según `story.structure` y todo lo que lee la config del perfil (`settings.role_config`, proveedores, tiempos estimados, el tope de espera) la toma de ahí. Así, adapters, factory y casos de uso no cambian. Fuera de un job, el perfil de siempre.
- **D3. Con el largo `off`.** `POST /stories/{id}/jobs` sobre una historia larga responde 409 con un mensaje coloquial (`core_messages.yaml`), igual que «hay un trabajo en curso». Crear una historia larga o pasar a largo (`PUT …/structure`) también se rechazan. `/authoring/options` devuelve cada largo con `disponible` y su nota, que es lo que lee la pantalla.
- **D4. `/health` y `/config/active-profile`** muestran los dos perfiles; `/health` verifica los proveedores de ambos (un largo `off` no verifica nada).
- **D5. Lo que no cambia.** El job ya guarda `profile` en `params` (Spec-510), así que las estimaciones de tiempo se separan solas por perfil. El registro (Parte B) anota el proveedor y el modelo de cada llamada, venga del perfil que venga.

---

## 4c. Parte E: un tope de relatos por día (D8)

- **E1. Qué cuenta.** Escribir un relato completo (`full_generation`) con un perfil que declara el tope (`limite_relatos_por_dia` en el perfil; `freellmapi-libre` lo declara, los de Claude no). Cuentan los que terminaron bien o están corriendo **hoy** (día de Argentina); los que fallaron no cuentan. Preguntas, armar o revisar los actos y regenerar un acto no cuentan: son pocas llamadas y bloquearlos frena el trabajo en «Los actos».
- **E2. Es de todo el sitio, no por persona.** La cuota del gateway es una sola. **También la comparten dev y prod:** las pruebas en dev gastan la misma cuota que usan las chicas. Por eso dev no cuenta para el tope de prod, pero sí gasta.
- **E3. Al llegar al tope.** `POST …/jobs` (`full_generation`) responde 409 con un mensaje coloquial («Hoy ya se escribieron N relatos. Mañana se puede escribir otro; lo que armaste queda guardado.»). Los botones de escribir se ven apagados con esa nota, y antes del tope dicen cuántos quedan hoy («Hoy podés escribir 1 relato más»).
- **E4. El número sale de S3**, con los cortos espaciados. Se cambia en el perfil, sin tocar código.

---

## 4d. Parte F: la API de OpenAI como alternativa paga a Claude (D9)

Lo pidió el usuario el 2026-11-06: comprar la API de GPT en lugar de recargar Claude. Esta parte deja **el sistema listo para usarla**; elegir el modelo y activarla en un perfil es aparte (F6).

- **F1. Un adapter propio, a semejanza del de Claude, no del de FreeLLMAPI.** Aunque OpenAI y FreeLLMAPI hablan el mismo formato (`/v1/chat/completions`), OpenAI se **comporta** como Anthropic: es pago, responde el modelo que se pidió y, si no atiende, hay que avisarlo enseguida. Nada de la lógica del gateway (esperar el cupo con A8, saltos de cadena, `X-FreeLLM-*`, `X-Session-Id`, `X-Routed-Via`) va en este adapter. `OpenAIAdapter` (`src/infrastructure/adapters/openai_adapter.py`) usa el SDK oficial (`openai`, `AsyncOpenAI`), igual que `AnthropicAdapter` usa `anthropic`.
- **F2. Config por rol** (en el perfil, como Anthropic): `model`, `num_predict` → `max_completion_tokens` (los modelos que razonan rechazan `max_tokens`), `temperature` solo si el modelo la acepta (lista por substring, como `AnthropicAdapter`) y `reasoning_effort` si el rol lo declara. Clave: `OPENAI_API_KEY` en `.env` / `.env.prod`; nunca se imprime ni se commitea.
- **F3. Errores como Claude (Spec-600 D3).** Un error de servicio → `LLMUnavailableError` con las mismas causas y los mismos mensajes de `core_messages.yaml` (`llm.credito`, `clave`, `saturada`, `sin_conexion`, `error`; ya dicen «la IA que escribe el relato», sin marca), **sin reintentos propios ni espera** (el SDK sale con `max_retries=0`). Sin saldo: 429 `insufficient_quota` → `credito` (no `saturada`, aunque sea 429). `refusal` en el mensaje o `finish_reason: content_filter` → `LLMRefusalError`; `finish_reason: length` → `LLMResponseError` (respuesta truncada); vacío → error.
- **F4. Salida estructurada.** `response_format: {type: json_schema, json_schema: {name, strict: true, schema}}` con el esquema traducido por `openai_json_schema()`: el modo estricto pide `additionalProperties: false` y **todos** los campos en `required` (los opcionales pasan a admitir `null`) y no acepta algunas restricciones; quien llama valida igual con Pydantic, como hoy.
- **F5. El registro y «Lo escribió…» no cambian.** El adapter llena `provider="openai"`, `model` (el que informa la respuesta) y los tokens; `RegistroLLM` lo anota y `config/modelos_ia.yaml` suma los nombres de los modelos de GPT que se usen. La factory suma la rama `"openai"` en `_single`; `/health` la verifica con una llamada barata (listar modelos).
- **F6. Lo que queda fuera de esta parte.** Qué modelo y para qué roles (un perfil nuevo, p. ej. `hibrido-gpt`) se decide **después de comparar precios actuales** contra Sonnet (~US$ 0,09 el largo, ~0,15 todo el relato con armado) y de una medición de prosa con «El monte prohibido» (los prompts de la Voz y del Planificador se ajustaron con Sonnet). Activarlo en dev o prod: **preguntar antes** (D5: es un proveedor nuevo y las historias salen a OpenAI).

---

## 5. Slices y verificación

Ver §9 (plan) y §10 (tareas). Cierre de cada checkpoint (Spec-540 §2.5): tests en verde, `make dev-status` en verde y la URL para mirar. La Parte B, la C y la D no dependen de FreeLLMAPI: sirven con cualquier proveedor.

---

## 6. Decisiones del usuario

Tomadas por el usuario el 2026-11-05.

| # | Decisión | Qué se decidió | Por qué |
|---|---|---|---|
| D1 | Qué roles se miden en FreeLLMAPI | **Todos.** Se descartó dejar Planificador, Verificador, Revisor y Guion en Sonnet | No hay crédito en Anthropic. Riesgo a medir: Sonnet ganó esos roles en las Spec-700 y 720 |
| D2 | Cómo se elige el modelo | **Una cadena con nombre** en FreeLLMAPI (`auto:narrativa`), a testear. La arma el usuario en el panel | S0: `auto` le dio la prosa a un modelo de robótica, y ningún modelo solo terminó un relato |
| D3 | Si se agota toda la cadena | **El job falla con el mensaje coloquial**, sin caer a otro proveedor (como Spec-600 D3), después de las esperas de A8. Lo escrito no se pierde | Un acto en otra IA, sin que nadie lo decida, cambia la voz |
| D4 | Qué se ve | **§4:** línea por versión, por acto si cambió, el resto plegado | Responde la pregunta sin llenar la pantalla |
| D5 | Privacidad y términos | **Aceptados los proveedores ya habilitados:** Google, Groq y OpenRouter. Sumar otro requiere volver a preguntar | Las historias salen a esos terceros, cuyas capas gratis pueden usar los datos según sus términos |
| D6 | Qué pasa con el largo (2026-11-06) | **Con Sonnet; sin crédito, deshabilitado** (Parte D, C6). Opción descartada: el largo también gratis con aviso | El largo es más frágil con cuotas gratis y en la prueba mezcló tres modelos (el error del sulki) |
| D8 | Límite diario (2026-11-06) | **Sí: con FreeLLMAPI, un tope de relatos por día (1 o 2), con el número que sostenga S3** (Parte E) | Mejor un relato menos que uno que se corta a la mitad gastando la cuota. Ojo: las chicas escriben 2 o 3 por día |
| D7 | Qué se mide (2026-11-06) | **Solo cortos.** Primero 2 cortos más para confirmar T1.9; después capacidad por día y lectura a ciegas | Es el uso real y lo que va a correr en FreeLLMAPI |
| D9 | La API de OpenAI (2026-11-06) | **Sí, como parte nueva (F):** un `OpenAIAdapter` propio, hecho como el de Claude. El modelo, el perfil y la activación se deciden después, con precios y una medición | Pago como Claude: falla enseguida y responde el modelo pedido. Juntarlo con FreeLLMAPI metería las esperas del gateway en un proveedor pago |

---

## 7. Boundaries

- **Siempre:** registrar lo que informó el proveedor, no lo que se pidió; `X-FreeLLM-Cache: off`; tests sin llamadas reales.
- **Preguntar antes:** activar el perfil en dev o prod; correr la medición con historias reales de las chicas (S4 usa «El monte prohibido» o las de `input_stories/`).
- **Nunca:** commitear la clave; exponer FreeLLMAPI a internet; mostrar modelo o tokens en un prompt; inferir el modelo de los relatos viejos; corregir o regenerar solo si un modelo salió flojo.

---

## 8. Mediciones

### S0 (2026-11-05, mañana; capas gratis, sin costo)

Prompts: snapshots de la Voz (`voice_prompts.json`, sin historias de las chicas) y del Planificador con su esquema real. **Es una sonda, no una medición:** una corrida por modelo, sin métricas de `evaluate_voice`, y las primeras llamadas en paralelo gastaron cooldowns que afectaron a las siguientes.

Disponibles: 35 de 287 modelos del catálogo (claves de Google, Groq y OpenRouter).

| Modelo pedido | Voz, acto 3 | JSON del Planificador | Observación al leer la prosa |
|---|---|---|---|
| `auto` | 235 palabras, respondió `gemini-robotics-er-2-preview` | Válido (`gemini-3.1-flash-lite-preview`) | Correcta; un modelo de robótica no es una elección que el autor querría |
| `gemini-3.5-flash` | 214 palabras, debajo de 250 | 502 (503 de Google) | La más natural y rioplatense |
| `qwen3.8-27b` (Groq) | 316 palabras, 1,4 s | Válido, 3,5 s | Rápida; errores («solía usarme», «el humo de los labios») y comparaciones gastadas |
| `gpt-oss-120b` (Groq) | 322 palabras, 2,9 s | **No valida** (`retoma`, 2 errores) | Correcta, con varias comparaciones; ya nombra a Marta |
| `nemotron-3.5-lightning` | 358 palabras, 35 s | Timeout de 60 s | **Se filtra el prompt:** «Pasó media hora desde el acto 2». Descartado |
| `dots3-note-preview` | `length`, 67 palabras, 56 s | Timeout de 60 s | Descartado |
| `gemini-3.8`, `3.7`, `3.5-flash-lite` | 502 (503 de Google, alta demanda) | 429 | Sin dato. Volver a probar a otra hora |
| `gemma-4-31b` | 429 | 429 | Sin dato |

**Un relato entero, en serie, con un solo modelo: ninguno terminó.**
- `qwen3.8-27b`: actos 1 y 3 bien; acto 2 413; actos 4 y 5 429.
- `gpt-oss-120b`: actos 1 y 2 bien; actos 3 a 5 429.
- `gemini-3.5-flash`: 502, y después 429 en los demás.

**Cadena simulada desde el cliente, con `max_tokens` 2000:** salió el relato completo (5 Voz + 5 Memoria con esquema chico) en 17 s, sin llegar a esperar:
- Voz: acto 1 `groq/openai/gpt-oss-120b`; acto 2 `groq/qwen/qwen3.8-27b`; actos 3 a 5 `google/gemini-3.1-flash-lite`.
- Son **tres modelos en un relato**, justo lo que tiene que mostrar §4. Falta medir si se nota en la voz.

**Cadenas reales (`auto:narrativa` para la Voz, `auto:estructura` para lo que devuelve JSON), creadas por el usuario.** Planificador + 5 Voz + 5 Memoria, en serie y con la misma sesión, sin reintentos ni esperas del cliente: **11 de 11 llamadas bien, 41 s, los 6 JSON válidos.**
- Planificador: `gemini-3.5-flash` dio error de upstream y pasó a `gemini-3.1-flash-lite`.
- Voz: actos 1 y 2 `groq/qwen/qwen3.8-27b`; Groq limitó en el 3 y los actos 3 a 5 fueron `google/gemini-3.1-flash-lite`. **Dos modelos en un relato.**
- Memoria: siempre `gemini-3.1-flash-lite`.
- **El orden no se respeta estrictamente:** el acto 1 fue al tercero de la cadena sin que fallaran antes los dos primeros. Puede ser que la estrategia no esté en Manual (no se ve sin entrar al panel); además, aun en modo manual el código suma una penalidad por 429 y fallos que reordena (`orderChain`).
- **Sesión:** el modelo se mantuvo mientras pudo (actos 1 y 2, actos 3 a 5), pero no alcanza para afirmar que lo retiene `X-Session-Id`.
- **Compresión:** el gateway la trae en `aggressive`. Con el prompt del acto 1 de la Voz no ahorró nada (2033 tokens con y sin) y `off` se acepta. En los prompts largos de esta corrida no se registró cuánto recortó. Ver A1.
- Es una historia de snapshot y un solo horario: no dice nada de la calidad ni de cómo está el gateway a la noche.

**Sin probar:** las esperas de A8, Verificador, Revisor, Consultor y Guion. No apareció ningún `content_filter` con este relato de terror, que es suave: las historias más duras pueden comportarse distinto.

**Con la estrategia en Manual (2026-11-05), llamadas mínimas y un prompt de la Voz:**
- `auto:narrativa` respondió siempre con `groq/openai/gpt-oss-120b`, el cuarto de la lista pedida, sin fallos previos.
- `auto:estructura` respondió con `gpt-oss-120b`, que no debería estar en esa cadena, y una vez con `gemini-3.1-flash-lite` después de que falló `gemini-3.5-flash`.
- **Resuelto:** el contenido de las cadenas no era el acordado. El usuario las corrigió.

**Cadenas corregidas (6 llamadas por cadena, con 2 s entre una y otra, `max_tokens` 30):**
- `gpt-oss-120b` ya no aparece en ninguna respuesta, y `gemini-3.5-flash` vuelve a ir primero.
- `auto:narrativa`: 6 de 6 bien (4 `qwen3.8-27b`, 2 `gemini-3.5-flash`). Los 4 saltos fueron `empty_completion` de `gemini-3.5-flash`, posiblemente por el tope de 30 tokens de esta prueba, sin confirmar.
- `auto:estructura`: 2 bien y **4 con 429**, con `gemini-3.5-flash` en `upstream_error` y Groq en `rate_limited`.
- **Sin explicar:** en estos saltos `gemini-3.1-flash-lite` no respondió, aunque va segundo; en la corrida anterior sí tomó el relevo. Si un fallo de Google enfría toda la clave, la cadena depende en la práctica de dos claves (Google y Groq), y A8 importa más de lo previsto. Medir en el relato real de S1; si se repite, evaluar sumar un modelo de OpenRouter a `estructura`.

### T1.9 (2026-11-05): relato real en dev, «El monte prohibido»

**Intento 1 (perfil sin `reasoning_effort`):** Planificador y Verificador bien, con A8 esperando 85 s y 79 s en real. **Falló en el acto 3:** `respuesta truncada (max_tokens=2000)`.
**Intento 2 (con `reasoning_effort: low`):** falló en el acto 1, `groq/qwen/qwen3.8-27b`, `finish=length`, 2000 tokens de salida.

Mediciones con el prompt de la Voz y `max_tokens` 2000 (una por caso, varias interrumpidas por cooldown):

| Modelo | Sin `reasoning_effort` | `none` | `low` |
|---|---|---|---|
| `gemini-3.5-flash` | `length`, 64 palabras (también `length` con 4000) | 502 | `stop`, 433 palabras |
| `qwen3.8-27b` | `stop`, 490 palabras, 694 tokens; 413 una vez | **`length`, 2000 de razonamiento** | **`length`, 2000 tokens** (en el job) |
| `gpt-oss-120b` | `stop`, 374 palabras, 501 de razonamiento | `stop`, 321 palabras, 94 de razonamiento | sin dato (429) |
| `gemini-3.1-flash-lite` | `stop` en S0 (3 actos) | sin dato (429) | sin dato (429) |

**Conclusión:** `gemini-3.5-flash` gasta el tope razonando y necesita `reasoning_effort`; `qwen3.8-27b` no lo tolera. Es un valor por pedido: no se puede dar uno por modelo dentro de una cadena. Además, un `length` corta el job. El perfil queda sin `reasoning_effort` y el adapter conserva la opción por rol (sirve con un modelo fijo). Propuesta: sacar `gemini-3.5-flash` de las dos cadenas.

**Intentos 3 y 4 (sin `gemini-3.5-flash`, 2026-11-05):**
- Intento 3: actos 1 a 3 completos (559, 482 y 581 palabras), todo por Groq. Falló en el acto 4: `All models exhausted` **sin hora de vuelta**, y A8 no esperaba en ese caso. Corregido: si no hay hora, prueba de a 30 s hasta el tope.
- Intento 4: actos 1 y 2 completos; en el 3, `All models exhausted … Soonest reset ~17h`. **La cuota diaria de toda la cadena se agotó.** El adapter hizo lo correcto: no esperó 17 h y falló.
- `gemini-3.1-flash-lite` no respondió en ninguno de los dos: 429 sin hora, posible cuota diaria. Otro modelo de Google informó `daily_quota_exhausted`.
- Groq limita `qwen3.8-27b` a 1000 tokens de salida por minuto (visto en el panel, «Presión del router»): con `num_predict` > 1000, el pedido se rechaza. En `estructura`, los roles de más de 1000 quedarían solo con `gemini-3.1-flash-lite`. No se pudo probar.
- El ritmo real con Groq: ~90 s de espera entre llamadas de `estructura`. Un relato tardaría varios minutos más que los 120 s estimados.

**Sin medir: cuántos relatos por día alcanza la cuota gratis.** Las pruebas del día la gastaron. Es el dato que decide si esto sirve para prod. T1.9 sigue abierta hasta tener el relato completo.

### T1.9 cerrada (2026-11-06): un corto y un largo completos en dev

Con la cuota del día renovada, sin pruebas sueltas antes.

| Relato | Llamadas | Tiempo | Palabras | Tokens | Modelos de la Voz | Esperas |
|---|---|---|---|---|---|---|
| Corto (copia de «El monte prohibido», con Planificador y Verificador) | 8 | 22 s | 1072 (310 / 491 / 271) | ~18 400 | `gemini-3.1-flash-lite` en los 3 actos | ninguna |
| Largo (escaleta ya armada) | 10 | 136 s | 2278 (515 / 428 / 553 / 516 / 266) | ~25 300 (~30 000 con armado y revisión) | actos 1–2 `gemini-3.1-flash-lite`, 3 y 5 `gpt-oss-120b`, 4 `qwen3.8-27b` | 24 s y 91 s |

- **Primer intento del largo:** falló en la Memoria del acto 5. El gateway devolvió 502 `upstream_failed` con `X-Fallback-Trail` = `rate_limited` + `model_not_found`: un límite por minuto que no llega como 429. `gemini-3.1-flash-lite` frenó después de ~16 llamadas seguidas. **A8 ampliado:** un 502 cuyo trail tiene `=rate_limited` espera de a 30 s, dentro del mismo tope.
- **Tres modelos en la Voz del largo.** En la costura, el acto 3 (`gpt-oss-120b`) dice que «el motor se apagó» y Ricardo «gira la llave»: en un sulki. Es un error de continuidad que el control de repetición no ve. Además, ese acto tiene 7 comparaciones (`too_literary`).
- El control de repetición marca demasiadas comparaciones en casi todos los actos de los dos relatos. El corto repite un gesto en los tres actos («me acomodé el pelo detrás de las orejas»).
- En la cadena `estructura` aparece `gemini-2.5-flash` (`model_not_found`): está en el panel aunque no fue acordado. Hay que sacarlo.
- **Capacidad por día: sin medir el techo.** El 2026-11-05 la cadena se agotó tras ~125 000 tokens en Groq y ~125 000 en Google, casi todo en pruebas. Con ~18 000 por corto y ~30 000 por largo, eso daría del orden de 8 a 13 relatos por día. Es una estimación: los límites son por modelo, por minuto y por día, y no se conocen.

### S3, primeros cortos (2026-11-06, tarde; cortos seguidos, minutos entre uno y otro)

| # | Hora | Resultado | Por dónde | Detalle |
|---|---|---|---|---|
| 1 | 14:15 | ✅ 22 s | todo `gemini-3.1-flash-lite` | el de T1.9 |
| 2 | 14:27 | ✅ 195 s | todo Groq (`qwen3.8-27b`, `gpt-oss-120b`) | 3 esperas de ~91 s |
| 3 | 14:32 | ❌ Planificador | Groq | 413 `context_too_large` de `qwen3.8-27b`; Google en cooldown, una sola ruta |
| 4 | 14:45 | ❌ Voz del acto 3 | Groq | el mismo 413; antes, 1 espera de 91 s |

- **Google (`gemini-3.1-flash-lite`) respondió ~18 llamadas desde las 14:15 y después no volvió en toda la tarde** (429 sin hora). Parece un tope diario chico: alcanza para ~2 cortos.
- **Groq** sostiene solo con esperas de ~90 s y rechaza con 413 cuando se juntan pedidos en el mismo minuto (el panel mostró «OTPM: Limit 1000» para `qwen3.8-27b`). `gpt-oss-120b` gasta 1200+ tokens por acto por el razonamiento.
- **Sesgo de esta medición:** los cortos fueron seguidos. Las chicas escriben 2 o 3 por día, espaciados: los límites por minuto pesan menos, los diarios igual. Falta medir espaciado.
- **2 de 4 completos.** Con 3 por día como criterio, todavía no alcanza para afirmar nada.

| 5 | 15:04 | ❌ Verificador | Groq | 413 de `qwen3.8-27b` tras esperar 91 s (Google sigue sin volver) |

- **El patrón de los 3 fallos:** con el cupo diario de Google agotado, `auto:estructura` queda con `qwen3.8-27b` solo, y Groq rechaza el pedido por grande (`num_predict` alto contra su límite de salida por minuto). Lo que escribe cada rol en estas pruebas: Verificador 13–170 tokens, Memoria 213–327, Planificador del corto 1084–1260, Voz 352–787 (`gpt-oss-120b`: 684–1562 con razonamiento).
- **Ajuste aplicado:** Verificador `num_predict` 2000 → 1000.
- **Candidato a sumar** (prueba de las 15:10): `gemini-3.5-flash-lite` (Google, con su propio cupo diario) dio el JSON válido del Planificador (1527 tokens) y prosa natural, aunque corta (240 palabras, 317 tokens). `gemma-4-31b-it` no respondió (502, 429).

*(S3: sigue. S4: pendiente.)*

---

## 9. PLAN (reescrito el 2026-11-06, enfoque en el corto)

**Rama:** `feat/spec-740-freellmapi`. Orden: lo que destraba prod primero (S2 a S4: el corto en FreeLLMAPI y el largo controlado), después lo que pidieron las chicas (S5, S6), la medición en paralelo (S3) y prod al final (S7). Un commit por slice.

### S1. El proveedor: hecho (af75ffe, 2026-11-06)

Adapter, esperas de A8 (429 con o sin hora, 502 por cuota), perfil `freellmapi-libre`, `/health`, red de los contenedores, filtros por el modelo que respondió. Un corto y un largo completos en dev (§8).

### S2. Un perfil por largo (Parte D)

| Qué | Dónde |
|---|---|
| `LLM_PROFILE_LARGO` (vacío / `off` / perfil), resuelto al arrancar con la misma precedencia que `LLM_PROFILE`; un perfil que no existe falla al arrancar (no cae en silencio a otro) | `src/config.py` |
| El perfil en el contexto: `settings` lee el perfil del contexto cuando lo hay (roles, proveedores, tiempos, bloque `freellmapi`) | `src/config.py`, `src/domain/llm_context.py` |
| `JobManager` fija el perfil según `story.structure` (con `params.profile` correcto) y rechaza con 409 un job de una historia larga con el largo `off` | `src/application/services/job_manager.py` |
| `LLMFactory.get_provider()` arma el adapter del perfil del contexto | `src/infrastructure/factories.py` |
| `/authoring/options` con `disponible` y nota por largo; crear o pasar a largo con `off` → 422 | `src/presentation/routers/authoring_router.py` |
| `/health` y `/config/active-profile` con los dos perfiles | `src/presentation/routers/stream_router.py` |
| Mensajes `job.largo_deshabilitado` y `historia_nueva.largo_deshabilitado` (o donde corresponda en `core_messages.yaml`) | `config/core_messages.yaml` |

**Tests:** perfil por largo (vacío, `off`, otro perfil, perfil inexistente), dos jobs a la vez (uno corto y uno largo) sin pisarse el perfil, 409 de cada tipo de job sobre una historia larga con `off`, `options`, `health`. Snapshots de prompts sin cambios.
**Checkpoint:** en dev, `LLM_PROFILE_LARGO=off`: un corto se escribe; sobre la historia larga, la API rechaza el job con el mensaje.

### S3. Medición de cortos (D7, en paralelo; sin código del sistema)

| Qué | Dónde |
|---|---|
| 2 cortos más, cada uno con armado de los actos, para confirmar T1.9 (en curso el 2026-11-06) | §8 |
| Capacidad por día: cortos seguidos, con espera, hasta que la cadena informe la cuota del día, en un día sin otras pruebas. Tokens, modelos, saltos, esperas y fallas por relato | `scripts/research/740/`, §8 |
| Lectura a ciegas: 2 o 3 cortos de FreeLLMAPI junto a cortos de Sonnet ya guardados de la misma historia o parecida. Vale o las chicas, sin saber cuál es cuál | El usuario, §8 |
| `evaluate_voice.py` reporta modelos por acto, saltos y esperas (sirve para todo lo anterior) | `scripts/evaluate_voice.py` |

**Criterio:** con el corto en FreeLLMAPI, se esperan al menos **3 cortos por día** (las chicas escriben 2 o 3 en un día normal, dato del usuario del 2026-11-06), sin un error que corte el job, y la lectura a ciegas los acepta. Si no, se dice y el usuario decide.

### S4. La pantalla del largo deshabilitado (C6)

| Qué | Dónde |
|---|---|
| «¿Qué tan largo?» con el largo apagado y la nota | `frontend/src/views/asistente/direccion.ejs`, `frontend/src/services/authoring.service.ts` |
| Nota en la barra del asistente de una historia larga, con «Pasarla a corto» (el cambio de largo que ya existe, con confirmación) | `frontend/src/views/asistente/_cabecera.ejs` (o el partial de la barra) |
| Botones de IA y de escribir de esa historia, apagados (y el 409 de la API como red de seguridad, que ya muestra el modal) | vistas del asistente, `relato_acciones.ejs`, `public/js/escribir-relato.js` |

**Tests:** Vitest de vista (corto disponible, largo `off`, historia larga), `sin-jerga`, `gramatica-visual`; E2E en Firefox con el mock y `LLM_PROFILE_LARGO=off`.
**Checkpoint:** en `https://storymaker.test`, crear un relato nuevo (solo corto) y abrir una historia larga existente.

### S4b. El tope diario (Parte E), después de S3

| Qué | Dónde |
|---|---|
| `limite_relatos_por_dia` en el perfil y la cuenta de hoy (jobs `full_generation` `done` o activos con ese perfil, día de Argentina) | `config/llm_core_definitions.yaml`, `SQLJobRepository`, `JobManager` |
| 409 al pasar el tope, con su mensaje; `GET /jobs/estimates` (o un endpoint chico) devuelve cuántos quedan hoy | `job_manager.py`, `job_router.py`, `core_messages.yaml` |
| Botones de escribir con la nota («Hoy podés escribir N más» / apagado al tope) | `escribir-relato.js`, vistas de «Los actos», «El relato» y la sala |

**Tests:** la cuenta (hecho, corriendo, fallado, ayer, otro perfil, otro tipo de job), el 409, la nota en la vista con 0, 1 y el tope.

### S5. El registro (Parte B, sin cambios de fondo)

Igual que el plan anterior: `LLMResponse` con `provider`, `via`, `fallback_*` y `respaldo`; tabla `llm_call`; envoltorio `RegistroLLM` en la factory; acto en el contexto; enlace al relato en `_finish`. El perfil del contexto también se anota (columna `profile`).

### S6. Lo que ven las chicas (Parte C1–C5)

Igual que el plan anterior: `GET /generated-narratives/{id}/ia`, `config/modelos_ia.yaml`, la línea «Lo escribió…» por versión, por acto si cambió, y el resto plegado.

### S8. El adapter de OpenAI (Parte F), independiente del resto

| Qué | Dónde |
|---|---|
| `OpenAIAdapter` (SDK `openai`, `max_retries=0`), `openai_json_schema()`, causas de error | `src/infrastructure/adapters/openai_adapter.py`, `pyproject.toml` (+ `make dev-rebuild`) |
| `openai_api_key` en settings; rama `"openai"` en la factory; `/health` | `src/config.py`, `factories.py`, `stream_router.py` |
| Nombres de los modelos de GPT | `config/modelos_ia.yaml` |
| Fake del SDK con sus tipos reales, sin llamadas | `tests/support/fake_openai.py`, `tests/unit/test_openai_adapter.py` |

**Sin perfil activo ni llamadas reales** en esta slice. La prueba con la API (una llamada chica y después un corto) va recién cuando el usuario tenga la clave y dé el OK.

### S7. Prod (solo con OK)

`.env.prod`: `LLM_PROFILE=freellmapi-libre`, `LLM_PROFILE_LARGO=off` (o `hibrido-sonnet55` si hay crédito), `FREELLMAPI_URL` y la clave. PR a `development` y `main`, `make deploy-check`, `make deploy`, un corto de prueba. El gateway tiene que estar levantado en esta máquina: si se cae, prod no escribe (lo dice `/health`).

### Riesgos

| Riesgo | Qué hacemos |
|---|---|
| La cuota diaria no alcanza para el uso real | S3 lo mide antes de prod; el mensaje `sin_cuota_hoy` ya dice qué pasa |
| El perfil por contexto se escapa a una llamada fuera de un job (CLI, scripts) | Fuera de un job manda `LLM_PROFILE`, como hoy; los scripts pasan `--profile` |
| Historias largas existentes en prod (5) quedan sin poder escribirse | La nota ofrece pasarlas a corto; vuelven solas cuando haya crédito |
| El Planificador y el Revisor en modelos gratis (los roles que gemma no pudo) | El armado del corto entra en S3; si falla, se dice |

### Docs al cerrar

`CLAUDE.md` (FreeLLMAPI, perfil por largo, `LLM_PROFILE_LARGO`, tabla `llm_call`, endpoint), `.env.example` si existe.

---

## 10. TASKS (reescritas el 2026-11-06)

### S1: hecho (af75ffe)

T1.1 a T1.9 hechas; ver §8 y el commit.

### S2: Un perfil por largo

- ✅ S2 hecha (2026-11-06): con `LLM_PROFILE_LARGO=off` en dev, la API rechaza con 409 todo trabajo sobre una historia larga, antes que las validaciones. El corto de prueba arrancó con su perfil y falló por cuota (§8).
- **T2.1** `LLM_PROFILE_LARGO` en config (vacío, `off`, perfil; perfil inexistente falla al arrancar). **Hecho cuando:** pasan los tests de resolución de los cuatro casos.
- **T2.2** El perfil en el contexto y `settings` leyéndolo (roles, proveedores, tiempos, bloque del proveedor). **Hecho cuando:** un test muestra dos tareas con perfiles distintos leyendo cada una su config, y fuera de contexto el de siempre.
- **T2.3** `JobManager` fija el perfil por `story.structure` y rechaza los jobs de una historia larga con `off` (409, mensaje coloquial). `params.profile` es el usado. **Hecho cuando:** hay un test por tipo de job y uno de un corto y un largo simultáneos.
- **T2.4** Factory desde el perfil del contexto. **Hecho cuando:** con un largo en otro proveedor, el job del largo usa ese adapter (test con el mock de Anthropic).
- **T2.5** `/authoring/options` con `disponible`; crear o pasar a largo con `off` → 422; `/health` y `/config/active-profile` con los dos perfiles. **Hecho cuando:** pasan los tests de cada endpoint.
- **T2.6** Checkpoint en dev con `LLM_PROFILE_LARGO=off`. **Hecho cuando:** `make test`, `make lint` y `make dev-status` están en verde; un corto se escribe y el job sobre la historia larga se rechaza con el mensaje.

### S3: Medición de cortos

- **T3.1** 2 cortos más con armado (en curso). **Hecho cuando:** §8 tiene sus tokens, modelos, esperas y fallas.
- **T3.2** `evaluate_voice.py` con modelos, saltos y esperas. **Hecho cuando:** corre con `--mock` y el reporte los trae.
- **T3.3** Capacidad por día, en un día sin otras pruebas. **Hecho cuando:** §8 dice cuántos cortos entraron y qué los cortó.
- **T3.4** Lectura a ciegas. **Hecho cuando:** la respuesta de Vale o las chicas está en §8.

### S4: La pantalla del largo deshabilitado

- ✅ S4 hecha (2026-11-06). El Core informa `ia_disponible`/`ia_nota` en el estado del asistente y en `GET /stories/{id}`; la nota va en la barra de los cuatro pasos y en corregir, video y la sala; los botones de IA vienen `disabled` con `data-ia-apagada`, y `public/js/ia-apagada.js` corta el clic aunque otro script los vuelva a habilitar; pasar a corto recarga la página. E2E: `E2E_LLM_PROFILE_LARGO=off npx playwright test largo-apagado` (la siembra del arnés corre sin esa variable). La suite completa pasó con una falla intermitente en `asistente-sin-recargar` (aislado, 12 de 12; también sin estos cambios).
- **T4.1** «¿Qué tan largo?» con el largo apagado y la nota. **Hecho cuando:** pasa el Vitest con el largo disponible y con `off`.
- **T4.2** Nota en la barra de una historia larga con «Pasarla a corto», y botones de IA apagados. **Hecho cuando:** pasan el Vitest, `sin-jerga` y `gramatica-visual`.
- **T4.3** E2E en Firefox con `LLM_PROFILE_LARGO=off`. **Hecho cuando:** está en verde y en `https://storymaker.test` se ve como se describe en C6.

### S4b: El tope diario (con el número de S3)

- **T4b.1** `limite_relatos_por_dia` y la cuenta de hoy. **Hecho cuando:** los tests cubren los casos de E1.
- **T4b.2** 409 al tope y cuántos quedan en la API. **Hecho cuando:** pasan los tests de la API.
- **T4b.3** La nota en los botones de escribir. **Hecho cuando:** pasan el Vitest (0, 1, tope), `sin-jerga` y un E2E con tope 1 en el mock.

### S5: El registro

- ✅ S5 hecha (2026-11-06): `LLMResponse` con `provider`, `via`, `fallback_*` y `respaldo`; tabla `llm_call` (con `profile`); `RegistroLLM` envuelve todo adapter en `LLMFactory.get_provider()` (los tests de tipo miran `.inner`); el acto en el contexto (`execute_full`, regenerar); `JobManager._finish` enlaza las llamadas al relato. En dev, la fila del Planificador coincide con el log del gateway (modelo, ruta, tokens, perfil).
- **T5.1** `LLMResponse` con los campos restantes; cada adapter los llena; `RoleRoutingAdapter` marca `respaldo`. **Hecho cuando:** hay un test por adapter.
- **T5.2** Tabla `llm_call` (con `profile`) y su repositorio. **Hecho cuando:** `init_db()` la crea sobre una base existente y los tests cubren alta, enlace, consultas y borrado en cascada.
- **T5.3** `RegistroLLM` en la factory, con `respaldos` por delegación. **Hecho cuando:** los tests cubren anotar con contexto, solo delegar sin él, falla de la DB que no rompe el job y reintentos de `generate_structured`.
- **T5.4** El acto en el contexto y el enlace al relato en `_finish`. **Hecho cuando:** una integración con el mock deja una fila por llamada con rol, acto y relato, y regenerar un acto cambia solo ese acto.
- **T5.5** Comprobar en dev. **Hecho cuando:** tras un corto real, `llm_call` coincide con el log del gateway.

### S6: Lo que ven las chicas

- ✅ S6 hecha (2026-11-06): `config/modelos_ia.yaml` (nombres y tareas), `ia_del_relato.resumen` (por acto la última Voz; el resto, el último modelo de cada tarea del relato y del asistente), `GET /generated-narratives/{id}/ia`, la línea «Lo escribió…» con marca por acto si hay más de un modelo y «Ver qué IA hizo cada cosa» plegado; nada se copia ni va al `.md`. El arnés E2E escribe con `RegistroLLM`. Suites: 1217 pytest, 454 Vitest, 92 E2E (6 saltados, los de siempre).
- **T6.1** `config/modelos_ia.yaml` y el servicio del resumen. **Hecho cuando:** los tests cubren uno, varios, sin dato, id desconocido y con prefijo o `:free`.
- **T6.2** `GET /generated-narratives/{id}/ia`. **Hecho cuando:** los tests cubren con datos, viejo (vacío) e inexistente (404).
- **T6.3** El front suma `ia` tolerando un error del Core, y `relato_panel.ejs` muestra la línea, la marca por acto y el plegado. **Hecho cuando:** pasan el Vitest y los guardianes de vistas.
- **T6.4** E2E en Firefox. **Hecho cuando:** en `https://storymaker.test` un corto nuevo muestra sus modelos y uno viejo no muestra la línea.

### S8: El adapter de OpenAI

- ✅ T8.1 a T8.5 hechas (2026-11-06): `OpenAIAdapter` con el SDK `openai` 3.46 (`max_retries=0`); los modelos que razonan (`gpt-5`, `o1`, `o3`, `o4`) van sin `temperature` y con piso de 16 000 tokens salvo `reasoning_effort` `none`/`minimal`; `openai_json_schema()` pone todos los campos en `required` y los opcionales admiten `null`, que `drop_added_nulls()` saca de la respuesta antes de que valide Pydantic (los esquemas reales de los 8 usos, del Consultor al Guion, van y vuelven con el mock). Factory, `openai_api_key`/`openai_model`, `/health` (`GET /v1/models`) y los nombres GPT-5 mini y nano. Suites: 1266 pytest; dev reconstruido (`make dev-rebuild`) y en verde, sin perfil de OpenAI activo. Falta T8.6 (clave, modelo, precios).
- **T8.1** `OpenAIAdapter` con el pedido por rol (F2). **Hecho cuando:** los tests cubren `max_completion_tokens`, `temperature` según el modelo, `reasoning_effort` y que no va ningún header del gateway.
- **T8.2** Errores y respuestas (F3). **Hecho cuando:** hay un test por causa (`insufficient_quota` → `credito`, 401 → `clave`, 429 y 5xx → `saturada`, sin red → `sin_conexion`), por `refusal`, `content_filter`, `length` y vacío, y ninguno reintenta.
- **T8.3** `openai_json_schema()` y `generate_structured` (F4). **Hecho cuando:** los esquemas de los roles (Planificador, Verificador, Consultor, Memoria, Guion) pasan por la traducción y el fake valida el modo estricto.
- **T8.4** Factory, settings, `/health` y `modelos_ia.yaml` (F5). **Hecho cuando:** un perfil de prueba con `provider: openai` arma el adapter envuelto en `RegistroLLM`, `/health` lo verifica con el fake y el resumen muestra el nombre de GPT.
- **T8.5** Checkpoint. **Hecho cuando:** `make test`, `make lint` y `make dev-status` están en verde, sin activar el perfil.
- **T8.6** (con clave y OK) Precios, perfil y un corto de prueba en dev. **Hecho cuando:** §8 tiene costo, tiempo y la prosa del corto comparada con la de Sonnet.

### S7: Cierre y prod

- **T7.1** `CLAUDE.md`, memoria y PR a `development`. **Hecho cuando:** las suites completas y `make dev-status` están en verde y el PR está abierto.
- **T7.2** Pase a prod **solo con OK del usuario** (§9 S7). **Hecho cuando:** un corto en `https://storymaker.prd` sale completo y muestra sus modelos, y una historia larga muestra la nota.

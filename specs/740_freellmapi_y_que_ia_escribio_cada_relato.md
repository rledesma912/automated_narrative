# SPEC-740: FreeLLMAPI como proveedor y qué IA escribió cada relato

**Fecha:** 2026-11-05
**Tipo:** SDD: proveedores LLM (adapter + perfil), registro de llamadas, «El relato» (UI)
**Estado:** TASKS escritas (§10, 2026-11-05), esperando el OK del usuario para pasar a IMPLEMENT.
**Rama:** a crear desde `development`, `feat/spec-740-freellmapi`
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

## OBJECTIVE

1. Que un rol pueda declarar `provider: freellmapi` en un perfil, igual que hoy declara `anthropic`.
2. Que cada llamada a una IA deje registrado qué modelo respondió **de verdad**, y que cada versión de un relato lo muestre.

**Éxito:** un relato escrito por FreeLLMAPI dice en «El relato» con qué modelos se escribió (también si cambió a mitad de camino); uno escrito con Sonnet dice Sonnet; los viejos no dicen nada; y hay una medición que permite decidir qué roles, si alguno, pasan a FreeLLMAPI.

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

---

## 5. Slices y verificación

| Slice | Qué | Cómo se valida |
|---|---|---|
| **S0** | Hecho (2026-11-05). Sonda real con modelos habilitados, prosa, esquema real del Planificador, errores y un relato en serie | Resultado en §8 |
| **S1** | A1–A6 | Tests con `httpx.MockTransport`: headers, esquema, cada error, `length`, `content_filter`. `test_prompts_fuera_del_codigo` en verde |
| **S2** | B1–B7 | Tests: cada adapter informa, fallback/respaldo, regenerar un acto, falla de registro, sin datos en prompts (snapshots sin cambios) |
| **S3** | C1–C5 | Vitest de vistas y E2E en Firefox. `storymaker.test`: un relato de un solo modelo, uno de varios y uno viejo |
| **S4** | Medición con la cadena `auto:narrativa`: `evaluate_voice.py --profile freellmapi-libre --runs 2` contra los relatos de Sonnet ya medidos, a distintas horas para ver la baja del día, y el armado de los actos (Planificador, Verificador, Revisor) con las historias de la Spec-720. Métricas de siempre + modelos usados + llamadas con fallback + esperas + fallas. Sin crédito no se corre Sonnet: se compara con la evidencia guardada | Tabla en §8 y decisión del usuario por rol |
| **S5** | Si la medición lo justifica: activar en `.env` o `.env.prod`. **Solo con OK del usuario**, con `make deploy` | `make deploy-check` y un relato de prueba |

Cierre de cada checkpoint (Spec-540 §2.5): tests en verde, `make dev-status` en verde y la URL para mirar. La Parte B y la C no dependen de FreeLLMAPI: pueden desplegarse aunque S4 diga que ningún rol pasa.

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

*(S4: pendiente.)*

---

## 9. PLAN (2026-11-05)

**Rama:** `feat/spec-740-freellmapi` desde `development`. Orden: primero lo que destraba escribir sin Anthropic (S1), después lo que pidieron las chicas (S2, S3), y la medición al final (S4).

### S1. El proveedor

| Qué | Dónde |
|---|---|
| `FreeLLMAPIAdapter` con `httpx.AsyncClient` inyectable: mapeo de `response_schema`, headers fijos (`X-FreeLLM-Cache: off`, `X-FreeLLM-Compress: off`), `X-Session-Id`, `max_tokens` desde `num_predict` | `src/infrastructure/adapters/freellmapi_adapter.py` (nuevo) |
| Errores: 401/403 `clave`, 429 y 5xx `saturada`, red `sin_conexion`, 503 `no_providers_configured` `sin_modelos`, 413 y 404 `error`. `length` → `LLMResponseError`; `content_filter` → `LLMRefusalError`; texto vacío → `LLMResponseError` | Mismo adapter |
| A8: con 429 `rate_limit_exceeded` y `retryAtMs`, `asyncio.sleep` hasta esa hora y reintenta; tope 120 s por llamada, configurable en el perfil. `quota_exceeded` no espera. La espera se cancela con el job | Mismo adapter |
| `freellmapi_url` y `freellmapi_api_key` en `Settings` (`extra="ignore"` ya los tolera); rama en `LLMFactory._single`; export | `src/config.py`, `src/infrastructure/factories.py`, `adapters/__init__.py` |
| Contexto del job en un `ContextVar` (`job_id`, `story_id`, `act`): lo fija `JobManager._run`; sin contexto (CLI, tests) el adapter no manda sesión. S2 lo reutiliza | `src/domain/llm_context.py` (nuevo), `src/application/services/job_manager.py` |
| `/health` con `GET /v1/models` y timeout corto; `provider_ok` incluye el proveedor | `src/presentation/routers/stream_router.py` |
| A5: `ResponseNormalizer` recibe el modelo que respondió, no el configurado. Hoy `normalize(..., model_name=model)` usa el del YAML | `src/application/use_cases/voz_use_case.py` |
| Perfil `freellmapi-libre`: Voz en `auto:narrativa`; Memoria, Consultor, Planificador, Verificador, Revisor y Guion en `auto:estructura`; `num_predict` por rol y `estimated_seconds` provisorios | `config/llm_core_definitions.yaml` |
| Mensaje `llm.sin_modelos`; revisar que los `llm.*` no digan algo falso con otro proveedor | `config/core_messages.yaml` |
| `extra_hosts: freellmapi.test:host-gateway`; `FREELLMAPI_URL` y clave en `.env` y `.env.prod` (el usuario, `.env.prod`) | `docker-compose.yml`, `docker-compose.dev.yml` |

**Tests:** `tests/unit/test_freellmapi_adapter.py` con `httpx.MockTransport` (headers, esquema, cada error, `length`, `content_filter`, espera con reloj falso, tope, sin sesión fuera de un job), factory con perfil mixto, `/health`, `test_prompts_fuera_del_codigo`, snapshots sin cambios.
**Checkpoint:** `make test`, `make lint`, `make dev-up` para tomar `extra_hosts`, y `make dev-status`. Con `LLM_PROFILE=freellmapi-libre` en `.env` (pide OK, ver §7), un relato completo de «El monte prohibido» en `https://storymaker.test`.

### S2. El registro

| Qué | Dónde |
|---|---|
| `LLMResponse` suma `provider`, `model`, `via`, `fallback_attempts`, `fallback_trail`, `respaldo`; todos con valor por defecto | `src/domain/interfaces.py` |
| Cada adapter los llena. Ollama, Anthropic y Gemini con su nombre y el modelo usado; `RoleRoutingAdapter` marca `respaldo=True` | `src/infrastructure/adapters/` |
| Tabla `llm_call` con FK a `story` y a `generated_narrative`, ambas `ON DELETE CASCADE`, e índices por `narrative_id` y `story_id` | `src/infrastructure/database/connection.py` |
| `SQLLLMCallRepository`: `add`, `link_narrative(job_id, narrative_id)`, consultas de versión e historia | `src/infrastructure/database/repositories/` |
| `RegistroLLM`: envoltorio de `LLMProvider`. Sin contexto de job solo delega; con contexto anota después de cada `generate` exitoso; si anotar falla, loguea y sigue (B4). Expone `respaldos` por delegación: lo leen `authoring_jobs.py:71` y `generate_story_use_case.py:143` | `src/infrastructure/adapters/registro_llm.py` (nuevo), `LLMFactory.get_provider` |
| El acto en el contexto: `execute_full` lo fija en cada vuelta, y `RegenerateBeatVozUseCase.execute` para el suyo | `src/application/use_cases/` |
| Enlazar al relato en `JobManager._finish`, con el `narrative_id` del evento `done` (los dos tipos de job ya lo mandan) | `src/application/services/job_manager.py` |

**Por qué un envoltorio y no el protocolo:** así ninguno de los ~10 lugares que llaman a `generate` cambia, ni los prompts (los snapshots lo prueban). Un `generate` del mock no anota nada si no hay job.

**Tests:** los de B1–B7: reintentos de `generate_structured` (se anotan todos), respaldo, regenerar un acto (B5), falla de la DB sin romper el job (B4), borrar relato o historia (B7), `respaldos` visible a través del envoltorio.
**Checkpoint:** `make test`, y consulta de `llm_call` tras un relato en dev. **La tabla nueva no necesita `make dev-db`.**

### S3. Lo que ven las chicas

| Qué | Dónde |
|---|---|
| `GET /generated-narratives/{id}/ia`: `{resumen, por_acto, resto}` con nombres para mostrar, vacío si no hay datos (B6) | `src/presentation/routers/narrative_router.py`, servicio de aplicación |
| `config/modelos_ia.yaml`: substring → nombre lindo. Sin coincidencia, el id sin prefijo ni `:free` (C4) | `config/`, test de un id desconocido |
| Sumar `ia` al relato, como `repetition`, tolerando un error del Core | `frontend/src/services/story.service.ts` |
| Línea por versión, marca por acto solo con más de un modelo, y «Ver qué IA hizo cada cosa» plegado | `frontend/src/views/partials/relato_panel.ejs` |

**Tests:** Vitest de vista (uno, varios, sin dato), `sin-jerga`, `gramatica-visual`, `no-hardcoded-colors`; E2E en Firefox con el mock. Regenerar la referencia de HTML solo si cambia a propósito.
**Checkpoint:** `https://storymaker.test`: un relato de S1 y uno viejo sin línea.

### S4. La medición

| Qué | Dónde |
|---|---|
| `evaluate_voice.py` reporta modelos por acto, saltos y esperas. Sin cambios en el cálculo de costo: `freellmapi` no está en `PAID_PROVIDERS` | `scripts/evaluate_voice.py` |
| Corridas en tres horarios (mañana, tarde, noche), con los tres modos del acuerdo: cadena normal, rotación (por script) y un modelo con esperas | `scripts/research/740/` |
| `evaluate_workshop.py` para Consultor, Planificador y Verificador; una corrida de Revisor y Guion | Mismo directorio |
| Comparar contra la evidencia guardada de Sonnet (Spec-600, 700, 720). No se corre Sonnet: no hay crédito | §8 |
| Lectura a ciegas de los tres modos por Vale o las chicas | Con el usuario |

**Criterio para pasar un rol:** ningún error de los que ya bloquearon a gemma: para Revisor, el umbral de la Spec-700 §11; para Planificador y Verificador, el de la Spec-720 §11. Para la Voz manda la lectura a ciegas. Si un rol no llega, queda dicho y el usuario decide.

### S5. Prod (solo con OK)

`FREELLMAPI_URL`, clave y `LLM_PROFILE` en `.env.prod`, PR a `development` y a `main`, `make deploy-check`, `make deploy`, un relato de prueba. La tabla se crea sola y la Parte B y C pueden ir antes, por sí solas. Prod sigue frenado hasta acá o hasta que haya crédito.

### Riesgos

| Riesgo | Qué hacemos |
|---|---|
| Los modelos gratis no alcanzan en Planificador o Revisor (como gemma) | S4 lo mide antes de prod. El Revisor tiene su nota sin IA si el perfil no lo declara |
| Guion: prompt largo, 1 llamada y mucho JSON. Es el que más puede chocar con el tope de una capa gratis | Probarlo temprano en S4; si no da, sin Guion hasta recargar |
| El orden de la cadena no es estricto (§8) | El registro lo muestra; no depende de que el orden sea exacto |
| El gateway cambia sin aviso (imagen `latest`, capas gratis) | Tests sin red; todo pasa por el adapter; fijar la imagen a `v0.16.19` es decisión del usuario |
| Una recarga de uvicorn corta un job de dev | Ya conocido (Spec-540): no editar `src/` durante una corrida |

### Docs al cerrar

`CLAUDE.md` (proveedor, perfil, tabla: 17 tablas, endpoint), `.env.example` si existe.

---

## 10. TASKS (2026-11-05)

Acordado con el usuario: activar `freellmapi-libre` en dev al cerrar S1 (probando con «El monte prohibido»), medir los tres modos en S4 y un commit por slice en `feat/spec-740-freellmapi`. Prod solo con OK aparte (S5).

### S1: El proveedor

- **T1.1** Rama desde `development`; la spec entra en el primer commit. **Hecho cuando:** la rama existe y `git status` solo muestra lo de esta spec.
- **T1.2** `src/domain/llm_context.py` (`ContextVar` con `job_id`, `story_id`, `act`) y `JobManager._run` lo fija. **Hecho cuando:** un test muestra que dos jobs simultáneos no se pisan el contexto y que fuera de un job está vacío.
- **T1.3** `FreeLLMAPIAdapter`, llamada feliz: mensajes, `max_tokens` desde `num_predict`, `response_format`, los dos headers fijos, `X-Session-Id` con contexto, tiempos y tokens. **Hecho cuando:** pasan los tests con `httpx.MockTransport`, incluida la llamada sin sesión fuera de un job.
- **T1.4** Errores (401/403, 413, 404, 429, 5xx, `no_providers_configured`, red) y cortes (`length`, `content_filter`, vacío), con `llm.sin_modelos` y los `llm.*` revisados. **Hecho cuando:** hay un test por caso con la excepción y la causa esperadas, y pasa `test_prompts_fuera_del_codigo`.
- **T1.5** A8: espera por `retryAtMs` con tope de 120 s configurable; `quota_exceeded` no espera; cancelable. **Hecho cuando:** los tests con reloj falso cubren esperar y responder, pasar el tope, sin `retryAtMs`, `quota_exceeded` y cancelar durante la espera.
- **T1.6** `Settings`, `LLMFactory._single`, export, `/health` con `GET /v1/models`. **Hecho cuando:** los tests cubren la factory (sola y en perfil mixto) y `/health` con el gateway arriba, abajo y sin clave.
- **T1.7** A5: `LLMResponse.model` opcional, lo llena el adapter, y `VozUseCase` lo pasa a `normalize` (o el configurado si no viene). **Hecho cuando:** un test con `model_overrides` aplica el filtro al modelo que respondió con `auto:narrativa` pedido, y los snapshots no cambian.
- **T1.8** Perfil `freellmapi-libre` y `extra_hosts` en los dos compose. **Hecho cuando:** un test carga el perfil con todos sus roles y `make dev-up` llega al gateway desde `narrative-api-dev`.
- **T1.9** ✅ (2026-11-06, §8) Activar en `.env` y escribir «El monte prohibido» en dev. **Hecho cuando:** `make test`, `make lint` y `make dev-status` están en verde, el relato completo está en `https://storymaker.test`, y en §8 quedan los modelos usados, los saltos, las esperas y si el problema de `gemini-3.1-flash-lite` se repite.

### S2: El registro

- **T2.1** `LLMResponse` con los campos restantes (`provider`, `via`, `fallback_attempts`, `fallback_trail`, `respaldo`) y cada adapter los llena. **Hecho cuando:** hay un test por adapter y uno de `RoleRoutingAdapter` que marca `respaldo`.
- **T2.2** Tabla `llm_call` y `SQLLLMCallRepository`. **Hecho cuando:** `init_db()` la crea sobre una base existente sin tocar lo demás, y los tests cubren `add`, `link_narrative`, las consultas y el borrado en cascada.
- **T2.3** `RegistroLLM` en `LLMFactory.get_provider`, con `respaldos` por delegación. **Hecho cuando:** los tests cubren anotar con contexto, solo delegar sin él, falla de la DB que no rompe el job, reintentos de `generate_structured` y `respaldos` a través del envoltorio.
- **T2.4** El acto en el contexto (`execute_full`, `RegenerateBeatVozUseCase`) y el enlace en `JobManager._finish`. **Hecho cuando:** una integración con el mock deja una fila por llamada con su rol, acto y relato, y regenerar un acto hace que la versión muestre el modelo nuevo solo en ese acto.
- **T2.5** Comprobar en dev. **Hecho cuando:** tras un relato real, `llm_call` coincide con lo que dicen los logs del gateway, y los snapshots de prompts siguen sin cambios.

### S3: Lo que ven las chicas

- **T3.1** `config/modelos_ia.yaml` y el servicio que arma `{resumen, por_acto, resto}`. **Hecho cuando:** los tests cubren un modelo, varios, sin dato, un id desconocido y uno con prefijo y `:free`.
- **T3.2** `GET /generated-narratives/{id}/ia`. **Hecho cuando:** los tests cubren un relato con datos, uno viejo (vacío, no error) y uno inexistente (404).
- **T3.3** `story.service.ts` suma `ia`, tolerando un error del Core. **Hecho cuando:** el Vitest muestra que el relato se ve igual aunque falle esa consulta.
- **T3.4** `relato_panel.ejs`: la línea, la marca por acto y «Ver qué IA hizo cada cosa». **Hecho cuando:** pasan el Vitest de vista (uno, varios, sin dato), `sin-jerga`, `gramatica-visual` y `no-hardcoded-colors`.
- **T3.5** E2E en Firefox con el mock. **Hecho cuando:** está en verde, y en `https://storymaker.test` el relato de S1 muestra sus modelos y uno viejo no muestra la línea. Los fixtures se regeneran solo con el diff revisado.

### S4: La medición

- **T4.1** `evaluate_voice.py` reporta modelos por acto, saltos y esperas. **Hecho cuando:** corre con `--mock` y el reporte trae esos datos.
- **T4.2** Script de los tres modos en `scripts/research/740/` (cadena normal, rotación, un modelo con esperas). **Hecho cuando:** genera las tres versiones de «El monte prohibido» con el pipeline real, en dev o en una DB temporal, sin tocar el sistema.
- **T4.3** Corridas en tres horarios. **Hecho cuando:** en §8 está la tabla con métricas, modelos, saltos, esperas y fallas por modo y horario.
- **T4.4** Consultor, Planificador y Verificador con `evaluate_workshop.py`; Revisor y Guion, una corrida cada uno. El Guion primero. **Hecho cuando:** en §8 cada rol está comparado con el umbral de las Spec-700 y 720, o dice qué falta para compararlo.
- **T4.5** Lectura a ciegas por Vale o las chicas: el usuario se las pasa sin decir cuál es cuál. **Hecho cuando:** su respuesta está en §8.
- **T4.6** Decisión del usuario por rol, y ajuste del perfil. **Hecho cuando:** el perfil refleja la decisión y §8 la explica.

### S5: Cierre y prod

- **T5.1** `CLAUDE.md`, memoria y PR a `development`. **Hecho cuando:** las suites completas (`make test`, Vitest, E2E) y `make dev-status` están en verde, y el PR está abierto.
- **T5.2** Pase a prod **solo con OK del usuario**: variables en `.env.prod`, `make deploy-check`, `make deploy`, y un relato de prueba. **Hecho cuando:** el relato en `https://storymaker.prd` muestra sus modelos y los relatos viejos siguen intactos.

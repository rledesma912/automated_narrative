# SPEC-600: Rumbo del proyecto: la Voz en un modelo frontier y el cierre

**Fecha:** 2026-09-30
**Tipo:** SDD, decisión de arquitectura y alcance de cierre
**Estado:** IMPLEMENT — S0 ✅ (PR #46); S1 en curso
**Rama:** S0 en `feat/spec-590-prosa` (PR #46, mergeado); S1 en `feat/spec-600-voz-frontier`
**Extiende:** Spec-480 (proveedor por rol), Spec-590 (prosa según la prueba con usuarias)

---

## PRINCIPIO

**Cerrar el proyecto.** El usuario lo pidió (2026-09-30): lleva mucho tiempo. Cada cambio de esta spec tiene que acercar el cierre. No entra nada que abra una línea nueva de investigación.

**La IA grande solo donde se nota.** La prosa es lo que leen las usuarias ([anexo de la 590](590_anexo_prueba_usuarias.md)). El resto del pipeline (Consultor, Planificador, Verificador, Memoria) produce datos estructurados que el autor revisa en la UI. Ahí el modelo local alcanza, y cuando se equivoca el autor lo corrige antes de generar.

---

## 1. LA PREGUNTA

El usuario (2026-09-30), con sus palabras:

1. «Aunque tratamos, el modelo falla en la generación incluso de un solo acto.» ¿Estamos en el camino correcto?
2. ¿Conviene enfocar el trabajo en el arnés, con **RAG + grafo** y un **agente** que arme mejor contexto para la Voz?
3. ¿El modelo no está preparado para narrativa? ¿Hay uno más nuevo y especializado?
4. ¿Estamos en condiciones de **dejar los modelos locales**?
5. Si usamos un **LLM frontier**, que sea **solo en la Voz**, para que sea óptimo y económico.

---

## 2. DIAGNÓSTICO: qué falla y por qué

### 2.1 Las fallas que vimos son de obediencia, no de contexto

Estas son las fallas de los relatos de dev del 2026-09-30 (Spec-590 §7, S2 y S3):

| Falla | ¿El dato estaba en el prompt? |
|---|---|
| Se saltea un hecho del acto (los vidrios en el oído, 7.º de 7) | Sí, en «EVENTOS DE ESTE ACTO» |
| Adelanta hechos de otros actos (astas en el acto 1) | Sí, con la instrucción de no hacerlo |
| Escribe diálogo con raya | Sí, con «Nunca escribas diálogo» en el system |
| Contradice un rasgo propio (la radio «siempre prendida» / «apagada, como siempre») | Sí, en «ASÍ ES …» |
| Inventa un hecho de cierre y lo copia al acto siguiente | Sí, «no inventes hechos» |
| Clichés prohibidos («me heló la sangre») | Sí, en la lista de clichés |

**En todos los casos el dato ya estaba en el prompt.** El prompt más largo tiene ~2 830 tokens, contra una ventana de 8 192. Al modelo no le **falta** contexto: tiene todo y **no lo sostiene** mientras escribe ~900 palabras. Así fallan los modelos chicos según la literatura: olvidan requisitos puntuales o, aunque los retengan, no logran integrarlos en un texto coherente ([Incremental Instruction Delivery, 2026](https://arxiv.org/html/2609.33738)). Otra referencia práctica: los modelos de 8–14B pierden consistencia pasadas ~1 000 palabras, los de 24B llegan a ~1 500 y hacen falta 70B para 1 000–3 000 palabras coherentes ([PromptQuorum, 2026](https://www.promptquorum.com/local-llms/best-local-llms-for-creative-writing)).

### 2.2 El techo del hardware

- **GPU:** RTX 3060 de **12 GB**. Entra un modelo de 12–14B cuantizado (gemma3:12b ocupa 8,1 GB), con margen para `num_ctx` 8192.
- Un 24B (Mistral Small) necesita ~16 GB y un 70B ~40 GB: habría que descargar a RAM (hay 62 GB). Anda, pero **mucho más lento**. Un relato que hoy tarda 5 min pasaría a tardar entre 20 y 60 min.
- Lo instalado (gemma3:12b, qwen2.5:14b, mistral-nemo:12b, qwen3:8b) es de la misma clase. Cambiar entre ellos **no cambia la clase de error**. Ya se probó con llama3.1 (desbordaba y era incoherente).

### 2.3 Lo que dice el estado del arte

- **RAG + grafo para ficción** es para **novelas**: decenas de miles de palabras que no entran en el contexto ([Long Story Generation via Knowledge Graph, 2025](https://pith.science/paper/2508.03137); [PlotGraph](https://link.springer.com/chapter/10.1007/978-3-032-31673-8_30); proyectos con «story bible» temporal y agenda de siembras en [GitHub · long-form-writing](https://github.com/topics/long-form-writing)). Nuestro relato tiene ~3 000 palabras en 5 actos y **la escaleta ya es ese grafo**: hechos por acto, siembras y cobros, lo que no se cuenta y en qué acto se revela, quién está en escena. El Planificador y el Verificador ya son los agentes que arman ese contexto.
- **Modelos chicos «especializados» en narrativa:** existen, pero se logran **entrenando**. POLARIS (Qwen3.5-9B con RL y un juez frontier) pasa de 18,5 a 52,1 en calidad y compite con modelos 3× más grandes. Lo hicieron en inglés, con 4 A100 durante 48 h ([POLARIS, 2026](https://arxiv.org/html/2606.04095v2)), y no usa RAG, grafos ni agentes. No hay un modelo de ese tipo **en español** listo para bajar. Entrenar uno es un proyecto nuevo, lo contrario de cerrar.
- **Ranking de escritura creativa** ([EQ-Bench Creative Writing v3](https://eqbench.com/creative_writing.html)): arriba de todo, modelos frontier (Claude Opus 5, Kimi K3, GPT-5.6). El mejor abierto es Qwen3-235B, que no entra en esta máquina.

### 2.4 Conclusión

| Pregunta | Respuesta |
|---|---|
| ¿Camino correcto? | **Sí en la arquitectura** (escaleta confirmada → Voz simple → detectar después). **No en insistir con prompts** para el 12b: cada ajuste arregla una falla y abre otra (S3 bajó las cortadas y subió el diálogo). |
| ¿RAG + grafo + agente? | **No.** El problema no es encontrar contexto, porque ya está todo en el prompt. Sumar un agente es sumar llamadas de un modelo que ya no sostiene las que tiene. La escaleta cumple ese papel. |
| ¿Modelo local más nuevo o especializado? | **No hay uno que entre en 12 GB y cambie la clase de error.** Entrenar uno es un proyecto aparte. |
| ¿Dejar lo local? | **Para la Voz, sí. Para el resto, no hace falta:** Consultor, Planificador, Verificador y Memoria dan salida estructurada que el autor revisa. |
| ¿Frontier solo en la Voz? | **Sí. La plataforma ya lo permite** (Spec-480: `provider` por rol, `RoleRoutingAdapter`). Falta poco (§3). |

---

## 3. PROPUESTA: la Voz en Claude, el resto local

### 3.1 Qué es

Se suma un perfil **híbrido** en `config/llm_core_definitions.yaml`: todo en `ollama-gemma3-12b` salvo `roles.voz`, con `provider: anthropic`. Pasa a ser el perfil activo en prod y dev. Los perfiles `ollama-gemma3-12b` (todo local) y `anthropic-sonnet5` quedan como alternativa.

### 3.2 Costo estimado

Precios de la API al 2026-09-25, por millón de tokens de entrada/salida: Sonnet 5.5 $2/$10, Opus 5.5 $4/$20, Haiku 4.5 $1/$5 (se verifican en la página oficial antes de activarlo). La Voz de un relato hace 5 llamadas de ~2 800 tokens de entrada y ~1 300 de salida (900 palabras), más lo que piense el modelo.

| Modelo de la Voz | Por relato (5 actos) | Por acto regenerado | 100 relatos |
|---|---|---|---|
| Sonnet 5.5, sin pensar | ≈ US$ 0,10 | ≈ US$ 0,02 | ≈ US$ 10 |
| Sonnet 5.5, pensando poco (`low`) | ≈ US$ 0,15–0,20 | ≈ US$ 0,04 | ≈ US$ 15–20 |
| Opus 5.5 (siempre piensa) | ≈ US$ 0,25–0,40 | ≈ US$ 0,06–0,08 | ≈ US$ 25–40 |

Son estimaciones. S1 las mide con `LLMResponse.input_tokens/output_tokens` y el medidor de `evaluate_voice.py`. Para 1–2 usuarias, el gasto mensual sería de unos pocos dólares. El caché de prompts no ahorra nada acá: el prompt de cada acto es distinto y la parte fija (el system de la Voz) no llega al mínimo cacheable.

### 3.3 Qué hay que hacer (poco, casi todo es configuración)

1. **Perfil híbrido** (`llm_core_definitions.yaml`): el adapter de Ollama para todo y `roles.voz: {provider: anthropic, model: …, num_predict: 2500}`. También `estimated_seconds` propios: la Voz en Claude tarda menos y la Memoria sigue local.
2. **Modelo actual:** el perfil usa `claude-sonnet-5` con `thinking: disabled`. El Sonnet actual es **Sonnet 5.5**, que **rechaza `thinking: disabled`** (400). Para no pensar se manda `{type: "between_tools"}`, o se deja pensar con `effort: low`. El `AnthropicAdapter` tiene que aceptar ese modo, con test en `fake_anthropic.py`.
3. **Si la API falla** (sin crédito, 401, 429, caída): el job de generación falla con un mensaje claro en la UI («No se pudo escribir el relato: revisá el crédito de la IA»). No cae solo al modelo local (decisión D3).
4. **Prompt de la Voz para un modelo grande:** el arnés de hoy está afinado para el 12b, con listas de «no hagas» y oficio muy prescriptivo. Los modelos frontier escriben mejor con menos reglas. Se mide primero con el prompt actual; solo si hace falta, se aliviana en un archivo aparte (`outline_voice*.md` por perfil) para no romper el camino local.
5. **Medir y leer:** `evaluate_voice.py --input input_stories/no_te_detengas_en_el_bosque.yaml --profile <híbrido> --runs 2 --yes`, con las mismas métricas de la Spec-590 (cortadas, diálogo, palabras, repetidas, clichés) y la lectura de la herida, los rasgos y los adelantos.
6. **Deploy:** `.env.prod` con `ANTHROPIC_API_KEY` (fuera de la imagen), `make deploy`, y verificar `/config/active-profile` y `/health`.
7. **Docs:** CLAUDE.md (perfiles, costo) y la memoria.

### 3.4 Lo que no entra

- RAG, grafo, agentes nuevos, embeddings o bases vectoriales (§2.4).
- Entrenar o ajustar un modelo (fine-tuning / RL).
- Mover al frontier el Consultor, el Planificador, el Verificador o la Memoria. Queda como palanca para después si el Planificador resulta ser el cuello (por ejemplo, las frases entre comillas de la escaleta).
- Cambiar la UI, salvo el mensaje de error de la API (§3.3.3).

---

## 4. EL CIERRE: qué pasa con la Spec-590

La 590 tiene S0–S3 commiteados. Con la Voz en Claude, varias de sus defensas (sin diálogo, rasgos en la memoria, primera oración de la premisa) **siguen sirviendo**, porque son datos y no parches del 12b. El diálogo del acto 4 probablemente lo resuelva el modelo frontier sin tocar nada.

**Propuesta:** cerrar la 590 **sin** el ajuste del diálogo. Su S4 queda en actualizar CLAUDE.md y la spec y abrir el PR a `development`. La medición «después» se hace una sola vez, en S1 de esta spec, y compara local contra híbrido.

---

## 5. PLAN

Cuatro slices, en este orden. S0 cierra lo abierto sin gastar. S1 hace el cambio y lo mide una vez. S2 existe solo si la medición lo pide. S3 lleva el cambio a prod y cierra el proyecto.

| Slice | Qué | Toca | Snapshot de prompts | DB | Llamadas pagas | Cierre |
|---|---|---|---|---|---|---|
| S0 | Cerrar la 590 (docs + PR a `development`) | `specs/590…`, `CLAUDE.md`, `llm_core_definitions.yaml` (`estimated_seconds`) | igual | — | 0 | PR mergeado |
| S1 | Sonnet 5.5 en el adapter + perfil híbrido + error claro de la API. **Medición**: 2 relatos del bosque con la Voz en Claude, contra la base local | `anthropic_adapter.py`, `domain/exceptions.py`, `llm_core_definitions.yaml`, `scripts/evaluate_voice.py` (si hace falta) | igual (el prompt no cambia) | — | ≈ US$ 0,50 | Números en §7 + lectura del usuario |
| S2 | Solo si S1 lo pide: prompt de la Voz aliviado para el frontier | `outline_voice*.md` por perfil, `TemplateLoader` | **cambia** (solo el perfil híbrido) | — | ≈ US$ 0,50 | Igual que S1 |
| S3 | Deploy (`.env.prod`, `make deploy`), CLAUDE.md, prueba con las usuarias | `.env.prod` (fuera del repo), `CLAUDE.md`, memoria | igual | recrear prod (esquema de la 590) | — | **Cierre del proyecto** |

**Diseño de los puntos con más código (S1):**

- **Modo sin pensar en Sonnet 5.5.** `thinking` por rol admite un valor nuevo, `between_tools` → `{"type": "between_tools"}` (Sonnet 5.5 rechaza `disabled` con un 400). `disabled` sigue igual para los modelos que lo aceptan. `effort` ya existe (`output_config.effort`). Antes de escribir el código se confirma el contrato en la documentación de la API (skill `claude-api`). Test con `tests/support/fake_anthropic.py`: el request lleva el `thinking` pedido y nunca `temperature`.
- **Perfil `hibrido-sonnet55`**: el bloque `ollama` de `ollama-gemma3-12b` y sus roles tal cual. Cambia solo `roles.voz: {provider: anthropic, model: claude-sonnet-5-5, num_predict: 2500, thinking: between_tools}`, y `estimated_seconds` propios (valores iniciales; manda el historial). `RoleRoutingAdapter` ya existe (Spec-480). En S1 queda activo **solo en dev**; en prod se activa en S3.
- **Error claro (D3).** Una excepción de dominio nueva, `LLMUnavailableError(LLMResponseError)`, con un mensaje en tono coloquial según la causa: sin crédito o clave inválida («La IA que escribe el relato no está disponible: falta crédito o la clave venció. Avisá a quien administra el sitio.»), 429/529 («La IA que escribe el relato está saturada. Probá de nuevo en unos minutos.») y sin conexión. El `AnthropicAdapter` la levanta en lugar del `RuntimeError` de hoy. El texto llega tal cual a `job.error`, que la UI ya muestra (banda de generación, pie, sala). No hay reintento automático ni caída a local. Test del adapter para cada causa y test del job: el job queda `failed` con ese texto.
- **Medición.** `evaluate_voice.py --input input_stories/no_te_detengas_en_el_bosque.yaml --profile hibrido-sonnet55 --runs 2 --out scripts/research/600 --label hibrido`, primero **sin `--yes`** (estima el costo) y con OK del usuario, con `--yes`. Se compara con `scripts/research/590/base/` y con el control de S3 de la 590.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| El 400 de Sonnet 5.5 cambia (otro nombre de modo) | Se confirma con la doc antes (skill `claude-api`) y con 1 llamada chica real antes de medir. |
| La clave vence el 2026-10-30 y prod se queda sin Voz | Mensaje claro (D3) + nota en CLAUDE.md y en la memoria; renovarla antes o crear una sin vencimiento en S3. |
| El arnés afinado para el 12b empeora la prosa de Claude (demasiadas reglas) | Para eso existe S2; se decide leyendo S1. |
| Un relato mezclado por fallar en el medio | D3: el job falla; se regenera el acto (2 llamadas). |

---

## 6. DECISIONES

| # | Decisión | Recomendación |
|---|---|---|
| D1 | ¿Seguimos con el frontier en la Voz y paramos de ajustar el 12b? | ✅ **Sí** (usuario, 2026-09-30). |
| D2 | ¿Qué modelo para la Voz? | ✅ **Sonnet 5.5** (usuario, 2026-09-30). S1 compara con Opus 5.5 en **1** relato (≈ US$ 0,40) solo si Sonnet no convence. |
| D3 | Si la API falla, ¿caer al modelo local o fallar? | ✅ **Fallar con mensaje claro** (usuario, 2026-09-30). Un relato mezclado (actos en Claude y actos en gemma) se nota y confunde; se reintenta regenerando el acto. |
| D4 | ¿Cerramos la 590 sin el ajuste del diálogo? | ✅ **Sí** (usuario, 2026-09-30; §4). |
| D6 | ¿Cómo piensa la Voz en Sonnet 5.5? | ✅ **Adaptativo con effort `low`** (2026-09-30): lo que recomienda la doc de la API para generar contenido; `between_tools` (sin pensar) queda como alternativa. La guía de la API confirmó que Sonnet 5.5 rechaza `disabled` y los parámetros de sampling. El fallback del servidor ante un rechazo no se usa: solo reintenta las categorías `cyber` y `frontier_llm`, que no aplican a un relato. |
| D5 | Crédito en la API: hoy no hay. ¿Cargás crédito (US$ 5–10 alcanzan para medir y varios meses de uso)? | ✅ Crédito cargado y clave nueva en `.env` (alcance: espacio de trabajo predeterminado, vence 2026-10-30), validada con `GET /v1/models` (2026-09-30). |

---

## 7. RESULTADOS

### S1 — La Voz en Sonnet 5.5 · 2026-09-30

Dos relatos de «No te detengas en el bosque» con `hibrido-sonnet55` (Voz en `claude-sonnet-5-5`, adaptativo `low`; Memoria en gemma3:12b), la escaleta del YAML y la extensión nueva (D11, ~2 000 palabras). Evidencia en `scripts/research/600/hibrido/`.

| | Palabras | Oraciones cortadas | Diálogo | Frases repetidas | Clichés |
|---|---|---|---|---|---|
| gemma, base (590 S0) | 1 989 | 53 % | 13,5 | — | — |
| gemma, 590 S3 (primera oración) | 3 190 | 15 % | 10 | 5 | 3 |
| **Sonnet 5.5 (2 relatos)** | **2 191 / 2 207** | **3 % / 4 %** | **0 / 0** | **0 / 0** | **0 / 0** |

- **Costo real: US$ 0,17 los dos (US$ 0,09 por relato)**, por debajo de la estimación (US$ 0,13).
- **Diálogo:** las preguntas del almacenero (entre comillas en la escaleta) salen contadas: «me preguntó si había visto cuántos eran». El problema que la 590 dejó abierto se resolvió sin tocar nada.
- **Continuidad del cuerpo:** la herida del oído vuelve en los actos 3 y 4 en los dos relatos («el zumbido del oído izquierdo», «la oreja goteándome sobre el hombro»).
- **Rasgos:** el termo, las galletitas, la vergüenza de llegar tarde y el silbar al manejar aparecen y vuelven; sin contradicciones.
- **Adelantos:** ninguno; las astas recién en el acto 3.
- **Cierre inventado del acto 4** (visto en la 590 S3): no aparece. El acto 5 recuerda «todavía no salieron del bosque», que viene de la escaleta.
- **Detalles:** dos erratas en el relato 1 («un banquina», «banquinal») y dos frases raras en el 2 («las zapatillas ajenas, por así decirlo», «me inventan excusas en la cara»). Se corrigen al editar.
- **Extensión:** ~2 200 palabras ≈ 17 min a 130 palabras por minuto, en el borde alto del objetivo de la Spec-610 (15 min). Se ajusta con el primer episodio grabado, cuando se sepa el ritmo real de lectura.

**Conclusión:** supera los criterios de éxito de la 590 (cortadas ≤ 26 %, diálogo 0, frases repetidas y clichés sin subir) en todos los puntos. S2 (aliviar el prompt) **no hace falta** según los números; lo decide la lectura del usuario (T1.7).

---

## 8. TASKS

Cada slice cierra con: `make lint`, `make test`, `cd frontend && npm test`, `npx playwright test` en verde (output filtrado), `make dev-status` en verde y la URL de `storymaker.test` con qué mirar.

### S0 — Cerrar la 590 (rama `feat/spec-590-prosa`)
- [x] T0.1 Spec-590: S4 queda en docs + PR (D4 de esta spec); T4.1–T4.3 pasan a S1 de esta spec; estado cerrado.
- [x] T0.2 `estimated_seconds.full_generation` de `ollama-gemma3-12b` 210 → 285 (medido en dev: 268 y 302 s). `regenerate_voz` queda: no hay corridas medidas.
- [x] T0.3 `CLAUDE.md`: qué recibe la Voz (premisa en su primera oración, lo que ya pasó desde la escaleta, cómo está, así es, último párrafo, sin diálogo), la Memoria (`cuerpo`, `asi_es`), el control de repetición (oraciones cortadas, diálogo) y la tabla `narrative_journal`. Mención de la Spec-590 y la 600 en «Specs».
- [x] T0.4 Esta spec se commitea con la 590 (es la que decide su cierre).
- [x] T0.5 Tests en verde, `make dev-status`, commit, push y PR a `development`. El usuario mergea.

### S1 — La Voz en Sonnet 5.5 (rama `feat/spec-600-voz-frontier`, desde `development`)
- [x] T1.1 Confirmar en la doc de la API (skill `claude-api`) el modo sin pensar de Sonnet 5.5 y los errores (402/401/429/529).
- [x] T1.2 `AnthropicAdapter`: `thinking: between_tools`; docstring al día. Test.
- [x] T1.3 `LLMUnavailableError` + mensajes coloquiales por causa en el adapter (402 o 400 «credit balance» → crédito; 401/403 → clave; 429/529/5xx → saturada; red → sin conexión). Tests del adapter y del job (`failed` con el texto, sin llamadas de la Voz al modelo local).
- [x] T1.4 Perfil `hibrido-sonnet55` en `llm_core_definitions.yaml`; `anthropic-sonnet5` pasa a `anthropic-sonnet55` (`claude-sonnet-5-5`, `between_tools`; la Voz adaptativa `low`). Test del resolver (el rol `voz` va a Anthropic, el resto a Ollama). `LLM_PROFILE=hibrido-sonnet55` en `.env` de dev; `/config/active-profile` y `/health` en verde.
- [x] T1.5 Una llamada chica real para confirmar el request antes de medir: HTTP 200, 65/132 tokens, US$ 0,0015, 2,9 s (2026-09-30).
- [x] T1.5b (Spec-610 D11) Extensión para un episodio de ~15 min: `word_range` 100 palabras por evento, 250–500 por acto, desenlace 180–300 (~2 000 palabras); «un párrafo por evento». Se mide ya con Sonnet para no medir dos veces.
- [x] T1.6 Medición (§5): estimar sin `--yes`, OK del usuario, 2 corridas. Resultados en §7: palabras, cortadas, diálogo, repetidas, clichés, costo real (tokens) y tiempo; lectura de la herida, rasgos, adelantos y el cierre inventado del acto 4.
- [ ] T1.7 El usuario lee un relato en `storymaker.test` y decide si hace falta S2.

### S2 — (solo si S1 lo pide) Prompt de la Voz para el frontier
- [ ] T2.1 Definir con el usuario qué se aliviana, a partir de la lectura de S1.
- [ ] T2.2 Plantillas por perfil sin romper el camino local; snapshot nuevo solo para el híbrido.
- [ ] T2.3 1 corrida con OK; resultados en §7.

### S3 — Producción y cierre
- [ ] T3.1 `.env.prod` con `ANTHROPIC_API_KEY` y `LLM_PROFILE=hibrido-sonnet55` (o `active_profile` en el YAML).
- [ ] T3.2 PR `development` → `main`, `make deploy-check`, `make deploy`. La 590 cambió el esquema: DB nueva (datos descartables).
- [ ] T3.3 Verificar `/config/active-profile` (voz en Anthropic) y `/health` en prod; generar un relato.
- [ ] T3.4 `CLAUDE.md` (perfiles, costo, vencimiento de la clave) y memoria.
- [ ] T3.5 Prueba con las usuarias; el proyecto queda cerrado.

---

## Fuentes

- [EQ-Bench Creative Writing v3](https://eqbench.com/creative_writing.html) · [Creative Writing v3, llm-stats](https://llm-stats.com/benchmarks/creative-writing-v3)
- [POLARIS: Guiding Small Models to Write Long Stories (2026)](https://arxiv.org/html/2606.04095v2)
- [The Effects of Incremental Instruction Delivery on Language-Model Creative Writing (2026)](https://arxiv.org/html/2609.33738)
- [Best Local LLMs for Creative Writing 2026, PromptQuorum](https://www.promptquorum.com/local-llms/best-local-llms-for-creative-writing)
- [Long Story Generation via Knowledge Graph and Literary Theory](https://pith.science/paper/2508.03137) · [PlotGraph](https://link.springer.com/chapter/10.1007/978-3-032-31673-8_30) · [GitHub topic: long-form-writing](https://github.com/topics/long-form-writing)
- Precios: tabla de modelos de la documentación de Anthropic (2026-09-25); confirmar en la página oficial de precios antes de activar.

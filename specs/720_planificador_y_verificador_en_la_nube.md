# SPEC-720: El Planificador y el Verificador en la nube

**Fecha:** 2026-10-29
**Tipo:** SDD: configuración de la IA por rol y prompts del asistente («Los actos»)
**Estado:** IMPLEMENT terminado (2026-10-29): S1–S4 hechos; falta el PR. Los personajes que propone la IA siguen en la Spec-730.
**Rama:** `feat/spec-720-actos-en-la-nube` (desde `development`, `b4e9e4e`)
**Extiende:** Spec-480 (proveedor por rol), Spec-530 (asistente), Spec-600 (la Voz en Claude), Spec-650 (relato corto), Spec-680 (recursos gastados), Spec-700 §12 (el próximo paso). Va **antes** de la Spec-710 (lugar por hecho).

---

## ASSUMPTIONS

1. Lo pidió el usuario después de medir el Revisor (Spec-700 §11 S4): con gemma no llegó al umbral y con Sonnet 5.5 sí, con margen. Decidió no comparar otros modelos locales: un 27B no entra en la RTX 3060 de 12 GB y no se espera que alcance a Sonnet en tareas de criterio (Spec-700 §12).
2. Prod usa `hibrido-sonnet55`. Hoy van a Claude la Voz, el Guion y el Revisor; esta spec suma el **Planificador** y el **Verificador**. Las preguntas (el rol `consultor`: Consultor, Forma y Final) y la Memoria **siguen en gemma** (decisión del usuario, 2026-10-29: sin fallas medidas).
3. La Spec-530 (supuesto 2) pedía que todo anduviera con gemma. Ese supuesto **cambia** para estos dos roles: el perfil local (`ollama-gemma3-12b`) sigue andando y sirve para probar gratis, pero la calidad de referencia pasa a ser la de Claude.
4. La IA nunca corre sola (Spec-530), los textos viven en `config/` (Spec-620), el tono es el coloquial (Spec-580) y no hay migraciones.
5. Las corridas pagas se hacen con el costo estimado y el OK del usuario antes de correr. **La clave de la API vence el 2026-10-30**: medir requiere una clave vigente.

---

## OBJECTIVE

Que «Los actos» salgan mejor armados y mejor revisados: el Planificador y el Verificador pasan a Claude Sonnet 5.5 en el perfil de prod. Los arreglos que se hicieron porque gemma no podía se revisan uno por uno. Si la nube no responde, el paso no se traba: lo hace gemma y queda claro en pantalla.

---

## 1. Relevamiento (2026-10-29)

### 1.1 Cómo es hoy (prod, `hibrido-sonnet55`)

| Rol | Modelo | Cuándo | Mediana en prod |
|---|---|---|---|
| Planificador | gemma3:12b | job `plan_outline` (+ `full_generation` sin escaleta) | **321 s** (12 jobs; incluye la revisión y el final de la idea) |
| Verificador | gemma3:12b | job `verify_outline`, y al final de `plan_outline` | 88 s (1 job suelto) |

Los dos usan `generate_structured` con esquema JSON. El ruteo por rol ya existe (`RoleRoutingAdapter`, Spec-480): pasarlos a Claude es, en lo mínimo, `provider: anthropic` en el rol.

### 1.2 Dónde falla gemma (evidencia de otras specs)

| Spec | Qué se vio | Qué se hizo |
|---|---|---|
| 680 S5 (D25) | El Planificador **no evitaba** los recursos gastados aunque se los listara, y quizás se los sugería (ojos y golpes subieron) | Se sacó la lista del prompt del Planificador; el Verificador avisa (`gastado:<id>`). «Si algún día el Planificador pasa a Claude, se puede volver a probar» |
| 650 T2.10 | El Planificador no respetaba la cantidad de hechos del corto (pedía 2–3 / 4–5 / 2 y armó 5 / 7 / 7) | Prompt más firme («Lleva N hechos, no más») y el aviso por regla `muchos_hechos` |
| 630 T6.5 | El Verificador no marcaba un hecho que contradice una regla del acto (0 de 3) si la instrucción iba al final | La instrucción va **primera** y más firme (3 de 3) |
| 710 §9 | Lugares que son cosas («Puerta», «Pared»), nombres de código («casa_susana»), lugares repetidos con otro nombre | Pendiente de la 710 (D9: regla en el prompt + `_lugar()` en el código) |
| 670 (supuesto 1) | Relatos «planos, comunes, sin originalidad»: en parte, el modelo del Planificador | Se atacó por el molde (forma + giro); el modelo quedó para probar aparte |
| 610 §EV | «Con la Voz en Claude, el techo pasa a ser la escaleta, que sigue armando gemma» | Quedó como evolutivo: «la palanca más barata es pasar el Planificador a Claude» |

### 1.3 Costo estimado (tabla de precios de `evaluate_voice.py`: Sonnet 5.5 US$ 2 / 10 por millón de tokens)

| Llamada | Entrada / salida aprox. | Por vez |
|---|---|---|
| Planificador | ~4 000 / ~3 000 tokens | ~US$ 0,04 |
| Verificador | ~3 000 / ~1 000 | ~US$ 0,02 |

Armar y revisar los actos sale **~US$ 0,06** por vez; un relato completo (~US$ 0,09 de la Voz, medido en la Spec-600) pasa a ~US$ 0,15 si se arman los actos una vez. Son estimaciones; la medición (§2 D) las confirma.

---

## 2. Qué se construye

### A. Los dos roles en Claude

`planificador` y `verificador` con `provider: anthropic` y Sonnet 5.5 en `hibrido-sonnet55`. El perfil local no cambia. `estimated_seconds` (`plan_outline`, `verify_outline`) con los valores medidos.

### B. Si la nube no responde, lo hace gemma y se avisa

Decisión del usuario (2026-10-29). Es distinta de la Voz (Spec-600 D3, que falla), porque en «Los actos» la autora siempre puede volver a armarlos y nada queda mezclado en un relato.

- Si la llamada a Claude falla (`LLMUnavailableError`: sin crédito, clave vencida, saturada, sin red), el mismo pedido se repite con gemma, con la config del rol en el perfil local.
- Queda una marca en la historia (como `idea_sin_revisar` de la 700), y «Los actos» muestran una nota de información: «Estos actos los armó la IA de tu compu porque la de la nube no respondió. Cuando vuelva, podés armarlos de nuevo.», con «Armar los actos de nuevo» (con confirmación, como en la 700).
- Lo mismo con la revisión: «Esta revisión la hizo la IA de tu compu…», con «Revisar de nuevo».
- La marca se borra cuando el paso sale bien con Claude, o con «Dejarlo así».

### C. Los arreglos hechos por gemma, revisados

Decisión del usuario: se revisan (2026-10-29). Cada uno se prueba en la medición (D) y se decide con los números:

1. **Recursos gastados al Planificador** (680 D25): volver a pasarle la lista. Si con Claude los evita, el aviso del Verificador queda como red y casi no salta.
2. **Cantidad de hechos** (650): se mide si Claude respeta «N hechos, no más». El aviso `muchos_hechos` queda igual (es una regla sin IA y no molesta si no salta).
3. **Reglas del acto primero en el Verificador** (630): queda igual, no le hace mal a Claude.
4. **Lugares** (710): se mide cuántos objetos o nombres de código salen con Claude, para que la 710 decida cuánto código de limpieza necesita.

### D. Medición antes de activarlo

Decisión del usuario (2026-10-29). Las historias de la copia de prod (las de Vale y las de las chicas), gemma contra Sonnet, 2 corridas, con el costo estimado y el OK antes de correr. Se cuenta, sin IA:

- recursos gastados en los hechos (el detector de la 680);
- actos con más hechos que `hechos_max`;
- lugares que son cosas o nombres de código (los criterios de la 710 §9);
- personajes inventados por la IA (avisos `elenco:` después de la 700);
- avisos de la IA del Verificador por escaleta, y una muestra leída a mano: ¿apuntan a un problema real?;
- el final intencional en el último acto y las decisiones de la autora ubicadas;
- segundos por llamada.

Además, **dos o tres escaletas lado a lado** (gemma | Sonnet) para que el usuario las lea: lo de «planos, comunes» no se cuenta con un script.

---

## 3. Decisiones (a confirmar)

| # | Pregunta | Recomendación |
|---|---|---|
| D1 | ¿Pensar o no? Sonnet 5.5 sin pensar es `between_tools`; pensando poco, `adaptive` + `effort: low` (como la Voz). | **Planificador pensando poco** (armar cinco actos con revelaciones y siembras es planificar), **Verificador sin pensar** (es comparar). Se mide el Planificador de las dos maneras en 3 historias para decidir con números. |
| D2 | ¿Dónde se declara el respaldo local? | En el mismo rol: `respaldo:` con la config de gemma (`provider: ollama`, modelo, temperatura…). Un rol sin `respaldo` falla como hoy. Así no queda nada escondido en el código y la Voz sigue sin respaldo (Spec-600 D3). |
| D3 | La marca de «lo hizo gemma»: ¿por historia o por acto? | **Por historia**, en `direction` (JSON, sin cambio de esquema): `actos_locales` y `revision_local`. Armar los actos es de una sola vez, no por acto. |
| D4 | ¿El Final de la idea (rol `consultor`), que corre adentro de `plan_outline`, también pasa? | **No**: sigue con el rol `consultor` (la decisión fue dejar las preguntas en gemma) y la Spec-690 lo midió bien. |
| D5 | ¿`full_generation` sin escaleta con el respaldo? | Igual que `plan_outline`: si la nube no responde, la Voz tampoco va a responder y el job falla por la Voz (Spec-600 D3). El respaldo solo importa si la caída es justo en esa llamada. No hace falta un caso aparte. |

---

## 4. Commands

```bash
uv run pytest -q                       # todo
cd frontend && npx vitest run          # vistas
cd frontend && npx playwright test     # E2E (Firefox)
uv run python scripts/research/720/medir_actos.py <salida.json> [corridas]   # la medición (D)
make dev-status
```

## 5. Testing Strategy

- Unit: el respaldo (un adapter que falla con `LLMUnavailableError` → la misma llamada va al rol local, con la marca); un rol sin `respaldo` falla como hoy.
- Integración con el mock: `plan_outline` y `verify_outline` con la nube caída terminan bien y dejan la marca; con la nube bien, la borran.
- Snapshots: el del Planificador cambia solo si vuelve la lista de recursos gastados (C1), y a propósito.
- Vitest y E2E de las dos notas de «Los actos».
- `test_hybrid_profile.py`: qué roles van a Claude en el híbrido y que el local no cambia.

## 6. SUCCESS CRITERIA

1. En la medición, Sonnet tiene **menos defectos que gemma** en cada métrica de D, y ninguna empeora. Si alguna empeora, se discute antes de activar.
2. Armar los actos tarda menos que hoy (mediana de 321 s en prod).
3. Con la nube caída, armar y revisar los actos termina bien, con la nota visible, y nunca en silencio.
4. Costo real por armado de actos ≤ US$ 0,10 (el doble de lo estimado, como techo).
5. El usuario leyó las escaletas lado a lado y está de acuerdo en activarlo.

## 7. BOUNDARIES

- **Siempre:** corridas pagas con el costo estimado y el OK; el perfil local sigue andando; los textos en `config/`.
- **Preguntar antes:** activar en prod (es `make deploy`, lo decide el usuario); sacar un aviso por regla.
- **Nunca:** el respaldo para la Voz o el Guion (un relato mezclado se nota, Spec-600 D3); mover las preguntas o la Memoria en esta spec.

## 8. OPEN QUESTIONS

1. D1–D5 (§3).
2. ¿Qué historias entran en la medición? Propuesta: las de la medición de la 710 (las 9 de la copia de dev, que es de prod del 2026-10-22), con «El trabajo de Yadira» seguro. ¿Conviene copiar prod de hoy, que tiene 16?
3. La clave de la API vence mañana: la medición se corre con la clave nueva.

---

## 9. PLAN (2026-10-29)

Decisiones del usuario sobre el SPECIFY (2026-10-29): sí a D1–D5; la medición con prod copiado de hoy y con la clave vigente.

**Restricción de costo (usuario, 2026-10-29):** el saldo de la cuenta puede no alcanzar para US$ 2. La medición se achica a **~US$ 0,60**, con un tope que corta sola, y va **primero** (S1): no depende del resto y se puede correr antes de que venza la clave.

### 9.1 Decisiones nuevas que salieron del relevamiento

| # | Riesgo encontrado | Decisión |
|---|---|---|
| D6 | El respaldo no puede vivir en `generate_structured`: recibe un solo `llm` y no sabe de proveedores. | En el **`RoleRoutingAdapter`**: si el adapter del rol lanza `LLMUnavailableError` y el rol tiene `respaldo:`, repite la llamada con el adapter de ese proveedor y los datos del respaldo (`model`, `temperature`, `num_ctx`, `num_predict`, `stop`), y anota el rol en `respaldos`. Cada job pide su propio proveedor (`LLMFactory.get_provider()`), así que el job lee `respaldos` al terminar. `LLMFactory` suma los proveedores de los respaldos (con todo en Claude, igual arma el ruteo si hay respaldo). |
| D7 | Las marcas (D3 del SPECIFY). | `Direction.actos_locales` y `revision_local` (bool, en el JSON, sin cambio de esquema). `plan_outline` y `full_generation` sin escaleta ponen las dos según `respaldos`; `verify_outline`, la segunda. Si sale bien con Claude, se borran. «Dejarlo así» es `POST …/idea-revisada {paso: "local"}` (borra las dos); el autoguardado de «Tu idea» las conserva. |
| D8 | Sumar `planificador` y `verificador` a lo pago cambia la estimación de `evaluate_voice.py`, que supone 16 200 / 4 750 tokens **por rol**. | **Se cuentan**: la historia por defecto («El monte prohibido») no trae escaleta y sí llama al Planificador. La estimación queda por arriba de lo real; el costo real lo mide `TokenMeter`. (Corregido en S2: el PLAN decía sacarlos.) |
| D9 | La lista de recursos gastados (680 D25) también le llegaría a gemma en el perfil local, donde empeoraba. | Se decide con la medición. Si con Sonnet ayuda, vuelve **para todos** (el local es para probar; supuesto 3) y se restaura tal como era antes de `9fab809` (fragmento `asistente/planificador/recursos_gastados`, `_worn_block`). Si no ayuda, queda afuera y se anota. |
| D10 | «Pensando poco» cuesta más (tokens de pensamiento). | Se arranca **sin pensar** (`between_tools`) en los dos roles. Pensar solo se activa si las 2 historias de la variante muestran una mejora clara. |

### 9.2 S1 — Medición (D del SPECIFY), primero

- `make dev-db` no: **copia de `data/prod/stories.db` a `data/dev/stories.db`** (con backup de la de dev en `data/dev/backup/`). Pisa «Prueba 700» (usuario, 2026-10-29).
- `scripts/research/720/medir_actos.py`: Planificador y Verificador reales (`OutlinePlanner`, `OutlineVerifier`, prompts de `config/`), con la config del rol cambiada en el script por variante. No guarda nada en la base.
  - Historias (6): «El trabajo de Yadira», «Los forasteros», «el engaño del diablo» (largas); «El último cliente», «La criatura del río Paraná», «La conejita» (cortas).
  - Variantes: `gemma` ×2 (gratis), `sonnet` ×1, `sonnet_gastados` ×1 en 3 historias (con la lista, D9), `sonnet_piensa` ×1 en 2 historias (D10).
  - Por corrida, sin IA: recursos gastados en los hechos, actos sobre `hechos_max`, lugares con «_» o compuestos, nombres de «Quiénes están» que no son de la autora (`elenco`), avisos de la IA del Verificador (con el texto), decisiones sin ubicar, segundos, tokens y costo (`TokenMeter` de `evaluate_voice.py`).
  - `--tope 1.0`: corta antes de la próxima llamada paga si el costo real ya pasó el tope. Sin `--yes`, solo estima.
  - Salida en `data/dev/research_720/` (historias reales, fuera de git) y un `.md` con 2 escaletas lado a lado (gemma | Sonnet) para que las lea el usuario.
- **Hecho cuando:** los resultados están en §11, el usuario leyó las escaletas lado a lado y quedan decididos D9 y D10.

### 9.3 S2 — Los dos roles en Claude, con respaldo (A, B, D6–D8)

| Lugar | Cambio |
|---|---|
| `llm_core_definitions.yaml` | `hibrido-sonnet55`: `planificador` y `verificador` con `provider: anthropic`, Sonnet 5.5, `between_tools` (o lo que diga D10), y `respaldo:` con la config de gemma de hoy; `estimated_seconds` con lo medido |
| `RoleRoutingAdapter` | `respaldo` por rol y `respaldos: set[str]` (D6) |
| `LLMFactory` | Los proveedores de los respaldos entran en el ruteo |
| `Direction`, `_direction` | `actos_locales`, `revision_local` (D7) |
| `authoring_jobs` (`plan_outline`, `verify_outline`), `GenerateStoryUseCase._plan` | Ponen o borran las marcas según `llm.respaldos` |
| `evaluate_voice.py` | D8 |
| `test_hybrid_profile.py` | Qué roles van a Claude; el local no cambia; los respaldos son la config de gemma tal cual |

### 9.4 S3 — La nota en «Los actos» (B)

| Lugar | Cambio |
|---|---|
| `_state`, `IdeaRevisadaForm` | `hecho_local: {actos, revision}`; paso `local` |
| `_escaleta_contenido.ejs` | Nota de información: con `actos`, «Estos actos los armó la IA de tu compu porque la de la nube no respondió. Cuando vuelva, podés armarlos de nuevo.» con «Armar los actos de nuevo» (con confirmación, como la 700) y «Dejarlo así»; si solo es `revision`, «La revisión la hizo la IA de tu compu…» con «Revisar de nuevo» y «Dejarlo así» |
| `run_api_mock.py` | Una idea con «SIN CRÉDITO» hace fallar al rol en la nube, como en la 700 |
| Tests | Vitest de las dos notas; E2E: armar con la nube caída → nota → «Dejarlo así» |

### 9.5 S4 — Prompts según la medición y cierre (C)

- D9: la lista de recursos gastados vuelve o queda afuera; si vuelve, se regenera el snapshot `assistant_prompts` a propósito y con el diff revisado.
- C2–C4: se anotan en §11 con los números (`muchos_hechos` y las reglas primero quedan; lo de los lugares pasa a la 710).
- CLAUDE.md (tabla de roles, perfiles, el respaldo, las marcas), memoria y PR a `development`. **Activar en prod** es `make deploy` con la clave nueva en `.env.prod`, y lo decide el usuario.

### 9.6 Slices

1. **S1 — Medición** (paga, ~US$ 0,60 con tope de US$ 1; con OK antes de correr).
2. **S2 — Roles en Claude con respaldo.**
3. **S3 — La nota en «Los actos».**
4. **S4 — Prompts y cierre.**

Cada slice cierra con tests en verde y dev con el cambio (Spec-540 §2.5).

---

## 10. TASKS (2026-10-29)

### S1 — Medición

- **T1.1** Backup de `data/dev/stories.db` en `data/dev/backup/` y copia de `data/prod/stories.db` a dev. **Hecho cuando:** `make dev-status` está en verde y dev muestra las 16 historias de prod.
- **T1.2** `scripts/research/720/medir_actos.py`: variantes por config del rol (en el script), métricas sin IA, `TokenMeter`, `--tope`, `--yes` y salida JSON + `.md` lado a lado. **Hecho cuando:** corre con `--mock` de punta a punta y, sin `--yes`, solo estima.
- **T1.3** Corridas: primero las pagas (`sonnet`, `sonnet_gastados`, `sonnet_piensa`), mientras la clave sigue vigente; después `gemma` ×2. **Hecho cuando:** los resultados y el costo real están en §11; quedan decididos D9 y D10 y el usuario leyó las escaletas lado a lado.

### S2 — Roles en Claude con respaldo

- **T2.1** `RoleRoutingAdapter` con `respaldo` y `respaldos`; `LLMFactory` con los proveedores de los respaldos. **Hecho cuando:** hay tests unitarios (cae al respaldo con `LLMUnavailableError` y lo anota; otro error no cae; un rol sin respaldo falla como hoy).
- **T2.2** `hibrido-sonnet55`: los dos roles en Claude con `respaldo` (gemma de hoy); `estimated_seconds`. `evaluate_voice.py` (D8). **Hecho cuando:** pasa `test_hybrid_profile.py` (roles, local intacto, respaldo = la config de gemma) y `/config/active-profile` lo muestra.
- **T2.3** `Direction.actos_locales` / `revision_local`; los jobs y `_plan` las ponen o las borran. **Hecho cuando:** pasan las integraciones con el mock: nube caída → termina bien con la marca; nube bien → la borra.

### S3 — La nota en «Los actos»

- **T3.1** `_state.hecho_local`, paso `local`. Nota en `_escaleta_contenido.ejs` (actos o revisión). **Hecho cuando:** pasan los Vitest de las dos notas y el de «sin nota».
- **T3.2** `run_api_mock.py` con «SIN CRÉDITO» para los roles en la nube; E2E: armar con la nube caída → nota → «Dejarlo así» → no vuelve al recargar. **Hecho cuando:** el E2E está en verde en Firefox.

### S4 — Prompts y cierre

- **T4.1** D9 según la medición (restaurar `_worn_block` y su fragmento, o anotar por qué no). **Hecho cuando:** el snapshot se regeneró a propósito (si cambió) y está la nota en §11.
- **T4.2** CLAUDE.md, memoria y PR a `development`. **Hecho cuando:** suites completas en verde, `make dev-status` en verde y el PR abierto.

---

## 11. Resultados

### S1 — Medición (2026-10-29)

`scripts/research/720/medir_actos.py` sobre la copia de prod de hoy (16 historias; la base de dev anterior quedó en `data/dev/backup/`). Salida en `data/dev/research_720/` (fuera de git): `gemma.json`, `gemma_resto.json`, `sonnet.json` y `lado_a_lado.md` (Yadira y La criatura del río Paraná, gemma | Sonnet). Seis historias: gemma ×2 (12 escaletas), Sonnet ×1 (6).

| Por escaleta (promedio) | gemma | Sonnet 5.5 |
|---|---|---|
| Respuestas de la autora sin ubicar en ningún acto | **2,6** | **0,5** |
| Lugares compuestos («Casa de Ximena, casa de Yadira») | 1,6 | 0 |
| Actos con más hechos que `hechos_max` (corto) | 0,5 | 0 |
| Personajes que inventó la IA (nombres distintos) | 1,0 (Sofía, Daniela, Lupita…) | 0,3 (Juan, «El doble de Lautaro»: de la historia) |
| Recursos gastados en los hechos | 0,08 (1 de 12) | 0,17 (1 de 6) |
| Avisos de la IA del Verificador | 3,5 | 4,2 |
| Segundos (armar + revisar) | 58 (mediana) | 28 |
| Costo real | gratis | **US$ 0,055** (0,044–0,074) |

- **Avisos de la IA, leídos a mano.** Los de Sonnet apuntan a problemas reales: hilos sueltos («el hombre de la capucha nunca se explica»), algo repetido entre actos («llama a su familia en el acto 3 y de nuevo en el 4»), respuestas de la autora que no están en ningún hecho («lo que Lautaro quiere cuidar no aparece») y sustos que se anuncian antes de llegar. Algunos son largos y unos pocos dicen «está bien» (de más). Dos repiten el aviso de personajes de la regla («Juan no figura en el elenco»). Los de gemma son genéricos («¿podés dar una pista sobre qué le preocupa?»).
- **D9, recursos gastados:** con la lista, el único caso de Sonnet (el perro que aúlla en Yadira) desaparece (0 de 3). **Vuelve la lista** al Planificador, también para el perfil local.
- **D10, pensar:** con «pensando poco», mismo costo y tiempo; Yadira da 8 avisos de la IA en vez de 5. Sin mejora clara: **sin pensar**.
- La salida del Planificador llegó a 3 850 tokens (Yadira): `num_predict` sube a 6000.
- Costo de la medición: **US$ 0,632** (estimado 0,74, tope 1).
- Las 3 últimas corridas de gemma se repitieron (fallaron porque el prompt del Planificador cambió en medio de la corrida); esas ya tienen la lista de recursos gastados.

### S2–S4 (2026-10-29)

- Respaldo en `RoleRoutingAdapter` (D6) y en `LLMFactory`; `hibrido-sonnet55` con los dos roles en Sonnet 5.5 sin pensar y `respaldo` = la config de gemma; `estimated_seconds.plan_outline` 45.
- Marcas `actos_locales` / `revision_local` (D7), con la nota en «Los actos» y «Dejarlo así» (`paso: local`).
- D8 corregido: `evaluate_voice.py` **sí** cuenta el Planificador y el Verificador (la historia por defecto no trae escaleta).
- D9: `_worn_block` y su fragmento vuelven tal como eran antes de `9fab809`; los snapshots del asistente y de los moldes cambian solo en ese bloque.
- `test_hybrid_profile.py`: la escaleta va a Claude y, sin crédito, cae a gemma; la Voz sigue sin respaldo.

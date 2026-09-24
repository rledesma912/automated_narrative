# SPEC-510: Tiempo estimado de generación (EV-6)

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development)
**Estado:** TASKS — pendiente de revisión (SPECIFY y PLAN aprobados 2026-09-24)
**Roadmap:** EV-6 (mostrar cuánto va a tardar antes de generar). Último evolutivo del alcance acordado.

---

## ASSUMPTIONS

1. El problema no es solo el tiempo (~3,7 min por relato con `gemma3:12b`) sino **no saber cuánto falta**: una espera anunciada se tolera mejor que una indefinida.
2. La estimación sale del **historial de jobs** (`generation_job.started_at` / `finished_at`) del mismo tipo y el mismo perfil LLM; sin historial, de un **valor inicial configurable por perfil**. Mejora sola con el uso.
3. Los jobs no guardan hoy con qué perfil corrieron: se agrega en `params` (JSON existente), **sin cambio de esquema**.
4. Tipos de job: `full_generation` (relato completo, 16 llamadas) y `regenerate_voz` (un acto, 1 llamada).
5. Se ignoran otros factores del tiempo (cantidad de entidades, largo de la sinopsis): el margen de «≈» los absorbe. Si el historial muestra mucha dispersión, se revisa en S-final.
6. Escala del proyecto: 1–2 usuarias, un job a la vez por historia. No hace falta nada más elaborado que una mediana.

---

## OBJECTIVE

Que antes de generar se sepa **cuánto va a tardar**, que durante la generación se vea **cuánto falta**, y que al terminar se vea **cuánto tardó**, con números redondeados y honestos (nunca negativos ni falsamente precisos).

**Éxito:** en la galería, la ficha, la sala y el panel de relatos, cada acción que lanza un job muestra «≈ N min»; el banner y la sala muestran «faltan ≈ N min» y lo ajustan con el avance; el aviso final dice «lista en N min»; después de unas pocas generaciones la estimación queda dentro de ±1 min del tiempo real con `gemma3:12b`.

---

## 1. HALLAZGOS

| Hallazgo | Consecuencia |
|---|---|
| `generation_job` tiene `started_at` y `finished_at`; prod y dev hoy **no tienen jobs** (bases recreadas). | Hace falta el valor inicial por perfil; el historial aparece con el uso. |
| `params` del job es JSON libre (`{beat, narrative_id}` en `regenerate_voz`). | El perfil activo se guarda ahí al crear el job, sin tocar el esquema. |
| El payload de los eventos de job (`JobManager._payload`) no incluye `started_at` ni la estimación. | Se agregan `started_at`, `finished_at` y `estimated_seconds` al payload. |
| El banner ya calcula el avance ponderado por etapa (`progressPct` en `generation-banner.js`: acto + peso de la etapa). | El tiempo restante se proyecta con ese mismo avance: no hay que inventar otro. |
| «Generar» / «Reintentar» en la galería y la ficha lanzan el job **directo**; «Regenerar» lleva a la sala con una confirmación («¿Listo para regenerar?»); regenerar un acto usa `hx-confirm`. | La estimación «antes» se muestra junto a esos botones y dentro de las confirmaciones. |

---

## 2. CAMBIOS PROPUESTOS

### 2.1 Estimación (Core)

- **Valor inicial por perfil** en `config/llm_core_definitions.yaml`: `profiles.<perfil>.estimated_seconds: {full_generation: 240, regenerate_voz: 60}` (valores de `gemma3:12b` a medir en S-final). Un perfil sin el bloque usa un default global.
- **Estimador** (servicio en `application`): mediana de la duración (`finished_at − started_at`) de los **últimos 5 jobs `completed`** del mismo `kind` y el mismo perfil. Con menos de 2 muestras, el valor inicial. Devuelve `{seconds, source: "history" | "default", samples}`.
- Al crear un job se guarda `params.profile` y se calcula `estimated_seconds`, que viaja en el payload del job junto con `started_at` y `finished_at`.
- `GET /api/v1/jobs/estimates` → la estimación de los dos tipos con el perfil activo (para mostrarla antes de lanzar).

### 2.2 Antes de lanzar

- Junto a **Generar / Reintentar / Regenerar** (galería y ficha): «≈ 4 min» en texto chico, apagado.
- En la confirmación de la sala («¿Listo para despertar al narrador?» / «¿Listo para regenerar?»): «Tarda ≈ 4 min. Podés cerrar la pestaña: sigue generándose.» (la segunda frase siempre; la primera, si hay estimación).
- Al regenerar un acto (`hx-confirm` del panel de relatos): «¿Regenerar este acto? Tarda ≈ 1 min. Se reemplazará el texto actual.»
- El frontend pide la estimación al Core al renderizar esas páginas (una llamada por página, sin JS nuevo); si el Core no responde, no se muestra nada.

### 2.3 Durante: tiempo restante

En el banner (`data-banner-step`) y en la sala: «Acto 2 de 5 · Narrando — faltan ≈ 3 min».

- **Cálculo** (cliente, con el reloj local y `started_at`): con avance `p` (el de `progressPct`) y tiempo transcurrido `t`:
  - `p < 15 %` → restante = `estimated_seconds − t` (al principio el avance dice poco);
  - `p ≥ 15 %` → proyección del ritmo real `proyectado = t / p`, **mezclada** con la estimación según el avance: `total = (1 − p) · estimado + p · proyectado`. Al principio pesa la estimación; cerca del final, el ritmo real. Así no salta con un acto más lento o más rápido;
  - restante = `total − t` (puede dar ≤ 0 si viene lento → «tardando más de lo habitual»).
- **Redondeo honesto:** ≥ 90 s → «faltan ≈ N min» (redondeo al minuto); 30–90 s → «falta ≈ 1 min»; < 30 s → «falta menos de 1 min»; si ya se pasó de lo proyectado → «tardando más de lo habitual». Nunca negativos, nunca segundos.
- Se recalcula con cada evento del job y cada 15 s (el tick del heartbeat), no cada segundo.

### 2.4 Al terminar

El aviso de terminado del banner y el panel final de la sala: «Lista en 3 min 42 s» (con `finished_at − started_at` del payload). Solo para `completed`.

---

## BOUNDARIES

- **Siempre:** estimación determinística y testeada; UI degradable (sin estimación, todo se ve como hoy).
- **Preguntar antes:** cambios de esquema de DB (no deberían hacer falta); cambiar la ponderación de etapas de `progressPct`.
- **Nunca:** mostrar tiempos negativos o con segundos durante la espera; bloquear el lanzamiento de un job porque falle la estimación; dependencias nuevas.

---

## TESTING

- **Unit (pytest):** estimador (sin historial → default; 1 muestra → default; ≥ 2 → mediana de los últimos 5; filtra por `kind`, perfil y `completed`; ignora jobs sin `started_at`/`finished_at`); config del valor inicial por perfil y default global.
- **API (pytest):** `GET /jobs/estimates` (los dos tipos, fuente `default` e `history`); el job creado guarda `params.profile`; el payload del job trae `started_at`, `finished_at`, `estimated_seconds`.
- **Unit (Vitest):** la función de tiempo restante y su redondeo (tabla de casos: inicio, mitad, pasado de tiempo, `p` = 0, sin estimación); el formateo de «lista en».
- **Vista (Vitest):** los botones y confirmaciones muestran «≈ N min» cuando hay estimación y nada cuando no.
- **E2E (Playwright):** con el LLM mock, generar muestra la estimación antes, «falta…» durante y «Lista en…» al terminar.

---

## SUCCESS CRITERIA

1. Galería, ficha, sala y regenerar acto muestran «≈ N min» antes de lanzar.
2. Banner y sala muestran el tiempo restante redondeado, que baja con el avance y nunca es negativo.
3. El aviso final muestra cuánto tardó.
4. La estimación usa el historial del perfil activo y cae al valor inicial sin historial.
5. Sin cambios de esquema; `make lint`, pytest, Vitest y Playwright en verde.

---

## DECISIONES (2026-09-24)

1. Los valores iniciales se **miden** con `gemma3:12b` en la implementación (un relato completo y un acto), no se adivinan.
2. La confirmación de la sala suma «Podés cerrar la pestaña: sigue generándose».
3. «Al terminar: cuánto tardó» entra en el alcance (§2.4).

---

## PLAN

### Estrategia

Primero el Core (la estimación y los tiempos del job), después la lógica pura del cliente con sus tests, después la UI durante y al terminar (banner y sala), y al final la UI antes de lanzar. Los valores iniciales se miden al final, con todo terminado, y se cargan en el perfil. Cada slice deja todo en verde y va en su propio commit.

### Decisiones técnicas

| Tema | Decisión |
|---|---|
| Valor inicial | `profiles.<perfil>.estimated_seconds: {full_generation, regenerate_voz}` en `llm_core_definitions.yaml`; `settings.estimated_seconds(kind)` lo lee y cae a un default global (`DEFAULT_ESTIMATED_SECONDS = {full_generation: 240, regenerate_voz: 60}` en `config.py`). |
| Historial | `SQLJobRepository.list_finished(kind, limit)`: jobs `completed` con `started_at` y `finished_at`, más nuevos primero. El filtro por perfil (`params.profile`) y el descarte de duraciones < 5 s (corridas con el LLM mock) se hacen en el estimador, en Python: a esta escala alcanza con traer los últimos 50. |
| Estimador | `application/services/job_duration_estimator.py`: `JobDurationEstimator(repo).estimate(kind, profile) -> Estimate(seconds, source, samples)`. Mediana de las últimas 5 duraciones válidas; con menos de 2, el valor inicial. |
| Guardar en el job | `JobManager.start()` agrega `profile` y `estimated_seconds` a `params` al crear el job. Queda fija para ese job (no cambia si en el medio termina otro) y viaja sola en el payload, que ya incluye `params`. |
| Tiempos en el payload | `JobManager._payload` y `JobResponse` suman `started_at`, `finished_at` y `elapsed_seconds` (calculado en el Core al publicar). El cliente usa `elapsed_seconds` más lo que pasó en su reloj desde que lo recibió: no le afecta una diferencia de hora entre máquinas. |
| Endpoint | `GET /api/v1/jobs/estimates` → `{full_generation: {seconds, source, samples}, regenerate_voz: {...}}` con el perfil activo. |
| Lógica del cliente | `public/js/eta.js` (script clásico, patrón UMD: `window.ForgeEta` en el browser, `module.exports` para Vitest): `STAGES` y `progress(job)` (movidos desde `generation-banner.js`, sin cambiar los pesos), `remainingSeconds(estimated, elapsed, p)`, `formatRemaining(s)`, `formatDuration(s)` («3 min 42 s») y `formatEstimate(s)` («≈ 4 min»). Se carga en `<head>` antes del banner. |
| Durante | Banner: `stepText` + « — faltan ≈ N min»; recalcula con cada evento `job_*` y con un `setInterval` de 15 s mientras haya un job corriendo. Sala: pide `GET /jobs/{id}` al conectar (trae `params` y `elapsed_seconds`) y muestra el restante bajo `#status-line` con la misma función. |
| Al terminar | Banner (estado `done`) y panel final de la sala: «Lista en N min M s» con `finished_at − started_at`. |
| Antes de lanzar | Middleware Express `loadEstimates` (una llamada al Core con timeout de 1,5 s → `res.locals.estimates`, `null` si falla), solo en las rutas de galería, ficha, sala y panel de relatos (incluidos los fragmentos HTMX del panel). Un helper EJS `formatEstimate` (el mismo algoritmo que `eta.js`, en TS) arma «≈ N min». |
| Textos | Botones: «≈ 4 min» en `text-xs text-forge-muted` al lado. Confirmación de la sala: «Tarda ≈ 4 min. Podés cerrar la pestaña: sigue generándose.» Regenerar un acto: `hx-confirm="¿Regenerar este acto? Tarda ≈ 1 min. Se reemplazará el texto actual."` |

### S0 — Estimación en el Core

Config del valor inicial, `list_finished`, `JobDurationEstimator`, `params.profile` y `params.estimated_seconds` al crear el job, `started_at`/`finished_at`/`elapsed_seconds` en el payload y en `JobResponse`, y `GET /jobs/estimates`. Tests unitarios y de API.

### S1 — Lógica del cliente

`public/js/eta.js` con `progress` movido desde el banner (sin cambio de comportamiento) y las funciones de tiempo. Tabla de casos en Vitest. El banner pasa a usar `ForgeEta.progress`; los E2E existentes del banner siguen en verde.

### S2 — Durante y al terminar

Tiempo restante en el banner y en la sala; «Lista en…» en el banner y en la sala. Tests de vista y E2E (con el LLM mock).

### S3 — Antes de lanzar

Middleware `loadEstimates`, helper `formatEstimate` y «≈ N min» en galería, ficha, confirmación de la sala (con «Podés cerrar la pestaña…») y regenerar un acto. Tests de vista, del middleware (Core caído → sin estimación, la página carga igual) y E2E.

### S4 — Valores iniciales y cierre

Medir con `gemma3:12b` en una DB temporal un relato completo y una regeneración de acto (~5 min en background). Cargar `estimated_seconds` en los perfiles de Ollama. Docs (`CLAUDE.md`), cierre de la spec, PR a `development`.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Las corridas con el LLM mock (E2E, `--mock`) ensucian el historial con duraciones de milisegundos. | El estimador descarta duraciones < 5 s. |
| Diferencia de hora entre el Core y el browser. | El cliente usa `elapsed_seconds` del Core, no `started_at` contra su reloj. |
| Los pesos de etapa de `progress` no reflejan el tiempo real (la Voz tarda más que el Mapper). | La mezcla con la estimación suaviza el efecto. En S4 se comparan avance y tiempo reales; si difieren mucho, se propone ajustar los pesos (preguntando antes, §BOUNDARIES). |
| Una llamada más al Core por página. | Solo en 4 rutas y con timeout corto; si falla, la página se ve como hoy. |
| Un job que tarda mucho más (Ollama cargando el modelo en frío). | «tardando más de lo habitual» en vez de números; la mediana amortigua un caso aislado en el historial. |

---

## TASKS

Formato: **Acceptance** / **Verify** / **Files**. Checkpoint por slice: `make lint` + `make test` + Vitest (+ Playwright completo desde S1, que toca el banner de todas las páginas) en verde → commit con tu OK.

### S0 — Estimación en el Core

- [ ] **T0.1:** Valor inicial por perfil.
  - Acceptance: `settings.estimated_seconds(kind)` → `profiles.<activo>.estimated_seconds.<kind>`; sin bloque o sin la clave → `DEFAULT_ESTIMATED_SECONDS[kind]` (240 / 60); valor no numérico o ≤ 0 → default.
  - Verify: pytest con un `llm_core_definitions` de prueba (con bloque, sin bloque, valor inválido).
  - Files: `src/config.py`, `tests/unit/test_config_profiles.py`
- [ ] **T0.2:** Historial de jobs terminados.
  - Acceptance: `SQLJobRepository.list_finished(kind, limit=50)` → jobs `completed` de ese `kind` con `started_at` y `finished_at`, del más nuevo al más viejo; excluye `failed`, `cancelled` y los activos.
  - Verify: pytest sobre una DB temporal con jobs de todos los estados y los dos kinds.
  - Files: `src/infrastructure/database/repositories/job_repository.py`, `tests/unit/infrastructure/test_job_repository.py`
- [ ] **T0.3:** `JobDurationEstimator`.
  - Acceptance: `estimate(kind, profile)` → `Estimate(seconds, source, samples)`: mediana (entera, en segundos) de las últimas 5 duraciones válidas del `profile` (`params.profile`); descarta < 5 s y jobs sin perfil; con < 2 válidas → valor inicial con `source="default"` y `samples` = las válidas.
  - Verify: pytest con repo falso (0, 1, 2, 7 muestras; otro perfil; otro kind; duraciones < 5 s; mediana par e impar).
  - Files: `src/application/services/job_duration_estimator.py`, `tests/unit/application/services/test_job_duration_estimator.py`
- [ ] **T0.4:** La estimación viaja en el job.
  - Acceptance: al crear un job, `params` suma `profile` (perfil activo) y `estimated_seconds`, sin pisar `beat`/`narrative_id` de `regenerate_voz`; `JobManager._payload` y `JobResponse` suman `started_at`, `finished_at` (ISO o `null`) y `elapsed_seconds` (entero; `null` si no arrancó; hasta `finished_at` si terminó).
  - Verify: pytest de `JobManager` (params y payload en `job_started` / `job_progress` / `job_done`) y del `GET /jobs/{id}`.
  - Files: `src/application/services/job_manager.py`, `src/presentation/routers/job_router.py`, `src/presentation/schemas/response.py`, `tests/unit/application/services/test_job_manager.py`, `tests/integration/test_job_api.py`
- [ ] **T0.5:** Endpoint de estimaciones.
  - Acceptance: `GET /api/v1/jobs/estimates` → `{full_generation: {seconds, source, samples}, regenerate_voz: {...}}` con el perfil activo; sin historial, `source="default"`.
  - Verify: pytest de API (sin historial; con 2 jobs `completed` del perfil activo sembrados en la DB → `source="history"`).
  - Files: `src/presentation/routers/job_router.py`, `tests/integration/test_job_api.py`
- [ ] **Checkpoint S0:** lint + pytest + Vitest → commit.

### S1 — Lógica del cliente

- [ ] **T1.1:** `eta.js`.
  - Acceptance: `public/js/eta.js` (UMD: `window.ForgeEta` / `module.exports`) con `STAGES` y `progress(job)` idénticos a los del banner actual (pesos y casos: `consolidando` → 1, sin etapa o sin acto → 0,03, tope 0,99); `remainingSeconds(estimated, elapsed, p)` según §2.3 (`p < 0,15` → `estimated − elapsed`; si no, mezcla); `formatRemaining(s)` → «faltan ≈ N min» (≥ 90 s, redondeo al minuto), «falta ≈ 1 min» (30–89 s), «falta menos de 1 min» (1–29 s), «tardando más de lo habitual» (≤ 0), `""` sin estimación; `formatDuration(s)` → «42 s» / «3 min 42 s» / «12 min»; `formatEstimate(s)` → «≈ N min» (mínimo 1).
  - Verify: Vitest con tabla de casos por función (incluidos `p` = 0, `p` = 1, `estimated` nulo, valores negativos y no numéricos).
  - Files: `frontend/public/js/eta.js`, `frontend/tests/unit/public/eta.test.ts`
- [ ] **T1.2:** El banner usa `eta.js`.
  - Acceptance: `eta.js` cargado en `<head>` antes de `generation-banner.js`; el banner llama a `ForgeEta.progress` y ya no define `STAGES`/`progressPct` propios; sin cambios visibles.
  - Verify: Vitest de vista del layout (orden de scripts) + E2E existentes (`generation-banner.spec.ts`) en verde.
  - Files: `frontend/src/views/partials/layout.ejs`, `frontend/public/js/generation-banner.js`
- [ ] **Checkpoint S1:** lint + pytest + Vitest + Playwright → commit.

### S2 — Durante y al terminar

- [ ] **T2.1:** Restante en el banner.
  - Acceptance: en estado `running`, `data-banner-step` = `stepText(job)` + « — » + `formatRemaining(...)` (sin sufijo si no hay estimación); el tiempo transcurrido es `elapsed_seconds` del último evento más el tiempo local desde que llegó; se recalcula en cada evento y cada 15 s mientras haya un job `running` (el intervalo se limpia cuando no queda ninguno).
  - Verify: E2E con el LLM mock y un job con `estimated_seconds` grande (el texto contiene «faltan ≈»).
  - Files: `frontend/public/js/generation-banner.js`, `frontend/tests/e2e/generation-banner.spec.ts`
- [ ] **T2.2:** «Lista en…» en el banner.
  - Acceptance: estado `done` → «<título> está lista · en 3 min 42 s» (`formatDuration(finished_at − started_at)`); sin tiempos, como hoy.
  - Verify: E2E (el aviso final contiene «está lista · en»).
  - Files: `frontend/src/views/partials/generation_banner.ejs`, `frontend/public/js/generation-banner.js`, `frontend/tests/e2e/generation-banner.spec.ts`
- [ ] **T2.3:** Restante y duración en la sala.
  - Acceptance: al conectar a un job, la sala pide `GET /api/v1/jobs/{id}` y muestra bajo `#status-line` el restante (misma función y el mismo tick de 15 s que el banner); en `done`, el panel final dice «Lista en …».
  - Verify: E2E en `streaming-room.spec.ts` (restante visible durante; «Lista en» al final).
  - Files: `frontend/public/js/streaming-room.js`, `frontend/src/views/streaming-room.ejs`, `frontend/src/views/partials/streaming_done_panel.ejs`, `frontend/tests/e2e/streaming-room.spec.ts`
- [ ] **Checkpoint S2:** lint + pytest + Vitest + Playwright → commit.

### S3 — Antes de lanzar

- [ ] **T3.1:** Middleware y helper.
  - Acceptance: `loadEstimates` pide `GET /api/v1/jobs/estimates` (timeout 1,5 s) y deja `res.locals.estimates` (`null` si falla o tarda, sin romper la página); `formatEstimate(seconds)` en TS con el mismo resultado que `eta.js` (disponible en las vistas vía `res.locals`); montado solo en las rutas de galería, ficha, sala y relatos (página y fragmentos del panel).
  - Verify: Vitest del middleware (Core ok, Core con error, Core lento) y test de paridad `formatEstimate` TS ↔ `eta.js`.
  - Files: `frontend/src/middleware/estimates.middleware.ts`, `frontend/src/services/core_api.service.ts`, `frontend/src/utils/eta.ts`, `frontend/src/routes/index.ts`, `frontend/tests/unit/middleware/estimates.middleware.test.ts`
- [ ] **T3.2:** Textos en las vistas.
  - Acceptance: «≈ N min» junto a Generar / Reintentar / Regenerar (galería y ficha); en la sala, «Tarda ≈ N min. Podés cerrar la pestaña: sigue generándose.» (la segunda frase siempre); regenerar un acto: `hx-confirm` con «Tarda ≈ N min.»; sin `estimates`, todo como hoy salvo la frase de la pestaña.
  - Verify: Vitest de vistas (galería, ficha, sala, panel de relatos) con y sin `estimates`.
  - Files: `frontend/src/views/gallery.ejs`, `frontend/src/views/historia.ejs`, `frontend/src/views/streaming-room.ejs`, `frontend/src/views/partials/relato_panel.ejs`, tests de vista correspondientes
- [ ] **T3.3:** E2E.
  - Acceptance: la galería muestra «≈ … min» junto a «Generar»; la sala de una historia completada muestra la confirmación con la estimación y la frase de la pestaña.
  - Verify: `npx playwright test --reporter=line` completo.
  - Files: `frontend/tests/e2e/estimates.spec.ts`
- [ ] **Checkpoint S3:** lint + pytest + Vitest + Playwright → commit.

### S4 — Valores iniciales y cierre

- [ ] **T4.1:** Medir con `gemma3:12b`.
  - Acceptance: en una DB temporal, un relato completo y una regeneración de acto por la API de jobs (script en el scratchpad, en background); duración de cada uno y, para el relato completo, el avance de `progress` contra el tiempo real por etapa. Resultados en la sección RESULTADOS de esta spec.
  - Verify: script de medición.
  - Files: `specs/510_tiempo_estimado_generacion.md`
- [ ] **T4.2:** Cargar los valores iniciales.
  - Acceptance: `estimated_seconds` con los valores medidos (redondeados a 10 s) en `ollama-gemma3-12b` y en el híbrido `ollama-gemma3-12b-voz-sonnet5`; si el avance por etapa difiere mucho del tiempo real, se propone el ajuste de pesos (sin aplicarlo sin OK).
  - Verify: `GET /jobs/estimates` en dev devuelve los valores medidos con `source="default"`.
  - Files: `config/llm_core_definitions.yaml`
- [ ] **T4.3:** Docs y cierre.
  - Acceptance: `CLAUDE.md` (endpoint, `estimated_seconds` del perfil, `eta.js`), spec en DONE, roadmap EV-6 hecho.
  - Verify: lectura.
  - Files: `CLAUDE.md`, `specs/510_tiempo_estimado_generacion.md`
- [ ] **Checkpoint S4:** suite completa en verde → commit → push → PR `feat/ev-6-tiempo-estimado` → `development`.

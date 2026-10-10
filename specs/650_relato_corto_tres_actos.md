# SPEC-650: Relato corto en 3 actos (~7 minutos)

**Fecha:** 2026-10-09
**Tipo:** SDD — épica (estructura del relato: asistente, pipeline, UI y video)
**Estado:** SPECIFY ✅ (D1–D8 con lo recomendado, OK del usuario 2026-10-09) · PLAN ✅ (D9–D11 con lo recomendado, OK 2026-10-09) · TASKS ✅ (OK 2026-10-09) · S1 ✅ (2026-10-09) · S2 ✅ · S3 ✅ (2026-10-10)
**Rama:** `feat/spec-650-relato-corto-tres-actos` (desde `development`, `cafb508`)
**Extiende:** Spec-530 (asistente y escaleta), Spec-560 (puente y receta del efecto), Spec-590/610 D11 (extensión por acto), Spec-610 (paquete para el video), Spec-620 (textos fuera del código).

---

## ASSUMPTIONS

1. El relato de 5 actos (~15 min, ~2 000 palabras) **sigue igual** y sigue siendo el de siempre: el corto es una opción más. Sus prompts no cambian (los snapshots de 5 actos quedan idénticos).
2. «7 minutos» se mide como hoy en el video: palabras ÷ **150 palabras/min** (`config/video/lectura.yaml`, medido con el TTS de `audiogen`). 7 min ≈ **1 050 palabras**.
3. La máxima del pipeline vale igual: la Voz recibe la escaleta del acto y listas cortas; la estructura (qué pasa en cada acto) se resuelve antes, en el Planificador y la UI.
4. Sin migraciones (memoria del proyecto): si hace falta guardar algo nuevo, va donde no cambia el esquema o se actualiza `init_db()` y se recrea la DB. Las historias existentes son descartables.
5. Todo texto nuevo (prompts, nombres de actos, mensajes) vive en `config/` (Spec-620); la UI en tono coloquial (Spec-580), sin «inicio / nudo / desenlace» en pantalla.
6. Perfil activo `hibrido-sonnet55`. Medir con `--yes` cuesta plata real (un relato corto debería costar ~US$ 0,05; se avisa antes).

---

## OBJECTIVE

Que quien arma una historia pueda elegir un **relato corto**: 3 actos (inicio, nudo, desenlace) que leídos en voz alta duran **~7 minutos** (6–8 min aceptable), con el mismo asistente (Tu idea → Preguntas → Los actos → El relato) y la misma calidad de prosa que el de 5 actos.

**Para qué:** episodios más cortos, generación más rápida y barata (8 llamadas en vez de 12 con escaleta: Planificador + Verificador + 3 × Voz/Memoria).

---

## 1. Qué asume hoy «5 actos» (relevamiento 2026-10-09)

| Capa | Dónde | Qué está fijo |
|---|---|---|
| Config | `config/llm_beats_definition.yaml` | Una sola estructura `5_actos`: label, intención, intensidad, `entity_exposure`, reglas de revelación |
| Config | `authoring_options.yaml` (`efectos[].planificador`) | Las recetas nombran actos: «nada se muestra entero antes del acto 3», «se revela en el acto 4» |
| Config | `workshop_criteria.yaml` | `acto: 1..5` en los 9 criterios |
| Prompts | `authoring_planner*.md`, `authoring_verifier_system.md`, `fragments/asistente/objetivo.md` | «en 5 actos», «actos 2–5» |
| Dominio | `models.py` | `ActOutline.number le=5`, `reveal_act le=5` (alcanza para 3) |
| Core | `planner.py`, `outline_narrator.py` | `NUM_ACTS = 5`; `word_range` (250–500 por acto, desenlace 180–300) |
| Core | `verifier.py`, `planner.py:187` | `reveal_act <= 5`; final forzado en el acto 5 |
| Core | `beat_spec_repository.py`, `narrator_config_sanitizer.py`, `mock_structured.py`, `yaml_exporter.py` | `range(1, 6)`, `len == 5` |
| API | `authoring_router.py:164`, `schemas/authoring.py` | `1 <= n <= 5` |
| DB | `act_outline.number CHECK 1..5` | alcanza para 3 |
| Front | `utils/actos.ts`, `_acto.ejs`, `streaming-room.ejs` (`TOTAL_BEATS = 5`), `eta.js`, `generation-banner.js`, `escaleta.ejs`, `home.ejs`, `asistente.js` | nombres de los 5 actos, «cinco actos», `|| 5` |
| Video | `biblia_visual.yaml` (10–15 momentos), `lectura.yaml` (episodio 12–17 min) | un relato de 7 min no pasa los chequeos del paquete |

**Conclusión:** la cantidad de actos tiene que salir de **la estructura de la historia**, no de una constante. El grueso del trabajo es sacar los «5» fijos; lo nuevo es poco (una estructura más en config y una opción en «Tu idea»).

---

## 2. Diseño propuesto

### 2.1 Estructuras en config (fuente única)

`config/llm_beats_definition.yaml` pasa de una lista `macro_beats` a `estructuras`:

```yaml
estructuras:
  largo:            # la de hoy, sin cambios de contenido
    label: "Largo · 5 actos · unos 15 minutos"
    actos: [ …los 5 macro_beats actuales… ]
  corto:
    label: "Corto · 3 actos · unos 7 minutos"
    actos:
      - id: 1   # inicio
        label: "Inicio"            # lo ve la Voz/Planificador
        nombre_ui: "Cómo empieza"  # lo ve la persona
        palabras: [260, 320]
        intensity: baja
        intent: "normalidad, regla o advertencia y una inquietud sutil"
        entity_exposure: { nunca: senales, insinuada: senales, progresiva: senales, explicita: presencia }
      - id: 2   # nudo: transgresión + escalada + clímax
        label: "Nudo"
        nombre_ui: "Qué pasa"
        palabras: [480, 560]
        intensity: alta
        intent: "romper la regla, el hecho anómalo, la explicación que no alcanza y el enfrentamiento"
        entity_exposure: { nunca: senales_intensas, insinuada: revelacion, progresiva: presencia_directa, explicita: confrontacion }
      - id: 3   # desenlace
        label: "Desenlace"
        nombre_ui: "Cómo termina"
        palabras: [200, 260]
        intensity: baja
        intent: "salida o alejamiento, la marca que queda, cierre corto"
        entity_exposure: { nunca: segun_acto_final, insinuada: huella, progresiva: huella, explicita: huella }
```

Total: **940–1 140 palabras = 6,3–7,6 min** a 150 palabras/min.

- `word_range(act)` lee `palabras` del acto en el corto. En el largo se mantiene la regla actual proporcional a los hechos (para no mover su snapshot ni su prosa).
- `NUM_ACTS` desaparece: `len(estructura.actos)` y «acto final» = el último.
- La cantidad de hechos por acto en el corto se acota en el Planificador (p. ej. 2–3 en el inicio, 4–5 en el nudo, 2 en el desenlace), porque la Voz escribe «un párrafo por evento».

### 2.2 Dónde se guarda

~~En `Direction` (JSON)~~ → **reemplazado por D9 (§6.1)**: columna `story.structure` (`largo` | `corto`), con un endpoint propio para cambiarla. Viaja en `export-yaml` / `import-yaml` (`estructura: corto`; sin la clave = largo).

### 2.3 UI

- **«Tu idea»:** una pregunta más con dos opciones (`.opcion-forge`): «¿Qué tan largo?» → «Corto · unos 7 minutos» / «Largo · unos 15 minutos». Default largo.
- **«Los actos»:** 3 tarjetas con «Cómo empieza · Qué pasa · Cómo termina»; los textos «cinco actos» pasan a decir la cantidad real o a no nombrarla.
- **Sala, banda, ETA:** `total_beats` del job (ya viaja en los eventos) en vez de `5` fijo; nombres de actos desde el Core (no repetidos en `actos.ts`, `_acto.ejs` y la sala).
- **Galería / «El relato»:** una etiqueta «Corto» en la tarjeta y en la versión.
- **Estimaciones (Spec-510):** el job guarda `length` en `params`; la mediana se calcula por tipo **y** largo.

### 2.4 Asistente (Consultor, Planificador, Verificador)

- Planificador y Verificador reciben la estructura (cantidad de actos, label e intención de cada uno) desde config; los prompts dejan de decir «5 actos» (`{num_actos}` y la lista de actos como fragmento).
- Recetas del efecto: `planificador` pasa a tener una variante por estructura (`planificador: {largo: …, corto: …}`).
- Criterios del taller: `acto` pasa a `acto: {largo: N, corto: M}` (p. ej. meta e inquietud → 1; en juego, vulnerabilidad, transgresión, historia secreta, descubrimiento → 2; reacción y final → 3).
- «Lo que todavía no se cuenta» / `reveal_act` y el final forzado se validan contra el último acto de la estructura.

### 2.5 Cambiar el largo con la historia ya armada

Si ya hay escaleta, cambiar el largo la deja inservible (los actos no se corresponden). Propuesta: se puede cambiar siempre, con una confirmación («Vas a tener que armar los actos de nuevo»); al confirmar se borran los actos y se vuelve a «Los actos» vacío. Lo respondido en «Preguntas» se conserva.

### 2.6 Paquete para el video (Spec-610)

`lectura.yaml` y `biblia_visual.yaml` pasan a tener rangos por largo: corto → episodio **6–8 min**, **6–9 momentos** (largo: 12–17 min y 10–15, como hoy). El chequeo de cobertura por acto ya recorre los actos que haya.

---

## 3. Decisiones para el usuario

| # | Decisión | Recomendación |
|---|---|---|
| D1 | Dónde se elige el largo | En «Tu idea», opción «¿Qué tan largo?», default **largo** |
| D2 | Palabras del corto | Rangos fijos por acto 260–320 / 480–560 / 200–260 (≈ 1 050, 7 min a 150 ppm), no proporcionales a los hechos |
| D3 | Dónde cae el clímax | Al final del **nudo** (acto 2); el desenlace es salida + marca + cierre |
| D4 | Nombres en pantalla | «Cómo empieza · Qué pasa · Cómo termina» (sin «nudo»/«desenlace», Spec-580) |
| D5 | Preguntas del taller en el corto | Las mismas 9, con su acto remapeado (no se recorta el taller) |
| D6 | Cambiar el largo con actos armados | Se permite con confirmación y se rearma la escaleta |
| D7 | Video para el corto | Sí, con rangos por largo (6–8 min, 6–9 momentos) |
| D8 | El largo actual | Sin cambios de contenido ni de prosa: snapshots de 5 actos idénticos |

---

## 4. Slices (para el PLAN)

- **S1 — Estructura parametrizada, sin cambio visible.** `estructuras` en config con `largo` = lo de hoy; servicio `Estructura` (lee config; cantidad, labels, palabras, exposición); fuera `NUM_ACTS` y los `range(1, 6)` / `<= 5` del Core, API y mocks. *Verificación:* toda la suite en verde y snapshots sin cambios.
- **S2 — El corto en el Core.** `Direction.length`, estructura `corto`, `word_range` por config, prompts del Planificador/Verificador con `{num_actos}`, recetas y criterios por largo, export/import YAML, mock de 3 actos. *Verificación:* snapshots nuevos `*_corto` (con test de secciones), CLI `generate --input <yaml corto> --mock` produce 3 actos.
- **S3 — UI.** Opción en «Tu idea», 3 tarjetas en «Los actos», sala/banda/ETA por `total_beats`, nombres desde el Core, confirmación al cambiar el largo, etiqueta «Corto». *Verificación:* Vitest + E2E de un recorrido corto con el mock; maqueta antes (memoria «UI con maquetas primero») solo si cambia algo más que la opción.
- **S4 — Video corto.** Rangos por largo en `lectura.yaml` / `biblia_visual.yaml`; chequeos del `VideoScriptBuilder`. *Verificación:* tests del builder con un relato de 3 actos.
- **S5 — Medición real y validación.** `scripts/evaluate_voice.py --input <historia corta> --runs 2 --yes` (con aviso de costo) y lectura de una versión en dev por las usuarias (una versión + 1–2 preguntas).

---

## 5. SUCCESS CRITERIA

1. Una historia corta se arma y se escribe de punta a punta en la web: 3 actos en «Los actos», 3 en la sala, 3 en «El relato».
2. Generar un corto con escaleta = **8 llamadas** (Planificador + Verificador + 3 Voz + 3 Memoria); regenerar un acto = 2.
3. Medido con `evaluate_voice.py` (2 corridas, Sonnet 5.5): total **900–1 200 palabras** (6–8 min a 150 ppm) en las dos, y cada acto dentro de ±15 % de su rango.
4. Las métricas de prosa del corto (clichés, comparaciones, oraciones cortadas, diálogo) no son peores que las del largo en la misma historia.
5. El largo no cambia: snapshots `pipeline/voice/assistant/video_prompts.json` idénticos.
6. No queda un «5» de actos fijo en `src/`, `frontend/` ni en los prompts (test que lo busque, al estilo del guardián de la Spec-620).
7. `make lint`, `make test`, Vitest y Playwright en verde; dev (`make dev-status`) con el cambio.
8. Las usuarias leen un relato corto en dev y les parece completo (no «cortado»).

## BOUNDARIES

- **Always:** estructura y textos en `config/`; el largo nunca se decide solo (lo elige la persona); tests en verde por checkpoint.
- **Ask first:** cualquier cambio de esquema de DB; tocar la prosa o los prompts del largo; corridas pagas.
- **Never:** reescribir la prosa para que «entre» en los minutos (si se pasa, se muestra; Spec-610 ya avisa la duración); migraciones.

## OPEN QUESTIONS

- ¿El corto necesita un límite de personajes o lugares (menos material para 1 000 palabras)? Propuesta: no al principio; se ve en S5.
- ¿Más adelante otras duraciones (p. ej. 4 actos, 10 min)? El diseño de §2.1 lo permite con solo agregar una estructura; fuera de alcance.

---

## 6. PLAN (revisión detallada, 2026-10-09)

Recorrí cada lugar donde el código depende de la cantidad de actos. Abajo: qué se toca, **qué bug podría aparecer** y cómo se evita. El principio: **una sola fuente** (`Estructura`, leída de config) y **el largo de la historia viaja explícito**, nunca se deduce de una constante ni se pisa por un autoguardado.

### 6.1 Decisiones nuevas que salieron de la revisión

| # | Riesgo encontrado | Decisión recomendada |
|---|---|---|
| D9 | Guardar el largo dentro de `direction` es frágil: el autoguardado de «Tu idea» rearma `Direction` entero desde el formulario (`_direction(form)`), así que una pestaña vieja o un campo que falte **volvería la historia a «largo» en silencio**. | Columna propia `story.structure TEXT NOT NULL DEFAULT 'largo' CHECK (structure IN ('largo','corto'))` y endpoint propio `PUT …/structure`. El autoguardado de «Tu idea» **no la toca**. Costo: cambio de esquema → `make dev-db` y, en prod, el procedimiento de siempre (export-yaml con el código viejo, DB nueva, import-yaml). |
| D10 | Al cambiar de largo, las **reglas ancladas** a los actos 4 y 5 quedarían huérfanas (nadie las ve ni le llegan a la Voz), y las ancladas a 2 y 3 caerían en actos que significan otra cosa. | Se reubican con una tabla en config: largo→corto `1→1, 2→2, 3→2, 4→3, 5→3`; corto→largo `1→1, 2→3, 3→5`. La confirmación lo dice («Las reglas de cada acto pasan al acto equivalente»). |
| D11 | Una versión del relato escrita con el **otro largo** (p. ej. 5 actos y ahora la historia es corta): «Regenerar el acto 2» usaría el acto 2 de la escaleta nueva con la prosa vieja → texto que no encaja, **sin error**. | Regenerar un acto exige que la versión tenga tantos actos como la estructura actual; si no, 422 (en S3 se vio que el front lee todo 409 como «la IA está trabajando») con un mensaje coloquial («Esta versión es de cuando la historia era larga: escribila de nuevo para regenerar actos»). La versión vieja se sigue leyendo, corrigiendo y descargando. |

### 6.2 Núcleo: `Estructura` (S1)

**Nuevo** `src/application/services/structure.py` (`Estructura`, `ActoDef`): carga `estructuras` de `llm_beats_definition.yaml` validado con Pydantic al arrancar (falla temprano si falta un campo). API:
`for_story(story)`, `get(id)`, `for_act_count(n)` (para relatos ya guardados), `.ids`, `.num_actos`, `.acto(n)`, `.ultimo`, `.revela_secreto` (acto que reemplaza a `NUM_ACTS - 1`), `.palabras(n)`, `.remap_from(otra)`.

| Lugar | Cambio | Bug que se evita |
|---|---|---|
| `beat_spec_repository.py` | `get_by_id(beat, reveal, structure="largo")`, `exposure_for(…, structure)`; `num_beats` se va. El fallback sin YAML (`range(1, 6)`) pasa a error claro | La Voz del corto recibiendo intención/exposición del acto 2 **del largo** |
| `prompt_builder.py` | `get_beat_info(beat, reveal, structure)`; sin `num_beats` global | Idem; un `num_beats` de instancia que no sabe de qué historia es |
| `generate_story_use_case.py:60` | `len(story.outline) != estructura.num_actos` | Hoy re-planifica si la escaleta no tiene 5: con 3 actos **re-planificaría siempre y borraría lo editado** por la persona |
| `streaming_service.py:62`, `generation.py:74`, `orchestrator.py:67` | `total_beats` desde la estructura de la historia | Sala y banda diciendo «Acto 1 de 5» |
| `planner.py` | `NUM_ACTS` → estructura; `Escaleta` validada contra N con una clase por estructura (`escaleta_model(n)`, cacheada; el esquema JSON no cambia); `_acts_block` recorre los actos de la estructura; `se_revela_en <= ultimo` | El validador rechazaría toda escaleta de 3 actos → `LLMStructuredOutputError` |
| `verifier.py:201` | `reveal_act <= ultimo` | Avisos «sin revelación» falsos o faltantes |
| `outline_narrator.py` | `act.number == estructura.ultimo` para el final del autor; `word_range(act, estructura)`: largo = regla actual, corto = `palabras` del config | El final del autor ignorado en el corto (se aplicaba solo en el acto 5) |
| `regenerate_beat_voz_use_case.py`, `generation.py` | D11 + `total_beats` | Regenerar con escaleta de otro largo |
| `authoring_router.py:164` y endpoints con `number`/`act` (outline, warnings, characters, scenarios) | Validan `1..num_actos` de la historia → 404/422 | Una pestaña vieja autoguardando el acto 4 de una historia corta **crearía una fila de acto 4**, la escaleta quedaría con 4 actos y la generación re-planificaría borrando lo editado |
| `schemas/authoring.py`, `models.py` (`le=5`) | Quedan como tope técnico (5 = máximo de cualquier estructura); el control fino es por historia | — |
| `mock_structured.py` | Arma tantos actos como pida el prompt (lee la estructura del contexto) | Tests con mock que pasan con 5 y fallan con 3 |
| `repetition_check.last_version_findings` | Solo si los `macro_beat` guardados son de la estructura actual | Avisos del acto 2 de un relato largo mandados a la Voz del acto 2 del corto |
| `narrator_config_sanitizer.py`, `yaml_loader`, `yaml_exporter` (YAML viejos de 5 actos) | Sin cambio: un YAML viejo es largo | — |

**Precaución de S1:** en S1 solo existe `largo`. Toda la suite y los **4 snapshots tienen que quedar byte a byte iguales**; si un snapshot cambia en S1, hay un bug.

### 6.3 El corto en el Core (S2)

| Lugar | Cambio | Precaución |
|---|---|---|
| `connection.py` `init_db()` | Columna `structure` (D9) | `make dev-db`; `story_repository` la lee con el mismo patrón tolerante que `direction` (`"structure" in keys`) para que una DB vieja no rompa al leer |
| `models.py` `Story.structure` | `Literal["largo","corto"] = "largo"` | Un valor desconocido falla al validar, no se cuela |
| `story_repository.py` | insert / select / `update_structure()` **en una transacción** que: cambia la columna, borra `act_outline`, `macro_beat` y `narrative_journal`, reubica las reglas (D10). Respeta el 409 con job activo | Que quede a medias (estructura nueva con actos viejos) |
| `authoring_router.py` | `POST /stories` acepta `structure`; `PUT …/structure`; `_state` devuelve `structure` y la lista de actos (número, nombre) | `update_direction` no la toca (test explícito) |
| `llm_beats_definition.yaml` | Estructura `corto` (§2.1) + `revela_secreto` y la tabla de reubicación | Validada al cargar |
| `authoring_options.yaml` | `planificador: {largo, corto}` en cada efecto | `catalog.effect_recipe` toma la de la estructura; falta una → error al arrancar, no en medio de un job |
| `workshop_criteria.yaml` | `acto: {largo: N, corto: M}` | `Criterion.for_story()` resuelve; test de que los 9 tienen las dos |
| Prompts del Planificador/Verificador y `objetivo.md` | «5 actos» → `{num_actos}`; `se_guarda: "" en el acto {ultimo}`; el objetivo con las palabras de la estructura | Verificado: los dos `_system.md` no tienen `{`/`}` (hoy se cargan sin `format`), así que se puede pasar a `format` sin romper nada |
| `core_messages.yaml` | `escaleta_sin_actos` con `{total}` | — |
| `fragments/README.md` | Documentar los huecos nuevos | — |
| CLI / YAML | `estructura:` en export/import; `generate --input` la respeta | Round-trip probado con las dos |
| `job_duration_estimator.py` + perfiles | La mediana se calcula por tipo, perfil **y** estructura (`params.structure`; jobs viejos = largo); default del corto = `full_generation_corto` si está en el perfil, si no 3/5 del largo; `GET /jobs/estimates?structure=` | Que los relatos cortos bajen la estimación de los largos (y al revés) |

**Snapshots nuevos:** `pipeline_prompts_corto.json`, `voice_prompts_corto.json`, `assistant_prompts_corto.json`, cada uno con su test de secciones (incluye: 3 actos en el Planificador, rangos 260–320/480–560/200–260 en la Voz, final del autor en el acto 3, receta del efecto del corto).

### 6.4 UI (S3)

| Lugar | Cambio | Precaución |
|---|---|---|
| `utils/actos.ts` | **Única** fuente de nombres en el front: `ESTRUCTURAS = {largo: […5], corto: [«Cómo empieza», «Qué pasa», «Cómo termina»]}`, `nombresPara(structure)` y `estructuraPorCantidad(n)` (para relatos guardados), en `app.locals` | Un Vitest compara contra `nombre_ui` de `config/llm_beats_definition.yaml`: si alguien cambia uno solo, falla |
| `_acto.ejs` (`NOMBRES`, `INTENSIDAD`, `a.number < 5`) | Desde `actos.ts` / `_state.structure`; «no es el último» = `a.number < total` | El campo «se descubre en» del acto 3 del corto ofreciendo actos 4 y 5 |
| `streaming-room.ejs` (lista de 5 y `TOTAL_BEATS = 5`), `streaming-room.js` | Lista y total desde la estructura de la historia | La sala esperando 5 actos y no cerrando nunca («beatCount === TOTAL_BEATS») |
| `eta.js`, `generation-banner.js`, `generation-guard.js` (`|| 5`) | Sin fallback 5: el job trae `total_beats` **desde que se crea** (el Core lo fija al crear el job) | «Acto 1 de 5» en los primeros segundos de un corto |
| `relatos.controller.ts` / `splitActs` | Nombres por cantidad de actos de la versión | Versión corta con el acto 2 llamado «Se complica» |
| «Tu idea» (`direccion.ejs`, `asistente.js`) | Opción «¿Qué tan largo?» fuera del formulario de autoguardado; si hay actos armados, `ForgeConfirm.ask` y `PUT …/structure`; después recarga la página | Doble clic / cambio sin confirmar; nada de `confirm()` nativo (test `no-native-dialogs`) |
| Textos «cinco actos» (`escaleta.ejs`, `_escaleta_contenido.ejs`, `taller.ejs`, `asistente.js`, `home.ejs`) | «los actos» o la cantidad real | `sin-jerga.view.test.ts` sigue verde |
| Galería y «El relato» | Chip «Corto» (`.chip-forge--info`) | `gramatica-visual.view.test.ts` |
| Fixtures `tests/fixtures/asistente/` | Regenerar con `UPDATE_FIXTURES=1` **y revisar el diff** | — |

Maqueta: la opción nueva es una `.opcion-forge` más, como las de «¿Cómo lo cuenta?»; propongo no hacer maqueta salvo que la pidas.

### 6.5 Video (S4)

| Lugar | Cambio | Precaución |
|---|---|---|
| `biblia_visual.yaml`, `lectura.yaml`, `video/config.py` | `momentos`, `videos` y `episodio_minutos` por estructura (`largo` igual que hoy; `corto`: 6–9 momentos, 1–2 videos, 6–8 min). Se valida que cada estructura cumpla «videos ≤ momentos» | — |
| `script_builder.py`, `prompts.py`, `video_service` | Rangos según la estructura del relato (por su cantidad de actos) | Un paquete corto rechazado por tener menos de 10 momentos (reintento pago que vuelve a fallar) |
| `video_router` `GET /video/lectura` y `GET …/video-script` | Devuelven el episodio de la estructura del relato | — |
| «Corregir el relato» y `tiempos.js` (= `timing.py`) | Regla de duración con el rango del relato; casos compartidos nuevos en `tests/fixtures/video/` para el corto | Un relato corto marcado siempre «muy corto» |

### 6.6 Tests que hoy asumen 5 (para que no se rompan sin querer)

23 archivos de `tests/` usan 5 actos (fixtures de escaleta, `range(1, 6)`, mocks). En S1 **no se cambian**: si pasan sin tocarlos, el refactor es fiel. En S2 se suman casos del corto al lado (no reemplazos). Además:
- **Guardián** `tests/unit/test_sin_cinco_actos_fijos.py`: recorre `src/` con `ast` y falla con `range(1, 6)`, comparaciones con `5` sobre números de acto o `NUM_ACTS`; en el front, un Vitest busca `|| 5` y `< 5` en vistas y `public/js`.
- **Recorrido E2E corto** (Playwright, LLM mock): crear corto → preguntas → armar actos (3) → escribir → sala con 3 → «El relato» con 3 nombres correctos → regenerar acto 2 → cambiar a largo con confirmación → 5 actos vacíos y reglas reubicadas.
- **Integración:** `PUT outline/4` en una historia corta → 404; regenerar acto de una versión del otro largo → 422; autoguardado de «Tu idea» no cambia `structure`.

### 6.7 Orden, checkpoints y riesgos

1. **S1** (refactor puro) → checkpoint: suite + snapshots idénticos + dev igual que antes.
2. **S2** (Core corto) → checkpoint: snapshots nuevos, CLI `generate --input <corto> --mock` con 3 actos, `make dev-db`.
3. **S3** (UI) → checkpoint: Vitest + E2E corto y los E2E de siempre; URL en `storymaker.test` para probar.
4. **S4** (video) → checkpoint: paquete de un corto con el mock.
5. **S5** (medición paga con aviso de costo + lectura de las usuarias).

| Riesgo | Mitigación |
|---|---|
| El refactor cambia sin querer la prosa del largo | S1 aislado; snapshots byte a byte |
| La Voz no respeta las ~1 050 palabras | Rangos por acto + tope de hechos en el Planificador; se mide en S5; si se pasa, se ajustan rangos (no se recorta la prosa) |
| Una recarga de uvicorn corta un job de dev | Avisar antes de editar `src/` con un job corriendo |
| Prod con DB vieja tras el deploy (D9) | El pase a prod sigue el procedimiento de cambio de esquema; `make deploy-check` antes |
| Planificador local (gemma) con 3 actos peor que con 5 | Se ve en S2 con una corrida local (gratis) antes de la UI |

**Línea base (2026-10-09, `cafb508`):** `pytest` 887 passed.

---

## 7. TASKS

Cada tarea cierra con su verificación. Checkpoint de slice = `make lint` + `make test` (+ Vitest/Playwright desde S3) en verde + `make dev-status` + URL para mirar.

### S1 — Estructura parametrizada, sin cambio visible · ✅ 2026-10-09

- **T1.1** `llm_beats_definition.yaml`: `macro_beats` → `estructuras.largo.actos` (contenido idéntico) + `revela_secreto: 4` + `nombre_ui` por acto. *Verif.:* el YAML carga; diff solo de forma.
- **T1.2** `structure.py` (`Estructura`, `ActoDef`, carga validada, `for_story`, `get`, `for_act_count`, `ultimo`, `revela_secreto`) + tests unitarios (estructura desconocida → error; YAML incompleto → error al cargar).
- **T1.3** `BeatSpecRepository` y `PromptBuilder` con `structure` (default `largo`); fuera `num_beats` y el fallback `range(1, 6)`. *Verif.:* `test_beat_spec_repository`, `test_beat_reveal_rules` sin cambios.
- **T1.4** `Story.structure` en el **dominio** (default `largo`, todavía sin columna) para que todo pueda preguntar por la historia.
- **T1.5** Core: `generate_story_use_case`, `streaming_service`, `generation.py`, `orchestrator`, `planner` (`escaleta_model(n)`, `_acts_block`, `se_revela_en`), `verifier`, `outline_narrator` (`ultimo`, `word_range(act, estructura)`), `mock_structured` (cantidad de actos según el prompt/estructura).
- **T1.6** Endpoints con número de acto validan `1..num_actos` de la historia (`authoring_router`: outline, warnings, characters, scenarios).
- **T1.7** `total_beats` fijado al crear el job (`job_router` / `JobManager.submit`).
- **T1.8** Guardián `test_sin_cinco_actos_fijos.py` (ast sobre `src/`).
- **Checkpoint S1:** 887+ tests sin tocar los existentes; `git diff --stat tests/fixtures/snapshots` vacío; dev igual que antes.
- **Resultado S1:** pytest 898 ✅ (887 + 11 nuevos), Vitest 383 ✅, Playwright 67 ✅ (3 skipped, como siempre), lint ✅, snapshots sin cambios, esquema JSON de la escaleta idéntico (comparado con el de `cafb508`), `make dev-status` ✅. El guardián detecta 14 casos en el código de `cafb508` y ninguno en el nuevo.
  Tests existentes que **sí** se tocaron, porque probaban la interfaz que cambió: `test_beat_spec_repository.py` (formato del YAML; el fallback de 5 actos vacíos sin YAML pasó a error), los dobles de `test_job_manager.py` / `test_streaming_service.py` (imitaban `prompt_builder.num_beats`), `recording_llm.py` (le pasa el prompt al mock, que cuenta los actos de ahí) y `PERMITIDOS` del guardián de la Spec-620 (errores de carga del YAML). El video sigue con la estructura larga hasta S4.

### S2 — El corto en el Core · ✅ 2026-10-10

- **T2.1** `init_db()`: columna `story.structure` con CHECK; `story_repository` insert/select tolerante/`update_structure()` transaccional (columna + borra actos, `macro_beat`, memoria + reubica reglas, D10). Tests de integración del repo.
- **T2.2** Config: estructura `corto` (§2.1) con `nombre_ui`, `palabras`, `revela_secreto: 2`, tabla de reubicación; validación al cargar.
- **T2.3** `authoring_options.yaml` (`planificador: {largo, corto}`) y `workshop_criteria.yaml` (`acto: {largo, corto}`) + `catalog`/`Criterion.for_story`; test de que todo efecto y criterio tiene las dos.
- **T2.4** Prompts: `{num_actos}` / `{ultimo}` en Planificador, Verificador, `objetivo.md`; `core_messages.yaml`; `fragments/README.md`. *Verif.:* snapshots del largo idénticos.
- **T2.5** API: `POST /stories` con `structure`; `PUT …/structure` (409 con job activo); `_state` con `structure` y actos; test de que `PUT …/direction` no cambia `structure`.
- **T2.6** D11 en la API (422 + mensaje en `core_messages.yaml`) y `last_version_findings` solo con la misma estructura.
- **T2.7** Estimaciones por estructura (`params.structure`, `JobDurationEstimator`, `GET /jobs/estimates?structure=`, `full_generation_corto` opcional).
- **T2.8** YAML: `estructura:` en export/import + CLI `generate --input`; round-trip de las dos.
- **T2.9** Snapshots `*_corto.json` con sus tests de secciones.
- **T2.10** Corrida local gratis (gemma, `--mock` no) del Planificador con una historia corta: ¿arma 3 actos sanos?
- **Checkpoint S2:** suite verde; `make dev-db`; `uv run python -m src generate --input <corto.yaml> --mock` → 3 actos.
- **Resultado S2:** pytest 934 ✅ (snapshots del largo idénticos; 3 nuevos del corto: `voice_prompts_corto`, `assistant_prompts_corto`, `pipeline_prompts_corto` = 8 llamadas), lint ✅, `make dev-db` (antes: copia de la DB y export-yaml de las 2 historias de dev, reimportadas como borradores), API de dev probada a mano (crear corto, acto 4 → 404, cambiar a largo, estimación), CLI `generate --input <corto> --mock` → 3 actos.
  **Encontrado al leer los snapshots** (ningún assert lo agarraba): «LOS 5 ACTOS», `"numero": 1 a 5` y «de 3 a 5 hechos» en `authoring_planner.md`, y «ACTO N DE 5» en `outline_voice.md`. Arreglados con `{num_actos}`, `{hechos_por_acto}` y `{total}`; el guardián ahora revisa también los prompts.
  **Encontrado en la corrida local (T2.10, gemma):** el Planificador no respeta la cantidad de hechos del corto (pidió 2–3 / 4–5 / 2 y armó 5 / 7 / 7). Se hizo: (1) el prompt lo pide más firme («Lleva N hechos, no más», «ni uno más: es un relato de unos 7 minutos») → bajó a 4 / 6 / 7; (2) aviso por regla `muchos_hechos` en «Los actos» (Verificador, ignorable) con el tope `hechos_max` de cada acto: la persona decide qué junta o saca, no se corrige solo; (3) el desenlace pasa a 2 o 3 hechos (absorbe el «qué hace después» del largo; las palabras de D2 no cambian). El acto 3 de «No te detengas en el bosque» sigue con 7 porque copia el final que escribió la autora (≈ 7 momentos): es su decisión y el aviso se lo muestra.

### S3 — UI · ✅ 2026-10-10

- **T3.1** `utils/actos.ts` (estructuras, `nombresPara`, `estructuraPorCantidad`) en `app.locals` + Vitest contra el YAML.
- **T3.2** `_acto.ejs`, `escaleta.ejs`, `_escaleta_contenido.ejs`, `taller.ejs`, `home.ejs`, `asistente.js`: nombres, intensidad y «último acto» por estructura; fuera «cinco».
- **T3.3** Sala (`streaming-room.ejs/js`), `eta.js`, `generation-banner.js`, `generation-guard.js`: total desde la historia/job, sin `|| 5`.
- **T3.4** `relatos.controller` / `splitActs`: nombres por cantidad de actos.
- **T3.5** «Tu idea»: «¿Qué tan largo?» fuera del autoguardado; `ForgeConfirm.ask` si hay actos; `PUT …/structure`; recarga.
- **T3.6** Chip «Corto» en galería y «El relato».
- **T3.7** Vitest guardián (`|| 5`, `< 5`); fixtures `UPDATE_FIXTURES=1` revisando el diff; E2E del recorrido corto (§6.6).
- **Checkpoint S3:** Vitest + Playwright completos; URL en `storymaker.test`.
- **Resultado S3:** Vitest 389 ✅, Playwright 71 ✅ (3 skipped; nuevo `relato-corto.spec.ts`, 4 casos, también con `--repeat-each=3`), pytest 934 ✅, lint y `tsc` ✅, `make dev-status` ✅. Referencias HTML del asistente (largo): idénticas salvo el JSON del estado embebido (que ahora trae `structure` y `structure_acts`). Guardián del front (`sin-cinco-actos.view.test.ts`): 16 casos en el front de `9d60c27`, ninguno ahora; «nudo» suma a la jerga prohibida.
  **Encontrado en S3:** (1) el front lee todo 409 como «la IA está trabajando»: D11 pasa a **422** (Core + Corregir muestra el motivo); además el panel del relato y Corregir **no ofrecen «Regenerar»** en una versión del otro largo y lo explican con una nota. (2) «≈ N min» antes de lanzar salía del largo: `GET /jobs/estimates?story_id=` (el Core resuelve el largo; el middleware lo pasa). (3) Cambiar el largo justo después de que se guardara «Tu idea» mostraba «Guardado» antes de tiempo (lo agarró el E2E): se vuelve a marcar pendiente después de descargar lo pendiente. (4) Si eligen el largo mientras la historia se está creando, se aplica apenas existe.
  **Aparte:** Vitest a veces se cae con *segmentation fault* / «Worker exited unexpectedly» (≈ 1 de 8 corridas), también con el front de `9d60c27`: es del entorno, no de estos cambios.

### S4 — Video

- **T4.1** Rangos por estructura en `biblia_visual.yaml`, `lectura.yaml`, `video/config.py` (validados).
- **T4.2** `script_builder`, `prompts`, `video_router` (`/video/lectura` y `…/video-script` con el episodio del relato).
- **T4.3** `timing.py` / `tiempos.js` en «Corregir» con el rango del relato + casos compartidos del corto.
- **Checkpoint S4:** paquete de un corto con el mock pasa los chequeos.

### S5 — Medición y validación

- **T5.1** `evaluate_voice.py --input <corto> --runs 2 --yes` (aviso de costo antes) → criterios 3 y 4 del §5; evidencia en `scripts/research/650/`.
- **T5.2** Una versión corta en dev para las usuarias + 1–2 preguntas.
- **T5.3** CLAUDE.md, memoria y PR a `development`.

# SPEC-750: tres largos y el relato de 35 minutos

**Fecha:** 2026-11-06
**Tipo:** SDD: estructuras del relato (config), dominio y base, asistente (UI), video
**Estado:** PLAN (SPECIFY cerrada: D1–D4 decididas por el usuario el 2026-11-06). Falta el OK para TASKS. Sin código.
**Rama:** `feat/spec-750-tres-largos` (desde `origin/development`)
**Extiende:** Spec-650 (relato corto; las estructuras salen de config), Spec-670 (moldes: intenciones por largo), Spec-610 (duración del episodio), Spec-740 D1 (un perfil por largo).

---

## ASSUMPTIONS

1. Lo pidió el usuario el 2026-11-06: una **tercera duración**. El largo de hoy (5 actos, ~15 min) pasa a llamarse **«Media»** y aparece un **largo nuevo de ~35 minutos**.
2. **Los actos son la dinámica del relato, no su largo** (decisión del usuario, D2): la larga tiene **los mismos 5 actos de Freytag** que la Media («Cómo empieza · Se complica · El peor momento · Qué hace después · Cómo termina»). Lo que crece es **cuántos hechos (beats) tiene cada acto** y cuántas palabras se escriben por acto.
3. Se lee en voz alta a 150 palabras por minuto (`config/video/lectura.yaml`): 35 min ≈ **5 250 palabras**, unas 2,1 veces la Media (~2 500).
4. Prod escribe con GPT-5.6 Sol (`openai-sol`, Spec-740 D10), con un límite de US$ 5 por mes en OpenAI.
5. Se trabaja en dev; prod solo con OK del usuario.

## OBJECTIVE

Que se pueda elegir entre **Corto (~7 min), Media (~15 min) y Larga (~35 min)**. La larga sale con el mismo método: escaleta por acto, la Voz acto por acto y la memoria entre actos; los mismos 5 actos que la Media, cada uno con más hechos y más texto.

**Éxito:**
- Un relato largo leído en voz alta dura entre 30 y 38 minutos.
- No repite más que una Media (el control de repetición, medido por cada mil palabras, no empeora).
- Las historias de hoy siguen igual: las de 5 actos se ven como «Media» y no pierden nada.

---

## 1. Relevamiento (2026-11-06)

Lo que ya ayuda: desde la Spec-650 los actos, sus nombres, palabras y hechos salen de `config/llm_beats_definition.yaml` (`estructuras`). Como la larga tiene los mismos actos que la Media, `act_outline.number` (1–5) **no cambia**, y las intenciones de los moldes por acto se pueden reusar.

Lo que hay que cambiar:

| Dónde | Hoy | Problema |
|---|---|---|
| `story.structure` | `CHECK (structure IN ('largo', 'corto'))` | Un tercer valor no entra. En SQLite **un CHECK no se cambia con ALTER**: hay que reconstruir la tabla |
| El largo de una **versión** del relato | Se **deduce de cuántos actos tiene**: `estructuraPorCantidad` (`frontend/src/utils/actos.ts`) y `estructura_del_relato` (`video/config.py`) | Media y Larga tienen 5 actos: ya no se puede deducir. La versión tiene que **guardar su largo** |
| `StructureId` (Python), `Estructura` (TS) | `"largo" \| "corto"` | Suma el tercero |
| Extensión de cada acto | Media: `word_range` proporcional a los hechos (250–500, desenlace 180–300; constantes en `outline_narrator.py`); Corto: `palabras` fijas por acto | La larga necesita su rango (`palabras` por acto, como el corto) |
| Hechos por acto | Media sin tope por config; Corto: `hechos_max` | La larga necesita más hechos y su `hechos_max` |
| `config/moldes/formas.yaml`, `authoring_options.yaml` | Intenciones y recetas por largo (`largo`, `corto`); `acto: {largo, corto}` en los giros | Se renombra `largo` → `medio` y la larga **reusa** las de 5 actos (ver C1) |
| `reubicar_desde` | Cómo se mueven las reglas al cambiar de largo | Media ↔ Larga es 1:1 (mismos actos); solo suman los mapeos con el corto |
| `config/video/` | Episodio de 12–17 min y el corto de 6–8 | Falta el rango de la larga y sus momentos de pantalla |
| Voz | `num_predict` 2 500 | Un acto de ~1 300 palabras son ~2 100 tokens: subir a ~3 500 en la larga |
| Planificador | `num_predict` 6 000 (hasta 3 850 tokens medidos) | Con el doble de hechos, subir a ~9 000 |
| Control de repetición | Umbrales **por acto** (comparaciones desde la 2.ª, enumeraciones desde la 3.ª, oraciones cortadas desde el 25 %) | Con actos de 2,5 veces el texto marcaría de más: pasar a umbrales por cada N palabras |
| Memoria | `MAX_MOTIFS = 30`, rasgos hasta 12 | Más texto por acto: medir si alcanza |
| `LLM_PROFILE_<LARGO>` (Spec-740) | Una variable por id de estructura | Con el nuevo id, una más |
| Exportar YAML | Solo escribe `estructura` si **no** es `largo`; al importar, sin la clave = `largo` | Clave para decidir los ids (D1) |

---

## 2. Parte A: los ids y los datos

**Propuesta: renombrar los ids a lo que se ve**: `corto` / `medio` / `largo`.
- Las historias de 5 actos pasan de `largo` a `medio` en la misma reconstrucción de la tabla que exige el CHECK, así que no hay un paso extra.
- Exportar YAML nunca escribió `estructura: largo`, porque lo omitía. Al importar, «sin la clave» pasa a ser `medio`, y los YAML viejos siguen siendo Media.
- `LLM_PROFILE_LARGO` pasa a significar la larga nueva; la Media usa `LLM_PROFILE_MEDIO`.
- Alternativa descartada (ver D1): dejar `largo` = Media y llamar al nuevo `extenso`. Evita renombrar, pero deja para siempre en el código un `largo` que en pantalla dice «Media».

**La reconstrucción de `story`:** en `init_db()`, si el `sql` de la tabla en `sqlite_master` tiene el CHECK viejo, se reconstruye siguiendo el procedimiento de SQLite: `foreign_keys` apagado, tabla nueva, copiar (con `largo` → `medio`), borrar, renombrar y `foreign_key_check`, todo en una transacción. Es idempotente y se prueba con una **copia de la base de prod**. Ojo: `DROP TABLE story` con las FK prendidas borraría en cascada todo lo demás.

**El largo de cada versión:** `generated_narrative.structure` (columna nueva, `ALTER TABLE … ADD COLUMN`, sin reconstruir). Se guarda al consolidar el relato con el largo de la historia en ese momento. Las versiones viejas quedan en `NULL` y se leen como hoy, por cantidad de actos (3 = corto, 5 = medio), porque antes de esta spec no existía la larga. El front y el video leen ese campo en vez de contar actos.

## 3. Parte B: la larga de 35 minutos

**Los mismos 5 actos, con más hechos y más texto** (D2). Propuesta de partida, a ajustar en la medición:

| # | Acto | Palabras | Hechos (máx.) | Media hoy |
|---|---|---|---|---|
| 1 | Cómo empieza | 800–950 | 6 | 250–500 |
| 2 | Se complica | 1 100–1 250 | 8 | 250–500 |
| 3 | El peor momento | 1 200–1 350 | 9 | 250–500 |
| 4 | Qué hace después | 1 100–1 250 | 8 | 250–500 |
| 5 | Cómo termina | 450–550 | 4 | 180–300 |

Total: 4 650 a 5 350 palabras. Los modelos escriben cerca del techo (Spec-650 S5), así que lo real queda en unos 34–36 min. Un párrafo por hecho como hoy, así que más hechos es más historia, no la misma estirada. La intención, la intensidad, la exposición de la amenaza y el acto de la revelación son **los de la Media**.

Lo que hay que cuidar con actos más largos:
- **Que tengan material:** el Planificador tiene que armar hechos distintos, no variaciones del mismo; el Verificador ya avisa hechos repetidos dentro del acto.
- **Que la Voz no se repita dentro del acto:** hoy la memoria y «no repetir» trabajan entre actos. Un acto de 1 300 palabras es más largo que un relato corto entero; en la medición se mira la repetición dentro de cada acto.

## 4. Parte C: lo que cambia alrededor

- **C1. Moldes y efectos:** la larga reusa las intenciones por acto de la Media (mismos actos). En config, `largo` → `medio` en `formas.yaml` y `authoring_options.yaml`, y la larga apunta a las de `medio` (sin copiar el texto). Si la medición muestra que algún acto largo necesita otra intención, se escribe aparte.
- **C2. Voz, Planificador y Memoria:** más tokens para la Voz (~3 500) y el Planificador (~9 000) en la larga; la Memoria se mide en §5.
- **C3. Control de repetición:** los umbrales por acto pasan a ser por cada N palabras (para la Media y el corto da lo mismo que hoy), así la larga no marca de más.
- **C4. La pantalla:** «¿Qué tan largo?» con tres opciones y su tiempo («Larga · 5 actos · unos 35 minutos»); la galería y «El relato» muestran el largo de cada versión (de `generated_narrative.structure`); el tiempo estimado sale del historial (Spec-510).
- **C5. Video:** la larga es **un solo episodio** (D4): rango de 30–38 min en `lectura.yaml` y su cantidad de momentos en `biblia_visual.yaml` (`por_estructura.largo`).
- **C6. Costo y tiempo:** las mismas 10 llamadas que la Media (5 Voces y 5 Memorias, más el armado), pero con más texto: ~US$ 0,30–0,55 con Sol (estimado, sin medir). Con el límite de US$ 5, unos 9 a 15 relatos largos por mes.

## 5. Medición (antes de prod)

Con «El monte prohibido» en dev, **solo con OK del usuario porque cuesta**: dos largas completas, en minutos de lectura, repetición por cada mil palabras (dentro del acto y entre actos), costo y tiempo, más la lectura del usuario. Si los actos largos repiten o se estiran, se prueba ajustar hechos y palabras por acto.

## 6. Decisiones

| # | Pregunta | Estado |
|---|---|---|
| D1 | Ids: ¿renombrar a `corto` / `medio` / `largo` o dejar `largo` = Media y sumar `extenso`? | **Decidido: renombrar** (A), aprovechando la reconstrucción que el CHECK exige igual |
| D2 | ¿Cuántos actos tiene la larga? | **Decidido (usuario, 2026-11-06): 5, los de Freytag.** Los actos son la dinámica del relato; el largo crece con más hechos por acto |
| D3 | ¿«Media» y «Larga» en femenino («la historia media»)? ¿O «Mediano» / «Largo» como «Corto»? | **Decidido: «Corto», «Media» y «Larga»** |
| D4 | Video: ¿la larga es un episodio o dos? | **Decidido: un episodio** (30–38 min); la cantidad de momentos de pantalla se fija en PLAN |
| D5 | ¿Se habilita la larga en prod con el límite de US$ 5? | Primero medir (§5); después decidir el límite |

## 7. Boundaries

- **Siempre:** las historias de hoy se conservan; la reconstrucción de la tabla se prueba antes con una copia de prod; la larga tiene los mismos actos que la Media; nada asume una cantidad fija de actos.
- **Preguntar antes:** correr la medición (cuesta); tocar prod; cambiar el límite de gasto.
- **Nunca:** generar la larga en una sola llamada; deducir el largo de una versión nueva por su cantidad de actos; borrar o reescribir relatos ya escritos.

---

## 8. PLAN

Cinco slices de código y uno de medición. Cada uno se commitea por separado y cierra con los tests en verde y dev mostrando el cambio (Spec-540 §2.5). Ninguno corre un relato de verdad: eso queda para S6.

### S1. Renombrar `largo` → `medio` (sin la larga todavía)

Al terminar, todo se ve y funciona igual que hoy, salvo que en pantalla la de 5 actos dice «Media».

- **Base (`connection.py`, `init_db()`):**
  - `story.structure` pasa a `CHECK (structure IN ('corto','medio','largo'))` con default `'medio'`.
  - Si el `sql` de `story` en `sqlite_master` tiene el CHECK viejo, se reconstruye la tabla:
    1. `PRAGMA foreign_keys=OFF`, fuera de la transacción.
    2. `BEGIN`.
    3. `CREATE TABLE story_new` con el CHECK nuevo.
    4. `INSERT … SELECT`, con `CASE structure WHEN 'largo' THEN 'medio' ELSE structure END`.
    5. `DROP TABLE story`, `ALTER TABLE story_new RENAME TO story` y volver a crear sus índices.
    6. `PRAGMA foreign_key_check` vacío.
    7. `COMMIT` y `foreign_keys=ON`.
  - En la misma transacción, `generation_job.params` cambia `"structure": "largo"` por `"medio"`. Si no, el estimador de tiempos (Spec-510) tomaría los jobs viejos como si fueran de la larga.
- **Dominio y API:**
  - `StructureId = Literal["corto","medio","largo"]` y `DEFAULT_STRUCTURE = "medio"`.
  - Los defaults de `models.py`, `story_dto.py`, `orchestrator.py`, `job_router.py`, `schemas/authoring.py` y `schemas/response.py`, y la lectura de `story_repository.py:728`.
- **YAML:**
  - El exportador omite `estructura` cuando es `medio`.
  - El importador toma `medio` cuando no viene la clave.
  - Una `estructura: largo` sí se importa como larga, porque nunca se exportó ninguna.
- **Config:** la clave `largo` pasa a `medio` en estos archivos:
  - `llm_beats_definition.yaml`: `estructuras` y `reubicar_desde`, con el `label` «Media · 5 actos · unos 15 minutos».
  - `moldes/formas.yaml`, `authoring_options.yaml` y `workshop_criteria.yaml`.
  - `video/lectura.yaml` y `video/biblia_visual.yaml`. El default del video es el de `DEFAULT_STRUCTURE`, así que pasa solo.
- **Perfil por largo:** `LLM_PROFILE_MEDIO`. `.env` y `.env.prod` no tienen `LLM_PROFILE_LARGO` activo, así que no hay nada que migrar. Se actualiza el comentario.
- **Front:** `Estructura` en `actos.ts`, `asistente.js` (305/314/326), `direccion.ejs` (20/85), los fixtures (`estado.json`, `escaleta.html`, `taller.html`) y los E2E de `relato-corto` y `largo-apagado`.
- **Tests:**
  - Se renombra `largo` → `medio` en los 22 archivos que lo usan.
  - Test nuevo: la reconstrucción sobre una base con el esquema viejo. Conserva las historias y todas sus filas hijas (FK), pasa `largo` → `medio`, toca los `params` de los jobs y, si se corre dos veces, no cambia nada.
- **Prueba con datos reales:** copia de `data/prod/stories.db` en el scratchpad. Se corre `init_db()` y se comparan los conteos por tabla antes y después.
- **Checkpoint:**
  - Dev con una copia de prod (`data/dev/` se respalda antes).
  - Las historias de 5 actos dicen «Media».
  - «Tu idea» ofrece Corto y Media.

### S2. La larga en config y en el pipeline

- **`llm_beats_definition.yaml`, `estructuras.largo`:**
  - `label` «Larga · 5 actos · unos 35 minutos» y `palabras_total` «5.250».
  - Por acto, `palabras` y `hechos` / `hechos_max` de la tabla de §3, con los `hechos_por_acto` de cada acto.
  - Lo mismo que la Media: `label`, `nombre_ui`, `intent`, `intensity` y `entity_exposure`, con `revela_secreto: 4` y `personajes_nuevos_max: 2`.
  - `reubicar_desde`: `medio` 1:1 y `corto` como en la Media.
  - En `medio` y `corto` se suma `largo` en `reubicar_desde`.
- **Los textos de la Media sirven para la larga (C1):**
  - Campo nuevo en la estructura, `textos_de: medio`. Sin el campo, cada estructura usa sus propios textos.
  - `Estructura.textos` lo resuelve. Lo usan `catalog.py` (efectos y el `acto` de los criterios), `molde.py` (las intenciones de la forma y el `acto` de `revela`) y la validación de `molde.py:187/201`, que exige los ids de `textos`, no todos los ids.
  - `validate()` falla si `textos_de` apunta a una estructura que no existe o que tiene otra cantidad de actos.
- **Perfiles (`llm_core_definitions.yaml`):**
  - Planificador: `num_predict` 9 000 en `openai-sol` y `hibrido-sonnet55`. Es un tope, no cuesta más si no se usa.
  - Voz y Guion: en Sol y en Claude razonan, así que el adapter ya les pone un piso de 16 000 tokens. Alcanza para actos de ~1 350 palabras (~2 200 tokens), así que no se toca.
  - El perfil local (gemma, 1 800) no alcanza para la larga. Se anota en su comentario: con gemma, la larga no sirve.
- **Tests:**
  - `test_estructuras_config` y `test_beat_spec_repository`: tres estructuras, y la larga con los mismos actos que la Media.
  - `test_moldes`: la completitud con `textos_de`.
  - Snapshot nuevo `pipeline_prompts` de la larga, con la Voz con «entre 1 100 y 1 250 palabras» en el acto 2, y del Planificador, con los hechos por acto. Un test que falle si la larga deja de recibir las intenciones de la forma.
  - `test_sin_cinco_actos_fijos` sigue en verde.
- **Checkpoint:** en dev, «Tu idea» ofrece la Larga y «Los actos» de una larga piden más hechos. Se arma la escaleta con el mock, sin IA paga.

### S3. Cada versión guarda su largo

- **Base:** `generated_narrative.structure TEXT` (`ALTER TABLE … ADD COLUMN` si no existe; `NULL` en las viejas).
- **Guardar:**
  - `GeneratedNarrative.structure` y `consolidate_and_save()` guardan el largo de la historia.
  - El UPSERT de `generated_narrative_repository.save()` incluye la columna.
- **Leer:**
  - Helper `largo_de_la_version(narrative)`: el campo, o, si es `NULL`, por cantidad de actos (3 = corto, 5 = medio).
  - Lo usan `video_router.py:35` (en lugar de `estructura_del_relato`), `narrative_acts.py:80` (regenerar un acto: si la versión es de otro largo que la historia, aunque tenga los mismos 5 actos, da el error `version_de_otro_largo` de hoy) y lo que la API devuelve de cada versión, para el front.
- **Front:** `actos.ts` toma el largo que viene de la versión y deja `estructuraPorCantidad` solo de respaldo. Los nombres de los actos de Media y Larga son los mismos, así que en eso no cambia nada.
- **Video:**
  - `lectura.yaml` con `episodio_por_estructura.largo: {desde: 30, hasta: 38}`.
  - `biblia_visual.yaml` con `por_estructura.largo: {momentos: {desde: 20, hasta: 28}, videos: {desde: 2, hasta: 4}}`. Son unos 1,5 momentos por minuto, como hoy.
  - `tiempos.js` y `timing.py` comparten casos en `tests/fixtures/video/` y suman uno de la larga.
- **Tests:**
  - La versión guarda y devuelve su largo, y las viejas se deducen.
  - No se puede regenerar el acto de una versión Media en una historia que pasó a Larga.
  - El video de una larga usa 30–38 min.
- **Checkpoint:** «Para el video» de una versión vieja se ve igual que antes.

### S4. El control de repetición, por cantidad de palabras (C3)

- `repetition_check.py`: la tolerancia de comparaciones (`COMPARISONS_PER_ACT`) y de enumeraciones (`TRIADS_WARNING`) se multiplica por `max(1, round(palabras_del_acto / 500))`. Los actos de la Media y del corto llegan a ~530 palabras, así que les da 1 y siguen igual que hoy. Las oraciones cortadas ya se miden en porcentaje.
- **Voz:** `voice_craft.md` dice «como mucho una comparación por acto». Pasa a un dato, `{comparaciones}` («una comparación por acto» en la Media y el corto, «una cada unas 500 palabras» en la larga), con un fragmento si hace falta. Los snapshots de la Media y del corto no cambian.
- **Tests:** casos con un acto de ~1 200 palabras y 2 comparaciones (sin aviso) y con 4 (con aviso). Los casos de hoy quedan iguales.

### S5. La pantalla (C4)

- **«Tu idea»:** tres opciones, con los `label` de la config. «Corto» sigue primero.
- **Galería y «El relato»:** el chip «Larga» además de «Corto». La Media va sin chip, porque es la de siempre.
- **El tiempo estimado:**
  - Valor inicial para la larga: `full_generation` × 2 hasta que haya historial.
  - `JobDurationEstimator` ya separa por estructura (`BY_STRUCTURE`): se verifica con la larga.
- **E2E (Firefox):** crear una Larga con el mock, ver «Larga · 5 actos · unos 35 minutos», armar los actos y ver el chip. También `sin-jerga` y `gramatica-visual`.
- **Checkpoint:** recorrido en `https://storymaker.test` con una Larga armada con el mock.

### S6. Medición (§5), solo con OK del usuario

- `scripts/evaluate_voice.py --label larga --runs 2` con «El monte prohibido» como Larga y el perfil `openai-sol`.
- Se miden los minutos de lectura, la repetición cada mil palabras (dentro del acto y entre actos), el costo (`llm_call`) y el tiempo.
- Primero se estima sin `--yes`. Antes de correr, se pasan el costo y el tiempo estimados.
- Con los resultados se ajustan `palabras` y `hechos_max` y se decide D5.

### Riesgos

| Riesgo | Qué se hace |
|---|---|
| La reconstrucción de `story` borra en cascada | Las FK se apagan **fuera** de la transacción, se corre `foreign_key_check` y hay un test con todas las tablas hijas. Se prueba con una copia de prod y `make deploy` hace backup |
| Prod: es un cambio de esquema | Lo resuelve `init_db()`, sin export/import (esa vía pierde relatos, ver memoria Spec-700) |
| El Planificador no llega a 8–9 hechos distintos por acto | Lo avisa el Verificador (hechos repetidos). Se ve en S6 |
| La Voz se estira o se repite dentro de un acto largo | S4 lo mide sin castigar el largo. Se ve en S6 |
| Un perfil sin tokens suficientes (gemma) | Se documenta. `LLM_PROFILE_LARGO` permite poner la larga en otro perfil, u `off` |

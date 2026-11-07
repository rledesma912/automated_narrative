# SPEC-750: tres largos y el relato de 35 minutos

**Fecha:** 2026-11-06
**Tipo:** SDD: estructuras del relato (config), dominio y base, asistente (UI), video
**Estado:** SPECIFY cerrada (D1–D4 decididas por el usuario el 2026-11-06); falta el OK para PLAN. Sin código.
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

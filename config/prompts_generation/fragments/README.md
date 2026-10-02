# Fragmentos de prompt (Spec-620)

Cada rol arma su prompt con una **plantilla** (`../<rol>*.md`) y estos **fragmentos**: las
secciones que van o no según los datos de la historia. El código decide **si** una sección
va y con **qué datos**; el texto está acá. Ningún texto que lee el LLM se escribe en Python
(lo controla `tests/unit/test_prompts_fuera_del_codigo.py`).

- Se cargan con `TemplateLoader.fragment("<carpeta>/<nombre>", **datos)` y se completan con
  `str.format`: `{narrador}`, `{acto}`… Una llave literal se escribe `{{` / `}}`.
- Se respeta el texto tal cual (sangría incluida) salvo el último salto de línea del
  archivo. Los saltos que separan una sección de la siguiente los pone el código.
- Un fragmento o un dato que falta es un error: el prompt nunca sale incompleto.
- Cambiar un fragmento cambia el prompt: los snapshots lo detectan
  (`tests/fixtures/snapshots/{pipeline,voice,assistant}_prompts.json`). Si el cambio es a
  propósito, se regeneran con `SNAPSHOT_UPDATE=1` y se revisa el diff.

Los mensajes que ve una persona (no el LLM) van en `config/core_messages.yaml`.

---

## La Voz (`voz/`)

**System** — `outline_voice_system.md`:

| Hueco | Sale de |
|---|---|
| `{presentacion}` | `voz/presentacion` (con nombre de quien narra) o `voz/presentacion_sin_nombre` |
| `{como_lo_cuenta}` | `config/authoring_options.yaml` (`telling.voice`) |
| `{parentescos}` | `voz/parentescos` + una `voz/parentesco` por personaje (`voz/parentesco_sin_rol` si no tiene rol); vacío si no hay a quién nombrar |
| `{guia_oficio}` | `../voice_craft.md` (con `voice_cliches.txt`; `voz/narrador_generico` si no hay nombre) |

**User** — `outline_voice.md`, en este orden:

| Hueco | Sale de | Va si… |
|---|---|---|
| `{nombre}` | `label` del acto en `config/llm_beats_definition.yaml` | siempre |
| `{historia}` | `voz/historia` (primera oración de la premisa) | hay premisa o sinopsis |
| `{funcion}` | `intent` del acto, o `voz/final_del_autor` en el acto 5 | siempre |
| `{meta}` | `voz/objetivo` | el acto tiene objetivo |
| `{puente}` | `voz/puente` | actos 2–5 con «cómo llega acá» |
| `{final_anterior}` | `voz/final_anterior` (último párrafo del acto anterior) | hay acto anterior |
| `{escenario}` | el escenario, o `voz/escenario_vacio` | siempre |
| `{reglas}` | `voz/reglas` + las reglas del acto | hay reglas |
| `{cambio}` | `voz/cambio` | el acto dice cómo termina |
| `{no_revelar}` | `voz/no_revelar` | hay algo que todavía no se cuenta |
| `{amenaza}` | `voz/amenaza/titulo` + por amenaza: `voz/amenaza/presencia` (si la exposición no deja ver el nombre), `que_es`, `como_se_percibe`, `limites`, `como_mostrarla` | hay amenaza; cada campo solo si la exposición del acto lo deja ver |
| `{ya_paso}` | una `voz/ya_paso_acto` por acto anterior, o `voz/ya_paso_vacio` | siempre |
| `{como_esta}` | `voz/como_esta` | la memoria trae estado o cuerpo |
| `{asi_es}` | `voz/asi_es` + los rasgos | la memoria trae rasgos |
| `{evitar}` | `voz/evitar/titulo` + `repetida`, `cliche`, `nombres`, `cortadas`, `dialogo` | se regenera un acto y el control marcó algo |
| `{ya_usado}` | los motivos usados, o `voz/ya_usado_vacio` | siempre |

`voz/protagonista` reemplaza el nombre cuando no hay uno. `voz/reintento` se agrega al
prompt si el modelo se niega a narrar (`NarratorRetryGenerator`).

## La Memoria (`memoria/`)

`outline_journal.md`: `{memoria}` (o `memoria/memoria_vacia`), `{cuerpo}` (o
`memoria/cuerpo_vacio`), `{asi_es}` (o `memoria/asi_es_vacio`). Los hechos de cada acto se
guardan como `memoria/hechos_acto` («Acto N: …»).

## El asistente (`asistente/`)

Contexto común (`context.py`), que reciben los tres roles:

| Hueco | Sale de |
|---|---|
| `{objetivo}` | `asistente/objetivo` |
| `{historia}` | `asistente/historia/*`: `titulo`, `tipo`, `de_que_trata`, `protagonista`, `quien_lo_cuenta`, `efecto`, `como_lo_cuenta`, `como_termina` (+ `final_decidido`), `personajes` — cada línea si hay dato |
| `{decisiones}` | por decisión del taller: `asistente/decisiones/intencional`, `con_pregunta` o `respondida` (+ `va_en_acto`); o `asistente/decisiones/vacio` |
| `{efecto}` | `asistente/efecto/planificador` o `asistente/efecto/verificador` (solo si el efecto tiene receta) |

**Consultor** — `authoring_consultant.md`: además `{pendientes}` (una
`asistente/pendientes/pendiente` por pregunta sin responder, o `asistente/pendientes/vacio`).

**Planificador** — `authoring_planner.md`: además `{borradores}`
(`asistente/planificador/borradores` + `borrador`), `{problemas}`
(`asistente/planificador/problemas` + una `asistente/aviso_de_acto` por aviso visible),
`{reglas}` (Spec-630: `asistente/planificador/reglas` + una `regla` por regla anclada a un acto;
vacío si no hay), `{escenarios}` (o `asistente/planificador/escenarios_vacio`) y `{actos}` (una
`asistente/planificador/acto` por acto; `final_del_autor` y `historia_secreta` cambian la
intención del acto 5 y del 4).

**Verificador** — `authoring_verifier.md`: además `{elenco}` (o
`asistente/verificador/elenco_vacio`), `{escaleta}` (por acto, `asistente/verificador/acto/*`:
`titulo` o `titulo_con_escenario`, `como_llega`, `quiere`, `en_escena`, los hechos, `cambia`,
`reglas` —las tres de la Spec-630, solo si el acto tiene el dato—, `no_se_cuenta` + `se_revela`,
`usa`) y `{descartados}` (una `asistente/aviso_de_acto` por aviso ignorado, o
`asistente/verificador/descartados_vacio`).

## El paquete para el video (`video/`, Spec-610)

`video_script_system.md`: `{presentador}` (nombre de la calabaza, de `config/video/presentador.yaml`).

`video_script.md` (`src/application/services/video/prompts.py`):

| Hueco | Sale de |
|---|---|
| `{relato}` | por acto, `video/acto` (`numero`, `nombre` = `label` de `llm_beats_definition.yaml`) con una `video/parrafo` por párrafo (`[n] texto`, numerado dentro del acto) |
| `{actos}` | por acto, `video/acto_contexto`: el escenario de la escaleta (o `video/lugar_vacio`) y, si hay amenaza, `video/amenaza` con la `guide` de su exposición en ese acto |
| `{calabaza}` | `video/calabaza` con la ficha, la intro, la forma del outro (`video/paso`) y los outros de ejemplo (`video/ejemplo`) |
| `{pantalla}` | `video/pantalla` con las palabras prohibidas de `config/video/biblia_visual.yaml` |
| `{reintento}` | vacío, o `video/reintento` con una `video/problema` por cada problema del chequeo (`video/problemas/*`: `bloques_cobertura`, `momentos_cobertura`, `faltan`, `repetidos`, `no_existe`, `acto_inexistente`, `enfasis`, `momentos_cantidad`, `prohibida`, `outro_cierre`, `largo_intro`, `largo_outro`) |
| `{momentos_desde}`, `{momentos_hasta}`, `{transiciones}`, `{ppm}`, `{duracion}`, `{titulo}`, `{presentador}` | `config/video/` y el relato |


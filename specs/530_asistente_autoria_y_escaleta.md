# SPEC-530: Asistente de autoría y escaleta por acto

**Fecha:** 2026-09-25
**Tipo:** SDD (Spec-Driven Development)
**Estado:** IMPLEMENT — PLAN aprobado 2026-09-25 (decisiones 1–9 adoptadas); las filas de §6 se marcan antes de S7
**Origen:** relato «la pena del colectivo» (prod, `4a4d8cab-…`): repetitivo, el fantasma aparece en todos los actos y el protagonista no hace nada. Diagnóstico y pruebas del 2026-09-25 (§1).

---

## ASSUMPTIONS

1. **El problema principal está en lo que entra, no en la Voz.** Con la misma Voz y el mismo perfil, una escaleta mejor produjo un relato mejor (§1.3). Primero se cambia lo que recibe el pipeline; la Voz se simplifica en el mismo movimiento.
2. **El modelo local sigue siendo `gemma3:12b`.** Todo lo que se diseñe tiene que funcionar con él (probado en §1). Un modelo más grande (Spec-480) es una mejora opcional, no un requisito.
3. **El asistente aconseja, no bloquea.** El usuario siempre puede pasar a generar, aunque queden criterios sin cumplir.
4. **La teoría narrativa (Freytag, pilares aristotélicos, Piglia, McKee…) se usa para diseñar los criterios, no como vocabulario en los prompts.** El modelo recibe preguntas concretas («¿cada encuentro es de otro tipo y más grave que el anterior?»), no «evaluá la peripecia» (§1.2).
5. **Escala:** 1–2 usuarios, una historia a la vez. Las llamadas del asistente pueden tardar 30–60 s cada una si se muestra el avance.
6. **Sin migraciones** (regla del proyecto): los cambios de esquema van en `init_db()`. Los datos de prod (3 historias, 2 relatos al 2026-09-25) se pasan con `export-yaml` → recrear la DB → `import-yaml`.
7. **Regenerar un acto «con arnés»** (que sepa qué hay antes y después) queda para una spec posterior. Esta spec deja los datos listos para hacerlo (§12).

---

## OBJECTIVE

Reemplazar el wizard de 76 campos por un **asistente de autoría**: el usuario marca la dirección de la historia en pocas decisiones, la IA le hace preguntas concretas para llenar los huecos y, entre los dos, arman una **escaleta de 5 actos** que se revisa antes de generar la prosa. Tiene que ser **ameno y didáctico**: cada pregunta explica en una línea por qué importa.

**Éxito se ve como:**
- Empezar una historia pide unos 10 datos, no 76.
- El usuario entiende por qué el asistente le pregunta cada cosa y puede contestar, elegir una opción, escribir la suya o marcar «esto es intencional».
- La escaleta muestra, acto por acto, qué quiere el protagonista, qué hace, qué cambia y dónde pasa. El escenario y las reglas se definen dentro del acto.
- Sobre las historias de referencia, los relatos salen con menos repetición y más hilos que se siembran y se cobran que hoy (§10).

---

## 1. HALLAZGOS (2026-09-25)

Todas las pruebas usaron `gemma3:12b` y la historia de prod «la pena del colectivo». Los scripts y las salidas están en el anexo (§14).

### 1.1 Qué salió mal en el relato

| Síntoma | Causa |
|---|---|
| El fantasma en el espejo en los actos 1, 2 y 4 | La regla global «el micro siempre presenta casos paranormales…» se inyecta en los 5 actos, en system y en user. La resonancia del Acto 4 que armó el Analyst pide volver al espejo. |
| El Acto 4 cuenta de nuevo el descarrilamiento del 3 | El evento del Acto 4 («baja horrorizado por descarrilar») y la memoria lo retoman, y nada marca que ya se contó. |
| Muletillas en varios actos («¿Todo bien, José?», «olor dulce», «animal herido») | El Journal copia frases de la prosa a la memoria. No hay registro de las imágenes ya usadas. |
| El Acto 3 «en la terminal» mientras maneja por la ruta | El Resolver repartió los 2 escenarios cargados y asignó la estación a los actos 3–5. |
| Relleno | Unos 3 hechos de horror para 5 actos de 450–530 palabras, con «no inventés eventos». |

### 1.2 El asistente es factible con `gemma3:12b`

Se probó el análisis de la sinopsis con 7 criterios y salida con esquema JSON (`format` de Ollama), en 4 corridas:
- **Detectó los huecos reales en las 4 corridas** (escalada: no; historia secreta: no). Las preguntas son específicas de esta historia y ofrecen 3 opciones útiles.
- **JSON válido siempre.** Unos 35 s por análisis (64 s con el modelo en frío).
- **Débil en:** citar evidencia, algunas opciones trilladas («grabarla con el celular»). **Impone convenciones del género**: en las 4 corridas quiso volver inquietante el final en paz que eligió el autor. De ahí el botón «intencional».
- **Nombrar la teoría no aporta.** Agregar Freytag y los pilares al contexto no mejoró las preguntas y llevó las opciones al melodrama. Lo que sí hace falta es el **objetivo** y la **dirección del autor**.

### 1.3 La escaleta mejora el relato

`gemma3:12b` armó una escaleta a partir de la sinopsis y de las respuestas del autor (simuladas). Después se generó el relato con el mismo pipeline y la misma Voz:

| | Sinopsis original | Escaleta |
|---|---|---|
| Clichés prohibidos | 3 | 0 |
| Frases repetidas entre actos | 4 | 1 |
| Narrador en 3ª persona por error | 2 | 0 |
| Escenario equivocado en los actos 3–5 | los 3 | ninguno |
| Hilos sembrados y cobrados | ninguno | 2 (la hija internada, el ramo) |
| El protagonista actúa | no | sí (pregunta, limpia el espejo, prende la radio) |

**Fallas de la escaleta:** perdió la historia secreta (la guardó y nunca la reveló), adelantó al Acto 4 el hecho del 5 (las flores) y siguió usando el espejo en todos los actos. **Por eso necesita una verificación y la revisión del usuario** (§5.3).

### 1.4 Variables que no sirven

- **Código:** `traits`, `distortion_triggers`, `paranormal_knowledge`, `religioso_knowledge` y `rule.type` **no llegan a la Voz**. `traits` solo va al Analyst y al Journal, dentro del string `protagonista`.
- **Ablación** (actos 2 y 4, 3 muestras por variante): dar vuelta el perfil del narrador («poético, formal, abundantes metáforas, cree en fantasmas, atento a olores») **no cambia la prosa**. Los símiles quedan en 0,7 contra 0,8 cada 100 palabras y el narrador sigue buscando explicaciones lógicas. Solo el **registro** mueve algo (+1,3 palabras por frase, desaparecen los insultos). Sin perfil, sale igual que ahora.
- **Datos:** ninguna regla en prod tiene acto asignado; el wizard no lo permite.

---

## 2. MODELO: TRES NIVELES

```
DIRECCIÓN (la historia entera)      →  TALLER (preguntas y respuestas)  →  ESCALETA (por acto)  →  PROSA
qué historia, efecto, final,            la IA evalúa criterios y              qué quiere, hechos,       Voz + Journal
protagonista, quién narra,              pregunta solo por los huecos;         qué cambia, escenario,    (acto por acto)
cómo lo cuenta, amenaza (opcional)      el usuario responde o marca           reglas del acto, qué se
                                        «intencional»                         guarda; la IA la propone,
                                                                              el usuario la edita
```

- Cada nivel tiene **su propia vista** y se puede volver atrás. Cambiar la dirección con la escaleta ya armada la marca «a revisar»; no se pierde.
- El taller itera en dos momentos: **sobre la dirección** (antes de la escaleta) y **sobre la escaleta** (antes de la prosa).

---

## 3. EXPERIENCIA (UI)

### 3.1 Principios

- **Una cosa por vez.** Cada paso pide pocas decisiones, con ejemplos. Nada de pantallas con 20 campos.
- **Didáctico.** Cada criterio y cada pregunta traen una línea de «por qué importa», en lenguaje llano y sin jerga. Ejemplo: «Si José solo mira, el lector también se aburre: ¿qué *hace* cuando la ve?».
- **La IA propone, el usuario decide.** Cada pregunta ofrece 2–3 opciones más «escribir la mía», «decidí vos» e «intencional, no lo toques».
- **El estado se ve.** Un semáforo por criterio (verde: cumple · amarillo: parcial · rojo: falta · gris: intencional).

### 3.2 Vistas

1. **Nueva historia (Dirección).** Título, género y subgénero, «¿de qué trata?» (2–5 líneas, sin estructura), efecto buscado, cómo termina (y si es intencional), protagonista (nombre y qué hace), quién narra (por defecto el protagonista), «¿cómo lo cuenta?» (opciones preparadas, §6) y amenaza (opcional: la ficha de la Spec-450, arrancando con una).
2. **Taller.** Lista de preguntas abiertas con su «por qué», las opciones y el semáforo. Botones «Analizar de nuevo» y «Pasar a la escaleta».
3. **Escaleta.** 5 tarjetas, una por acto: qué quiere el protagonista, hechos (lista editable), qué cambia (de → a), escenario (los ya usados como opciones rápidas, o «+ nuevo»), reglas del acto y qué se guarda para después. Los avisos del verificador van en la tarjeta que corresponda. Botones «Revisar con la IA» y «Generar relato».
4. **Generación y relatos:** la sala y el panel de relatos actuales, sin cambios de fondo.

**Diseño antes que código:** el PLAN de esta spec arranca con un slice de maquetas navegables (sobre el tema de la Spec-531, con datos de «la pena del colectivo») para Dirección, Taller y Escaleta: cómo se muestran las preguntas y sus opciones, los controles para responder, marcar «intencional» o dar un criterio por completo, y la disposición de las tarjetas de acto con sus hechos, escenario y reglas. El usuario las revisa y ajusta antes de construir las vistas reales.

### 3.3 Cuándo termina el taller

Cualquiera de estas condiciones, y siempre visible cuál se cumplió:
- **Se cumple:** todos los criterios están en verde o en gris. Se calcula de forma determinística.
- **Sin preguntas:** la IA no devuelve preguntas nuevas.
- **Ya no suma:** las preguntas nuevas son sobre criterios ya resueltos, o repiten otras ya respondidas. Se filtran sin mostrarlas; si no queda ninguna, se considera «sin preguntas».
- **Decisión del usuario:** «Pasar a la escaleta» o «Generar» están siempre disponibles.
- Tope de seguridad: 5 rondas por nivel.

---

## 4. CRITERIOS NARRATIVOS

Los criterios salen de la teoría, pero el modelo solo ve la columna «pregunta operativa». Cada uno declara si lo evalúa la IA o una regla determinística.

### 4.1 Dirección

| Criterio | Pregunta operativa | Origen | Evalúa |
|---|---|---|---|
| Meta | ¿Qué quiere el protagonista esa noche, algo que la amenaza pueda frustrar? | Swain / McKee | IA |
| En juego | ¿Qué pierde si esto sigue? | McKee | IA |
| Vulnerabilidad | ¿Qué hace o cree el protagonista que lo expone a esto? | Hamartia | IA |
| Historia secreta | ¿Hay algo oculto que explique por qué le pasa a él? | Piglia | IA |
| Final | ¿El final deja una marca coherente con el efecto elegido? | Poe / residuo | IA, respetando el final «intencional» |

### 4.2 Escaleta

| Criterio | Pregunta operativa | Origen | Evalúa |
|---|---|---|---|
| Cambio | ¿La situación al terminar el acto es distinta que al empezar? | McKee (cambio de valor) | Regla («de» ≠ «a») + IA |
| El protagonista actúa | ¿El protagonista hace algo en el acto (no solo ve o siente)? | Swain | IA |
| Escalada | ¿Cada encuentro es de otro tipo y más grave que el anterior? | Peripecia | IA |
| Siembra y cosecha | Lo que se sembró, ¿se cobra en algún acto? | Chéjov | Regla sobre los campos «siembra» y «cobra en» |
| Un hecho, una vez | ¿Hay hechos repetidos o adelantados a otro acto? | Economía | IA (clasificación) |
| Decisiones integradas | Cada decisión del taller, ¿está en algún acto? | — | IA (clasificación) + regla |
| Revelación | Lo que «se guarda», ¿se revela en un acto posterior? | Anagnórisis | Regla + IA |

---

## 5. ROLES LLM NUEVOS

Todos usan salida con esquema JSON (`format` de Ollama; en Anthropic, el equivalente) y un rol propio en el perfil (`consultor`, `planificador`, `verificador`), con su modelo y temperatura.

### 5.1 Consultor (taller)
Recibe la dirección, la sinopsis y las respuestas previas. Devuelve por criterio: estado, una pregunta y 2–3 opciones. Temperatura baja para evaluar. Una llamada por ronda (unos 35 s).

### 5.2 Planificador (escaleta)
Recibe la dirección y las decisiones del taller. Devuelve los 5 actos con los campos de §3.2 y, por acto, la lista de decisiones del taller que integra. Una llamada (unos 45 s).

### 5.3 Verificador (escaleta)
Tareas de clasificación simples, para que las resuelva un 12B:
- ¿Qué decisiones del taller no aparecen en ningún acto?
- ¿Qué hechos se repiten o están en el acto equivocado?
- ¿Lo que se guarda se revela en algún acto?

Sus avisos van a la tarjeta del acto. No corrige solo: propone el cambio y el usuario lo acepta.

### 5.4 Qué pasa con los roles actuales

- **Voz:** recibe la escaleta del acto (§8). Su prompt se simplifica.
- **Journal:** devuelve **hechos** y **motivos usados**, no frases de la prosa (§8.2).
- **Mapper y Analyst:** con la escaleta, sus funciones (sacar los hechos del acto N y los pilares) quedan cubiertas. **Hipótesis:** se pueden sacar y el pipeline baja de 16 a unas 11 llamadas. Se decide midiendo en el PLAN; mientras tanto se mantienen como respaldo para las historias sin escaleta (YAML importado).
- **Resolver:** con el escenario elegido en cada acto, queda solo como respaldo.

---

## 6. VARIABLES: QUÉ QUEDA, QUÉ SE VA

Hoy se piden **76 campos**: título y atmósfera 4, personajes y narrador 17, «cómo suena» 10, mundo 40, trama 5. La columna «Acuerdo» la completa el usuario.

| Variable actual | Decisión | Evidencia | Acuerdo |
|---|---|---|---|
| `distortion_triggers`, `paranormal_knowledge`, `religioso_knowledge` | Se eliminan | No llegan a ningún prompt | ☐ |
| `perception_reliability`, `distortion_level`, `interpretation_style`, `figurative_density`, `fear_focus`, `attention_focus` | Se eliminan | Ablación sin efecto medible | ☐ |
| `traits` («Cómo es») | Se elimina; lo reemplaza el criterio «Vulnerabilidad» del taller | No llega a la Voz | ☐ |
| `rule.type` | Se elimina | No se usa | ☐ |
| `voice_style` + `language_register` + «Tono» del relator | Se fusionan en **«¿Cómo lo cuenta?»**: 3–4 opciones preparadas (p. ej. «como un caso entre amigos», «como una confesión», «literario») | El registro es lo único que mueve la prosa | ☐ |
| `tono` (evolución de la tensión) | Lo reemplaza **«Efecto buscado»** | Choca con la curva de intensidad fija de los 5 actos | ☐ |
| Escenarios cargados al inicio (hasta 4) | Se eligen o crean **dentro de cada acto** | Error del Resolver en los actos 3–5 | ☐ |
| Reglas globales (hasta 7) | **Por acto**, o como límites de la amenaza | La regla global puso el fantasma en el Acto 1 | ☐ |
| Entidades (hasta 3 × 6) | Se mantienen; la UI arranca con una y es opcional | Es la ficha de la amenaza | ☐ |
| Personajes (5 × 3) | Nombre y qué hace. Al inicio solo el protagonista; el resto se agrega desde un hecho de la escaleta | La Voz los usa | ☐ |
| Quién narra | Se mantiene, con el protagonista por defecto | Mueve la persona gramatical y los parentescos | ☐ |
| Título, género, subgénero | Se mantienen | Catálogo y naturalezas de la amenaza | ☐ |
| 5 textos de actos | Pasan a la escaleta | §1.3 | ☐ |
| — | **Nuevo:** «¿de qué trata?», efecto buscado, final (+ intencional) | §1.2 | ☐ |

**Resultado:** unos 10 datos al inicio. El resto lo completa el taller y la escaleta.

---

## 7. DOMINIO

| Cambio | Detalle | Costo |
|---|---|---|
| `story.direction` (JSON, nueva columna) | `{premisa, efecto, final, final_intencional, meta, en_juego, vulnerabilidad, historia_secreta}` | Bajo |
| `story_workshop` (tabla nueva) | Preguntas y respuestas del taller: `story_id, nivel (direccion│escaleta), criterio, estado, pregunta, respuesta, intencional, ronda` | Bajo–medio |
| `act_outline` (tabla nueva) | La escaleta, **separada de `macro_beat`** (que es la salida generada): `story_id, number, meta, hechos (JSON), cambio_de, cambio_a, scenario_id, se_guarda, siembra (JSON), cobra (JSON), decisiones (JSON), locked` | Medio |
| `rule.applies_to_beat` | Ya existe y ya filtra; la UI empieza a cargarlo | Nulo |
| `macro_beat.active_scenario_id` | Ya existe; lo toma de `act_outline` | Nulo |
| Se borran `character.traits`, `rule.type`, `rule.intensity` | `init_db()` + repos + exporter + loader + tests (unos 10 archivos de tests) | Bajo |
| `story.tono` → `direction.efecto` | 15 archivos de src, 10 de tests; el string `atmosfera` pasa a «género (subgénero)» | Medio |
| Claves que se quitan de `narrator_config` | Queda `{storyteller_id, storyteller_name, voice: {person, tense}, registro}` | Bajo |
| YAML (`export-yaml` / `import-yaml`) | Exporta la dirección y la escaleta; importa también el formato viejo (ignora las claves eliminadas y mapea `tono`) | Medio |
| Datos de prod | `export-yaml --all` → recrear → `import-yaml` | Bajo (3 historias) |

---

## 8. VOZ Y MEMORIA

### 8.1 Prompt de la Voz

- **Sale:** el bloque «Perfil del Narrador» y el tono, junto con ARCO, «Efecto buscado» y PROHIBIDO por acto (a revisar en el PLAN cuáles quedan). La resonancia del Analyst deja de ir a la Voz.
- **Queda:** quién narra y cómo lo cuenta (1 línea), la guía de oficio (Spec-470), los hechos del acto, el escenario, las reglas del acto, la memoria (hechos) y **«ya usado, no repetir»**.
- **Extensión proporcional a los hechos del acto** (rango por acto en `llm_beats_definition.yaml`, ajustado por la cantidad de hechos), en lugar de 450–530 fijo.
- Los hechos que ya ocurrieron en actos anteriores se marcan como «ya contado»: el acto siguiente no los vuelve a narrar.

### 8.2 Memoria (Journal)

- Devuelve `hechos` (lo que pasó, sin frases de la prosa), `estado` (actualizado al tiempo del acto siguiente) y `motivos_usados` (imágenes, sonidos, frases de diálogo, comparaciones).
- Los `motivos_usados` **se acumulan** a lo largo del relato y llegan a la Voz como lista de «no repetir».

### 8.3 Control de repetición (determinístico)

Después de cada acto, se buscan n-gramas y frases repetidas contra los actos anteriores (base: `scripts/voice_metrics.py`). También se detectan los clichés por lema, no solo por forma exacta: se coló «me había helado la sangre». En esta spec **solo se muestra** en el panel del relato; la regeneración automática queda para la spec del arnés (§12).

---

## 9. BOUNDARIES

- **Siempre:** esquema JSON en todas las salidas nuevas de la IA; toda decisión de la IA es editable; el usuario puede pasar a generar en cualquier momento; «intencional» se respeta en todas las rondas.
- **Siempre:** regresión cero para las historias viejas: el YAML importado sin escaleta se sigue generando con el pipeline actual.
- **Preguntar antes:** sacar el Mapper o el Analyst del pipeline (solo con medición); dependencias nuevas; cambiar el modelo por defecto.
- **Nunca:** jerga teórica en la UI o en los prompts; bloquear la generación por criterios en rojo; scripts de migración.

---

## 10. SUCCESS CRITERIA

1. **Carga inicial ≤ 12 datos** para empezar una historia (hoy: 76 campos).
2. **Taller:** con `gemma3:12b`, cada ronda tarda ≤ 60 s en caliente; el taller termina por una de las condiciones de §3.3 en ≤ 3 rondas por nivel en las historias de referencia.
3. **Escaleta:** el verificador marca el 100 % de las decisiones no integradas y de los hechos repetidos en un set de casos armados a mano.
4. **Relato**, sobre «la pena del colectivo» y «El monte prohibido», 2 corridas cada una, contra la línea base de hoy: frases repetidas y clichés iguales o menores; ningún acto con un escenario que contradiga la escaleta; cada hilo sembrado se cobra.
5. **Compatibilidad:** los 3 YAML de `input_stories/` y los 3 de prod se importan y generan.
6. `make lint`, pytest, Vitest y Playwright en verde.

---

## 11. TESTING

- **Unit (pytest):** criterios determinísticos (§4); condiciones de fin del taller (§3.3); ensamblado de los prompts nuevos con snapshots (`SNAPSHOT_UPDATE=1`); repositorios de `act_outline` y `story_workshop`; loader YAML viejo → nuevo.
- **Contrato de la IA:** Consultor, Planificador y Verificador con `MockLLMAdapter` (JSON fijo), incluyendo JSON inválido o incompleto (reintento una vez, después error visible).
- **Evaluación (script, no CI):** `scripts/evaluate_workshop.py` sobre las historias de referencia: tiempos, criterios detectados y métricas del relato (amplía `evaluate_voice.py`).
- **Vitest:** semáforo, «intencional», tarjetas de la escaleta, opciones rápidas de escenario.
- **E2E (Playwright, LLM mock):** nueva historia → taller (1 ronda) → escaleta → generar → relato.

---

## 12. FUERA DE ALCANCE (specs posteriores)

- **Regenerar un acto con arnés:** re-narrar el acto N conociendo los motivos usados antes y el hecho del acto siguiente; re-correr el Journal de N y marcar «a revisar» los actos siguientes si cambió algún hecho. Esta spec deja los datos necesarios (`act_outline`, `motivos_usados`).
- Regeneración automática cuando el control de repetición supera un umbral.
- Evaluar la Voz en Sonnet 5 (Spec-480) **después** de esta spec, para no mezclar cambios en la medición.
- El tema claro y el favicon van por la Spec-531, independiente de esta.

---

## 13. PREGUNTAS ABIERTAS (para el usuario)

1. **¿El asistente reemplaza al wizard o conviven un tiempo?** Propuesta: lo reemplaza; `import-yaml` sigue como vía rápida.
2. **Opciones de «¿Cómo lo cuenta?»:** ¿cuáles 3 o 4? Propuesta: caso entre amigos (coloquial) · confesión íntima · crónica seca · literario.
3. **Efectos buscados:** ¿lista cerrada o texto libre con ejemplos? Propuesta: lista (pavor creciente · susto · melancolía inquietante · horror que se revela) más «otro».
4. **¿La sinopsis de corrido sigue existiendo?** Propuesta: sí, como «¿de qué trata?» (corta), y la escaleta pasa a ser la fuente de verdad.
5. **¿Hasta cuántas entidades?** El dominio mantiene 3. ¿La UI muestra solo una, con «agregar otra» escondido?
6. **Personajes secundarios:** ¿se agregan desde la escaleta, cuando un hecho los nombra, o en una sección aparte?
7. **Rol por proveedor:** ¿Consultor, Planificador y Verificador en `gemma3:12b`, o se deja preparado para mandar el Consultor a Claude si las preguntas no convencen?

---

## 14. ANEXO: evidencia

Scripts y salidas de las pruebas del 2026-09-25 en `scripts/research/530/` (ver su README):
- `probe.py`, `probe2.py`: análisis de criterios, con y sin contexto teórico.
- `escaleta.py`, `escaleta_{1,2}.json`: escaleta generada a partir de la sinopsis y las respuestas.
- `build_yaml.py`, `run_pipe.py`, `salidas/relato_*.txt`, `salidas/metrics_*.json`: relatos y métricas.
- `ablation.py`, `ablation.log`, `salidas/abl_*.txt`: ablación del perfil del narrador.

---

## PLAN

**Estado:** aprobado (2026-09-25). Se escribe sobre la Spec-531 (tema «Papel»), que ya está implementada (PR #30).

### Estrategia

1. **Diseño primero:** maquetas navegables antes de cualquier cambio de dominio (S0). Lo que se ajuste ahí actualiza §3 y §7 antes de seguir.
2. **Sumar antes de quitar:** los slices S1–S6 **agregan** el camino nuevo (dirección, taller, escaleta, pipeline con escaleta) sin romper el actual. Las historias sin escaleta se siguen generando igual (regresión cero, con los snapshots de prompts actuales).
3. **Medir antes de recortar:** sacar el Mapper, el Analyst o el Resolver, y eliminar variables del dominio (S7), recién después de medir (S6) y con las filas de §6 marcadas por el usuario.

### Hallazgos del relevamiento (complementan §1)

| Hallazgo | Consecuencia |
|---|---|
| `LLMProvider.generate()` no admite salida estructurada; `OllamaAdapter` usa `/api/generate` sin `format`. El Journal parsea JSON «a mano» (`split("{")`) y, si falla, devuelve el journal anterior en silencio. | Se agrega `response_schema: dict \| None` al protocolo. Ollama lo manda como `format`; Anthropic usa su salida estructurada; Gemini CLI y Mock lo ignoran (Mock devuelve un JSON fijo por rol). |
| `DirectorUseCase._execute_single_beat` arma cada acto así: `synopsis_slice` → `mapper.map_one()` → `build_narrative_context()` → Voz → Journal. El escenario sale de `rule_distribution` (Resolver). | El camino con escaleta se inserta ahí: si el acto tiene `act_outline`, se saltea el Mapper y el escenario sale de la escaleta. |
| `StoryCreateDTO` exige `protagonista`, `relator` y `sinopsis` no vacíos. | La Dirección crea el borrador con esos campos derivados (`protagonista` = nombre + qué hace; `relator` desde «¿cómo lo cuenta?»; `sinopsis` = «¿de qué trata?»). El DTO no cambia hasta S7. |
| `JobKind` tiene `full_generation` y `regenerate_voz`. `JobManager` ya resuelve el lock por historia, las estimaciones, los eventos SSE y la cancelación. | El taller, la escaleta y la verificación corren como **jobs** (`consult`, `plan_outline`, `verify_outline`): tardan 30–60 s, sobreviven a cerrar la pestaña y reusan el banner y el ETA (Spec-510). |
| El wizard sale de `ui_definitions.yaml` y guarda en sesión hasta «Guardar historia». | Las vistas nuevas guardan en el Core a cada paso (borrador persistido), no en sesión: el taller necesita la historia en la DB. |

### Decisiones (se adoptan las propuestas de §13 salvo que el usuario diga otra cosa)

1. El asistente **reemplaza** al wizard. El wizard viejo se retira en S7, no antes; mientras tanto conviven y «Nuevo relato» apunta al asistente desde S4.
2. «¿Cómo lo cuenta?»: caso entre amigos · confesión íntima · crónica seca · literario. Cada opción se traduce en **una** línea del prompt de la Voz (se define y se mide en S5).
3. Efecto buscado: lista cerrada (pavor creciente · susto · melancolía inquietante · horror que se revela) + «otro» con texto libre.
4. «¿De qué trata?» se conserva (2–5 líneas) y la escaleta pasa a ser la fuente de verdad de los hechos.
5. Entidades: la UI muestra una y deja «agregar otra» (máx. 3, como el dominio).
6. Personajes secundarios: se agregan desde la escaleta («+ personaje» en la tarjeta del acto) y quedan en la lista de la historia.
7. Consultor, Planificador y Verificador en `gemma3:12b`, con el rol configurable por proveedor (Spec-480) por si hace falta mandar el Consultor a Claude.
8. Salida JSON inválida: un reintento y después `job_failed` con un mensaje claro. Nunca se usa el resultado anterior en silencio (se corrige también en el Journal).
9. Maquetas como vistas EJS reales con datos fijos detrás de `/maquetas/*` (solo con `ENV=dev`). Se ven con `make dev` y con el tema real, y sus parciales se reusan en S4.

### Decisiones de la revisión de S0 (2026-09-25)

10. **Guardado automático real.** Cada campo se guarda en el Core mientras se escribe (con debounce, como el `autoSaveField` del wizard actual), con un indicador «Guardado hace un momento». No hay botón «Guardar».
11. **La IA nunca se dispara sola.** Cada llamada tiene un comando explícito, con su tiempo estimado en el botón:
    - Dirección: «Analizar mi historia»;
    - Taller: «Analizar de nuevo» y «Armar la escaleta» (Planificador + Verificador);
    - Escaleta: «Revisar con la IA».

    Pasar de una vista a otra es solo navegación.
12. **Modal bloqueante mientras la IA trabaja:** spinner grande, un título que dice qué está haciendo («Interpretando la historia…», «Armando la escaleta…», «Revisando la escaleta…»), el tiempo que falta y «Cancelar». Toda la página queda `inert`: no se puede tocar ningún campo ni botón. Si se cierra la pestaña, el job sigue; al volver, el modal reaparece atado al job activo hasta que termina. Con un job activo, el guardado automático responde 409 (ya pasa hoy con `PATCH /stories`).
13. **«Decidí vos» no llama a la IA:** elige la primera opción, que es la que la IA propone como más fuerte. Es instantáneo.
14. **Personajes** (caso «El galpón»: 3 con nombre, otros sin nombre y grupos enteros):
    - Cada personaje tiene **tipo** (con nombre · sin nombre · grupo) y **qué es para quien narra** («mi mamá», «el patrón»). Así la Voz los nombra bien; es el insumo de los parentescos de la Spec-470.
    - **Cada personaje se agrega cuando hace falta, en el acto donde aparece** («+ personaje» en «En escena»), o cuando el Verificador lo propone. La Dirección pide solo al protagonista y a quien narra: no hay una lista de personajes para cargar de antemano (confirma la decisión 6; revisión del usuario, 2026-09-25).
    - Cada acto marca **quiénes están en escena**, y la Voz recibe solo a esos (más quien narra). Con muchos personajes, así evita meter a todos en todos los actos.
    - El Verificador avisa cuando un hecho nombra a alguien que no está en el elenco, y lo propone como personaje sin nombre.
    - Impacto en §7: `character` suma `kind` (`persona` / `sin_nombre` / `grupo`) y `relation` (qué es para quien narra); `act_outline` suma `on_stage` (JSON con los personajes en escena).

### Slices

#### S0 — Maquetas navegables
- `/maquetas/direccion`, `/maquetas/taller` y `/maquetas/escaleta`, con los datos de «la pena del colectivo» y las preguntas y la escaleta reales de las pruebas (`scripts/research/530/`).
- Controles visibles, aunque todavía no funcionen: opciones, «escribir la mía», «decidí vos», «intencional», semáforo por criterio, motivo de fin del taller, tarjetas de acto (hechos editables, escenario con opciones rápidas, reglas del acto, «+ personaje»), avisos del verificador.
- **Verificación:** revisión del usuario. Los cambios que pida van a §3 y §7 antes de S1.

#### S1 — Dominio (aditivo)
- `init_db()`: `story.direction` (JSON), tablas `story_workshop` y `act_outline`. No se borra nada.
- Modelos de dominio (`Direction`, `WorkshopItem`, `ActOutline`) y repositorios; `Story` los carga.
- YAML: `export-yaml` / `import-yaml` incluyen la dirección y la escaleta; los YAML viejos se importan igual.
- **Verificación:** unit de repos y round-trip YAML; pytest completo en verde; `make db` recrea sin errores.

**Hecho (2026-09-25).** Además de lo previsto:
- `Direction` guarda solo lo que el autor escribe; las decisiones del taller (meta, qué está en juego, historia secreta…) viven en `WorkshopItem`, sin duplicarse en la dirección. Esto ajusta §7.
- `character` suma `kind` y `relation` (§14); `act_outline` guarda el escenario y los personajes en escena **por nombre**, porque se reescriben con ids nuevos al editar.
- `update_inputs` (edición desde el wizard) no toca la dirección, el taller ni la escaleta: tienen sus propios métodos (`update_direction`, `save_workshop_items`, `save_outline`, `save_act`).
- `CreateStoryUseCase` ahora conserva el acto de cada regla (`applies_to_beat`, que antes se perdía al crear) y rechaza con `InvalidAuthoringError` (422) una escaleta o un taller inválidos, o un tipo de personaje desconocido.
- El YAML exporta las claves nuevas solo si existen: los YAML de las historias viejas salen idénticos.
- **Deploy:** es un cambio de esquema. El primer `make deploy` que incluya S1 necesita el pase de datos de prod (`export-yaml --all` → recrear `data/prod/stories.db` → `import-yaml`), ensayado antes sobre una copia. Sin eso, prod arranca con el esquema viejo y falla al guardar.

#### S2 — Salida estructurada y roles nuevos
- `response_schema` en el protocolo y en los adapters (Ollama `format`; Anthropic; Mock con un JSON por rol).
- Roles `consultor`, `planificador` y `verificador` en los perfiles de `llm_core_definitions.yaml`.
- Templates `consultant.md`, `outline_planner.md` y `outline_verifier.md`, con los criterios de §4 como preguntas operativas y la dirección del autor como contexto.
- Servicios `WorkshopConsultant`, `OutlinePlanner` y `OutlineVerifier`, más `WorkshopRules` (criterios determinísticos y condiciones de fin de §3.3).
- **Verificación:** unit con Mock (JSON válido, JSON inválido con reintento, filtro de «ya no suma», «intencional» respetado); prueba manual con `gemma3:12b` sobre «la pena del colectivo» (tiempos y calidad, contra §1.2).

**Hecho (2026-09-25).** Probado con `gemma3:12b` sobre «la pena del colectivo»: ronda del taller 7–17 s, escaleta ~45 s, revisión ~12 s, JSON válido siempre (también con `$ref`).
- `response_schema` en el protocolo: Ollama lo manda como `format`; Anthropic como `output_config.format` (`json_schema`), adaptado a sus límites (`additionalProperties: false`, sin `minItems`/`maxLength`…). Helper `generate_structured`: valida con Pydantic, reintenta una vez y después `LLMStructuredOutputError`.
- Roles `consultor`, `planificador` y `verificador` en los perfiles de `gemma3:12b`; en los demás heredan la config del `director`.
- Criterios en `config/workshop_criteria.yaml` y opciones de la Dirección en `config/authoring_options.yaml` (fuente única para la UI y los prompts). La teoría (`origen`) no va al prompt.
- **El historial del taller retroalimenta al modelo** (pregunta del usuario, 2026-09-25): cada ronda recibe las decisiones como pares pregunta → respuesta y las preguntas pendientes. Con eso, la escaleta revela la historia secreta en el Acto 4 (en la prueba de S0, sin el historial, se perdía).
- **Una pregunta sin responder no se reformula:** el Consultor tendía a reescribirla en cada ronda; se mantiene la original y solo se actualiza el semáforo. Una ronda sin preguntas nuevas termina en «no suma».
- El Verificador empujaba las convenciones del género («el final podría ser más ambiguo»): el prompt le prohíbe opinar sobre tono y estilo y discutir lo decidido por el autor. Máximo 2 avisos del LLM por acto, además de las reglas determinísticas.
- La amenaza no cuenta como elenco: el Planificador pone solo personas «en escena».
- **Para S5:** `llm_beats_definition.yaml` define el Acto 5 como «escape incompleto y secuela», que choca con un final intencional en paz. El Planificador ya prioriza el final del autor; la Voz tiene que hacer lo mismo.

#### S3 — API y jobs
- `PUT /stories/{id}/direction`; `GET/PATCH /stories/{id}/workshop` (responder, marcar intencional o completo); `GET/PUT /stories/{id}/outline` y `PATCH …/outline/{n}`.
- `POST /stories/{id}/jobs` con `kind` `consult` | `plan_outline` | `verify_outline`, con eventos y ETA como los jobs actuales.
- **Verificación:** tests de API (202/409/422) y de jobs con Mock.

**Hecho (2026-09-25).** Probado de punta a punta con `gemma3:12b` (API → JobManager → Ollama): taller 12 s (estimado 20), escaleta con revisión 56 s (estimado 60).
- Rutas bajo `/api/v1/authoring`: `GET /options`; `POST /stories` (crea el borrador desde la Dirección); `PUT /stories/{id}/direction` (guardado automático; deriva protagonista, relator, sinopsis y narrador); `GET /stories/{id}` (todo el estado de las 3 vistas, con el job activo); `PATCH /stories/{id}/workshop/{criterio}` (`answer` | `decide` | `intentional` | `reopen`, sin IA); `PUT /stories/{id}/outline/{n}` (guardado de un acto; los avisos quedan hasta revisar de nuevo). Con un job activo, todo guardado responde 409 con `X-Job-Id`.
- Jobs `consult`, `plan_outline` (Planificador + Verificador) y `verify_outline` por `POST /stories/{id}/jobs`, con etapas `consultor` / `planificador` / `verificador` y tiempo estimado. Precondiciones: dirección con «¿de qué trata?» (taller y escaleta), escaleta existente (revisión); si no, 422.
- El motivo de fin del taller se recalcula siempre desde lo guardado: `WorkshopItem.question_round` dice en qué ronda se hizo la pregunta vigente.
- El LLM simulado responde JSON coherente para cada rol (`mock_structured.py`): los tests de la API y los E2E recorren el flujo sin un modelo real.
- La banda de generación y el punto del sidebar ignoran los jobs del asistente: antes de esto, un análisis terminado habría mostrado «está lista · Leer relato». El aviso del asistente es su modal (S4).

#### S4 — Vistas reales
- Dirección, Taller y Escaleta con HTMX sobre los parciales de S0. «Nuevo relato» apunta al asistente; la ficha de una historia con escaleta enlaza a sus vistas.
- **Verificación:** Vitest de controllers y parciales; E2E con Mock: dirección → taller (1 ronda) → escaleta → generar → relato.

#### S5 — Pipeline con escaleta, Voz y memoria
- `DirectorUseCase`: si hay escaleta, los hechos, el escenario y las reglas del acto salen de ella (sin Mapper para ese acto; el Analyst sigue corriendo hasta decidir en S6).
- Prompt de la Voz para historias con escaleta (§8.1): sin perfil del narrador, «¿cómo lo cuenta?» en una línea, «ya contado» y «ya usado, no repetir», extensión proporcional a los hechos.
- Journal con `response_schema`: `hechos`, `estado` y `motivos_usados` (acumulados), y sin fallback silencioso.
- Control de repetición (§8.3) con clichés por lema; se muestra en el panel del relato.
- **Verificación:** snapshots nuevos para el camino con escaleta; los snapshots actuales **sin cambios** (regresión cero); E2E del relato con el aviso de repetición.

#### S6 — Medición
- `scripts/evaluate_workshop.py`: sobre «la pena del colectivo» y «El monte prohibido», 2 corridas cada una, compara la línea base (pipeline actual) contra el asistente con escaleta: tiempos por rol, criterios detectados, métricas del relato (§10).
- Con Analyst y sin Analyst, sobre las historias con escaleta.
- **Verificación:** informe en la spec (RESULTADOS). **Preguntar antes** de sacar el Mapper, el Analyst o el Resolver.

#### S7 — Limpieza del dominio (solo las filas de §6 aprobadas)
- Se eliminan las variables aprobadas (`traits`, `rule.type`, `rule.intensity`, las claves de `narrator_config`, `tono` → `direction.efecto`), el wizard viejo (`ui_definitions.yaml` y sus vistas y controllers) y lo que S6 permita del pipeline.
- Loader tolerante a los YAML viejos. Datos de prod: `export-yaml --all` → recrear la DB → `import-yaml` (probado antes contra una copia de `data/prod`).
- **Verificación:** suite completa en verde; los 3 YAML de `input_stories/` y los 3 de prod se importan y generan.

#### S8 — Cierre
- `CLAUDE.md`, estado de la spec y del roadmap. El pase a prod, cuando el usuario lo pida.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| El Consultor empuja convenciones del género por encima del autor (§1.2). | «Intencional» persistido y enviado en cada ronda; test de que un criterio intencional no vuelve a preguntarse. |
| El Planificador pierde decisiones o adelanta hechos (§1.3). | Verificador obligatorio después de planificar; la escaleta es editable y los avisos se ven en la tarjeta. |
| La escaleta queda desactualizada al cambiar la dirección. | Estado «a revisar» en `act_outline`; no se borra nada automáticamente. |
| Regresión en las historias viejas. | S1–S6 son aditivos; los snapshots actuales tienen que seguir iguales. |
| Tiempos: 3 roles nuevos en un 12B local. | Jobs con ETA (Spec-510); una llamada por ronda; tope de rondas. |
| Datos de prod en S7. | Backup automático de `make deploy` más un ensayo previo sobre una copia. |

### Qué necesita el usuario y cuándo

- **Antes de S0:** OK a este PLAN y a las decisiones 1–9.
- **Al cerrar S0:** feedback sobre las maquetas.
- **Antes de S7:** marcar las filas de §6 (se pueden validar con el uso de S4–S6).

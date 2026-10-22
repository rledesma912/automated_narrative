# SPEC-680: Recursos gastados del género, tics de la IA y el habla de quien narra

**Fecha:** 2026-10-10
**Tipo:** SDD — calidad (Planificador, Verificador, Voz, control de repetición)
**Estado:** TASKS (esperando OK); SPECIFY y PLAN aprobados 2026-10-22
**Rama:** `feat/spec-680-recursos-gastados` (desde `development`, `1e52f06`; la SPECIFY de A y B salió de `404085f` y ya está en `development`)
**Extiende:** Spec-470 (clichés de la Voz), Spec-530 §8.3 (control de repetición), Spec-590 (rasgos del narrador en la memoria), Spec-640 (anécdota, comparaciones), Spec-670 (moldes; su medición en §7).
**Suma (2026-10-22):** la parte C, «el mate en todas las historias» (iba a ser la Spec-690; se resuelve acá porque es el mismo síntoma: lo de manual en vez de lo propio de la historia).

---

## ASSUMPTIONS

1. Hay dos niveles distintos y hoy solo uno está cubierto:
   - **Frases gastadas de la prosa** («un escalofrío recorrió mi espalda»): **resuelto** desde la Spec-470 (`voice_cliches.txt`, 20 frases; el control de repetición las marca; 0 en las mediciones de la 650).
   - **Recursos gastados en lo que pasa** (huellas enormes, perros que ladran y se callan de golpe, una sombra enorme, ojos que brillan, golpes en la puerta): **sin cubrir**. Los arma el Planificador como hechos y la Voz los cuenta tal cual.
2. La máxima del pipeline: lo conceptual se resuelve antes (en «Los actos»); lo que solo aparece en la prosa se **detecta después y se muestra, nunca se corrige solo**. Cada regla nueva previene un error que se vio de verdad.
3. Lo que el autor escribió o eligió manda: si en su idea o en sus respuestas hay «huellas», no es un recurso gastado de la IA.
4. Textos en `config/` (Spec-620), avisos en tono coloquial (Spec-580).
5. (C) El sistema no sabe cómo habla quien narra: da por hecho que todo es rioplatense. Las pantallas siguen en voseo (se le habla a quien arma la historia, Spec-580); lo que cambia es la prosa y lo que la alimenta (Planificador, Voz, Memoria). Una historia sin el dato nuevo se comporta **igual que hoy**, como la forma `regla` de la 670.

---

## OBJECTIVE

Que los hechos y la prosa no caigan en lo de siempre:

**A. Recursos gastados del género (en «Los actos»).** Una lista de recursos de manual que el Planificador evita y que la revisión marca cuando aparecen, para que la historia busque señales propias de su lugar y sus personajes (como el balde de lata que salió con el giro en la medición de la 670).

**B. Tics de la IA en la prosa: enumerar de a tres.** La hija del usuario notó que la IA «enumera siempre tres cosas». Es un tic documentado de la escritura con IA (la «regla de tres» o *tricolon* aplicada de forma automática); el problema no es la figura sino su repetición mecánica.

**C. El habla de quien narra y sus gestos.** La hija del usuario notó que «el personaje toma mate, sea argentino o mexicano». Que la prosa suene como habla quien narra (una historia en un pueblo de México, con el español de México, sin voseo ni mate) y que sus gestos cotidianos salgan de esa persona y no del estereotipo de un país (una historia argentina sigue rioplatense, pero sin mate o termo en casi todos los relatos).

---

## 1. Relevamiento (2026-10-10)

### 1.1 Recursos gastados (medición de la Spec-670, §7)

La misma idea («La laguna oscura») con tres moldes, actos armados por Claude: aparecen en **los tres**, sin importar el molde.

| Molde | Menciones de manual | Cuáles |
|---|---|---|
| La de siempre | 5 | huellas (3), golpes (2) |
| Algo viene por nosotros | 7 | huellas, sombra, golpe, perros que ladran, chapoteo (2), rasca |
| Algo viene por nosotros + giro | 5 | huellas (3), golpe, perros que ladran |

En la prueba de la S1 (Claude) y en los actos de gemma: «huellas enormes», «el brillo de unos ojos», «una sombra enorme», «una figura oscura que desaparece al acercarse», «los perros del vecino ladran sin parar».

### 1.2 Enumerar de a tres (en la prosa de la Voz)

Contadas con un patrón estricto («A, B y C», cada ítem de hasta 4 palabras) en 5 relatos (8 042 palabras): **33**, unas **4 cada 1 000 palabras**, alrededor de **7 por relato**. Ejemplos: «unas luces amarillas, chiquitas y fijas», «Eran hondas, con tres dedos largos y anchos», «me acerqué al vidrio, apoyé las manos en el marco frío, entrecerré los ojos». El patrón todavía cuenta algunos falsos positivos (p. ej. «entre El Cruce y La Esperanza»): se afina en el PLAN.

Fuentes sobre el tic: [GPTZero — The Rule of Three](https://gptzero.me/news/the-rule-of-three/), [tropes.fyi — Tricolon abuse](https://tropes.fyi/tropes/tricolon-abuse), [Kompozy — AI Tells Index](https://kompozy.io/research/ai-tells-index) (índice curado, no un estudio), [LilysAI — La epidemia de escritura con IA](https://lilys.ai/es/notes/ai-writing-20260102/ai-writing-epidemic). Todas coinciden en que la figura es legítima y el problema es el uso reflejo; ninguna mide su frecuencia en un modelo concreto.

### 1.3 El mate y el habla (2026-10-22)

Ninguna instrucción dice «usá el mate». La suma sí:

| # | Dónde | Qué dice | Efecto |
|---|---|---|---|
| 1 | `outline_voice_system.md:5` | «Escribís solo prosa narrativa en **español rioplatense**» | Fija el habla y la cultura para cualquier historia. |
| 2 | `voice_craft.md:26` | «Usá solo palabras que existan en el **español rioplatense**» | Ídem, en la guía de oficio. |
| 3 | `voice_craft.md:11` y `authoring_options.yaml:42` (`caso`) | «se lo contás a alguien en una **sobremesa**», «habla **rioplatense** coloquial» | Escena de charla argentina. |
| 4 | `outline_voice_system.md:6` | «Sumá… tus gustos, tus manías… y **gestos chicos** (comer algo, prender la radio)… **Inventalos vos**» | Pide un gesto cotidiano inventado: con 1–3, el más probable es el mate o el termo. |
| 5 | `fragments/voz/asi_es.md` | «ASÍ ES {narrador} (**mantenelo**; podés sumar)» | Una vez anotado por la Memoria, el mate es un rasgo que vuelve en cada acto. |
| 6 | `outline_journal_system.md`, `authoring_planner_system.md:11` | «Español rioplatense» | La Memoria y los hechos de la escaleta, también. |
| 7 | `workshop_criteria.yaml:189` | «¿Qué objeto o costumbre común se vuelve raro… (**el mate**, la radio…)?» | Instala el mate como el objeto cotidiano por excelencia. |
| 8 | `mock_structured.py:34` | rasgo «toma mate amargo» | Solo tests y snapshots; sin efecto real. |

No hay ningún dato de país, región o habla en `Story` ni en `Direction` (`src/domain/models.py:190`).

Cuánto aparece: en prod, 1 de 6 relatos con mate (*El empleado del maletín*) y 3 memorias de acto con «Le gusta tomar mate.» (ninguna idea lo menciona; la hija ya corrigió a mano otros relatos); en dev, 1 de 1; en las evaluaciones (`scripts/research/530–650`), 19 menciones en 9 relatos, hasta 5 en uno; en las lecturas de rasgos de las Specs 590 y 600, «termo» en las dos. Prod tiene una historia mexicana, **«El trabajo de Yadira»** (Ximena, un pueblo de México), sin relato todavía: hoy saldría en voseo y con costumbres rioplatenses. Es el caso de la medición (D10).

**Base local (2026-10-22):** `data/dev/stories.db` es una copia de prod (9 historias, 6 relatos, esquema idéntico, `integrity_check` ok); la dev anterior quedó en `data/dev/backups/pre-copia-prod_2026-10-22/`.

---

## 2. Qué se construye

### A. Recursos gastados (Planificador + revisión)

- **`config/recursos_gastados.yaml`** (nuevo): cada recurso con un nombre, las raíces que lo detectan (como `voice_cliches.txt`) y una línea de por qué está gastado. Arranca con los vistos: huellas enormes, perros que ladran / se callan de golpe, sombra o figura enorme que desaparece, ojos que brillan en la oscuridad, golpes en la puerta en la noche, la luz que parpadea, el silencio repentino de los animales.
- **Planificador:** un bloque «RECURSOS GASTADOS (no los uses como hechos; si hace falta una señal, buscá una propia de este lugar y estos personajes)». Lo que el autor ya escribió (idea, respuestas, la amenaza) no entra en la lista para esa historia.
- **Revisión (sin IA, como las reglas del Verificador):** un aviso por acto cuando un hecho usa un recurso gastado que no viene del autor («Las huellas enormes ya se vieron en muchos cuentos: ¿hay una señal más de este lugar?»), con «Ignorar» como los demás avisos.
- **Medición:** `medir_moldes.py` lee la lista del YAML (hoy la tiene fija en el código).

### B. Enumerar de a tres (Voz + control de repetición)

- **Guía de oficio de la Voz** (`voice_craft.md`): una línea, como la de las comparaciones (Spec-640): no describir ni enumerar siempre de a tres; una cosa, dos, y de a tres solo cuando de verdad son tres.
- **Control de repetición:** cuenta las enumeraciones de tres por acto y avisa desde un umbral (con hasta 3 ejemplos), como las comparaciones y las oraciones cortadas. No corrige nada (máxima del pipeline). Al regenerar un acto, lo marcado vuelve a la Voz (`_avoid`).
- **Métrica** en `voice_metrics.py` para medir antes y después.

### C. El habla de quien narra y sus gestos (Planificador, Voz, Memoria + control de repetición)

**C1. El habla, elegida en «Tu idea».**
- **`config/hablas.yaml`** (nuevo), validado al arrancar como `config/moldes/`: cada habla con `id`, `label` (lo que ve la persona), `voz` (cómo escribe: trato —vos / tú / usted / vosotros—, léxico, «si dudás, elegí la palabra más simple») y `ajenas` (raíces que no van en esa habla, para C3). Cuatro: **rioplatense** (la de siempre, la primera), **mexicano**, **neutro** y **español de España**.
- **`Direction.habla`** (`""` o un id que no existe → rioplatense). En «Tu idea», un selector «¿Cómo habla quien lo cuenta?» (`.opcion-forge`), con la de siempre elegida. **Lo decide la persona; la IA no lo sugiere** (D11). Round-trip en `export-yaml` / `import-yaml`.
- **Planificador, Voz y Memoria** reciben el habla en lugar del «rioplatense» fijo (puntos 1, 2, 3 y 6 de §1.3). En la Voz va como un fragmento `voz/habla`; `caso` («Como un caso entre amigos») pierde «rioplatense»: la forma de contarlo no decide el habla.
- **Consultor, Verificador y FormSuggester no cambian:** le hablan a quien arma la historia.

**C2. Gestos propios, no los de manual.**
- `outline_voice_system.md`: los gestos chicos salen de **quién es quien narra, su trabajo y el lugar de esta historia**, no de las costumbres típicas de un país; ejemplos que no sean de un país.
- **Gestos gastados** como una sección de `recursos_gastados.yaml` (A): mate, termo… La Voz los evita salvo que vengan del autor (idea, respuestas, escaleta, la amenaza; mismo criterio que `_motifs_for` y D3).
- **Rasgos de la memoria (`asi_es`):** «mantenelo» pasa a «no lo contradigas; no hace falta que aparezca en cada acto» (D13).
- `workshop_criteria.yaml:189` y el mock: ejemplos sin mate.

**C3. Detectar después (control de repetición, sin IA).**
- **Gesto gastado** que no viene del autor: aviso en el panel del relato y en «Corregir el relato».
- **Palabras de otra habla:** raíces de `ajenas` del habla de la historia (en mexicano y neutro, el voseo —«vos», «mirá», «contás»— y «che», «pibe», «laburo»…; en España, además, lo americano que no va). Aviso con hasta 3 ejemplos. Rioplatense, sin `ajenas` (D14).
- Al regenerar un acto, lo marcado vuelve a la Voz (`_avoid`). Nada se corrige solo. Métrica en `voice_metrics.py`.

---

## 3. Decisiones

| # | Duda | Recomendación |
|---|---|---|
| D1 | ¿Qué quiso decir la hija con «enumera tres cosas»? | **La prosa** (confirmado por el usuario, 2026-10-22): lo medido en §1.2. Las 3 opciones del asistente no se tocan. |
| D2 | ¿Prohibir o evitar? | **Evitar**, con alternativa («buscá una señal propia»), y **marcar** lo que igual aparezca. Ningún recurso se borra solo. |
| D3 | ¿Y si el recurso lo eligió el autor? | Manda el autor: lo que está en su idea, sus respuestas o la ficha de la amenaza no se evita ni se marca (mismo criterio que `_motifs_for` de la Voz). |
| D4 | Umbral de las tríadas | Aviso desde la **tercera** del acto (una o dos son naturales en una anécdota); se ajusta con la medición. |
| D5 | Medición | Antes/después con `medir_moldes.py` (solo actos, ~US$ 0,10) para A, y `evaluate_voice.py` (relato corto, ~US$ 0,15) para B; las dos pagas, con aviso de costo y OK. |
| D10 | Medición de C | `evaluate_voice.py` con **«El trabajo de Yadira»** (exportada de la copia local de prod, habla mexicana) y «El monte prohibido» (rioplatense), 2 corridas cada una, relato corto, antes y después: ~8 relatos, unos US$ 0,40. Paga, con aviso y OK. Se puede correr junto con la de B. |
| D11 | ¿Quién decide el habla? | **La persona, con el selector** (decidido por el usuario). La IA no la sugiere. |
| D12 | ¿El habla es de quien narra o del lugar? | **De quien narra** (narra en primera persona): un argentino que vive en México narra en rioplatense. El lugar ya está en la idea y en los escenarios. |
| D13 | ¿Cambiar «mantenelo» de los rasgos? | **Sí**: lo que había que evitar en la 590 era la contradicción, no la ausencia. |
| D14 | ¿Marcar regionalismos en una historia rioplatense? | **No** en la primera versión: es la base y no se vio un problema. |
| D15 | ¿Nombrar el mate en el prompt de la Voz? | Sí, en la lista de gestos gastados con «salvo que esté en los EVENTOS» (Sonnet 5.5 respeta listas de prohibidos: los clichés bajaron a 0 en la 650). Si la medición muestra que lo empeora, se saca y queda solo la detección. |
| D16 | ¿Y el paquete para el video (Spec-610)? | **Fuera de alcance**: la calabaza y el canal son rioplatenses por diseño (`presentador.yaml`). Se revisa si aparece un problema real. |

---

## 4. SUCCESS CRITERIA

1. En la medición de la 670 repetida (mismos 3 moldes), las menciones de recursos gastados en los hechos bajan **al menos a la mitad**, sin perder hechos concretos.
2. Lo que escribió el autor nunca se marca ni se evita (test).
3. Las enumeraciones de tres en la prosa bajan (meta: menos de 2 cada 1 000 palabras) sin subir las oraciones cortadas ni el diálogo.
4. Los avisos de los dos tipos aparecen en «Los actos» y en el panel del relato, con «Ignorar» (A) y sin corregir nada solo.
5. (C) En la medición (D10), «El trabajo de Yadira» sale **sin voseo y sin mate ni termo** en las 2 corridas; en «El monte prohibido», las menciones de mate o termo bajan a **0 o 1 por relato** (hoy hasta 5), sin subir clichés, oraciones cortadas ni diálogo.
6. (C) Una historia sin `habla` genera prompts iguales a los de antes salvo las líneas de C2 (diff de snapshots revisado); snapshot nuevo `voice_prompts_mexicano.json` con su test.
7. Snapshots actualizados a propósito; guardianes y tests en verde; dev con el cambio.

## BOUNDARIES

- **Always:** listas en `config/`; detectar y mostrar, nunca corregir solo; respetar lo que escribió el autor.
- **Ask first:** corridas pagas; cambiar el registro de la Voz más allá de una línea de la guía; sumar hablas además de las cuatro de C1; tocar el paquete para el video.
- **Never:** reescribir la prosa automáticamente; prohibir algo que el autor eligió; cambiar el tono de las pantallas (siguen en voseo); columnas nuevas o migraciones (`habla` vive en el JSON de `direction`).

## OPEN QUESTIONS

- ¿La lista de recursos gastados la amplía el usuario (como la de clichés) o solo el desarrollo? Propuesta: un YAML editable por quien desarrolla; más adelante, si hace falta, desde la pantalla.

---

## 5. PLAN (2026-10-22)

Relevado en `feat/spec-680-recursos-gastados` (`2f88bfa`). Principio, como en la 650 y la 670: **una sola fuente en `config/`** y la historia de siempre (rioplatense, sin nada nuevo elegido) con prompts **iguales a hoy** salvo las líneas que esta spec cambia a propósito.

### 5.1 Decisiones nuevas que salieron de la revisión

| # | Riesgo encontrado | Decisión recomendada |
|---|---|---|
| D17 | Un archivo y un validador nuevos solo para cuatro opciones de habla. | Las hablas van en `config/authoring_options.yaml` como sección `hablas:`, igual que `como_lo_cuenta` (`catalog.hablas()`, `Option` con `voice`; `ajenas` aparte). Mismo camino a la UI: `/authoring/options`. Reemplaza el `config/hablas.yaml` de C1. |
| D18 | **«mate» se confunde con «matar».** El control de clichés compara raíces de 3 letras (`_same_root`): «mate» y «matar» serían lo mismo, y «que me mate» marcaría un gesto gastado. | Lo gastado (recursos, gestos y palabras de otra habla) se detecta con **patrones** (regex) escritos en el YAML: `\b(un|el|otro|unos|los) mates?\b`, `\btermo\b`, `\bceb(ar|é|ó|aba)\b`, `\bhuellas?\b`. Test con «que me mate» y «el mate». |
| D19 | **¿Qué es «lo del autor»?** `known_text()` incluye la escaleta, pero en A la escaleta la escribió el Planificador: si se usa, las huellas que él inventó se perdonarían solas. | Dos textos: `author_text(story)` = idea, final, respuestas del taller, personajes, lugares, reglas y amenaza (**sin** la escaleta): es lo que exime en A. En la prosa (C3) exime `known_text()` (con la escaleta, que el autor confirmó): si un hecho dice «toma mate», la Voz puede contarlo. |
| D20 | Los avisos de recursos gastados compiten con los demás en el tope de 3 visibles por acto. | Van con `source="regla"` y clave estable `gastado:<id>` (se ignoran como cualquier aviso, H10), **después** de los de estructura **y de los de la IA** (continuidad, hechos repetidos): primero lo que rompe, después lo de estilo (ajustado en S4). |
| D21 | Falsos positivos de las tríadas (§1.2: «entre El Cruce y La Esperanza»). | Patrón «A, B y C» con ítems de hasta 4 palabras, **sin** ítems que empiecen con mayúscula a mitad de oración (nombres propios); aviso desde la tercera del acto (D4). Casos de prueba en un fixture compartido con `voice_metrics.py`. |
| D22 | Qué escribe cada habla nueva. | `voz` por habla: **mexicano** = tú y ustedes, léxico de México; **neutro** = tú y ustedes, sin regionalismos marcados; **España** = tú y vosotros, léxico peninsular. `ajenas`: voseo y rioplatenses («vos», «sos», «mirá», «che», «pibe», «laburo»…) en las tres; en España, además, americanismos claros («celular», «manejar», «carro»…). **El contenido (los textos y las listas) te lo paso para leer antes de seguir**, como el catálogo de la 670. |
| D23 | Medición sin gastar de más, **con el perfil de prod** (`hibrido-sonnet55`: la Voz en Claude, el resto en gemma; el usuario lo confirmó el 2026-10-22, prod sigue híbrido). | **Antes:** 1 corrida de «El trabajo de Yadira» con el código de hoy (muestra lo que vio tu hija); la base de B y del mate en «El monte prohibido» ya está medida (§1.2 y §1.3). **Después:** Yadira (largo, su escaleta, habla mexicana) ×2, «El monte prohibido» (corto) ×2, `medir_moldes.py` (A) ×1. El estimador da ~US$ 0,13 por relato (la 600 midió 0,09 reales): total estimado **US$ 0,50 a 0,70**; cada corrida, con aviso de costo y OK. Neutro y España **no** se miden con relatos generados a propósito: los validan los relatos nuevos que generen las chicas (usuario, 2026-10-22). |
| D24 | El YAML de Yadira es una historia real de prod. | Se exporta a `data/dev/research_680/` (ignorado por git) y no se commitea; en `scripts/research/680/` van solo las métricas y los relatos medidos, si das el OK. |

### 5.2 S1 — Cómo habla quien narra (C1)

| Lugar | Cambio | Precaución |
|---|---|---|
| `authoring_options.yaml` | `hablas:` con `id`, `label`, `prompt` («español rioplatense»), `voz` (trato y léxico; **vacío en rioplatense**) y `ajenas` (patrones; vacío en rioplatense). `caso` pierde «rioplatense». | `caso` cambia una línea en todos los snapshots: diff revisado. |
| `catalog.py` | `hablas()` y `habla_de(story)` (`""` o un id que no existe → la primera, D16 de la 670) | Test: un id viejo cae a rioplatense. |
| `Direction` + `DirectionForm` + `_direction` / `_form` (`authoring_router.py`) | `habla: str = ""`; viaja en el formulario (la elige la persona) | El autoguardado rearma `Direction` entero (D13 de la 670): test de que se guarda y vuelve. |
| `outline_voice_system.md`, `voice_craft.md` (LÉXICO), `outline_journal_system.md`, `authoring_planner_system.md` | «español rioplatense» → `{habla}` (el `prompt` del habla); en la Voz, la línea `voz` del habla bajo LÉXICO (no aparece en rioplatense) | Con rioplatense, esos cuatro textos quedan **idénticos**. |
| `outline_narrator.py` (Voz y Memoria), `prompt_builder._voice_extras`, `planner.system_prompt` | Pasan el habla de la historia | Consultor, Verificador y FormSuggester no se tocan. |
| `direccion.ejs` + `asistente.js` | «¿Cómo habla quien lo cuenta?», `.opcion-forge` compactas debajo de «¿Cómo lo cuenta?», la de siempre elegida | Guardianes `sin-jerga`, `gramatica-visual`; fixtures del asistente (`UPDATE_FIXTURES=1`, diff revisado). |
| Export / import YAML | Viaja dentro de `direction` (el exportador ya la vuelca entera) | Test de ida y vuelta. |

**Tests:** `voice_prompts_mexicano.json` (snapshot nuevo) con su test de secciones: dice «español de México», no dice «rioplatense» ni «sobremesa rioplatense»; el Consultor sigue en voseo con cualquier habla.

### 5.3 S2 — Lo que la Voz evita (C2 + B en la guía)

| Lugar | Cambio |
|---|---|
| `config/recursos_gastados.yaml` (nuevo) | Dos listas con la misma forma (`id`, `nombre`, `detecta`: patrones, `por_que`): `hechos` (A: huellas enormes, perros que ladran o se callan, sombra o figura que desaparece, ojos que brillan, golpes en la puerta, la luz que parpadea, el silencio de los animales) y `gestos` (C2: el mate, el termo y la yerba; se suman otros si la medición los muestra). Un cargador con validación (`recursos_gastados.py`, como `voice_cliches.py`). |
| `outline_voice_system.md` | Los gestos chicos salen de quién es quien narra, su trabajo y el lugar de esta historia, no de las costumbres típicas de un país; ejemplos sin país. |
| Fragmento `voz/gestos_gastados` | «GESTOS QUE YA SE VIERON EN MUCHOS RELATOS (no los uses salvo que estén en los EVENTOS): …», sin los que vengan del autor (D19, con escaleta). |
| `voice_craft.md` | B: una línea, como la de las comparaciones: no describir ni enumerar siempre de a tres. |
| `fragments/voz/asi_es.md` | «mantenelo» → «no lo contradigas; no hace falta que aparezca en cada acto» (D13). |
| `workshop_criteria.yaml:189`, `mock_structured.py` | Ejemplos sin mate. |

### 5.4 S3 — Detectar en la prosa (C3 + B)

| Lugar | Cambio |
|---|---|
| `repetition_check.py` | `ActRepetition` suma `gestos` (los gastados que no vienen del autor), `ajenas` (hasta 3 ejemplos, según el habla de la historia) y `triadas` / `triad_count` (aviso desde la tercera, `too_listy`). `check()` recibe el habla y lo del autor. |
| `narrative_router.py` (`/repetition`), `relato_panel.ejs`, `corregir-relato.js` | Los tres avisos nuevos, con «Buscar» en «Corregir el relato», como las comparaciones. |
| `outline_narrator._avoid` + `fragments/voz/evitar/` | `gestos.md`, `ajenas.md`, `triadas.md`: al regenerar un acto, lo marcado vuelve a la Voz. |
| `scripts/voice_metrics.py` | Métricas: mate y termo, palabras de otra habla, tríadas cada 1 000 palabras. |

### 5.5 S4 — Recursos gastados en los hechos (A)

| Lugar | Cambio |
|---|---|
| `authoring_planner.md` + fragmento `asistente/planificador/recursos_gastados` | «RECURSOS GASTADOS (no los uses como hechos; si hace falta una señal, buscá una propia de este lugar y estos personajes)», sin los que trae el autor (D19, sin escaleta). |
| `verifier.rule_warnings` | Aviso `gastado:<id>` por acto cuando un hecho usa uno que no viene del autor (D20); texto en `core_messages.yaml` (`verifier.gastado`). |
| `scripts/research/670/medir_moldes.py` | Lee la lista del YAML. |

**Ojo:** hoy prod usa `hibrido-sonnet55`, donde el Planificador es **gemma**, que respeta peor las listas de prohibidos: por eso el aviso del Verificador es la red. Prod sigue híbrido (D23), así que la medición de A muestra cuánto evita gemma y cuánto queda para el aviso.

### 5.6 S5 — Medición y cierre

Medición D23 (con aviso de costo y OK en cada corrida). Resultados en §7. CLAUDE.md (hablas, recursos gastados, avisos nuevos del control), memoria, PR a `development`. Dev: `make dev-status` y la URL para validar en cada slice.

### 5.7 Slices

0. **S0 — Medición «antes»** de Yadira (1 corrida, ~US$ 0,09).
1. **S1 — El habla.** Antes del código, te paso el contenido de las cuatro hablas para leer (D22).
2. **S2 — Lo que la Voz evita** (gestos, tríadas en la guía, rasgos).
3. **S3 — Detectar en la prosa** (gestos, otra habla, tríadas).
4. **S4 — Recursos gastados en los hechos.**
5. **S5 — Medición «después» y cierre.**

Cada slice cierra con tests en verde y dev mostrando el cambio (la base de dev es la copia de prod: las 9 historias reales sirven para mirar).

---

## 6. TASKS (2026-10-22)

Perfil de medición: el de prod, **`hibrido-sonnet55`** (D23). Rioplatense: en vez de «El monte prohibido», `scripts/research/650/no_te_detengas_corto.yaml`, que ya tiene la base medida con el mismo código de la Voz (`650/corto/relato_{1,2}.txt`: 2 mates en cada uno). Tests: `make test`, `cd frontend && npm test`, `npx playwright test`, `make lint`.

### S0 — Medición «antes»

- **T0.1** Exportar «El trabajo de Yadira» de la base local (copia de prod) a `data/dev/research_680/yadira.yaml` (`export-yaml`, D24). **Hecho cuando:** el YAML trae su dirección, su taller y sus 5 actos.
- **T0.2** `evaluate_voice.py --profile hibrido-sonnet55 --input data/dev/research_680/yadira.yaml --runs 1 --label 680-antes --out data/dev/research_680/antes` (aviso de costo y OK). **Hecho cuando:** relato con métricas; se cuentan a mano voseo, mate y termo, y tríadas (las métricas nuevas todavía no existen).

### S1 — El habla (C1)

- **T1.1** Redactar las cuatro hablas (`label`, `prompt`, `voz`, `ajenas`; D22) y pasártelas para leer (artifact, sin código). **Hecho cuando:** tu OK o tus cambios.
- **T1.2** `authoring_options.yaml` → `hablas:`; `catalog.hablas()` / `habla_de(story)` con caída a la primera; `caso` sin «rioplatense». **Hecho cuando:** tests del catálogo (ids únicos, rioplatense primero, id viejo → rioplatense, cada `ajenas` compila como regex).
- **T1.3** `Direction.habla`, `DirectionForm`, `_direction` / `_form`, `_state` y `/authoring/options` (`hablas`). **Hecho cuando:** test de que el autoguardado la guarda y vuelve, y round-trip YAML con `habla`.
- **T1.4** `{habla}` en `outline_voice_system.md`, `voice_craft.md` (LÉXICO + línea `voz`), `outline_journal_system.md`, `authoring_planner_system.md`; el habla llega a `_voice_extras`, `voice_prompts`, `remember` y `planner.system_prompt`. **Hecho cuando:** con rioplatense, los snapshots cambian **solo** en la línea de `caso` (diff revisado y regenerados con `SNAPSHOT_UPDATE=1`); snapshot nuevo `voice_prompts_mexicano.json` con su test (dice el habla de México y no dice «rioplatense»); el Consultor y el Verificador siguen en voseo con habla mexicana.
- **T1.5** UI: «¿Cómo habla quien lo cuenta?» en `direccion.ejs` + `asistente.js`. **Hecho cuando:** Vitest (vista y guardianes `sin-jerga`, `gramatica-visual`), fixtures del asistente con `UPDATE_FIXTURES=1` (diff revisado), E2E: elegir «mexicano», recargar, sigue elegida.
- **T1.6** Cierre: tests y lint en verde; dev: elegir «mexicano» en «El trabajo de Yadira» (copia local) y ver el prompt de la Voz en `/debug`.

### S2 — Lo que la Voz evita (C2 + B en la guía)

- **T2.1** `config/recursos_gastados.yaml` (`hechos` y `gestos`, D18) y `recursos_gastados.py` (carga, validación, `vienen_del_autor(story, texto)` con los dos textos de D19: `author_text` nuevo y `known_text`). **Hecho cuando:** tests: «que me mate» no es un gesto, «el mate» sí; un recurso que está en la idea del autor no se cuenta.
- **T2.2** `outline_voice_system.md` (gestos propios, ejemplos sin país), fragmento `voz/gestos_gastados` (sin los que vienen del autor), `voice_craft.md` (línea de las tríadas), `voz/asi_es.md` (D13). **Hecho cuando:** snapshots regenerados con el diff revisado; test: con «toma mate» en un hecho del acto, el mate no está en la lista de gestos de ese acto.
- **T2.3** `workshop_criteria.yaml:189` y `mock_structured.py` sin mate. **Hecho cuando:** `grep` de «mate» en `config/` y `src/` solo encuentra la lista de gestos gastados.
- **T2.4** Cierre: tests en verde; dev: escribir de nuevo un acto de una historia rioplatense y mirar el prompt en `/debug`.

### S3 — Detectar en la prosa (C3 + B)

- **T3.1** `repetition_check.py`: `gestos`, `ajenas` (con el habla de la historia), `triadas` / `triad_count` / `too_listy` (D21, aviso desde la tercera); `has_findings` las suma; `last_version_findings` pasa el habla y lo del autor. Fixture compartido `tests/fixtures/repeticion/triadas.json` (casos positivos y negativos de §1.2). **Hecho cuando:** tests con cada caso; el relato de la 650 marca sus 2 mates; voseo en rioplatense no avisa.
- **T3.2** `narrative_router` (`/repetition`), `story.service.ts`, `relato_panel.ejs` y `corregir-relato.js` (con «Buscar»). **Hecho cuando:** Vitest de la vista con los tres avisos; guardianes en verde.
- **T3.3** `_avoid` + `fragments/voz/evitar/{gestos,ajenas,triadas}.md`; `fragments/README.md`. **Hecho cuando:** snapshot de la Voz al regenerar con los tres avisos.
- **T3.4** `voice_metrics.py`: mate y termo, palabras de otra habla, tríadas cada 1 000 palabras (con el mismo detector). **Hecho cuando:** medido sobre `650/corto/` y `600/hibrido/` da la base para comparar.
- **T3.5** Cierre: dev: el panel de «El empleado del maletín» (copia local) avisa su mate.

### S4 — Recursos gastados en los hechos (A)

- **T4.1** Fragmento `asistente/planificador/recursos_gastados` en `authoring_planner.md` (sin los del autor, D19: sin escaleta). **Hecho cuando:** snapshot del asistente regenerado; test: con «huellas» en la idea, no aparecen en la lista.
- **T4.2** `verifier.rule_warnings`: `gastado:<id>` después de los de estructura (D20); `verifier.gastado` en `core_messages.yaml`. **Hecho cuando:** tests: aviso con un hecho de manual, sin aviso si viene del autor, «Ignorar» lo deja ignorado al revisar de nuevo.
- **T4.3** `scripts/research/670/medir_moldes.py` lee la lista del YAML.
- **T4.4** Cierre: dev: «Revisar los actos» de «La laguna oscura» muestra el aviso de las huellas.

### S5 — Medición «después» y cierre

- **T5.1** Yadira con `habla: mexicano` ×2 y `no_te_detengas_corto.yaml` ×2 (`--profile hibrido-sonnet55`), `medir_moldes.py` ×1 con el perfil activo (`hibrido-sonnet55`) (aviso de costo y OK en cada una). **Hecho cuando:** resultados en §7 contra los criterios 1, 3 y 5 de §4 y la base de S0 / §1.
- **T5.2** CLAUDE.md (hablas en `authoring_options.yaml`, `recursos_gastados.yaml`, avisos nuevos del control, `Direction.habla`), memoria, PR a `development`.

---

## 7. Resultados

### S0 — «Antes» (2026-10-22, `hibrido-sonnet55`, US$ 0,10 reales)

«El trabajo de Yadira» (largo, su escaleta, código de hoy), 1 corrida, 2 162 palabras. Relato en `data/dev/research_680/antes/` (fuera de git, D24).

| Qué | Resultado |
|---|---|
| Mate, termo | **0**: con la escaleta y la idea ancladas en México, la Voz no lo inventó. |
| Léxico mexicano | Lo toma bien de la escaleta: tienda de abarrotes, veladoras, refrescos, papitas, limpias, doña Aurelia. |
| Rioplatense que se cuela | **Voseo** en la narración («todos saben a qué hora **abrís** la cortina y qué **comprás**»), «la **plata**», «la **vereda**», «una risa **media** nerviosa». Pocos, pero suenan raros para una narradora mexicana: el «español rioplatense» del prompt sigue mandando en el trato y en las palabras de todos los días. |
| Tríadas | 10 (4,6 cada 1 000 palabras), en línea con §1.2. |
| Otras métricas | 0 clichés, 0 diálogo, 3 % de oraciones cortadas, 1 comparación. |

Base rioplatense («No te detengas en el bosque», corto, `650/corto/`): **2 mates en cada relato**.

**Qué cambia para el plan:**
- En S0 el mate no apareció: el problema del mate se ve sobre todo en las historias rioplatenses (C2 y C3 siguen igual). En la historia mexicana lo que aparece es **el habla** (C1).
- Para la detección (C3, D22): el voseo se reconoce por los verbos con tilde final de segunda persona (`abrís`, `comprás`, `tenés`), no solo por «vos». El detector usa una lista de excepciones (`más`, `después`, `atrás`, `detrás`, `demás`, `jamás`, `además`, `país`, `través`…). «Nomás» **no** va en `ajenas` del mexicano: también se dice allá.
- Los patrones de tríadas de borrador cruzan cláusulas («lo cambié por otro, le pedí disculpas y pensé que…»): D21 los acota a ítems sin verbo conjugado (se reusa `has_finite_verb`) o separa las tríadas de acciones.

### S1 — El habla (2026-10-22)

- `hablas:` en `authoring_options.yaml` (rioplatense, mexicano, neutro, España; D17), `catalog.hablas()` / `habla_de()`, `Direction.habla`, `/authoring/options` (`hablas`), 422 con un habla que no existe.
- La Voz (sistema y LÉXICO de la guía), la Memoria y el Planificador dicen el habla de la historia; Consultor, Verificador y la IA de la forma siguen en voseo (test).
- Con rioplatense, los snapshots cambiaron **solo** en la línea de `caso` («habla coloquial»; verificado línea por línea). Snapshot nuevo `voice_prompts_mexicano.json`.
- Voseo detectado por la tilde final de segunda persona con excepciones («nomás», «quizás», «después», «estás»…), probado con lo que se coló en S0.
- UI: «¿Cómo habla quien lo cuenta?» en «Tu idea», la de siempre elegida en las historias viejas. Vitest (`hablas.view.test.ts`) y E2E (elegir «De México», recargar).
- Tests: 994 pytest, 416 Vitest, 79 E2E (78 + el nuevo), lint en verde. Los E2E pasan a **Firefox** (pedido del usuario: no Chrome); en Ubuntu 26.04 se instala con `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64 npx playwright install firefox` (Playwright todavía no soporta esa versión). «Copiar» se prueba con las preferencias de portapapeles de Firefox en vez del permiso `clipboard-read` (solo existe en Chrome). Suite completa en Firefox: 79 en verde.

### S2 — Lo que la Voz evita (2026-10-22)

- `config/recursos_gastados.yaml` (`hechos`: 7 de manual; `gestos`: el mate, con cebar, el termo y la yerba) y `recursos_gastados.py` (carga con validación, `author_text` sin los actos y `gestos_a_evitar` con ellos, D19). «que me mate», «lo mate» y «un color mate» no cuentan (D18, test).
- Voz: los gestos chicos salen de quién es, su trabajo y el lugar, «no de las costumbres típicas de un país» (ejemplos: acomodar algo, mirar la hora); línea «Gestos que ya se vieron en muchos relatos (no los uses; buscá otros)», que no va si el mate está en lo del autor o en los actos; guía de oficio: no enumerar siempre de a tres (B); rasgos: «no lo contradigas; no hace falta que aparezca en cada acto».
- Sin mate en `config/` ni `src/` fuera de la lista (criterio del giro, mock, datos de los snapshots).
- Snapshots regenerados: el diff son exactamente esas cuatro líneas y el rasgo del mock. 1 013 pytest, 416 Vitest, lint en verde.

### S3 — Detectar en la prosa (2026-10-22)

- `repetition_check`: `gestures` (los gastados que no trae el autor), `foreign` / `foreign_count` (los `ajenas` del habla de la historia, solo en la narración) y `triads` / `triad_count` / `too_listy` (desde la tercera, D4). `story_context(story)` junta lo del autor, el habla y los gestos para el panel y para regenerar.
- Tríadas (D21): «A, B y C» en una oración, ítems de 1 a 4 palabras, C hasta el final de su tramo, sin nombres propios. Con eso el «antes» de Yadira baja de 10 (el conteo de borrador cruzaba frases) a 1; los de la 650, 5 y 1. Quedan afuera tríadas de acciones largas («hacía limpias, conocía remedios para todo y tenía fama de saber cosas»): es a propósito, para no avisar de más.
- Panel del relato y «Corregir el relato» (con «Buscar»): «Un gesto que ya se vio en muchos relatos», «Palabras que no van con cómo habla quien lo cuenta», «Enumera de a tres». Al regenerar, vuelven a la Voz (`voz/evitar/{gestos,ajenas,triadas}`).
- `voice_metrics.py` / `evaluate_voice.py`: `gestos_gastados` (una vez por aparición), `otra_habla`, `de_a_tres_cada_1000`. Base: 600/híbrido 5 y 3 gestos; 650/corto 2 y 2; Yadira «antes» 5 palabras de otra habla, 0 gestos, 0,5 de a tres cada 1 000.
- Dev (copia de prod): el panel de «El empleado del maletín» avisa «un mate» en el acto 1.
- 1 026 pytest, 418 Vitest, lint en verde.

### S4 — Recursos gastados en los hechos (2026-10-22)

- Planificador: bloque «RECURSOS GASTADOS (ya se vieron en muchos cuentos: no los uses como hechos; si hace falta una señal, buscá una propia de este lugar y de estos personajes)» con los 7 de `hechos`, sin los que trae el autor (D19, sin los actos). Snapshots: el diff es solo ese bloque (14 prompts).
- Verificador: `worn_warnings` → aviso `gastado:<id>` por acto (««huellas»: huellas enormes… ya se vio en muchos cuentos. ¿Hay una señal más propia de este lugar o de estos personajes?»), **después** de los de la IA (D20); «Ignorar» lo deja ignorado; no avisa lo que trae el autor.
- `medir_moldes.py` suma `gastados` con la lista del YAML (y sigue contando `de_manual` para comparar con la 670). Base con la lista nueva sobre los actos de la 670 (Claude): regla 5, asedio 3, asedio + giro 4.
- Dev (copia de prod): en las 9 historias reales, los recursos de manual que aparecen en los actos (la luz, los ojos, los golpes) **vienen todos de lo que escribió la autora**: ninguno se avisa. Es la prueba de que D19 hacía falta.
- 1 029 pytest, lint en verde.

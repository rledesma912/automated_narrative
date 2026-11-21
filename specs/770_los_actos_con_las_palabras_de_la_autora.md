# SPEC-770: los actos con las palabras de la autora

**Fecha:** 2026-11-21
**Tipo:** SDD: prompt del Planificador (config), medición
**Estado:** IMPLEMENT (OK al alcance del usuario el 2026-11-21). S1, S2 y S4 hechos: la Parte A cumple (con las ideas cortas, con el criterio de D5) y la Parte B no hace falta. En prod el 2026-11-21.
**Rama:** `feat/spec-770-palabras-de-la-autora` (desde `development`)
**Extiende:** Spec-530 (escaleta), Spec-720 (el Planificador en la nube), Spec-760 (ideas largas; la medición de S3).

---

## ASSUMPTIONS

1. Lo pidió el usuario el 2026-11-21. La medición de la Spec-760 (S3) mostró que **la IA resume la idea al armar los actos**, y la autora (Yael) confirmó que por eso volvía a meter su texto en los hechos a mano.
2. **No se suman pasos a la UI** (Spec-760 D5). El arreglo va donde hoy se arman los actos (job `plan_outline`), sin llamadas nuevas a la IA si se puede.
3. La medición la corre Claude, sin validación del usuario. La calidad la juzgan las autoras con el uso.
4. Prod arma los actos con GPT-5.6 Sol (`openai-sol`). El perfil local (gemma) no se optimiza en esta spec.
5. **Esta spec autoriza cambiar el prompt del Planificador** (la Spec-760 lo dejaba afuera). Los snapshots de los prompts se regeneran a propósito.

## OBJECTIVE

Que los actos que arma la IA cuenten la historia **con las palabras y los detalles de la autora**, para que no tenga que reescribirlos a mano.

**Éxito:**
- En las ideas del «ritual», lo que llega de la idea a los hechos armados por la IA pasa del 56 % a **≥ 70 %**, cerca del 72 % que logró Yael a mano. Se mide con la misma cuenta de la Spec-760.
- Ningún hecho pasa de 800 caracteres (el tope de la Spec-760). Los hechos no suman más palabras que la idea.
- Con una idea corta, la IA **no inventa** detalle para llenar: los hechos no crecen más de lo que crece el texto de la autora.
- La estructura no empeora: el final de la idea queda en el último acto y no suben los avisos del Verificador.

---

## 1. Relevamiento (2026-11-21)

### 1.1 Qué pierde la IA

Se comparó «Culpable» (917 palabras, Corto) armada por la IA en la medición de la Spec-760 con la versión que dejó Yael después de editarla durante unas dos horas:

| | Lo que arma la IA | Lo que deja Yael |
|---|---|---|
| Largo de cada hecho | 200–290 caracteres | 230–400 (chocaba con el tope de 400) |
| Detalle | «cabezas humanas que mueven la boca sin sonido» | «Todas tienen los ojos abiertos y las bocas se mueven, como si intentaran decir algo, pero no emiten ningún sonido» |
| Lo que siente el personaje | «empieza a ahogarse… y trata de respirar despacio» | El mismo ahogo, más «La experiencia reproduce el pánico que él había desestimado» (lo que une el viaje con la culpa) |
| Momentos por hecho | Un hecho del último acto junta tres: despierta en la puerta, cierra el ritual y semanas después se reconcilia | Uno o dos momentos por hecho, con su texto |
| Forma | Una oración larga con punto y coma | Dos a cuatro oraciones, con sus palabras |

**Los momentos grandes quedan casi todos.** Lo que se pierde es **el detalle concreto** (lo que se ve, se oye y se siente) y **la forma de decirlo**. La Voz solo recibe los hechos y la primera oración de la idea (Spec-590), así que lo que no está en los hechos no llega al relato.

### 1.2 Por qué resume

En `config/prompts_generation/authoring_planner*.md`:
- El sistema pide «Hechos concretos, en tercera persona y en orden. {habla}, frases simples».
- «La historia es del autor: respetá sus hechos» habla de **qué pasa**, no de **cómo lo cuenta**.
- El Corto pide «exactamente los que pide cada acto (ni uno más…)»: 2–3, 4–5 y 2–3 hechos. Con ideas de ~900 palabras, la IA aprieta varios momentos en un hecho.
- Nada le dice que conserve las palabras, las imágenes ni las sensaciones de la autora.

### 1.3 Lo que no se toca

- **La cantidad de hechos por acto** (`hechos_max`). Yael tampoco sumaba hechos: los hacía más largos. Más hechos también cambiaría el ritmo de la Voz.
- **La Voz.** Escribe desde los hechos: si los hechos traen el detalle, la prosa también.

## 2. Parte A: el Planificador conserva lo que contó la autora

Cambios en el prompt del Planificador (`authoring_planner_system.md` y `authoring_planner.md`), para todos los largos:

- **A1. Las palabras de la autora.** Cuando un hecho cuenta algo que está en la historia, usa las palabras y los detalles de la autora: lo que se ve, se oye y se siente, las imágenes y lo que piensa el personaje. No lo resume ni lo cambia por sinónimos. Puede pasarlo a tercera persona y ordenarlo.
- **A2. Uno o dos momentos por hecho.** Si un acto tiene más momentos de la historia que hechos, se juntan los que van seguidos, pero cada uno con su detalle. El largo de cada hecho sigue a cuánto contó el autor de ese momento: con detalle, de 2 a 4 oraciones; con poco, una o dos (ajuste de S2). Nunca más de {tope_hecho} caracteres (el tope de `topes.event`, que llega por config).
- **A3. No inventar para llenar.** Lo que la autora no contó se escribe breve, como hoy: la IA no le agrega imágenes propias.
- **A4. «Frases simples» se queda,** pero sobre la forma: oraciones completas y claras, no resúmenes.

Los textos exactos se escriben en IMPLEMENT y se ajustan con la medición (§4). El `{tope_hecho}` sale de `catalog.topes()["event"]`, así que el prompt y la pantalla no se desalinean.

## 3. Parte B (condicional): el texto de la autora en cada hecho

**Solo si la Parte A no llega al 70 %** (§4). El Planificador devuelve, por hecho, el comienzo de la parte de la idea que cuenta (`desde`), como hace `FinalDeLaIdea` (Spec-690). El código recorta ese tramo de la idea, sin que la IA lo copie, y lo guarda con el hecho. La Voz lo recibe como «ASÍ LO CONTÓ LA AUTORA».
- En «Los actos», debajo del hecho, con una pista (`.pista-forge`) plegada: «De tu idea: …». No es un paso nuevo.
- Cambia el esquema de la salida del Planificador y suma una columna JSON en `act_outline` (`event_sources`), así que hay que tocar `init_db()` y recrear la base de dev.
- Es más grande: si hace falta se escribe aparte (Spec-771) antes de implementarla.

## 4. Medición (la corre Claude)

Con `scripts/research/760/medir_ideas_largas.py` (exportando el `.env`), sobre copias de la base de prod:

| Corrida | Para qué | Costo aprox. |
|---|---|---|
| Las 3 ideas del «ritual» en Corto, con el prompt nuevo | El objetivo: eco ≥ 70 % (hoy 56 %) | US$ 0,20 |
| 2 historias de prod con ideas cortas (~300–500 palabras, Corto) | Que no invente: los hechos no crecen más que la idea | US$ 0,12 |
| 1 relato Corto escrito con los actos nuevos («Culpable») | Que la prosa traiga el detalle y cuánto se alarga (hoy, con los hechos de Yael, sale 1 360–1 540 palabras para una meta de ~1 050) | US$ 0,10 |

- **Tope:** US$ 0,60. Más que eso se pregunta.
- **Qué se mira:** eco, caracteres por hecho (ninguno > 800), palabras de hechos contra palabras de la idea, final en el último acto, avisos visibles, y en el relato, palabras por acto contra `palabras` de la estructura.
- **Una lectura de Claude** de los hechos de «Culpable» contra §1.1: si aparecen los detalles que Yael tuvo que volver a poner.
- **Evidencia** en `scripts/research/770/`, solo números y extractos de pocas palabras.

## 5. Riesgos

- **El relato sale más largo que su meta.** Con más detalle por hecho, la Voz escribe más. Es lo que ya pasa con los hechos de Yael y ella está conforme. Se mide (§4) y se anota. Si se pasa mucho (> 30 %), se mira con el usuario antes de prod.
- **La IA copia de más.** Por ejemplo, pone toda la idea en el acto 1. Lo frenan la cantidad de hechos, el tope de 800 y el chequeo de palabras de hechos ≤ palabras de la idea.
- **Las ideas cortas o en punteo.** A3 y la medición con ideas cortas.
- **Gemma (perfil local):** puede seguir peor el prompt. No se mide porque no está en prod.

## 6. Decisiones

| # | Decisión | Estado |
|---|---|---|
| D1 | El arreglo va en el prompt del Planificador, sin llamadas nuevas ni pasos en la UI | Propuesta |
| D2 | No cambia la cantidad de hechos por acto: cambia cuánto detalle trae cada uno | Propuesta |
| D3 | La Parte B (texto de la autora por hecho) solo si la A no llega al 70 % | Propuesta |
| D4 | La medición la corre Claude, tope US$ 0,60 | Propuesta (siguiendo la Spec-760 D4) |
| D5 | Con una idea corta, el criterio «los hechos no suman más palabras que la idea» no se puede cumplir: un Corto pide 10 u 11 hechos. Propuesta: medirlo como **«no inventa más que antes»** (palabras nuevas: 46 % y 35 %, contra 58 % y 60 % en prod) | Usuario, 2026-11-21 |

## 7. Boundaries

- **Siempre:** los textos de los prompts en `config/` (Spec-620); los snapshots de los prompts se regeneran a propósito (`SNAPSHOT_UPDATE=1`) y se revisa el diff; tests en verde y dev al día en cada checkpoint.
- **Preguntar antes:** pasar los US$ 0,60; implementar la Parte B; deploy a prod.
- **Nunca:** commitear los textos de las autoras; cambiar la Voz en esta spec.

## 8. PLAN (borrador, a confirmar)

- **S1. El prompt (Parte A). Hecho (2026-11-21).** El sistema del Planificador suma dos reglas: contar los hechos con las palabras del autor (A1) y lo que no contó, breve (A3). «frases simples» queda (A4). La lista de `hechos` pide un momento por hecho (dos como mucho, si van seguidos), de 2 a 4 oraciones y hasta `{tope_hecho}` caracteres (A2, de `topes.event`). Se regeneraron 7 snapshots y el diff es solo ese texto. Test: `tests/unit/application/authoring/test_planificador_palabras.py`. Suite en verde (1 313).
  - Plan original: Los textos de A1–A4 en las plantillas del Planificador, `{tope_hecho}` desde los topes, y snapshots regenerados. Tests:
  - El snapshot de `assistant_prompts.json` trae las líneas nuevas, con un test que falla si desaparecen.
  - Un test que verifica que `{tope_hecho}` es el `topes.event` de config.
- **S2. Medición (§4). Hecha (2026-11-21).** Informe en `scripts/research/770/informe.md` (US$ 0,576).
  - Ideas largas: eco del **85–96 %** (antes 56 %), 5–8 % de palabras nuevas (antes 30–41 %) y ningún hecho de más de 657 caracteres.
  - Relato «Culpable»: 1.192 palabras (13 % arriba de la meta, contra 30–45 % con los hechos de Yael), con su detalle en la prosa.
  - Ideas cortas: con «de 2 a 4 oraciones» la IA rellenaba. Se ajustó una vez: el largo de cada hecho sigue a cuánto contó el autor. Los hechos igual suman más palabras que la idea (D5).
  - Plan original: Si el eco llega a ≥ 70 % sin inventar, sigue S4. Si no, se ajusta el texto una vez y se vuelve a medir, dentro del tope de gasto. Si sigue sin llegar, se propone la Parte B (S3).
- **S3. Parte B** (solo con OK del usuario).
- **S4. Cierre:** dev al día, informe al usuario y, con su OK, deploy.

# SPEC-780: «Tu idea» más simple (sin giros, sin efecto, sin «quién lo cuenta») y dos formas de contarlo

**Fecha:** 2026-11-21
**Tipo:** SDD: asistente (UI), molde y prompts (config), guía de oficio de la Voz
**Estado:** IMPLEMENT (OK al plan el 2026-11-21). S1 hecho.
**Rama:** `feat/spec-780-tu-idea-mas-simple` (desde `development`)
**Extiende / deshace en parte:** Spec-670 (moldes: el giro), Spec-560 A5 (la receta del efecto), Spec-530 (quién lo cuenta, cómo lo cuenta), Spec-640 (la Voz como anécdota).

---

## ASSUMPTIONS

1. Lo pidió el usuario el 2026-11-21, con lo que dijeron las autoras (Yael):
   - **Los giros** no los usan.
   - **«¿Qué querés que sienta quien lo escuche?»** no vale para toda la historia: un susto puede estar en una parte, y el sistema ya lo entiende desde la idea.
   - **«Quién lo cuenta»** siempre es el protagonista.
   - **«¿Cómo lo cuenta?»:** «caso entre amigos» y «confesión» son lo mismo. «Crónica seca» no se entiende. Se pide una opción **literaria**, como si lo escribieras, más trabajada pero sin exagerar: lo contrario de contárselo a un amigo.
2. Sacar algo de la pantalla es también sacarlo de los prompts. Si una historia vieja lo tiene guardado, **se ignora** (no se borra), igual que hoy pasa con un giro que ya no existe (Spec-670 D16).
3. No se suman pasos a la UI (Spec-760 D5). La medición la corre Claude.
4. Prod escribe con GPT-5.6 Sol (`openai-sol`).

## OBJECTIVE

Que «Tu idea» pregunte solo lo que las autoras usan y entienden, y que «¿Cómo lo cuenta?» ofrezca dos formas que de verdad suenen distintas.

**Éxito:**
- En «Tu idea» no hay más giros, ni «¿Qué querés que sienta…?», ni el selector «Quién lo cuenta».
- Ningún prompt recibe el giro, el efecto ni su receta. Las historias que los tenían se arman y se escriben igual que una nueva.
- «¿Cómo lo cuenta?» tiene dos opciones, «Como a un amigo» y «Como si lo escribieras», y un relato escrito con cada una se nota distinto sin que el literario exagere (§6).

---

## 1. Qué se pierde con cada cosa (relevamiento, 2026-11-21, base de prod: 21 historias)

### 1.1 Los giros (Spec-670)

- **Uso:** 1 de 21 historias («No entres al bosque (halloween)», con «La amenaza tiene una regla rara»).
- **Qué hacen hoy:** cada uno de los 6 giros suma **una pregunta** en «Preguntas», que lleva el tope de 9 a 10, y **una regla** para el Planificador. Ejemplo: «La víctima no es quien parece» le pide que el giro aparezca. Tienen su sección en «Tu idea», con «Sorprendeme».
- **Qué se pierde:** la forma de empujar la historia hacia una vuelta de tuerca de catálogo. Lo que la autora cuente en su idea se sigue respetando: si su idea tiene una víctima que no es quien parece, el Planificador lo toma de ahí.
- **La historia con giro:** pasa a armarse sin él. Su respuesta a la pregunta del giro queda guardada y no llega a ningún prompt (como hoy, Spec-670 D11).

### 1.2 «¿Qué querés que sienta quien lo escuche?» (el efecto)

- **Uso:** 19 de 21 lo eligieron (11 pavor, 4 revelación, 3 susto, 1 melancolía); 2 no.
- **Qué hace hoy:**
  - **El Planificador** recibe la **receta** del efecto, que le impone una forma a toda la historia (`authoring_options.yaml`):
    - Pavor: «nada se muestra entero antes del acto 3».
    - Susto: «al menos dos irrupciones bruscas en los actos 2 y 3».
    - Revelación: «una verdad que se revela en el acto 4 y cambia el sentido de todo».
    - Melancolía: «el final deja una pena».
  - **El Verificador** avisa si la escaleta no cumple la receta.
  - **El Consultor** usa el efecto para que sus opciones de respuesta vayan con él.
  - **La Voz no lo recibe.**
- **Qué se pierde:** esa forma impuesta. Lo que decían las autoras se ve en la receta: el efecto manda sobre toda la historia, aunque la idea tenga un susto en una sola parte.
- **Lo que queda y ya da la forma:**
  - La intensidad de cada acto (`llm_beats_definition.yaml`).
  - La regla de que cada encuentro con la amenaza es más grave que el anterior.
  - Lo que pide la forma de la historia en cada acto (Spec-670).
  - Lo que se revela y en qué acto.
  - Desde la Spec-770, lo que cuenta la idea con sus palabras.

### 1.3 «Quién lo cuenta»

- **Uso:** 0 de 21. Siempre quedó «El protagonista».
- **Qué hace hoy:** permite que lo cuente otro personaje, un testigo (la abuela que cuenta lo que le pasó al nieto). Todo el pipeline se arma alrededor de quien narra: la Voz en primera persona, cómo llama a cada personaje, los rasgos de la memoria y el elenco.
- **Qué se pierde:** esa posibilidad en la pantalla. El código la sigue entendiendo (`context.narrator`), porque cae al protagonista cuando no hay otro y la usan los YAML importados.

### 1.4 «¿Cómo lo cuenta?»

- **Uso:** 18 caso, 1 confesión, 0 crónica, 2 sin elegir.
- **Qué hace hoy:** una línea en el prompt de la Voz (`voz`), y el nombre de la opción en lo que leen el Planificador y el Consultor. **La guía de oficio es toda de anécdota** (`voice_craft.md`, «CONTALO COMO UNA ANÉCDOTA», Spec-640): «es algo que te pasó y se lo contás a alguien en una sobremesa, **no un cuento escrito**», sin metáforas e imágenes de escritor. Por eso caso y confesión suenan iguales: la guía pesa más que la línea de la opción.
- **Lo que cambia:** una opción literaria no entra con esa guía. Hace falta que el bloque de anécdota dependa de la opción.

## 2. Parte A: sacar los giros

- **Pantalla:** sale la sección del giro de «Tu idea» (con «Sorprendeme» y su JS).
- **Config:** sale `config/moldes/ingredientes.yaml` y, del banco (`workshop_criteria.yaml`), los 6 criterios de los giros.
- **Código:** `molde.py` sin giros (`Molde` = base + forma + largo); `/authoring/options` sin `ingredients`; el schema y el router sin `ingredient`.
- **Historias viejas:** `direction.ingredient` se conserva y se ignora. El YAML (export/import) lo sigue llevando dentro de la dirección, para no perder el dato (D5); el molde no lo lee.
- **Tests:** el tope de preguntas vuelve a 9 en todas las combinaciones (`test_moldes.py`), y se regeneran los snapshots `moldes_*`.

## 3. Parte B: sacar el efecto

- **Pantalla:** sale «¿Qué querés que sienta quien lo escuche?» (con «Otro»).
- **Planificador:** sale `{efecto}` («CÓMO TIENE QUE PEGAR»). Queda el arco de «Otra», que va en el mismo hueco.
- **Verificador:** sale `{efecto}` y con él los avisos de receta.
- **Consultor:** «coherentes con el efecto que busca el autor y con su final» pasa a «coherentes con la idea del autor y con su final».
- **Lo que lee toda la IA de la historia:** `story_block` sin la línea del efecto.
- **Config:** salen las `efectos` de `authoring_options.yaml`, con su fragmento `asistente/efecto/*`.
- **Historias viejas:** `direction.effect` se conserva y se ignora.

## 4. Parte C: sacar «Quién lo cuenta»

- **Pantalla:** sale el selector. La sección pasa de «¿A quién le pasa y quién lo cuenta?» a «¿A quién le pasa?».
- **API:** `narrator` se ignora al guardar «Tu idea». Lo cuenta siempre el protagonista.
- **Historias importadas:** las que traen otro narrador por YAML lo conservan. El pipeline no cambia.

## 5. Parte D: dos formas de contarlo

| id | En pantalla | Qué recibe la Voz |
|---|---|---|
| `caso` (el de siempre) | **Como a un amigo** — «Mirá, yo no creía en nada de eso, pero esa noche…» | El bloque de anécdota de hoy, sin cambios: oral, coloquial, sin imágenes de escritor |
| `escrito` (nuevo, en lugar de `cronica`) | **Como si lo escribieras** — un ejemplo literario corto, a escribir en IMPLEMENT | Un bloque **escrito** en lugar del de anécdota (borrador abajo) |

**Borrador del bloque escrito** (`voice_craft`, se ajusta con la medición):
- Es un relato escrito, para leerse en voz alta: oraciones completas, más trabajadas y variadas que en una charla, sin muletillas ni marcas de sobremesa («mirá», «te juro»).
- Describí con precisión lo que se ve, se oye y se siente. Una imagen propia y clara está bien; nunca rebuscada ni de manual.
- Sin exagerar: el miedo lo da lo que pasa, no los adjetivos.
- Lo de siempre sigue igual: primera persona, sin diálogo directo, oraciones completas, clichés prohibidos, no enumerar siempre de a tres y cerrar con algo concreto.

**Lo que no cambia:**
- El control de repetición sigue igual con las dos opciones: clichés, oraciones cortadas y diálogo.
- El aviso de comparaciones (desde la segunda del acto) queda como está hasta ver la medición (D6).

**Historias viejas:** `confesion` pasa a leerse como `caso`; `cronica` (ninguna en prod) como `escrito`; sin elegir, `caso`.

## 6. Medición (la corre Claude, tope US$ 0,40)

| Corrida | Para qué |
|---|---|
| 2 historias de prod, armadas sin efecto (`plan_outline`) | Que la estructura no empeore: el final en el último acto, la intensidad sube y los avisos no aumentan |
| «Culpable» (Corto) escrita con «Como a un amigo» y con «Como si lo escribieras», con los mismos actos | Que se noten distintas sin que la literaria exagere |

Para comparar las dos versiones de «Culpable» se miden comparaciones, clichés, oraciones cortadas y marcas orales por cada mil palabras, y Claude lee las dos. Evidencia en `scripts/research/780/`: solo números y extractos de pocas palabras.

## 7. Decisiones

| # | Decisión | Estado |
|---|---|---|
| D1 | Se sacan los giros | Usuario, 2026-11-21 |
| D2 | Se saca el efecto de la pantalla **y de los prompts** (no queda escondido mandando) | Usuario, 2026-11-21 |
| D3 | Se saca «Quién lo cuenta» de la pantalla. El código sigue entendiendo un narrador distinto (YAML) | Usuario, 2026-11-21 |
| D4 | «¿Cómo lo cuenta?» queda con dos opciones: «Como a un amigo» (`caso`, absorbe confesión) y «Como si lo escribieras» (`escrito`, en lugar de crónica) | Usuario, 2026-11-21 |
| D5 | Lo guardado en historias viejas (giro, efecto, narrador elegido) se conserva y se ignora; no se migra la base | Usuario, 2026-11-21 |
| D6 | El literario tiene el mismo control de repetición (comparaciones incluidas) hasta ver la medición | Usuario, 2026-11-21 |

## 8. Boundaries

- **Siempre:**
  - Textos en `config/` y vistas (Spec-620).
  - Snapshots regenerados a propósito, con el diff revisado.
  - `sin-jerga`, gramática visual y tests en verde.
  - Dev al día en cada checkpoint.
- **Preguntar antes:** pasar los US$ 0,40; cambiar el bloque de anécdota de `caso` (hoy funciona); deploy.
- **Nunca:** borrar datos de historias viejas; commitear textos de las autoras.

## 9. PLAN (borrador, a confirmar)

- **S1. Sacar los giros (A). Hecho (2026-11-21).** Sale `config/moldes/ingredientes.yaml` y los 6 criterios de los giros del banco. `Molde` queda en forma + largo. La API deja de ofrecer `ingredients`, de validar y de devolver el giro, y conserva el guardado. En «Tu idea» sale la sección (con «Sorprendeme») y en «Preguntas» el grupo del giro («Son 9 como mucho»).
  - Tests: una historia vieja con giro se arma igual que una sin giro (`test_moldes.py`); un giro que manda una pestaña vieja se ignora.
  - Snapshot `moldes_asedio` regenerado: el diff es solo la regla y la pregunta del giro.
  - Resultado: pytest 1 313 · Vitest 493 · E2E de moldes y asistente 22, todo en verde.
  - Plan original: config, molde, API, pantalla, tests y snapshots.
- **S2. Sacar el efecto (B):** pantalla, prompts del Planificador, del Verificador y del Consultor, `story_block`, config y snapshots.
- **S3. Sacar «Quién lo cuenta» (C):** pantalla y API.
- **S4. Dos formas de contarlo (D):** las opciones, el bloque escrito en `voice_craft` (el de anécdota solo con `caso`), cómo se leen `confesion` y `cronica`, y snapshots de la Voz.
- **S5. Medición (§6)** y, si hace falta, un ajuste del bloque escrito.
- **S6. Cierre:** dev al día, PR y, con OK, deploy.

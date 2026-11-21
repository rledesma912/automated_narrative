# SPEC-760: ideas largas en «¿De qué trata?»

**Fecha:** 2026-11-21
**Tipo:** SDD: asistente (UI), API (validación), config de las estructuras
**Estado:** IMPLEMENT (OK al plan del usuario el 2026-11-21). S1 hecho. Enfoque: sin cortes en silencio y una nota cuando la idea no entra en el largo; el mapa de Freytag queda descartado por ahora (D6).
**Rama:** `feat/spec-760-ideas-largas` (desde `development`)
**Extiende:** Spec-530 (asistente), Spec-690 (el final sale de la idea), Spec-750 (tres largos).

---

## ASSUMPTIONS

1. Lo reportó el usuario el 2026-11-21: una autora no pudo seguir desde el miércoles 2026-11-18 porque su texto de «¿De qué trata?» **no entró** en la pantalla.
2. El tope nuevo de la idea es **20 000 caracteres** (~3 500 palabras), decisión del usuario (D1).
3. **El usuario no valida a mano** (D4). Las pruebas las corre Claude, cortas y sin intervención; la calidad la juzgan las autoras con el uso en prod.
4. **No se suman pasos a la UI** (D5): todo se resuelve en «Tu idea», «Preguntas» y «Los actos» con los componentes de hoy (contadores como `.pista-forge`, notas con acción, avisos).
5. No hay apuro por un arreglo parcial: la autora espera la versión completa en prod.
6. Prod escribe con GPT-5.6 Sol (`openai-sol`, Spec-740). Se trabaja en dev; prod solo con `make deploy` y OK del usuario.

## OBJECTIVE

Que una autora pueda escribir sus ideas tan largas como las escribe, que **ningún campo del asistente le corte el texto sin avisar**, y que la pantalla le avise cuando su idea no entra en el largo que eligió.

**Éxito:**
- Ningún campo del asistente tiene un `maxlength` que corte en silencio. Pasado un tope, el texto queda en el cuadro, no se guarda y se ve un aviso con cuánto sobra.
- Una idea de 20 000 caracteres se guarda entera, y el final que sale de ella se puede «Cambiar» sin perder texto.
- Un hecho de «Los actos» admite el texto que la autora le mete hoy (ver §1.2).
- Con una idea demasiado larga para el largo elegido, «Tu idea» lo dice y ofrece «Cambiar el largo».

---

## 1. Relevamiento (2026-11-21, base de prod, 14 historias con ideas de más de 1 500 caracteres)

### 1.1 La idea se corta a los 6 000 caracteres

«no los dejes pasar» (Larga, 2026-11-16) tiene una idea de **5 985 caracteres que termina a mitad de frase** («…desde el auto. pero que») y ningún job: la autora la dejó ahí. El `maxlength="6000"` del textarea (`direccion.ejs:114`) hace que el navegador corte lo que se pega de más **sin avisar**. La API tiene el mismo tope (`DirectionIn.premise`). Sus tres historias anteriores venían pegadas al techo: 5 975, 5 500 y 5 422.

### 1.2 Los hechos se cortan a los 400 caracteres

Cada hecho de «Los actos» tiene `maxlength="400"` (`_acto.ejs:102` y el que suma `asistente.js:476`), y la API **no** tiene tope por hecho. En prod:
- «El halloween de Peter»: un hecho termina en «…Él siempre se reía», **cortado a mitad de frase**.
- Otros dos hechos de exactamente 400 («El empleado del maletín», «No es tu culpa») y seis de 395 a 399 caracteres (las tres historias del ritual). La autora usa los hechos para meter su texto y choca contra el tope.

### 1.3 Más topes que cortan o rompen

| Campo | Front | API | Problema |
|---|---|---|---|
| El final que sale de la idea (criterio `final`) | `maxlength="2000"` (`_taller_contenido.ejs:186`) | `text` ≤ 2 000 | Es un recorte de la idea (Spec-690): con una idea de 20 000 puede pasar los 2 000. Hoy el más largo es de 961 |
| Cantidad de hechos por acto | sin tope | `events` ≤ 8 | `hechos_max` es solo un aviso: el Planificador no tiene tope. **En prod, dos actos de «la cosa agachada» (corto) tienen 9 hechos, y editarlos daba 422.** La Larga (Spec-750) además pide 9 en el acto 3 |
| Respuesta del taller | 600 / 2 000 | 2 000 | Revisar con el mismo criterio (A3) |
| Resto (`bridge`, `goal`, `change_*`, `held_back`, reglas, la amenaza, nombres) | 60–600 | igual o sin tope | Mismo `maxlength` que corta en silencio, aunque no se vio que choque |
| Mensaje del 422 | `errorText` muestra `premise: String should have at most …` | — | En inglés y con el nombre del campo |

### 1.4 Sus ideas no entran en un corto

| Ideas | Historias | Hechos que entran del corto (3 + 5 + 3) | Relato escrito (meta ~1 050) | Oraciones de la idea con eco en los hechos |
|---|---|---|---|---|
| ~300–620 palabras | 8 cortos | 11 | 850–1 185 | ~90 % (casi todas entre 80 y 100 %) |
| 870–950 palabras | las 3 del «ritual» | 11 | **1 360–1 540** (~9–10 min) | **~70 %** |

El eco es una cuenta gruesa: proporción de las palabras de 5 letras o más de cada oración de la idea que aparecen en los hechos (≥ 40 % = con eco). Alcanza para ver la tendencia, no para medir fino.

### 1.5 Lo que funciona y no se toca

- **La estructura sale bien.** En «Culpable» (917 palabras), los actos ubican la exposición, el incidente, el clímax y el desenlace donde la idea los pone. El Consultor marcó casi todo `cumple`, y el final salió de la idea (Spec-690).
- **Tokens.** El Planificador, la llamada más grande, usa ~3 600 tokens de entrada con ideas de ~5 900 caracteres. A 20 000 caracteres son ~3 500 tokens más por llamada: sin problema de contexto ni de costo. La Voz recibe solo la primera oración de la idea (Spec-590).
- **Base de datos.** `story.direction` y `act_outline.events` son JSON en `TEXT`. **Sin cambio de esquema.**
- **Tamaño de los pedidos.** Express (`express.json()`, 100 kB) y nginx (1 MB) alcanzan: 20 000 caracteres son ≤ 80 kB en UTF-8.

---

## 2. Parte A: ningún campo corta en silencio

- **A1. Un solo mecanismo para todos los campos con tope del asistente.** Se saca el `maxlength` y se pone `data-tope="N"` en su lugar. Un script chico (`public/js/tope.js`, UMD testeable como `eta.js`) hace dos cosas:
  - Desde el 80 % muestra un contador debajo del campo (`.pista-forge`): «16.200 de 20.000 letras».
  - Pasado el tope, el contador pasa a aviso (`.nota-forge--warning`): «Sobran 1.300 letras: acortalo un poco para que se guarde».

  Los textos van en la vista, en `data-*` (Spec-620, `sin-jerga`).
- **A2. El autoguardado no manda un campo pasado de su tope.** La notificación de guardado queda en error con el mismo texto, y el texto sigue en el cuadro. Lo demás del formulario se guarda igual.
- **A3. Los topes.**
  - **La idea:** 20 000 (D1).
  - **El final (criterio `final`):** 20 000, validado en el router, porque el schema no conoce el criterio.
  - **Cada hecho:** 800, el doble de hoy. Se suma también en la API (hoy no tiene).
  - **Cantidad de hechos por acto:** 15 (`topes.events`). Como `hechos_max` es solo un aviso y el Planificador lo pasa, el tope tiene que dejar margen sobre el mayor `hechos_max`. `test_topes.py` controla que lo pase.
  - **El resto:** queda con su número de hoy, pero sin el corte en silencio.

  Los topes viven en **un solo lugar**: una sección `topes` en `config/authoring_options.yaml`. La API los lee de ahí y la vista los recibe por `/authoring/options`. Un test verifica que ningún `maxlength` quede en las vistas del asistente ni en `asistente.js`.
- **A4. La API responde en el tono del sitio.** Un 422 por largo responde `validacion.texto_largo` de `core_messages.yaml` («Este texto tiene 21.300 letras y entran hasta 20.000: acortalo un poco para que se guarde.»; para una lista, `validacion.lista_larga`). Los números van con punto de miles, como en el resto del sitio, y `errorText` muestra el `detail` tal cual cuando es texto.
- **A5. El alto del cuadro.** Los textareas que crecen con el texto (`[field-sizing:content]`) llegan como mucho a `max-h-[70vh]` y después hacen scroll.

## 3. Parte B: la nota «tu idea no entra en este largo»

- **B1. La regla, sin IA.** Las palabras de la idea se comparan con un umbral **por estructura**: `idea_palabras_max` en `estructuras.<largo>` de `config/llm_beats_definition.yaml`. El valor de partida es el 70 % de `palabras_total`: ~735 en el corto, ~1 750 en la media y ~3 675 en la larga. Lo ajusta la medición (§4).
- **B2. Dónde se ve.** En «Tu idea», debajo de «¿Qué tan largo?», con una nota de info: «Tu idea es larga para un relato corto: es probable que algunas partes no entren y que el relato salga más largo. Si querés que entre todo, probá con Media.»

  Trae la acción «Cambiar el largo», que ya existe (`PUT …/structure`, con su confirmación, porque borra los actos). Sugiere **el largo más corto habilitado en el que entra la idea**. Si no entra en ninguno, sugiere el más largo habilitado y lo dice.
- **B3. Se recalcula sola.** Se recalcula mientras se escribe la idea, con el mismo JS que el contador y sin llamar a la API. La cuenta de palabras es la misma en Python y en TS (casos compartidos en `tests/fixtures/`, como `tiempos.js` = `timing.py`).
- **B4. Nunca cambia el largo sola** (la IA nunca corre sola). Si el largo elegido ya es el más largo habilitado, la nota dice solo que algunas partes pueden no entrar.
- **B5. En «Los actos», la misma nota** arriba de las tarjetas, si la idea no entra en el largo de la historia, para quien ya pasó por «Tu idea» antes de esta spec.

## 4. Parte C: medición (la corre Claude, sin el usuario)

- **Qué:** las 3 ideas del «ritual» (870–950 palabras) se arman (`plan_outline` + `verify_outline`) en **Corto y en Media**, y se escribe una sola en Media para ver cuánto sale. Es en una copia descartable de la base de dev, con `openai-sol`.
- **Qué se mira:**
  - El eco de la idea en los hechos, con la misma cuenta de §1.4.
  - Los hechos por acto contra `hechos_max`.
  - El largo del relato contra `palabras_total`.
  - Tokens y costo (`llm_call`).
- **Para qué:** confirmar que en Media la idea entra (eco ≥ ~85 % y relato dentro de su rango) y fijar `idea_palabras_max`.
- **Tope de gasto:** US$ 0,30 (6 armados y un relato). Más que eso se pregunta.
- **Evidencia:** `scripts/research/760/`, solo números y extractos de pocas palabras. **Las ideas de las autoras no se commitean.**

## 5. Lo que no se hace

- **El mapa de Freytag de la idea** (una IA que ubique cada tramo de la idea en su acto, con nota y aviso del Verificador). Queda descartado por ahora (D6): con GPT-5.6 Sol la estructura sale bien (§1.5) y lo que se pierde se explica por el largo, no por la ubicación. Se reabre si en Media o Larga aparecen tramos de la idea en el acto equivocado.
- **Cambiar prompts** del Planificador o de la Voz.
- **Pasos o pantallas nuevas** (D5).

## 6. Decisiones

| # | Decisión | Estado |
|---|---|---|
| D1 | Tope de la idea: 20 000 caracteres | Usuario, 2026-11-21 |
| D2 | Pasado un tope no se corta ni se guarda: se avisa y el texto queda en el cuadro | Usuario, 2026-11-21 (enfoque) |
| D3 | Hecho: 800 caracteres; hasta 15 hechos por acto (con margen sobre `hechos_max`, §1.3); final: 20 000 | S1, 2026-11-21 |
| D4 | La medición la corre Claude; la calidad la juzgan las autoras con el uso | Usuario, 2026-11-21 |
| D5 | Sin pasos nuevos en la UI: todo con los componentes de hoy | Usuario, 2026-11-21 |
| D6 | El mapa de Freytag queda descartado por ahora (§5) | Usuario, 2026-11-21 |
| D7 | La nota del largo es sin IA, con un umbral por estructura en config | Usuario, 2026-11-21 (enfoque) |

## 7. Boundaries

- **Siempre:** tests en verde y dev reflejando el cambio en cada checkpoint (Spec-540 §2.5); textos de pantalla en vistas o `core_messages.yaml`; colores solo con tokens `forge-*`; topes en config.
- **Preguntar antes:** cambiar prompts de la IA; gastar más de US$ 0,30 en la medición; deploy a prod.
- **Nunca:** commitear las ideas de las autoras; recortar el texto de una autora en el front o en el back sin avisar; sumar un paso o una pantalla.

## 8. PLAN (borrador, a confirmar)

- **S1. Topes y API (A3, A4). Hecho (2026-11-21).** `topes` en `config/authoring_options.yaml` (lo lee `catalog.topes()`), el schema sin números fijos, el final por criterio en el router, `src/presentation/validation.py` (handler de `RequestValidationError` solo para texto o lista de más; el resto sigue igual) y `topes` en `/authoring/options`. Tests: `tests/unit/test_topes.py`, `tests/integration/test_topes_api.py`; suite completa en verde (1 311). La pantalla todavía tiene sus `maxlength`: los saca S2.
  - Plan original: Sección `topes` en config, la API los lee, tope por hecho, cantidad de hechos según las estructuras, el final a 20 000 en el router, mensajes de `core_messages.yaml`, y `topes` en `/authoring/options`. Tests: pytest de cada tope (20 000 entra, 20 001 da 422 con el mensaje), un acto de la Larga con 9 hechos que se guarda y un final de 5 000.
- **S2. El contador y el guardado (A1, A2, A5).** `tope.js`, `data-tope` en todas las vistas del asistente y en `asistente.js`, el autoguardado que no manda un campo pasado y el alto máximo. Tests:
  - Vitest de `tope.js` (80 %, pasado del tope, cuenta de letras).
  - Un test que falla si queda un `maxlength` en el asistente.
  - E2E en Firefox:
    - Pegar 20 000 caracteres en la idea y encontrarlos guardados.
    - Pegar 20 500 y ver el aviso sin perder el texto.
    - Un hecho de 700 caracteres que se guarda.
- **S3. Medición (§4).** Script, corrida e informe, y con eso `idea_palabras_max` en las tres estructuras.
- **S4. La nota del largo (B).** Config, la cuenta de palabras compartida Python/TS, la nota en «Tu idea» y en «Los actos» con «Cambiar el largo». Tests: unidad de la regla (qué largo sugiere, con largos apagados), casos compartidos y vista.
- **S5. Cierre.** `make dev-status` en verde, informe al usuario y, con su OK, `make deploy`.

**Riesgos:**
- El autoguardado manda la idea entera en cada pausa. Con ≤ 80 kB es aceptable.
- El umbral de la nota puede molestar a una autora que escribe ideas largas a propósito para un corto y está conforme. Por eso es una nota de info y no un aviso.
- Una base sin las historias del ritual no reproduce la medición. El script recibe las ideas desde un archivo local fuera del repo.

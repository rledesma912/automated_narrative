# SPEC-710: Cada hecho pasa en un lugar

**Fecha:** 2026-10-28
**Tipo:** SDD — escaleta (Planificador, Verificador, Voz) + tarjeta del acto
**Estado:** IMPLEMENT (2026-10-29): S1 a S4 hechos; falta S5 (medición y cierre).
**Rama:** a crear desde `development`
**Extiende:** Spec-530 (escaleta), Spec-630 B6/B7 (lugares de la historia), Spec-590 (lo que recibe la Voz).
**Hermana:** Spec-700 (salió de la misma revisión del uso de Vale).

---

## ASSUMPTIONS

1. La idea es del usuario: un acto pasa a menudo en varios lugares, y «Dónde pasa» con un lugar por acto no alcanza. Los datos de prod le dan la razón (§1.2).
2. La máxima del pipeline (2026-09-27): cada campo nuevo tiene que prevenir un error que se vio de verdad. Acá el error visto es que **el lugar del acto contradice a sus hechos** (§1.2). El lugar se resuelve en la escaleta, no lo resuelve la Voz mientras escribe.
3. Quien carga el lugar de cada hecho es el **Planificador**. La autora solo lo corrige: no se suma un campo para llenar a mano.
4. Prod usa `hibrido-sonnet55`: el Planificador es **gemma**; la Voz, Sonnet 5.5.
5. Textos en `config/` (Spec-620), tono coloquial (Spec-580). Sin migraciones: si cambia el esquema, se actualiza `init_db()` y prod pasa con `export-yaml --all` / `import-yaml`.

---

## OBJECTIVE

Que cada hecho de «Qué pasa» diga dónde pasa, que el lugar del acto salga de esos lugares (para que no se contradigan) y que la Voz reciba cada hecho con su lugar.

---

## 1. Relevamiento (2026-10-28)

### 1.1 Cómo es hoy

| Dónde | Qué hace | Archivo |
|---|---|---|
| Dominio | `ActOutline.scenario: str` (uno por acto, por nombre); `events: list[str]` | `models.py:309` |
| Planificador | devuelve `escenario: str` por acto («dónde ocurre») | `planner.py` `ActoPlan`, `authoring_planner.md:21` |
| Tarjeta del acto | «Dónde pasa» es un **radio**: un solo lugar. Las opciones son los lugares de la historia **más los textos de `scenario` de todos los actos** | `_acto.ejs:104`, `authoring_router._state` |
| Verificador | título del acto «ACTO N — {escenario}» | `fragments/asistente/verificador/acto/titulo_con_escenario.md` |
| Voz | «DÓNDE: {escenario}», con la descripción solo si el texto coincide exacto con un lugar de la historia | `outline_voice.md:7`, `outline_narrator._scenario` |
| Hechos | los usan como texto la Voz, la Memoria, el Verificador, la repetición, la amenaza (`manifestations_for_act`) y el YAML | `outline_narrator`, `verifier`, `repetition_check`, `story_repository` |

### 1.2 Lo que se ve en prod (16 historias, 58 actos)

- **31 de 58 actos** tienen varios lugares metidos en un solo texto: «Tienda de abarrotes, casa de Ximena», «Maizal / Camioneta», «Casa de Mary - Altillo, Escalera».
- **58 de 58** no coinciden con un lugar de la historia (solo una tiene lugares cargados). Resultado:
  - la Voz nunca recibe la descripción del lugar;
  - cada texto compuesto aparece como **una opción más** en «Dónde pasa» de todos los actos. El radio se llena de combinaciones.
- **El lugar contradice a los hechos** («El trabajo de Yadira»):

| Acto | «Dónde pasa» | Dónde pasan los hechos |
|---|---|---|
| 3 | Casa de Ximena, Iglesia, calle del pueblo | todos en **la tienda** (la caja con el ave, la estantería) |
| 4 | Plaza del pueblo, casa de Ximena | **el hospital**, el traslado a otro hospital, la mudanza |

La Voz recibe «DÓNDE: Casa de Ximena, Iglesia, calle del pueblo» para un acto que pasa en la tienda. En el mejor caso lo ignora; en el peor, mete una iglesia que la historia no tiene.

---

## 2. Qué se construye

### A. El lugar de cada hecho
- Cada hecho lleva un lugar (por nombre, como hoy `scenario`). Puede quedar vacío: «el mismo que el hecho anterior».
- El **lugar del acto** deja de cargarse aparte: es la lista, sin repetir y en orden, de los lugares de sus hechos. Así no se pueden contradecir.
- Las historias viejas siguen andando: un acto sin lugares por hecho usa su `scenario` de siempre (prompts **idénticos**).

### B. El Planificador los carga
- `ActoPlan.hechos` pasa a ser una lista de `{texto, lugar}`. El prompt pide un lugar corto por hecho, de los ya definidos si sirve uno, y **un lugar por hecho** (sin comas ni barras).
- Los lugares nuevos que nombra se suman a los de la historia (`story.scenarios`) al guardar la escaleta. Dejan de ser textos sueltos en cada acto.

### C. La tarjeta del acto
- Cada hecho de «Qué pasa» muestra su lugar como un chip chico al lado; tocarlo deja elegir otro de los de la historia o sumar uno («+ Lugar», como hoy).
- «Dónde pasa» queda como un resumen de solo lectura (los lugares de los hechos), no como un radio.
- Borrar un lugar de la historia (tacho, Spec-630 B7) avisa en qué actos y hechos se usa.

### D. Lo que reciben las IA
- **Voz:** cada hecho con su lugar, solo cuando cambia («- En la tienda: …»), y la descripción del lugar, si la tiene, una vez. El «DÓNDE» del acto pasa a ser la lista.
- **Verificador:** el título del acto con la lista; aviso por regla (sin IA) si un hecho nombra un lugar de la historia distinto del suyo (`lugar:<n>`, como `elenco:`). *A medir: puede salir de más.*
- **Memoria y repetición:** sin cambios (siguen leyendo el texto de los hechos).

### E. YAML
- `export-yaml` / `import-yaml` llevan el lugar de cada hecho. Un YAML viejo (hechos como texto) entra igual, sin lugares.

---

## 3. Decisiones (a confirmar)

| # | Duda | Recomendación |
|---|---|---|
| D1 | ¿Cómo se guarda? | **Lista paralela** `event_places: list[str]` en `ActOutline` (una columna JSON más en `act_outline`), mismo largo que `events`. Así todo lo que lee `events` como texto (Voz, Memoria, repetición, amenaza, Verificador) no cambia. La alternativa, hechos como objetos, toca una docena de lugares. **Cambio de esquema → ask first.** *Usuario, 2026-10-28: sí al cambio de esquema.* |
| D2 | ¿Hecho sin lugar? | Vacío = «el del hecho anterior»; el primero vacío = el `scenario` viejo del acto. |
| D3 | ¿Qué pasa con `ActOutline.scenario`? | Se conserva para las historias viejas; en las nuevas se calcula de los hechos (no se edita). |
| D4 | ¿La Voz recibe el lugar en cada hecho? | Solo cuando cambia, para no repetir «En la tienda» en cinco hechos seguidos. |
| D5 | Los textos compuestos de prod («Maizal / Camioneta») | No se tocan: siguen como el lugar del acto hasta que se armen los actos de nuevo. No se convierten solos (adivinar el lugar de cada hecho es trabajo de la IA). |
| D6 | ¿Con gemma sale un lugar por hecho, sin comas? | **Medirlo antes de implementar** (gratis): las 16 historias de prod, 2 corridas. ¿Cuántos hechos con lugar, cuántos compuestos, cuántos coinciden con lo que cuenta el hecho? *Usuario, 2026-10-28: medir.* |
| D7 | Aviso `lugar:` del Verificador (D) | Entra solo si la medición muestra que avisa bien. Si avisa de más, sale del alcance. |

---

## 4. Commands

```bash
make test
make lint
cd frontend && npm test && npx playwright test     # Firefox
SNAPSHOT_UPDATE=1 uv run pytest tests/...          # snapshots a propósito, diff revisado
make dev-db                                        # esquema nuevo (D1)
make dev-status
```

## 5. Testing Strategy

- **Unit:** lugar del acto calculado (orden, sin repetir, vacíos = anterior); acto viejo sin lugares → `scenario` de siempre; `_to_outline` con el esquema nuevo; lugares nuevos del Planificador suman a la historia; YAML ida y vuelta, y uno viejo.
- **Snapshots:** Voz y Planificador **idénticos** para las historias de los tests sin lugares por hecho; uno nuevo con lugares por hecho (la Voz los recibe solo cuando cambian).
- **Front/E2E:** el chip de lugar en cada hecho, cambiarlo, «Dónde pasa» como resumen; borrar un lugar avisa dónde se usa.
- **Medición (gemma, gratis):** D6.

## 6. SUCCESS CRITERIA

1. Al armar los actos, cada hecho tiene su lugar y ninguno es compuesto (medido con gemma en las historias de prod).
2. El lugar del acto nunca contradice a sus hechos: sale de ellos.
3. «Dónde pasa» ya no ofrece combinaciones («Tienda, casa de Ximena») como opciones.
4. La Voz recibe el lugar de cada hecho; las historias viejas, los mismos prompts que hoy.
5. Snapshots revisados; tests y E2E en verde; dev con el cambio.

## 7. BOUNDARIES

- **Always:** lo que cargó la autora manda; el Planificador propone y ella corrige; textos en `config/`.
- **Ask first:** el cambio de esquema (D1); corridas pagas; cambiar lo que recibe la Voz más allá de §2 D.
- **Never:** que la Voz decida los lugares; convertir solos los textos compuestos viejos; migraciones.

## 8. OPEN QUESTIONS

Ninguna abierta: D1 aceptada (el deploy pasa prod con `export-yaml --all` / `import-yaml`) y D6 se mide (§9).

---

## 9. Medición (D6, gemma, gratis)

Script: `scripts/research/710/medir_lugares.py`. Corre el Planificador real con una variante que vive solo en el script: cada hecho es `{texto, lugar}` y el acto ya no trae «escenario». Salidas en `data/dev/research_710/` (fuera de git). Se corre sobre la copia de prod en dev, 16 historias, 2 corridas.

**Prueba (El trabajo de Yadira, 1 corrida, 400 s):** 20 hechos, 20 con lugar, 0 compuestos, 9 lugares. Los lugares acompañan a los hechos (tienda, río, carretera). Detalle a mirar: «Casa» y «Casa de Ximena» aparecen como dos lugares cuando son el mismo.

**Resultado completo (2026-10-28, `gemma_2.json`):** la copia de prod en dev tiene **9** historias (es del 2026-10-22; prod tiene 16 hoy): 18 corridas, ~5 min cada una, sin errores.

| Métrica | Resultado |
|---|---|
| Hechos con lugar | **305 de 305** |
| Lugares compuestos | **2 de 305** (0,7 %): «Pasillos/Enfermeria», «Pasillos/Habitación», en una corrida de «No es tu culpa». Hoy son 31 de 58 actos |
| Mismo lugar con dos nombres en una corrida | 3 pares: «Casa» / «Casa de Ximena» (en la prueba), «Calle» / «Calle Principal», «despacho» / «pasillo_despacho» |
| Lugares por corrida (mediana) | 5 (de 3 a 13) |

Leyendo las corridas a mano:
- **Los lugares acompañan a los hechos.** En Yadira: tienda, plaza, la puerta trasera de la tienda, la carretera al irse, la ciudad al final. Ya no aparece la iglesia que no estaba en la historia, ni se pierde la tienda del acto 3.
- **Tres defectos que se corrigen en el PLAN:**
  1. **Objetos o partes como lugar:** «Puerta», «Ventana», «Pared» («Los forasteros»), «fogata», «montañas». El prompt tiene que pedir un lugar donde se puede estar (la casa, el cuarto de Ingrid, la cueva) y no una cosa del lugar.
  2. **Nombres con formato de código:** «casa_susana», «cueva_en_llamas», «estacion_servicio» («el engaño del diablo», 13 lugares). Que el código los pase a texto («Casa de Susana» no se puede deducir; «casa susana» sí) y que el prompt los pida como los diría una persona.
  3. **Un lugar general y uno más preciso** («Casa» / «Casa de Ximena»). Con D2 (vacío = el anterior) y los lugares ya definidos en el prompt, debería bajar. Medir de nuevo después del ajuste.
- **Conclusión para D6:** gemma da un lugar por hecho y casi nunca compuesto. El diseño se sostiene con un prompt más preciso (1 y 2) y una limpieza mínima en el código («_» → espacio; un compuesto con «/» se queda con el primero).

---

## 10. PLAN (2026-10-28)

Relevado en `feat/spec-700-idea-y-personajes` (`d50427e`; la 710 sale de `development` después de que entre la 700). Principio: **todo lo que lee `events` como texto no cambia** (lista paralela, D1), y para las historias viejas los prompts son **idénticos**.

### 10.1 Decisiones nuevas

| # | Riesgo encontrado | Decisión recomendada |
|---|---|---|
| D8 | `act.scenario` lo leen siete lugares: la Voz, el título del acto en el Verificador, el paquete del video (`video/prompts.py`), «lo conocido» de la repetición, y en el router los usos de un lugar, borrarlo y las opciones de `_state`. | Un solo método: **`ActOutline.places()`**, los lugares del acto en orden y sin repetir (los de `event_places` o, si no hay, `[scenario]`). Todos leen `places()`; `scenario` queda solo como dato viejo. |
| D9 | La medición: objetos como lugar («Puerta», «Pared») y nombres de código («casa_susana»). | Prompt: «el lugar donde se está (la casa, el cuarto de Ingrid, la cueva), no una cosa del lugar (la puerta, la ventana); escrito como lo dirías (con espacios); si sigue en el mismo lugar, el mismo nombre». Código, `_lugar()`: «_» → espacio, primera letra en mayúscula, y un compuesto con «/», «,» o « y » se queda con el primero. |
| D10 | Los lugares que nombra el Planificador hoy quedan sueltos en cada acto: 58 de 58 fuera de la lista. | Al guardar la escaleta, los lugares nuevos de los hechos **se suman a `story.scenarios`** (como los personajes de la autora en la 700). Así son opciones de verdad y la Voz recibe su descripción si la tienen. |
| D11 | Cómo recibe la Voz los hechos con lugar. | Fragmento `voz/hecho_en`: «- En {lugar}: {hecho}» **solo cuando cambia** el lugar (D4); los siguientes en el mismo lugar van como hoy. «DÓNDE» pasa a ser la lista de `places()`, con la descripción de los que la tienen. Sin `event_places`, el texto de hoy. |
| D12 | El campo `needs_review` que la 700 dejó sin uso (D15 de la 700). | Se borra en el mismo cambio de esquema. |
| D13 | Editar un hecho en la tarjeta: hoy cada hecho es un `textarea` sin nada al lado. | Al lado de cada hecho, un `select` compacto con los lugares de la historia, «el mismo de antes» (vacío) y «+ Lugar». El autoguardado manda `event_places` junto con `events`, en el mismo orden. «Dónde pasa» queda como resumen de solo lectura. Las historias viejas (sin `event_places`) siguen viendo el radio de hoy hasta que se armen los actos de nuevo. |
| D14 | El paquete del video (Spec-610) recibe «dónde pasa cada acto». | Lee `places()`, unidos con « · ». Su snapshot cambia solo para escaletas con lugares por hecho. |

### 10.2 S1 — Dominio, base y YAML (D1, D8, D12), sin cambios visibles

| Lugar | Cambio | Precaución |
|---|---|---|
| `models.ActOutline` | `event_places: list[str]` y `places()`; sale `needs_review` | Un validador recorta o completa `event_places` al largo de `events` |
| `connection.init_db` | columna `event_places TEXT DEFAULT '[]'`; sale `needs_review` | `make dev-db` sobre una copia; el pase a prod, con export/import (§10.7) |
| `story_repository` | guarda y lee `event_places` | |
| Los siete lectores de D8 | leen `places()` | Snapshots **idénticos** (las historias de los tests no tienen `event_places`) |
| `ActForm`, `update_act` | `event_places` opcional | Sin la lista, se conserva la guardada si `events` no cambió de largo |
| YAML | `export-yaml` lleva `event_places` dentro de `outline` (sale con `model_dump`); `import-yaml` lo acepta y uno viejo entra sin | Test de ida y vuelta, y uno viejo |

### 10.3 S2 — El Planificador (B, D9, D10)

| Lugar | Cambio |
|---|---|
| `planner.ActoPlan` | `hechos: list[{texto, lugar}]`; sale `escenario` |
| `authoring_planner.md` | La línea de hechos con el lugar (D9); sale «escenario» |
| `planner._to_outline` | `events` + `event_places` (con `_lugar()`) |
| `authoring_jobs` / `GenerateStoryUseCase._plan` | Suman los lugares nuevos a `story.scenarios` (D10) |
| `mock_structured.py` | Hechos con lugar |
| `scripts/research/710/medir_lugares.py` | Pasa a usar el Planificador real; medición de nuevo (gemma, gratis) |

### 10.4 S3 — Lo que reciben las IA (D, D11, D14)

| Lugar | Cambio |
|---|---|
| `outline_narrator` | Hechos con «En {lugar}:» cuando cambia; «DÓNDE» con la lista |
| `fragments/voz/hecho_en.md` (nuevo), README de fragmentos | |
| `verifier._acts_block` | Título del acto con la lista; cada hecho con su lugar |
| `video/prompts.py` | `places()` (D14) |
| Snapshots | Uno nuevo de la Voz con lugares por hecho; los de siempre idénticos |

El aviso `lugar:` (D7) **no entra** en este PLAN: la medición no mostró hechos que nombren otro lugar. Si aparece el error en el uso, va a otra spec.

### 10.5 S4 — La tarjeta del acto (C, D13)

| Lugar | Cambio |
|---|---|
| `_acto.ejs` | Un `select` de lugar al lado de cada hecho; «Dónde pasa» como resumen; el radio solo para las historias viejas |
| `asistente.js` | El autoguardado manda `event_places`; «+ Lugar» desde el `select`; agregar o quitar un hecho mueve su lugar con él |
| Borrar un lugar | La confirmación dice en qué actos y hechos se usa; al borrarlo, esos hechos quedan con «el mismo de antes» |
| Tests | Vitest de la tarjeta; E2E: cambiar el lugar de un hecho, sumar uno, agregar y quitar hechos sin desordenar los lugares; fixtures del asistente con el diff revisado |

### 10.6 S5 — Medición y cierre

- Medición de nuevo con el Planificador real (gemma, las historias de la copia de prod, 2 corridas). Se compara con §9: compuestos, objetos como lugar, nombres de código, lugares duplicados.
- CLAUDE.md (esquema, `places()`, Voz) y PR a `development`.

### 10.7 El pase a prod

Cambia el esquema (`event_places`, sale `needs_review`). Antes de `make deploy`:
1. `export-yaml --all` con el código de prod.
2. Base nueva.
3. `import-yaml` con el código nuevo.

Las historias vuelven como borradores, como dice CLAUDE.md. Se anota en el PR; el deploy lo decide el usuario.

### 10.8 Slices

1. **S1 — Dominio, base y YAML** (sin cambios visibles; prompts idénticos).
2. **S2 — El Planificador.**
3. **S3 — Lo que reciben las IA.**
4. **S4 — La tarjeta del acto.**
5. **S5 — Medición y cierre.**

---

## 11. TASKS (2026-10-29)

**Orden:** el usuario decidió (Spec-700 §12) que el próximo paso es pasar a la nube los roles donde gemma falla, entre ellos el Planificador. La 710 va **después** de esa spec: S2 y S5 usan el Planificador del perfil activo, y la medición de S5 se compara con §9 sea cual sea el modelo. Si la spec de la nube cambia el esquema de salida del Planificador, S2 se ajusta a lo que quede.

### S1 — Dominio, base y YAML (D1, D8, D12)

- **T1.1** `ActOutline.event_places` con un validador que la ajusta al largo de `events`, `places()` (D8); sale `needs_review`. **Hecho cuando:** hay tests unitarios de `places()` (con lugares por hecho, sin ellos, repetidos, vacíos) y del validador.
- **T1.2** `init_db` (columna `event_places`, sale `needs_review`) y `story_repository`. **Hecho cuando:** pasa un test de guardar y leer; `make dev-db` sobre una copia de la base de dev; `make dev-status` en verde.
- **T1.3** Los siete lectores de `scenario` pasan a `places()`. **Hecho cuando:** los snapshots `pipeline`, `voice`, `assistant` y `video` quedan **idénticos** y un `grep` de `.scenario` en `src/` solo encuentra `places()` y el dato viejo.
- **T1.4** `ActForm` / `update_act` con `event_places` opcional (si no viene, se conserva el guardado). **Hecho cuando:** hay tests de integración de los dos casos.
- **T1.5** YAML: `export-yaml` lleva `event_places`; `import-yaml` acepta un YAML viejo sin ellos. **Hecho cuando:** pasan un test de ida y vuelta y otro con un YAML viejo de `input_stories/`.

### S2 — El Planificador (B, D9, D10)

- **T2.1** `ActoPlan.hechos` como `{texto, lugar}`; sale `escenario`. Prompt con la regla de D9. `_lugar()` normaliza: «_» → espacio, mayúscula inicial, de un compuesto queda el primero. **Hecho cuando:** hay tests de `_lugar()` con los casos de §9 («casa_susana», «Cocina / living», «Puerta») y el snapshot del Planificador se regenera a propósito, con el diff revisado.
- **T2.2** `_to_outline` → `events` + `event_places`. Al guardar la escaleta, los lugares nuevos se suman a `story.scenarios` (D10), en `plan_outline` y en `full_generation` sin escaleta. **Hecho cuando:** pasa una integración con el mock donde los lugares de los hechos quedan como opciones de la historia y ningún acto queda con un lugar suelto. `mock_structured` devuelve hechos con lugar.

### S3 — Lo que reciben las IA (D, D11, D14)

- **T3.1** La Voz: fragmento `voz/hecho_en` («- En {lugar}: {hecho}» solo cuando cambia el lugar) y «DÓNDE» con `places()` y sus descripciones. README de fragmentos. **Hecho cuando:** hay un snapshot nuevo de la Voz con lugares por hecho y una sección que se verifica; el de siempre queda idéntico.
- **T3.2** El Verificador (título del acto con la lista, cada hecho con su lugar) y el video (`places()` unidos con « · »). **Hecho cuando:** los snapshots cambian solo en las escaletas con lugares por hecho.

### S4 — La tarjeta del acto (C, D13)

- **T4.1** `_acto.ejs`: un `select` de lugar al lado de cada hecho («el mismo de antes», los lugares de la historia, «+ Lugar»), «Dónde pasa» como resumen y el radio solo para las historias viejas. **Hecho cuando:** pasan los Vitest de los dos modos y los fixtures del asistente se regeneran con el diff revisado.
- **T4.2** `asistente.js`: el autoguardado manda `event_places`; agregar, quitar o subir un hecho lleva su lugar con él; «+ Lugar» desde el `select`. **Hecho cuando:** un E2E cambia el lugar de un hecho, suma uno nuevo y agrega y quita hechos sin desordenar los lugares; al recargar todo sigue igual.
- **T4.3** Borrar un lugar: la confirmación dice en qué actos y hechos se usa, y esos hechos quedan con «el mismo de antes». **Hecho cuando:** hay una integración y un E2E de la confirmación.

### S5 — Medición y cierre

- **T5.1** `medir_lugares.py` con el Planificador real (perfil activo), sobre las historias de la copia de prod, 2 corridas. **Hecho cuando:** los resultados están en §12 y se comparan con §9: compuestos, objetos como lugar, nombres de código, duplicados. Si el Planificador ya está en Claude, el costo estimado se pasa antes de correr.
- **T5.2** CLAUDE.md (esquema, `places()`, la Voz), memoria y PR a `development`, con la nota del pase a prod (§10.7: export/import).

---

## 12. Resultados

### S1 — Dominio, base y YAML (2026-10-29)

- `ActOutline.event_places` (se ajusta al largo de `events` si trae lugares), `event_place(i)` (D2: vacío = el del anterior; el primero vacío = `scenario`) y `places()` (D8). Sale `needs_review` (D12).
- `act_outline.event_places` en `init_db`; sale `needs_review`. El repositorio guarda y lee la lista.
- Los lectores pasan a `places()`: la Voz (`_scenario`: sus lugares con descripción, unidos con «; »), el título del acto en el Verificador y el paquete del video (unidos con « · »), lo conocido del control de repetición y, en el router, los usos de un lugar, borrarlo (también de los hechos, que quedan con «el de antes») y las opciones de `_state`. Con escaletas viejas `places()` es `[scenario]`: **snapshots idénticos**.
- `ActForm.event_places` opcional: los lugares van de a pares con los hechos (un hecho vacío se va con su lugar; un lugar vacío queda). Sin la lista, se conserva la guardada si los hechos no cambiaron de largo.
- YAML: `export-yaml` lleva `event_places` (sale con `model_dump`); un YAML viejo con `needs_review` se importa igual. Hay tests de ida y vuelta y de un YAML viejo.
- **Ensayo del pase a prod** sobre una copia de la base de dev (copia de prod del 2026-10-29): `export-yaml --all` con el código de `development` → base nueva → `import-yaml` con el código nuevo. Volvieron 16 historias, 58 actos, 135 respuestas y 45 personajes (los mismos números).
- **Dev:** se sumó la columna a mano a `data/dev/stories.db` (backup en `data/dev/backup/`, sin script en el repo), para no perder los relatos de la copia.
- 1 107 pytest, 435 Vitest y 88 E2E (Firefox), en verde.

### S2 — El Planificador (2026-10-29)

- `ActoPlan.hechos` es una lista de `{texto, lugar}`; sale `escenario`. El prompt pide el lugar de cada hecho con la regla de D9 (dónde se está, no una cosa del lugar; uno solo, corto, con espacios; si sigue donde el anterior, el mismo nombre) y dice «si un hecho ocurre en otro lugar» en vez de «un acto».
- `_lugar()` (D9): «_» → espacio, primera letra en mayúscula, de un compuesto («/», «,», « y ») queda el primero, sin la aclaración entre paréntesis. Un hecho vacío se va con su lugar. `scenario` del acto = el lugar del primer hecho (D3).
- D10: `lugares.py` (`nuevos`, `con_lugares`). `plan_outline` y `full_generation` sin escaleta suman los lugares de los hechos a `story.scenarios`.
- **Mientras la tarjeta tenga el radio de «Dónde pasa»** (hasta S4): elegir un lugar para el acto (`…/scenarios` con `act`, o cambiar el radio en el autoguardado sin mandar `event_places`) pone todo el acto en ese lugar: el primer hecho con ese lugar y los demás con «el de antes».
- Snapshots: cambia solo el prompt del Planificador; lo que recibe la Voz queda igual (en el mock todos los hechos pasan en el mismo lugar).
- 1 112 pytest, 435 Vitest y 88 E2E (Firefox), en verde. En una corrida falló un E2E de lugares, que mostró el caso del radio (ya resuelto), y en otra el de cancelar en la sala, intermitente como en la 720.

### S3 — Lo que reciben las IA (2026-10-29)

- `ActOutline.events_with_place()`: cada hecho con su lugar solo donde cambia (D4); vacío en las escaletas viejas.
- La Voz: `voz/hecho_en` («- En la terminal: …», con el artículo en minúscula, `lugares.en_lugar`) y «DÓNDE» con los lugares del acto y su descripción (desde S1).
- El Verificador: título del acto con los lugares unidos con « · » (desde S1) y `asistente/verificador/acto/hecho_en` donde cambia el lugar.
- El video: los lugares del acto con « · » (desde S1; D14).
- Snapshot nuevo `voice_prompts_lugares.json` (un acto con dos lugares y uno descripto), con su test de sección. `voice_prompts.json` y el del video, **idénticos**. Los del pipeline suman «En Escenario de ejemplo:» en el primer hecho de cada acto (la escaleta sale del mock, que ya trae lugares).
- 1 115 pytest, 435 Vitest y 88 E2E (Firefox), en verde.

### S4 — La tarjeta del acto (2026-10-29)

- `_acto.ejs`, con lugar por hecho (`data-por-hecho`): **debajo** de cada hecho, un selector compacto con un ícono de ubicación («Donde el anterior», los lugares de la historia, «+ Lugar nuevo…»). Al lado del hecho, en Firefox, el texto quedaba cortado (`field-sizing` no tiene soporte), así que se movió abajo después de la captura. «Dónde pasa» pasa a ser un resumen («La casa · El patio») con los lugares de la historia y su tacho, sin radios. Las escaletas viejas siguen con el radio.
- `asistente.js`: el autoguardado manda `events` y `event_places` alineados. Un hecho nuevo trae su selector; subir o quitar un hecho lleva su lugar. «+ Lugar nuevo…» abre el campo y el lugar queda en ese hecho (`…/scenarios` con `act` y `event`); con lugar por hecho y sin hecho, solo se suma a la historia.
- Borrar un lugar: la confirmación dice en cuántos hechos pasa («hoy está en el acto 1, en 1 hecho»; `_state.scenarios[].hechos`); esos hechos quedan «donde el anterior».
- Una lista de lugares toda vacía es lo mismo que no tener lugares por hecho (`ActOutline`): la tarjeta vuelve al radio.
- Tests: Vitest de los dos modos; E2E nuevo `lugar-por-hecho.spec.ts` («+ Lugar nuevo…» en un hecho; agregar, subir y quitar hechos sin desordenar los lugares; borrar). Los dos E2E del radio arman sus actos sin lugar por hecho, como una escaleta vieja. Fixture del asistente: solo estructura (el envoltorio del hecho y `data-hechos`).
- 1 116 pytest, 437 Vitest y 91 E2E (Firefox), en verde. En una corrida falló el E2E intermitente de cancelar en la sala; la siguiente pasó completa.

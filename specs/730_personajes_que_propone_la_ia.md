# SPEC-730: Los personajes que propone la IA

**Fecha:** 2026-10-29
**Tipo:** SDD: Planificador, Verificador y «Los actos» (avisos de personajes)
**Estado:** TASKS (2026-10-29). Falta el OK para pasar a IMPLEMENT.
**Rama:** a crear desde `feat/spec-720-actos-en-la-nube` (la 720 todavía no entró a `development`)
**Extiende:** Spec-700 B (personajes de la autora), Spec-720 (el Planificador en Claude), Spec-630 B2/B7 (personajes por acto), Spec-530 §445 (nombres inventados en la prosa).

---

## ASSUMPTIONS

1. Lo pidió el usuario (2026-10-29) al leer la medición de la 720: inventar personajes no es malo, sobre todo en historias largas, **si la IA les da un sentido** que empuje la trama («con el punto justo»). La tabla de la 720 los contaba como defecto; ese criterio cambia.
2. Lo que se vio en la medición de la 720: gemma nombraba al azar a gente que la autora dejó sin nombre («sus amigas» → Sofía y Daniela en una corrida, Lupita y Sofía en la otra). Sonnet sumó personajes que la historia necesitaba («El doble de Lautaro», el centro del misterio de «El último cliente»; Juan en «La criatura del río Paraná»).
3. El riesgo real de un personaje inventado es la **prosa** (Spec-530 §445): la Voz lo nombra distinto en cada acto. Si entra a los personajes, la Voz lo recibe con su descripción y lo nombra siempre igual.
4. Lo de la autora manda (Spec-680 D19): la IA propone, pero lo que Vale escribió no se toca. La IA nunca corre sola (Spec-530).
5. El Planificador y el Verificador corren en Sonnet 5.5 (Spec-720); en el perfil local (gemma) esto tiene que andar igual, aunque proponga peor.

---

## OBJECTIVE

Que la IA pueda sumar a la historia un personaje que Vale no imaginó, **solo si dice para qué**: quién es y qué empuja en la trama. Ese personaje entra a la historia sin preguntar, con una nota que lo cuenta. El aviso de «no está entre tus personajes» queda solo para los nombres que la IA puso sin decir para qué.

---

## 1. Relevamiento (2026-10-29)

### 1.1 Cómo es hoy

- **Planificador** (`planner.ActoPlan`): por acto, `en_escena` es una lista de nombres. El prompt dice «los nombres de las PERSONAS que aparecen en el acto», sin nada sobre inventar ni por qué.
- **Regla de personajes** (`verifier.rule_warnings`, Spec-700): todo nombre de «Quiénes están» que no está en la lista (ni es de la autora, ni quien narra, ni la amenaza) da el aviso `elenco:` «La IA puso a «X» en este acto y no está entre tus personajes…», en **cada** acto donde aparece. En la tarjeta: «Sí, es «Y»» si hay un parecido y «Sumarlo a los personajes».
- **Verificador con IA:** su prompt le pide avisar «una persona que aparece en un hecho y no está en el elenco (proponé sumarla)». La regla sin IA ya lo hace, y en la medición de la 720 salieron **avisos duplicados** («Juan aparece en los hechos y no figura en el elenco: sumalo»).
- **Personajes de la historia** (`story.personajes_full`): `name`, `role` (qué hace: «Chofer»), `kind`, `relation`. La Voz recibe `role` o, si no hay, `relation`.

### 1.2 Lo que se quiere

| Caso | Hoy | Con esta spec |
|---|---|---|
| La IA suma a alguien **con un para qué** | Aviso de error en cada acto | Entra solo a los personajes, con `role` = quién es; una **nota de información** en el primer acto donde aparece: «La IA sumó a Juan, el compañero del turno de día: es quien le cuenta la regla a Marcelo.» |
| La IA pone un nombre **sin decir para qué**, o se pasa del tope | Aviso de error | Igual que hoy |
| Un grupo de la autora sin nombres («sus amigas») | gemma les ponía nombre | El prompt pide no ponerles nombre, salvo que una tenga un papel propio (y entonces es una propuesta con su para qué) |
| Vale no quiere al personaje | — | Lo acepta. Si no le cierra, lo saca al final, al corregir el relato (decisión del usuario, 2026-10-29) |

---

## 2. Qué se construye

### A. El Planificador propone, con un para qué

- La escaleta trae, aparte de los actos, `personajes_nuevos: [{nombre, quien_es, para_que}]`. `quien_es` es corto («el compañero del turno de día»); `para_que` dice qué empuja en la trama («le cuenta la regla a Marcelo»).
- El prompt lo permite «solo si empuja la trama», **como mucho 1 en el corto y 2 en el largo** (decisión del usuario), y pide no ponerles nombre a los grupos que la autora no nombró, salvo que uno tenga su propio papel.
- Si propone más del tope, entran los primeros; el resto queda como un nombre sin para qué (el aviso de hoy).

### B. Se suman solos, con una nota

- Al guardar la escaleta (jobs `plan_outline` y `full_generation` sin escaleta), los propuestos que aparecen en «Quiénes están» se suman a los personajes: `role` = `quien_es`, `kind` persona. Es el mismo camino que los de la autora (Spec-700 D22).
- El primer acto donde aparece cada uno trae una nota de información (un aviso con su propia clave, `propuesto:<nombre>`, que se puede cerrar con «Entendido»): «La IA sumó a «Juan», el compañero del turno de día: es quien le cuenta la regla a Marcelo.»
- Como ya está entre los personajes, la regla `elenco:` no lo avisa, y la Voz lo recibe con quién es.

### C. Sin el aviso duplicado del Verificador

- Sale del prompt del Verificador el punto «una persona que aparece en un hecho y no está en el elenco»: lo cubre la regla sin IA.

---

## 3. Decisiones

| # | Pregunta | Decisión o recomendación |
|---|---|---|
| D1 | ¿Cuántos? | **1 en el corto, 2 en el largo** (usuario, 2026-10-29). |
| D2 | ¿Grupos sin nombre? | **No se nombran**, salvo que uno tenga un papel propio (usuario, 2026-10-29). |
| D3 | ¿Y si Vale no lo quiere? | **Lo acepta**; lo saca al final, al corregir el relato (usuario, 2026-10-29). No hay botón de «no lo quiero». |
| D4 | ¿Se suman solos o con un botón? | **Solos, con la nota** (usuario, 2026-10-29). |
| D5 | ¿Dónde vive la nota? | Un `OutlineWarning` con clave `propuesto:<nombre normalizado>` y `source="regla"` en el primer acto, sin contar para el tope de 3 avisos (como el de recurso gastado, Spec-680). En el JSON de `warnings`, sin cambio de esquema. |
| D6 | ¿Y «Revisar» sin rearmar? | `verify_outline` no propone (no arma); solo recalcula los avisos. Los personajes ya sumados quedan. |
| D7 | ¿El perfil local (gemma)? | Mismo esquema y mismo prompt. Si gemma propone sin para qué, es el aviso de hoy. |

---

## 4. Commands

```bash
uv run pytest -q
cd frontend && npx vitest run
cd frontend && npx playwright test
uv run python scripts/research/730/medir_propuestos.py <salida.json> [--yes] [--tope 0.5]
make dev-status
```

## 5. Testing Strategy

- Unit: el esquema del Planificador con `personajes_nuevos`; el tope por largo; quién se suma y quién queda con el aviso de hoy; la nota en el primer acto; el prompt del Verificador sin el punto del elenco.
- Integración con el mock: `plan_outline` suma al propuesto con su `role` y deja la nota.
- Snapshots: Planificador (el pedido nuevo) y Verificador (sin el punto), regenerados a propósito con el diff revisado.
- Vitest y E2E de la nota («Entendido» la cierra y no vuelve).
- Medición (paga, chica): 3 historias largas y 1 corta con Sonnet. ¿Cuántos propone, son de la trama, respeta el tope y no nombra grupos? Costo estimado ~US$ 0,25, con tope.

## 6. SUCCESS CRITERIA

1. En la medición, todo propuesto trae `quien_es` y `para_que`, y respeta el tope (D1).
2. Ningún grupo sin nombre de la autora sale con nombres inventados (D2).
3. Los propuestos entran a los personajes y no dan el aviso `elenco:`; la nota se ve una sola vez.
4. El Verificador ya no repite el aviso de personajes.
5. El usuario lee los propuestos de la medición y está de acuerdo en que «empujan la trama».

## 7. BOUNDARIES

- **Siempre:** lo de la autora manda; el texto en `config/`; corridas pagas con estimado, OK y tope.
- **Preguntar antes:** subir el tope o permitir propuestos en otra parte (las preguntas, la Voz).
- **Nunca:** que la Voz invente personajes en la prosa (sigue avisándose en el control de repetición).

## 8. OPEN QUESTIONS

Ninguna (D4 confirmada el 2026-10-29).

---

## 9. PLAN (2026-10-29)

### 9.1 Decisiones nuevas que salieron del relevamiento

| # | Riesgo encontrado | Decisión |
|---|---|---|
| D8 | `OutlineVerifier.verify` rearma todos los avisos y conserva solo los ignorados: la nota se perdería en la primera revisión. | `verify` conserva los avisos `propuesto:` que traen los actos (aparte del tope de 3, como el de recurso gastado). Cerrada con «Entendido», queda como ignorada y no vuelve. |
| D9 | Al rearmar, el Planificador recibe los avisos visibles de la escaleta anterior como «problemas» (Spec-560 A6): la nota le llegaría como un problema. | `_problems_block` saltea las claves `propuesto:`. |
| D10 | `OutlinePlanner.plan` devuelve `(acts, elapsed)`, y lo desempaquetan dos lugares del código y dos scripts de medición. | No cambia la firma. Después de `plan`, el planificador deja `self.propuestos` (como `respaldos` en la 720). |
| D11 | El tope no puede quedar fijo en el código (nada asume 5 actos). | `personajes_nuevos_max` en `config/llm_beats_definition.yaml` por estructura (largo 2, corto 1), leído con `Estructura`. |
| D12 | La nota en la tarjeta: hoy todo aviso es una nota de aviso con «Ignorar», y el ignorado se lista con «Volver a mostrar». | Con clave `propuesto:`: nota de **información** con «Entendido» (el mismo `…/warnings/dismiss`). Cerrada, no aparece en la lista de ignorados. |
| D13 | Un propuesto que no aparece en ningún «Quiénes están» no tiene acto para su nota. | No se suma: si la IA lo propone y no lo usa, no hace falta. |

### 9.2 Slices

**S1 — El Planificador propone (A, D10, D11, D13)**

| Lugar | Cambio |
|---|---|
| `llm_beats_definition.yaml`, `structure.Estructura` | `personajes_nuevos_max` (largo 2, corto 1) |
| `planner.Escaleta` | `personajes_nuevos: list[{nombre, quien_es, para_que}]` |
| `authoring_planner.md` + fragmento `asistente/planificador/personajes_nuevos` | Cuándo proponer (solo si empuja la trama), el tope, y nada de nombres para los grupos que la autora no nombró |
| `OutlinePlanner.plan` | `self.propuestos`: los primeros hasta el tope, con nombre, quién es y para qué, y que aparezcan en algún «Quiénes están». La nota `propuesto:` en el primer acto donde aparece cada uno |
| `core_messages.yaml` | `verifier.propuesto`: «La IA sumó a «{nombre}», {quien_es}: {para_que}» |
| `mock_structured.py` | Un propuesto en el acto 2 |
| Snapshots | Planificador, regenerado a propósito |

**S2 — Se suman solos y la nota sobrevive (B, D8, D9)**

| Lugar | Cambio |
|---|---|
| `elenco.con_personajes` | Acepta un `role` por nombre (`quien_es`) |
| `authoring_jobs._with_cast`, `GenerateStoryUseCase._plan` | Suman los propuestos además de los de la autora |
| `verifier.verify` | Conserva los `propuesto:` (D8) |
| `planner._problems_block` | Saltea los `propuesto:` (D9) |

**S3 — La nota en «Los actos» (D12)**

| Lugar | Cambio |
|---|---|
| `_acto.ejs` | Nota de información con «Entendido»; no va en la lista de ignorados |
| Tests | Vitest; E2E con el mock: armar → nota en el acto 2 → «Entendido» → no vuelve al recargar ni al revisar |

**S4 — Sin el aviso duplicado, medición y cierre (C)**

- `authoring_verifier.md`: sale el punto de las personas fuera del elenco; snapshot regenerado a propósito.
- `scripts/research/730/medir_propuestos.py`: Planificador y Verificador reales con Sonnet, sobre 3 historias largas (Yadira, Los forasteros, el engaño del diablo) y 1 corta (El último cliente), 1 corrida. Mide cuántos propone, si traen quién es y para qué, el tope, grupos con nombres inventados y avisos duplicados. Estimado ~US$ 0,25, tope US$ 0,50, con OK antes de correr.
- CLAUDE.md, memoria y PR.

Cada slice cierra con tests en verde y dev con el cambio.

---

## 10. TASKS (2026-10-29)

### S1 — El Planificador propone

- **T1.1** `personajes_nuevos_max` por estructura en `llm_beats_definition.yaml` y en `Estructura`, con su validación al cargar. **Hecho cuando:** pasan los tests de `Estructura` (largo 2, corto 1) y `test_sin_cinco_actos_fijos` sigue en verde.
- **T1.2** `Escaleta.personajes_nuevos`, el fragmento `asistente/planificador/personajes_nuevos` (con `{max}`) y la línea en `authoring_planner.md`. **Hecho cuando:** el snapshot del Planificador se regenera a propósito y hay un test de sección («personajes_nuevos»).
- **T1.3** `OutlinePlanner.plan` deja `self.propuestos` y la nota `propuesto:` en el primer acto (D10, D13); `verifier.propuesto` en `core_messages.yaml`; `mock_structured` con un propuesto. **Hecho cuando:** hay tests unitarios de los casos: con para qué, sin para qué, sobre el tope, sin aparecer en ningún acto y ya entre los personajes.

### S2 — Se suman solos y la nota sobrevive

- **T2.1** `elenco.con_personajes` con `role`; `_with_cast` y `GenerateStoryUseCase._plan` suman los propuestos. **Hecho cuando:** una integración con el mock muestra que `plan_outline` deja al propuesto entre los personajes con su `role` y sin aviso `elenco:`.
- **T2.2** `verify` conserva los `propuesto:` (D8) y `_problems_block` los saltea (D9). **Hecho cuando:** hay tests unitarios de los dos; en la integración, `verify_outline` mantiene la nota y, cerrada, no vuelve.

### S3 — La nota en «Los actos»

- **T3.1** `_acto.ejs`: nota de información con «Entendido» y fuera de la lista de ignorados. **Hecho cuando:** pasa el Vitest de la tarjeta, con y sin la nota, y cerrada.
- **T3.2** E2E con el mock: armar → nota en el acto donde aparece → «Entendido» → no vuelve al recargar ni al revisar. **Hecho cuando:** está en verde en Firefox; los fixtures del asistente se regeneran con el diff revisado (si cambian).

### S4 — Sin el aviso duplicado, medición y cierre

- **T4.1** `authoring_verifier.md` sin el punto de las personas fuera del elenco. **Hecho cuando:** el snapshot del Verificador se regenera a propósito y el diff es solo esa línea.
- **T4.2** `scripts/research/730/medir_propuestos.py` (Sonnet, 3 largas + 1 corta, tope US$ 0,50; corre con OK). **Hecho cuando:** los resultados están en §11 y el usuario leyó los propuestos.
- **T4.3** CLAUDE.md, memoria y PR. **Hecho cuando:** suites completas en verde, `make dev-status` en verde y el PR abierto.

---

## 11. Resultados

### S1 — El Planificador propone (2026-10-29)

- `personajes_nuevos_max` por estructura (largo 2, corto 1), validado al cargar (`Estructura`).
- `Escaleta.personajes_nuevos` (opcional: si gemma no la devuelve, anda igual) y el fragmento `asistente/planificador/personajes_nuevos`, al final del prompt del Planificador. Si el tope es 0, no se pide.
- `elenco.propuestos` (los que valen: con quién es y para qué, que no son de la historia ni de la autora, que aparecen en algún acto, hasta el tope) y `elenco.con_nota` (la nota `propuesto:` en el primer acto). `OutlinePlanner.plan` deja `self.propuestos` (D10).
- `verifier.propuesto` en `core_messages.yaml`.
- **Desvío de T1.3:** el mock propone recién en S2. Con el propuesto en el mock, una integración falla hasta que S2 lo suma a los personajes; S1 se prueba con un LLM guionado.
- Snapshots del asistente, de los moldes y del pipeline: cambian solo en el pedido nuevo.
- 1 100 pytest y 432 Vitest, en verde. La UI no cambia en S1.

### S2 — Se suman solos y la nota sobrevive (2026-10-29)

- `elenco.con_personajes` con `role` por nombre. `_with_cast` (`plan_outline`) y `GenerateStoryUseCase._plan` suman los propuestos con quién es, además de los de la autora. `_state.characters` trae `role`.
- `verify` conserva los `propuesto:` sin cerrar, aparte del tope (D8); cerrada, la nota queda como ignorada y no vuelve. `_problems_block` saltea las notas al rearmar (D9).
- El mock propone a «Don Ramón, el sereno de la terminal» en el acto 2. Por eso el snapshot del pipeline lo muestra entre los personajes y en escena, con su quién es (la Voz lo recibe). Se ajustaron 4 integraciones y un E2E (el «Ignorar» del aviso de la IA).
- 1 102 pytest, 432 Vitest y 87 E2E (Firefox), en verde.

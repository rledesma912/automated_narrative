# SPEC-700: La idea cambia y los personajes son de la autora

**Fecha:** 2026-10-28
**Tipo:** SDD — asistente: «Tu idea» ↔ «Preguntas» ↔ «Los actos» (Consultor, Verificador, UI)
**Estado:** TASKS (2026-10-28) — falta el OK para pasar a IMPLEMENT
**Rama:** a crear desde `development` (`8e06077`)
**Extiende:** Spec-530 (asistente), Spec-550 H10 (avisos), Spec-630 B2/B7 (personajes por acto), Spec-670 (molde), Spec-690 (final desde la idea).

---

## ASSUMPTIONS

1. El pedido viene del uso real: Vale va y vuelve varias veces entre «Tu idea», «Preguntas» y «Los actos». Cambia la idea y no ve el cambio en «Preguntas». En «Los actos» le saltan avisos de personajes que ella misma nombró.
2. La IA nunca corre sola (Spec-530): nada de esto lanza una llamada por guardar. Como mucho, **avisa** que conviene pedirla.
3. Lo de la autora manda (Spec-680 D19): una respuesta suya no la pisa la IA. La IA puede **señalar** que ya no coincide, pero no reescribirla.
4. Prod usa `hibrido-sonnet55`: Consultor y Verificador corren en **gemma**. Lo que se diseñe tiene que andar con gemma.
5. Textos en `config/` (Spec-620), tono coloquial (Spec-580), sin migraciones. Si hace falta guardar algo, va en el JSON de `direction` o en las marcas de `asked` (como la 670 y la 690).

---

## OBJECTIVE

Que ir y venir entre los pasos funcione:

- **A.** Si la autora cambia la idea, «Preguntas» y «Los actos» se enteran: se ve que cambió y la IA puede volver a leerla, también contra lo que ya respondió.
- **B.** Un personaje que nombró la autora (en la idea o en sus respuestas) no dispara «¿lo sumamos?». El aviso queda solo para lo que inventó la IA, y una vez resuelto no vuelve a aparecer en los otros actos.

---

## 1. Relevamiento (2026-10-28)

### 1.1 Qué pasa hoy cuando cambia la idea

| Hecho | Dónde |
|---|---|
| Guardar «Tu idea» **no toca** «Preguntas» ni «Los actos» | `authoring_router.update_direction` («No toca el taller ni la escaleta») |
| Cada «Que la IA me pregunte» es una ronda nueva, pero el Consultor evalúa **solo** lo que no tiene respuesta ni está «a propósito» o «No va» | `workshop_rules.to_evaluate` |
| Una pregunta sin responder **conserva su texto** en las rondas siguientes; solo cambia el semáforo. Se hizo a propósito, porque el Consultor reformulaba lo mismo en cada ronda | `workshop_rules.merge_round` |
| Lo evaluado como `cumple` sin respuesta (deducido de la idea) **sí** se vuelve a evaluar | `to_evaluate` |
| El final **sacado de la idea** se vuelve a sacar si la idea ya no lo cuenta (Spec-690 D12). El de las historias viejas (`Direction.ending`) y el que se cambió con «Cambiar» no se actualizan | `final_de_la_idea.needs_it` |
| Con todo respondido, «Preguntame lo que falta» se esconde (`finish = respondido`). Desde «Tu idea», «Que la IA me pregunte» lanza la ronda igual, pero no tiene nada que evaluar | `taller.ejs:21`, `workshop_rules.finish` |
| `ActOutline.needs_review` («a revisar si cambió la dirección») existe en el modelo, la base y el front, pero **ningún código lo pone en `true`** | `models.py:317` |

**Resultado:** después de la primera ronda completa, cambiar la idea no tiene efecto visible en «Preguntas». Los actos tampoco avisan.

### 1.2 Qué pasa hoy con «¿lo sumamos?»

- Lo arma una **regla sin IA** del Verificador (`verifier.py:209`): cada nombre de «Quiénes están» que no está entre los personajes ni es la amenaza → `elenco:<nombre>`. Quien narra nunca dispara el aviso (`cast_names` la incluye).
- Compara **solo con la lista de personajes**, no con lo que escribió la autora.
- **Para qué sirve:** la Voz ve solo a los personajes del acto, con su parentesco (`_scene_story`), y así los llama («mi suegra»). Además, el control de repetición marca los nombres que no están entre los personajes. Un nombre sin ratificar le llega a la Voz sin decir qué es de quien narra.
- «Sumarlo a los personajes» desde el aviso suma el personaje y resuelve **ese** aviso de **ese** acto (`asistente.js:848`, `…/warnings/resolve`). El mismo aviso en los otros actos queda hasta la próxima revisión.
- «Tu idea» carga solo a quien narra. Los demás personajes se suman acto por acto (Spec-630 B2): en una historia nueva, **todo** personaje que no es quien narra arranca fuera de la lista.

### 1.3 El caso real: «El trabajo de Yadira» (prod, 2026-10-28)

Narra Ximena; Yadira es la exnovia de Gael. Las 9 preguntas están respondidas en la ronda 1 y el final viene de `Direction.ending` (historia vieja). Hoy, la idea cambie lo que cambie, «Preguntas» no se mueve.

Avisos de personajes en sus actos (todos de la regla `elenco:`):

| Aviso | ¿De dónde sale el nombre? |
|---|---|
| Yadira (actos 2, 4, 5) | **la idea** («…haber terminado con Yadira, su antigua novia») |
| Gael (2, 4) | **la idea** |
| Mamá de Ximena (3, 5) | **la autora** («la tienda de abarrotes de su mamá», en quién narra) |
| Amigas de Ximena (5) | **la idea** («sus amigas le advierten») |
| Doña Aurelia (3) | **una respuesta de la autora** («la tía de Yadira, Doña Aurelia, sabe hacer trabajos») |
| Amigos de Ximena (2) | variante de «Amigas de Ximena»: la puso la IA |
| Perro de Ximena (4) | la IA |

- **5 de 7 nombres son de la autora.** Solo 2 los puso la IA, y uno de esos es el mismo grupo escrito distinto.
- Vale ya sumó a los cinco a la lista de personajes, pero los avisos siguen ahí (se habían armado antes). El de Yadira en el acto 2 sigue aunque ella ya no está en «Quiénes están» de ese acto.

---

## 2. Qué se construye

### A. Cambiar la idea se nota

- **A1. Saber qué idea leyó la IA.** Al terminar `consult` (y `plan_outline`), se guarda la idea que se leyó (`direction.idea_leida`, en el JSON: sin columnas). «La idea cambió» = la idea de hoy es distinta de esa.
- **A2. «Preguntas» lo dice.** Con la idea cambiada: una nota arriba («Cambiaste tu idea después de estas preguntas. ¿La IA la vuelve a leer?») con el botón de la ronda, **visible aunque todo esté respondido** (hoy se esconde).
- **A3. La ronda con la idea cambiada revisa también lo respondido.** Además de lo pendiente, el Consultor recibe lo respondido y dice, criterio por criterio, si la respuesta **ya no coincide** con la idea, con un motivo corto. La respuesta no se toca: queda con la marca `·no_coincide` en `asked` y en la pantalla una nota con el motivo y dos acciones, «Cambiar» o «Está bien así» (que quita la marca). Lo «a propósito» no se revisa (es decisión de la autora), salvo el final (A4).
- **A4. El final viejo también.** Si el final viene de `Direction.ending` o de un «Cambiar», y la idea cambiada **cuenta otro final**, se señala igual que A3 (no se pisa). El que salió de la idea sigue como hoy (D12 de la 690).
- **A5. «Los actos» ofrecen armarlos de nuevo.** Con la idea cambiada después de armar los actos: se prende `needs_review` en todos (por fin se usa) y arriba va una nota («Cambiaste tu idea después de armar los actos») con **«Armar los actos de nuevo»**. El botón siempre pasa por la confirmación (`ForgeConfirm.ask`, que ya ignora el doble clic, Spec-660) y avisa que reemplaza lo que se editó en los actos: no se dispara por reflejo ni por error. Armar de nuevo apaga la nota; editar un acto le apaga su marca. *Definición a probar con el uso (usuario, 2026-10-28): puede cambiar.*

### B. Los personajes de la autora

- **B1. Lo de la autora no dispara el aviso.** La regla `elenco:` ignora un nombre que aparece en lo que escribió la autora: la idea, quién narra, sus respuestas y sus reglas (`author_text` de la Spec-680, sin los actos).
- **B2. Se suman solos al armar los actos.** Los nombres de «Quiénes están» que están en lo de la autora y no en la lista se suman a los personajes al guardar la escaleta (`plan_outline`), con el parentesco que dio el Planificador si lo dio. Así la Voz los recibe con su relación desde el primer relato.
- **B3. Resolver es en toda la historia.** «Sumarlo a los personajes» resuelve el aviso `elenco:<nombre>` en **todos** los actos, no solo en el que se tocó. Lo mismo al sumar un personaje con «+ Personaje» o al quitar el nombre de «Quiénes están».
- **B4. Variantes del mismo grupo.** «Amigos de Ximena» contra «Amigas de Ximena»: si un nombre se parece mucho a uno de la lista (`workshop_rules.similar`), el aviso propone **usar el que ya está** («¿Es «Amigas de Ximena»?») en vez de sumar uno nuevo.
- **B5. El texto dice para qué sirve.** Por ejemplo: «La IA puso a «Perro de Ximena» en este acto y no está en tu historia. Si lo sumás, decís qué es de quien cuenta y el relato lo nombra siempre igual. Si no va, sacalo del acto».

---

## 3. Decisiones (a confirmar)

| # | Duda | Recomendación |
|---|---|---|
| D1 | ¿Cómo se sabe que la idea cambió? | Guardando la idea leída en `direction` (A1). Comparar espacios normalizados: un retoque de una coma no cuenta como cambio. |
| D2 | ¿Qué cuenta como «la idea»? | «¿De qué trata?» (o la sinopsis en las importadas) y la amenaza de «Tu idea». El título, el género o el habla no. |
| D3 | ¿La ronda revisa lo respondido **siempre** o solo con la idea cambiada? | **Solo con la idea cambiada**: si no, el prompt crece en cada ronda sin motivo, y con gemma eso rinde peor. |
| D4 | ¿Llamada aparte para A3 o dentro del Consultor? | Medirlo con gemma (como §1.3 de la 690). Si dentro del Consultor marca bien en las historias de prod con la idea cambiada a mano, va dentro; si no, va aparte en el mismo job. |
| D5 | ¿Y si la autora ignora la nota? | Nada: es una nota, no un bloqueo. Generar el relato sigue igual. |
| D6 | B2: ¿sumar solos o preguntar? | **Sumar solos** lo que nombró la autora (es suyo). Preguntar solo lo de la IA (B5). *Usuario, 2026-10-28: se suman solos.* |
| D9 | A3: ¿señalar o volver a preguntar? | **Señalar sin pisar** (nota + «Cambiar» / «Está bien así»). *Usuario, 2026-10-28.* |
| D10 | A5: ¿nota o armar de nuevo? | **Ofrecer «Armar los actos de nuevo»**, siempre con la confirmación. *Usuario, 2026-10-28; se revisa con el uso.* |
| D11 | Alcance | **A y B en esta spec**, en slices separados; B primero (chico, sin IA). Los lugares por hecho van aparte: Spec-710. *Usuario, 2026-10-28.* |
| D7 | B1 con nombres genéricos («la vecina»): ¿cuentan como de la autora si el texto dice «una vecina»? | Solo con el nombre tal cual (normalizado). «Mamá de Ximena» contra «su mamá» no coincide literal: va al aviso, que con B5 ya se entiende. |
| D8 | ¿Se revisan los avisos viejos de las historias de prod (los de Yadira)? | No hace falta migrar nada: «Revisar los actos» los vuelve a calcular con la regla nueva. |

---

## 4. Commands

```bash
make test
make lint
cd frontend && npm test && npx playwright test     # Firefox
SNAPSHOT_UPDATE=1 uv run pytest tests/...          # snapshots a propósito, diff revisado
make dev-status
```

## 5. Testing Strategy

- **Unit:** «la idea cambió» (D1/D2); `to_evaluate` con la idea cambiada incluye lo respondido; la marca `·no_coincide` no pisa la respuesta y nunca llega a un prompt como pregunta (`workshop_rules.questions`); la regla `elenco:` con nombres de la idea, de una respuesta y de la IA; resolver en todos los actos; variante parecida.
- **Snapshots:** el Consultor sin la idea cambiada **idéntico**; el nuevo bloque «ya respondido» solo con la idea cambiada (`assistant_prompts`).
- **Integración:** `consult` con el mock, con la idea cambiada → marca un criterio; `plan_outline` suma los personajes de la idea; `update_direction` + escaleta armada → `needs_review`.
- **Front/E2E:** la nota en «Preguntas» con todo respondido; «Está bien así»; la nota en «Los actos»; «Sumarlo» borra el aviso en los otros actos.
- **Medición (gratis, gemma):** las historias de prod con la idea cambiada a mano. ¿Marca lo que ya no coincide sin marcar de más?

## 6. SUCCESS CRITERIA

1. Cambiar «¿De qué trata?» después de responder todo → «Preguntas» lo dice y ofrece la ronda; la ronda señala las respuestas que ya no coinciden sin pisarlas.
2. Cambiar la idea con los actos armados → «Los actos» lo dicen (`needs_review` en uso) y ofrecen «Armar los actos de nuevo», que no corre sin confirmar.
3. En «El trabajo de Yadira», revisar los actos deja como mucho los avisos de «Perro de Ximena» y «Amigos de Ximena» (este, proponiendo «Amigas de Ximena»).
4. En una historia nueva, los personajes nombrados en la idea quedan en la lista al armar los actos.
5. Snapshots revisados; tests y E2E en verde; dev con el cambio.

## 7. BOUNDARIES

- **Always:** lo de la autora manda; la IA solo con comandos explícitos; textos en `config/`.
- **Ask first:** corridas pagas; cambiar criterios del banco o el esquema de salida del Planificador (para B2 con parentesco).
- **Never:** reescribir una respuesta de la autora; lanzar la IA al guardar; columnas nuevas o migraciones.

## 8. OPEN QUESTIONS

Ninguna para el SPECIFY: resueltas en D9–D11 y D6. Quedan para el PLAN: D4 (llamada aparte o dentro del Consultor, se decide midiendo) y el esquema del Planificador para el parentesco de B2 (*ask first*).

---

## 9. PLAN (2026-10-28)

Relevado en `development` (`8e06077`). Principio: **sin IA donde alcance una regla** (B entera y la detección del cambio) y **una sola llamada nueva**, que corre solo cuando cambió la idea (A3).

### 9.1 Decisiones nuevas que salieron del relevamiento

| # | Riesgo encontrado | Decisión recomendada |
|---|---|---|
| D12 | Hay dos momentos que leen la idea: «Preguntas» (`consult`) y «Los actos» (`plan_outline`). La autora puede rearmar los actos sin volver a preguntar, o al revés. | **Dos sellos** en `direction` (JSON, sin columnas): `idea_preguntas` e `idea_actos`, el hash corto de la idea que leyó cada uno. Se ponen al terminar el job. `_direction` los conserva en el autoguardado, como `form_suggested` (D13 de la 670). |
| D13 | D2 decía «la idea + la amenaza». Comparar la amenaza (cuatro campos) suma ruido y casi nunca contradice una respuesta. | **Solo «¿De qué trata?»** (o la sinopsis en las importadas, como `story_block`), con espacios y mayúsculas normalizados. Reemplaza D2. |
| D14 | Historias que ya existen: no tienen sellos. Con «sin sello = cambió», todas mostrarían la nota de golpe. | **Sin sello = no se sabe = no hay nota.** El sello aparece en la próxima ronda o al rearmar. |
| D15 | A5 decía prender `needs_review` en cada acto. Para la definición elegida («Armar de nuevo» con confirmación) no hace falta una marca por acto, y persistirla agrega estados para sincronizar. | **Se calcula** en `_state` (`idea_cambio: {preguntas, actos}`) comparando el hash actual con el sello: sin escrituras al guardar «Tu idea». `needs_review` sigue sin usarse; se borra con el próximo cambio de esquema (Spec-710, que ya recrea la base). |
| D16 | Si la autora no quiere rearmar ni volver a preguntar, la nota quedaría para siempre. | Cada nota trae además **«Dejarlo así»**: pone el sello con la idea actual sin llamar a la IA (`POST …/idea-revisada {paso: preguntas|actos}`). |
| D17 | A3: el Consultor tiene una salida temprana (`analyze` no llama al LLM si no queda nada por evaluar), justo el caso de Vale (todo respondido). Meter la revisión adentro obliga a cambiar su esquema y su prompt, que ya es largo para gemma. | **Llamada aparte** (`RevisorDeRespuestas`, rol `consultor`, prompt en `config/`), en el mismo job `consult`, **antes** del Consultor y **solo** si `idea_cambio.preguntas` y hay respuestas para revisar. Esquema chico: por criterio `{criterio, coincide, motivo}`. Resuelve D4: no hace falta medir dentro contra aparte, solo la calidad (S4). |
| D18 | Dónde guardar «ya no coincide» y su motivo sin columnas. En una respuesta, `question` ya está vacío y la pantalla lo usa para las preguntas abiertas. | Marca en `asked`: **`·no_coincide:<motivo>`** (como `·de_la_idea`). `workshop_rules.questions()` ya filtra las marcas, así que no llega a un prompt. `answer`, `mark_intentional` y `reopen` la quitan; la acción nueva `keep` («Está bien así») también. |
| D19 | Qué revisa el Revisor. | Las respuestas `cumple` con texto y el final `intencional` **sin** `·de_la_idea` (el viejo `Direction.ending` o un «Cambiar»): A4. El final con `·de_la_idea` lo vuelve a sacar la 690 (D12 de la 690). El resto de lo `intencional` («Es así a propósito») no se revisa. |
| D20 | B1/B2: un nombre como «Mamá de Ximena» o «Amigas de Ximena» no aparece literal en la idea («su mamá», «sus amigas»). | Un nombre es **de la autora** si aparece entero (normalizado, con límites de palabra) en `author_text` de la Spec-680, **o** si tiene la forma «<palabra> de <quien narra>» y la palabra aparece. Probado sobre «El trabajo de Yadira»: Yadira, Gael, Doña Aurelia, Mamá y Amigas de Ximena → de la autora; «Amigos de Ximena» y «Perro de Ximena» → no. |
| D21 | B2 pedía el parentesco del Planificador (*ask first*: cambia su esquema). | **No se cambia el Planificador.** Se suman con parentesco vacío, como hoy cuando Vale toca «Sumarlo». La Voz ya los recibe por el nombre en los hechos. Si hace falta el parentesco, es otra spec, con evidencia de un error visto. |
| D22 | Un solo mecanismo para B1 y B2. | `personajes_de_la_autora(story, acts)` (sin IA) devuelve los nombres de «Quiénes están» que son de la autora y no están en la lista. Los runners `plan_outline` y `verify_outline`, y `_plan` de `full_generation`, **los suman antes** de la regla `elenco:`. Así B1 sale solo: cuando la regla corre, ya están en la lista. |
| D23 | La pantalla saca el nombre del aviso con una regex sobre el texto (`PERSONAJE_FUERA`, `_acto.ejs:14`). Cambiar el texto (B5) la rompe. | `OutlineWarning.subject` (JSON, sin columnas): el nombre tal cual. La vista usa `key` (`elenco:`) y `subject`; la regex se va. Para B4, `OutlineWarning.similar`: el nombre de la lista que se le parece (o vacío). |
| D24 | B4: «Es «Amigas de Ximena»» tiene que cambiar el nombre en «Quiénes están» del acto, y no sumar uno nuevo. | `POST …/characters/same {name, as}`: reemplaza `name` por `as` en «Quiénes están» de **todos** los actos y resuelve sus avisos. |

### 9.2 S1 — Los personajes de la autora (B, D20–D24), sin IA

| Lugar | Cambio | Precaución |
|---|---|---|
| `src/application/services/authoring/elenco.py` (nuevo) | `de_la_autora(story, name)` (D20) y `personajes_de_la_autora(story, acts)` (D22) | Reusa `author_text` y `workshop_rules.normalize` |
| `authoring_jobs.plan_outline_runner`, `verify_outline_runner`; `GenerateStoryUseCase._plan` | Suman esos personajes (`kind` persona, sin parentesco) y recargan la historia antes de `verify` | `full_generation` no cambia su conteo de llamadas |
| `verifier.rule_warnings` | `elenco:` con `subject` y `similar` (D23); texto nuevo (B5) | Las claves no cambian: un «Ignorar» viejo sigue valiendo |
| `models.OutlineWarning` | `subject`, `similar` (opcionales) | Snapshots del Verificador idénticos (los avisos no entran al prompt salvo los visibles al rearmar, con su texto) |
| `authoring_router` | `add_character` y `remove_character` resuelven `elenco:<nombre>` en **todos** los actos (B3); `PUT outline/{n}` lo resuelve si el nombre sale de «Quiénes están»; `characters/same` (D24) | |
| `core_messages.yaml` | `verifier.elenco` (B5) y `verifier.elenco_parecido` | Tono de la 580 |
| `_acto.ejs`, `asistente.js` | Sin `PERSONAJE_FUERA`: «Sumarlo» con `subject`; «Es «X»» con `similar` | Fixtures del asistente (`UPDATE_FIXTURES=1`, diff revisado) |

### 9.3 S2 — Se nota que cambió la idea (A1, A2, A5, D12–D16), sin IA

| Lugar | Cambio |
|---|---|
| `models.Direction` | `idea_preguntas`, `idea_actos` (hash corto; `""` = sin sello) |
| `context.py` | `idea_hash(story)` (D13) e `idea_cambio(story) -> {preguntas, actos}` (D14) |
| `authoring_router._direction` | Conserva los sellos |
| `consult_runner`, `plan_outline_runner` | Ponen su sello al terminar bien |
| `authoring_router` | `POST …/idea-revisada {paso}` («Dejarlo así», D16); `_state` trae `idea_cambio` |
| `taller.ejs` / `_taller_contenido.ejs` | Nota arriba con «Que la IA la vuelva a leer» (job `consult`) y «Dejarlo así»; «Preguntame lo que falta» visible con la idea cambiada aunque todo esté respondido |
| `_escaleta_contenido.ejs` | Nota arriba con «Armar los actos de nuevo» (`data-confirmar`, Spec-660: avisa que reemplaza lo editado) y «Dejarlo así» |
| `core_messages.yaml` / vistas | Textos de las notas |

### 9.4 S3 — La IA revisa lo respondido (A3, A4, D17–D19)

| Lugar | Cambio |
|---|---|
| `config/prompts_generation/authoring_revisor{,_system}.md` (nuevos) | La idea, las respuestas (pregunta → respuesta, como `decisions_block`) y qué devolver: `coincide` y, si no, un `motivo` corto en el tono de la 580 |
| `src/application/services/authoring/revisor.py` (nuevo) | `a_revisar(story)` (D19, sin IA) y `RevisorDeRespuestas.revisar(story) -> list[WorkshopItem]` (marca `·no_coincide:<motivo>`) |
| `workshop_rules` | `NO_COINCIDE`, `no_coincide(item) -> str` (el motivo), `keep(item)`; `answer` / `mark_intentional` / `reopen` quitan la marca |
| `consult_runner` | Con `idea_cambio.preguntas`: revisor → guardar → Consultor → sello |
| `WorkshopAction` / `_apply` | Acción `keep` |
| `_state`, `_taller_contenido.ejs` | Por ítem `no_coincide`; nota con el motivo, «Cambiar» y «Está bien así» |
| `mock_structured.py` | Respuesta para el esquema nuevo (marca la primera respuesta) |
| `llm_core_definitions.yaml` | `estimated_seconds.consult` +10 en los perfiles con el consultor en gemma (la mediana corrige sola después, Spec-510) |

### 9.5 S4 — Medición y cierre

- `scripts/research/700/medir_revisor.py` (gemma, gratis): historias de la copia de prod con la idea cambiada a mano, en dos grupos. Unas con un cambio que contradice una respuesta (por ejemplo, en Yadira, «Ximena se queda en el pueblo» contra la respuesta de «Qué hace después»). Otras con un cambio que no contradice nada (reescribir una oración). Mide si marca lo que debe y si marca de más.
- CLAUDE.md, memoria, PR a `development`.

### 9.5.1 S4 — Lo que cambió después de medir (2026-10-29)

La medición con gemma no llegó al umbral, ni con la idea vieja y la nueva (v1) ni con la cita de lo que cambió (v2). Con el mismo prompt, Sonnet 5.5 marcó 12 de 12 y nada de más (§11, S4). Decisiones del usuario:

- **D25.** El Revisor tiene su propio rol, `revisor`, declarado en los perfiles que lo corren en Claude (`hibrido-sonnet55` y `anthropic-sonnet55`: Sonnet 5.5, sin pensar). Un perfil que no lo declara (el local, todo gemma) **no** revisa con IA: gemma marcaba de más y no veía lo obvio.
- **D26.** Si el perfil no declara `revisor` o la llamada falla (sin crédito, clave vencida, sin red, respuesta inválida), la ronda **no** falla y no cae a gemma. Queda una marca programática: `Direction.idea_sin_revisar` = la idea que había leído «Preguntas» antes del cambio. Si ya había una, se conserva la más vieja: la nota muestra todo lo que cambió desde la última revisión. El Consultor sigue como siempre.
- **D27.** «Preguntas» muestra una nota de información (no de aviso), arriba de las preguntas: «Cambiaste tu idea y la IA no pudo fijarse si tus respuestas siguen yendo. Esto es lo que cambió:», con lo que se sacó tachado y en gris y lo que se agregó resaltado, oración por oración (`context.lo_que_cambio`, sin IA). Botón «Listo, ya las revisé» (`POST …/idea-revisada {paso: "respuestas"}`), que borra la marca. Si la idea volvió a ser la de antes, no hay nota.
- **D28.** Una revisión con IA que sale bien después no borra la marca. Revisó solo el último cambio, no el que quedó sin revisar; la nota se va cuando la autora dice que ya revisó.

| Lugar | Cambio |
|---|---|
| `src/config.py` | `revisor` en `LLM_ROLES`; `settings.has_role(role)` |
| `config/llm_core_definitions.yaml` | `roles.revisor` en `hibrido-sonnet55` (con `provider: anthropic`) y `anthropic-sonnet55` |
| `revisor.py` | `ROLE = "revisor"`; `con_ia()`; `sin_revisar(story)` (la marca de D26) |
| `consult_runner` | IA si `con_ia()`; si no, o si la llamada falla, `sin_revisar` y sigue |
| `Direction`, `_direction` | `idea_sin_revisar` (el autoguardado la conserva) |
| `_state`, `IdeaRevisadaForm` | `idea_sin_revisar: {sacado, agregado}` o `null`; paso `respuestas` |
| `_taller_contenido.ejs`, `asistente.js` | La nota de D27 |

### 9.6 Slices

1. **S1 — Los personajes de la autora** (sin IA; resuelve el ruido que vio Vale).
2. **S2 — Se nota que cambió la idea** (sin IA).
3. **S3 — La IA revisa lo respondido.**
4. **S4 — Medición y cierre.**

Cada slice cierra con tests en verde y dev con el cambio (Spec-540 §2.5).

### 9.7 Cambios a la sección 2

- A5 y D2 quedan como dicen D15 y D13: la marca de «a revisar» se calcula y no se guarda, y «la idea» es solo «¿De qué trata?».
- Criterio de éxito 3, probado con D20: en «El trabajo de Yadira», después de revisar los actos quedan solo «Perro de Ximena» y «Amigos de Ximena» (este, con «¿Es «Amigas de Ximena»?»).

---

## 10. TASKS (2026-10-28)

Tests: `make test`, `make lint`, `cd frontend && npm test`, `npx playwright test` (Firefox). Todo gratis: el consultor y el verificador de prod son gemma local. Rama: `feat/spec-700-idea-y-personajes` desde `development`.

### S1 — Los personajes de la autora (D20–D24)

- **T1.1** `elenco.py`: `de_la_autora(story, name)` (entero en `author_text`, o «<palabra> de <quien narra>» con la palabra en `author_text`) y `personajes_de_la_autora(story, acts)` (en «Quiénes están», de la autora, fuera de la lista, sin repetir, sin quien narra ni la amenaza). **Hecho cuando:** tests con nombre de la idea, de una respuesta, de una regla, «Mamá de <narra>», uno de la IA («Perro de <narra>») y uno parecido («Amigos» contra «Amigas»).
- **T1.2** `plan_outline_runner`, `verify_outline_runner` y `GenerateStoryUseCase._plan` suman esos personajes (persona, sin parentesco) antes de verificar. **Hecho cuando:** test de integración con el mock: el elenco queda con los de la idea y la regla `elenco:` no los avisa; `full_generation` hace las mismas llamadas que antes.
- **T1.3** `OutlineWarning.subject` y `.similar`; `rule_warnings` los llena para `elenco:`; textos `verifier.elenco` (B5) y `verifier.elenco_parecido` en `core_messages.yaml`. **Hecho cuando:** tests de la regla (con y sin parecido); las claves no cambian (un ignorado viejo sigue ignorado); snapshots del asistente revisados (solo el texto de los avisos visibles al rearmar, si alguno aparece).
- **T1.4** Resolver en toda la historia (B3): `add_character` y `remove_character` sacan `elenco:<nombre>` de todos los actos; `PUT outline/{n}` lo saca del acto si el nombre ya no está en «Quiénes están»; `POST …/characters/same {name, as}` (D24). **Hecho cuando:** tests de API de los cuatro casos.
- **T1.5** `_acto.ejs` y `asistente.js` sin `PERSONAJE_FUERA`: «Sumarlo a los personajes» con `subject`; «Es «X»» con `similar` → `characters/same`. **Hecho cuando:** Vitest de la vista (los dos botones), `sin-jerga` y `gramatica-visual` en verde; fixtures del asistente regenerados con el diff revisado; E2E: sumar desde un aviso lo borra en los otros actos.
- **T1.6** Cierre: tests y lint; dev: «Revisar los actos» en «El trabajo de Yadira» (copia de prod) deja solo «Perro de Ximena» y «Amigos de Ximena» (con «¿Es «Amigas de Ximena»?»).

### S2 — Se nota que cambió la idea (D12–D16)

- **T2.1** `Direction.idea_preguntas` e `idea_actos`; `context.idea_hash(story)` (solo «¿De qué trata?» o la sinopsis, normalizado) e `idea_cambio(story)` (sin sello = `False`). `_direction` conserva los sellos. **Hecho cuando:** tests: una coma o espacios de más no cuentan como cambio; sin sello, no cambió; el autoguardado no borra los sellos; YAML ida y vuelta sin romperse.
- **T2.2** `consult_runner` y `plan_outline_runner` ponen su sello al terminar bien (no si falla o se cancela); `POST …/idea-revisada {paso}`; `_state.idea_cambio`. **Hecho cuando:** tests de integración y de API (409 con un job activo, como el resto).
- **T2.3** «Preguntas»: nota arriba con «Que la IA la vuelva a leer» y «Dejarlo así»; «Preguntame lo que falta» visible con la idea cambiada aunque esté `respondido` (también en `asistente.js`, que lo esconde sin recargar). **Hecho cuando:** Vitest de la vista con y sin cambio.
- **T2.4** «Los actos»: nota arriba con «Armar los actos de nuevo» (`data-confirmar`, título y botón propios, ícono `aviso`) y «Dejarlo así». **Hecho cuando:** Vitest; E2E: cambiar la idea → la nota en «Los actos» → el botón pide confirmar y cancelar no arma nada.
- **T2.5** Cierre: tests y lint; dev: cambiar «¿De qué trata?» en una historia de prueba con sellos y ver las dos notas.

### S3 — La IA revisa lo respondido (D17–D19)

- **T3.1** `authoring_revisor_system.md` y `authoring_revisor.md`; `revisor.py`: `a_revisar(story)` (D19) y `RevisorDeRespuestas.revisar(story)` (esquema `{criterio, coincide, motivo}` limitado a los criterios a revisar; marca `·no_coincide:<motivo>`). **Hecho cuando:** tests con un LLM guionado (marca, no marca, criterio inventado descartado por el esquema); snapshot del prompt en `assistant_prompts`.
- **T3.2** `workshop_rules`: `NO_COINCIDE`, `no_coincide(item)`, `keep(item)`; `answer`, `mark_intentional` y `reopen` quitan la marca; `questions()` no la devuelve. **Hecho cuando:** tests de cada uno; la marca nunca aparece en un prompt (test sobre el Consultor y el Planificador con un ítem marcado).
- **T3.3** `consult_runner`: con la idea cambiada y algo para revisar → revisor → guardar → Consultor → sello; sin cambio, igual que hoy (sin llamada de más). `WorkshopAction` con `keep`. `mock_structured` para el esquema nuevo. **Hecho cuando:** tests de integración con el mock de los dos caminos y del caso de Vale (todo respondido: corre el revisor y el Consultor no llama al LLM).
- **T3.4** `_state` con `no_coincide` por ítem; `_taller_contenido.ejs`: nota con el motivo, «Cambiar» y «Está bien así». **Hecho cuando:** Vitest; E2E con el mock: cambiar la idea → «Que la IA la vuelva a leer» → una respuesta marcada → «Está bien así» la desmarca.
- **T3.5** `estimated_seconds.consult` +10 (perfiles con el consultor en gemma). Cierre: tests y lint; dev con una historia de prueba (gemma, gratis).

### S4 — Medición y cierre

- **T4.1** `scripts/research/700/medir_revisor.py` sobre la copia de prod: por historia, una idea cambiada que contradice una respuesta conocida y otra reescrita sin contradecir nada; 2 corridas con gemma. **Hecho cuando:** resultados en §11. Contradicciones marcadas: al menos 4 de 5. Marcas de más con la idea reescrita: como mucho 1 de 5. Si no se llega, se ajusta el prompt o se discute antes de cerrar.
- **T4.3** (D25, D26) Rol `revisor`; `con_ia()`; `sin_revisar`; `consult_runner` con los dos caminos y la falla de la API. **Hecho cuando:** tests con el perfil sin `revisor` (nota, sin llamada al Revisor), con un LLM que falla con `LLMUnavailableError` (la ronda termina bien, con la marca) y con IA (como en S3).
- **T4.4** (D27, D28) `idea_sin_revisar` en `_state`, paso `respuestas` y la nota en «Preguntas». **Hecho cuando:** Vitest del parcial; E2E con el mock (perfil sin `revisor`): cambiar la idea → «Que la IA la vuelva a leer» → la nota con lo que se sacó y lo que se agregó → «Listo, ya las revisé» la saca y no vuelve al recargar.
- **T4.2** CLAUDE.md (tabla de roles: el Revisor; avisos de personajes; sellos de la idea), memoria, PR a `development`.

---

## 11. Resultados

### S1 — Los personajes de la autora (2026-10-28)

- `elenco.py` (sin IA):
  - `de_la_autora`: el nombre entero en `author_text`, o «<algo> de <quien narra>» con ese algo en el texto.
  - `personajes_de_la_autora`, `con_personajes`.
  - `clave` / `sin_aviso` (B3).
  - `parecido` (B4): letra por letra; con el mismo «de <alguien>» al final se compara solo lo de adelante. Con el corte en 0,8, «Amigos»/«Amigas de Ximena» se parecen y «Amigas»/«Mamá de Ximena» no.
  - `next_id`: sale del router.
- Los jobs `plan_outline` y `verify_outline` y `full_generation` sin escaleta suman los personajes de la autora antes de revisar (D22). `full_generation` hace las mismas llamadas que antes.
- Aviso `elenco:`:
  - Trae `subject` y `similar` (D23).
  - Texto nuevo (B5): «La IA puso a «X» en este acto y no está entre tus personajes…», con «¿Es «Y»?» si hay un parecido.
  - Las claves no cambian.
- Resolver en toda la historia (B3):
  - Sumar o borrar un personaje, o sacarlo de «Quiénes están» de un acto, resuelve su aviso.
  - `POST …/characters/same` (D24) reemplaza el nombre en todos los actos sin repetirlo.
  - «Sumarlo» ya no llama a `warnings/resolve`: el servidor lo resuelve en todos los actos.
- Tarjeta del acto: sin la regex sobre el texto nuevo; lee `subject` (y el texto viejo como respaldo para los avisos guardados antes, como los de prod). «Sí, es «Y»» antes de «Sumarlo». El fixture cambió solo en el `data-aviso` que ya no hace falta.
- Dev, «El trabajo de Yadira» (copia de prod, gemma): «Revisar los actos» sumó solo a **Doña Aurelia** (sale de una respuesta de Vale) y no quedó **ningún** aviso de personajes. «Perro de Ximena» y «Amigos de Ximena» ya no están en «Quiénes están» de la escaleta actual; esos avisos eran de una versión anterior. Los avisos que quedan son de siembras y de la IA.
- 1 073 pytest, 422 Vitest, 81 E2E (Firefox), lint en verde. Snapshots sin cambios.

### S2 — Se nota que cambió la idea (2026-10-28)

- `Direction.idea_preguntas` / `idea_actos`: el hash de 12 caracteres de «¿De qué trata?» o de la sinopsis, normalizado. Una coma o una mayúscula no cuentan como cambio.
- `context.idea_hash`, `idea_cambio` (sin sello no hay aviso; «Los actos» solo con actos armados) y `con_idea_leida`. Una historia sin dirección no se sella: no se le inventa una dirección.
- Ponen su sello al terminar bien: `consult` («preguntas»), `plan_outline` y `full_generation` sin escaleta («actos»). El autoguardado de «Tu idea» los conserva.
- `POST …/idea-revisada {paso}` («Dejarlo así», D16), con 409 si hay un job activo. `_state.idea_cambio`.
- «Preguntas»: nota con «Que la IA la vuelva a leer» y «Dejarlo así». «Preguntame lo que falta» se ve con la idea cambiada aunque todo esté respondido (también al actualizar sin recargar).
- «Los actos»: nota con «Armar los actos de nuevo», que siempre pide confirmar y avisa que reemplaza lo editado, y «Dejarlo así».
- 1 079 pytest, 425 Vitest, 84 E2E (Firefox), lint en verde. Fixtures del asistente sin cambios.

### S3 — La IA revisa lo respondido (2026-10-28)

- `revisor.py`:
  - `a_revisar` (D19): las respuestas `cumple` del molde y el final decidido que no salió de la idea.
  - `RevisorDeRespuestas.revisar`, rol `consultor`, con el esquema `{criterio, coincide, motivo}` limitado a esos criterios. Marca `·no_coincide:<motivo>` y desmarca lo que ahora coincide. Sin motivo no marca. Sin respuestas no llama a la IA.
  - Prompt en `authoring_revisor{,_system}.md`, que reusa los fragmentos `asistente/decisiones/*`.
- `workshop_rules`: `NO_COINCIDE`, `no_coincide`, `mark_no_coincide` y `keep`. Responder, «Es así a propósito», «Que la IA lo vuelva a preguntar» y «Está bien así» quitan la marca.
- `consult`: con la idea cambiada, el revisor corre antes del Consultor. En el caso de Vale (todo respondido) hay **una sola** llamada: el Consultor no tiene nada que evaluar.
- La acción `keep` del taller y `no_coincide` por ítem en `_state`. «Ya lo tenés» muestra la nota «Esto ya no va con tu idea nueva: …» con «Está bien así»; «Cambiar» sigue al lado.
- Snapshot del asistente: suma solo `revisor`. La historia del snapshot ahora trae la marca en `meta` y los demás prompts quedaron **idénticos**: la marca no se filtra.
- El mock lee los valores de un `Literal` también como `const`. Con un solo criterio Pydantic no escribe `enum`, y el mock devolvía una lista vacía (lo mostró el E2E).
- **Desvío de T3.5:** no se sumaron 10 s a `estimated_seconds.consult`. El revisor corre solo con la idea cambiada; subir la estimación de todas las rondas la empeora en el caso común, y la mediana de los jobs reales se ajusta sola (Spec-510).
- Dev, «Prueba 700» con gemma: la idea nueva termina con «Rosa deja el trabajo y nunca más cuida casas». «Qué hace Rosa después» («Se queda en la casa y la sigue cuidando todo el año…») quedó marcada con «Ahora Rosa se asusta y deja el trabajo.». «Qué quiere Rosa» (juntar plata para estudiar) no se marcó. El job tardó 117 s, con el final sacado de la idea nueva.
- 1 085 pytest, 426 Vitest, 85 E2E (Firefox), lint en verde.

### S4 — Medición y cierre (2026-10-29)

**Medición del Revisor** (`scripts/research/700/medir_revisor.py`, salida en `data/dev/research_700/`, fuera de git). Seis historias de la copia de prod; a cada una se le cambió la idea a mano de dos maneras: «contradice» (choca con una respuesta conocida) y «reescrita» (suma algo que no contradice nada). Dos corridas por variante: 12 de cada una.

| | gemma v1 (idea vieja y nueva) | gemma v2 (lo que cambió + cita) | Sonnet 5.5 (v2) | Umbral |
|---|---|---|---|---|
| Contradicciones marcadas | 7 / 12 | 5 / 12 | **12 / 12** | ≥ 10 / 12 |
| Marcas de más con la idea reescrita | 10 / 12 | 3 / 12 | **0 / 12** | ≤ 2 / 12 |
| Segundos por revisión | ~60 | ~60 | 2–6 | — |

- gemma tiene dos fallas. **Marca de más:** un solo cambio en Yadira («se queda en el pueblo») marcó 5 respuestas, 3 sin relación; «Es invierno» marcó el final del bosque y un gato marcó «Qué puede perder». **No ve lo obvio:** «no se duerme ni un minuto» contra «quedarse dormido» (Paraná), «sin ninguna venda» contra «tiene un vendaje» (maletín), «ya entregó toda la carga» contra «entregar un cargamento urgente» (bosque): 0 de 2 cada uno.
- Sonnet marca a veces una respuesta más de la esperada, casi siempre con razón: «Porque quiere pedir ayuda» contra «sin animarse a pedir ayuda». La única dudosa: en Yadira marcó «Qué descubre» con un motivo que en realidad corresponde a «Cómo termina».
- v2 queda como diseño del prompt: el sello guarda el **texto** de la idea (ya no un hash), el Revisor recibe qué oraciones se sacaron y se agregaron (`context.lo_que_cambio`) y solo marca si cita una oración que de verdad cambió (`_cita`).

**Lo que se construyó después de medir (D25–D28):**
- Rol `revisor` (`LLM_ROLES`, `settings.has_role`), declarado en `hibrido-sonnet55` (con `provider: anthropic`) y `anthropic-sonnet55`. El perfil local no lo declara. `/config/active-profile` muestra el consultor y, si está, el revisor. `evaluate_voice.py` no lo cuenta en el costo de un relato.
- `consult_runner._revisar`: con el rol, Sonnet; si falla (`LLMUnavailableError`, `LLMResponseError`, `LLMStructuredOutputError`) o no hay rol, `revisor.sin_revisar` guarda `Direction.idea_sin_revisar` (la más vieja) y la ronda sigue con el Consultor. Sin respuestas que revisar no queda marca.
- `_state.idea_sin_revisar` = `{sacado, agregado}` o `null` (nada si la idea volvió a la de antes). `POST …/idea-revisada {paso: "respuestas"}` la borra.
- «Preguntas»: nota de información con «Ya no dice» (tachado, gris) y «Ahora dice», y «Listo, ya las revisé». Va arriba de «Cómo viene tu historia».
- El arnés E2E corre el Revisor como un perfil con el rol; una idea con «SIN CRÉDITO» simula que la API no atiende.
- 1 089 pytest, 429 Vitest, 86 E2E (Firefox), lint en verde. Snapshots sin cambios en S4 después del de v2 (solo `revisor`).
- Dev: «Prueba 700» quedó con una nota pendiente sembrada a mano, para ver cómo se ve.


---

## 12. Evolutivo: el próximo paso (2026-10-29)

Lo dejó el usuario como siguiente trabajo, con su propia spec: **el Planificador y el Verificador en Claude**. Es donde más falla gemma: lugares que son objetos y lugares duplicados (Spec-710 §9), recursos gastados que no evita (Spec-680 S5) y avisos de más. Decisión del usuario: **no** se comparan otros modelos locales. Un 27B no entra en la RTX 3060 de 12 GB, sería lento y no se espera que alcance a Sonnet en tareas de criterio. Se va directo a la nube en los roles donde gemma falla. La spec nueva define qué roles van y verifica con las historias de Vale que los defectos desaparecen, con el costo estimado antes de correr llamadas pagas. Se cruza con la Spec-710.

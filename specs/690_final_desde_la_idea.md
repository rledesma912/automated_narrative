# SPEC-690: El final sale de la idea («¿Cómo termina?» se va de «Tu idea»)

**Fecha:** 2026-10-22
**Tipo:** SDD — UI del asistente + Consultor (una llamada más) + de dónde leen el final el Planificador, el Verificador y la Voz
**Estado:** TASKS (esperando OK); SPECIFY y PLAN aprobados 2026-10-22
**Rama:** `feat/spec-690-final-desde-la-idea` (desde `development`, `53a967d`)
**Extiende:** Spec-530 (asistente), Spec-550 H1 (escribir el final es decidirlo), Spec-670 (molde: el criterio `final` es de la base).

---

## ASSUMPTIONS

1. El pedido viene de la hija del usuario: «saquen "¿Cómo termina?" porque ya lo escribo en "¿De qué trata?"». Los datos de prod le dan la razón (§1.2).
2. Lo que no se pierde: **escribir el final es decidirlo** (Spec-550 H1). Si la autora contó cómo termina, el Planificador no lo cambia y la Voz cierra con eso.
3. La IA nunca corre sola: sacar el final de la idea es parte de un comando explícito («Que la IA me pregunte»), no un efecto del autoguardado.
4. Prod usa `hibrido-sonnet55`: el Consultor es **gemma**. Lo que se diseña tiene que andar con gemma (medido en §1.3).
5. Textos en `config/` (Spec-620), tono coloquial (Spec-580), sin migraciones (el esquema no cambia).

---

## OBJECTIVE

Que la autora cuente su historia una sola vez. «Tu idea» pierde «¿Cómo termina?»; cuando pide las preguntas, la IA se fija si la idea ya cuenta el final y, si lo cuenta, lo deja resuelto en «Preguntas» («lo sacamos de tu idea»), donde se puede corregir. Desde ahí, el final manda igual que hoy.

---

## 1. Relevamiento (2026-10-22)

### 1.1 Qué hace hoy «¿Cómo termina?» (`Direction.ending`)

| Dónde | Qué hace | Archivo |
|---|---|---|
| Dominio | `ending_intentional` se deriva de que haya texto (H1) | `models.py:205` |
| Preguntas | el criterio `final` queda «A propósito» con ese texto; la IA no pregunta por el final | `workshop_rules.initial_items` |
| Planificador | el último acto pide «cerrar con el final del autor» y lleva la decisión `final` | `planner.py:88`, `_acts_block` |
| Verificador | ubica `final` en el último acto, siempre | `verifier.py:87` |
| Voz | en el último acto: «cerrar la historia con el final que decidió el autor: …» | `outline_narrator._function`, `voz/final_del_autor` |
| Contexto del asistente | «CÓMO TERMINA … (decidido)» en el bloque de la historia | `context.py:58` |
| Lo del autor | suma el final a lo que no se marca como inventado (Spec-680) | `repetition_check.known_text`, `recursos_gastados.author_text` |

**Bug de hoy, de paso:** si la autora cambia el final en «Preguntas» («Cambiar» en «Cómo termina»), la próxima ronda `initial_items` lo pisa con `Direction.ending`, y el Planificador y la Voz siguen leyendo `Direction.ending`. Hay **dos lugares** para el final y no se hablan.

### 1.2 Las 9 historias de prod

| Cómo está el final | Historias |
|---|---|
| La idea cuenta el final y «¿Cómo termina?» lo repite (casi o literalmente copiado del último párrafo) | 5: El último cliente, El empleado del maletín, La criatura del río Paraná, No es tu culpa, el engaño del diablo |
| La idea cuenta el final y «¿Cómo termina?» está vacío | 2: Los forasteros, la cosa agachada |
| El final está **solo** en «¿Cómo termina?» | 2 (las más viejas): El trabajo de Yadira, No te detengas en el bosque |

En las dos con el campo vacío, el final de la idea hoy **no** cuenta como decidido.

### 1.3 Medición con gemma (consultor de prod, gratis, 2 corridas por historia)

Script: `scripts/research/690/medir_final.py`; salidas en `data/dev/research_final/` (fuera de git).

- **¿La idea cuenta el final?** 9 de 9 bien, en las dos variantes y las dos corridas (Yadira y el bosque: no).
- **Variante 1 — copiar el final entero:** bien en 5 de 7. En «Los forasteros» copió el susto del medio y perdió el final real («días después les cuentan de una leyenda»); en «la cosa agachada» copió 206 palabras (clímax + final).
- **Variante 2 — marcar dónde empieza el final; el código toma desde ahí hasta el final de la idea:** bien en 6 de 7, estable entre corridas, siempre texto de la idea, ~7 s.

| Historia | Dónde empieza el final (variante 2) | |
|---|---|---|
| el engaño del diablo | «al llegar a una estación de servicio…» | ✓ |
| Los forasteros | «días después, cuando van al pueblo, les cuentan de una leyenda…» | ✓ |
| El último cliente | «Lautaro cuenta que al final corrió hasta la casa…» | ✓ |
| La criatura del río Paraná | «Después cuenta que ya no pasó nada más…» | ✓ |
| No es tu culpa | «Verónica cuenta que desde ese momento…» | ✓ |
| El empleado del maletín | «Nunca más volvió a ver a Arturo…» | ✓ (más corto que el de la autora) |
| la cosa agachada | «el muchacho… mira la tierra blanda…» | ✗ arranca antes (incluye el hallazgo de la novia) |

---

## 2. Qué se construye

### A. «Tu idea» sin «¿Cómo termina?»
- Sale la tarjeta de `direccion.ejs` y el campo del autoguardado. El servidor **conserva** el `Direction.ending` guardado (como `form_suggested`, D13 de la 670): las historias viejas no lo pierden.
- La ayuda de «¿De qué trata?» invita a contar también cómo termina («Contala de punta a punta, con el final si ya lo sabés»).

### B. La IA saca el final de la idea (comando explícito)
- Dentro del job `consult` («Que la IA me pregunte»), **antes** del Consultor: una llamada corta, rol `consultor`, con la variante 2 (§1.3): `{cuenta_final, inicio}`. El código busca `inicio` en la idea y toma desde ahí hasta el final; si no lo encuentra textual, no inventa: el final queda para preguntar.
- Prompt en `config/prompts_generation/authoring_final*.md` (Spec-620).
- Si la idea cuenta el final → el criterio `final` queda resuelto con ese texto, marcado como **sacado de la idea**. Si no → «Preguntas» lo pregunta como hoy.
- No se vuelve a sacar si la autora ya lo tocó (lo cambió o lo respondió). Si se sacó de la idea y la idea cambió, se vuelve a sacar en la próxima ronda.

### C. Un solo lugar para el final
- El final de la autora vive en el criterio `final` de «Preguntas» (respuesta decidida). `Direction.ending` queda como dato viejo: si una historia lo tiene y el criterio no tiene respuesta, se toma de ahí (Yadira, el bosque).
- Un helper (`context.author_ending(story)`) es lo único que leen el Planificador, el Verificador, la Voz, el contexto del asistente y «lo del autor» (Spec-680). Arregla el bug de §1.1.

### D. «Preguntas»
- «Cómo termina» resuelto con la marca «Lo sacamos de tu idea» y «Cambiar» (recortar o reescribir; queda como decidido por la autora) o «Que la IA lo vuelva a preguntar».
- Si la idea no cuenta el final, la pregunta de siempre.

---

## 3. Decisiones

| # | Duda | Recomendación |
|---|---|---|
| D1 | ¿Cómo saca la IA el final? | **Variante 2** (marca dónde empieza; el código corta), medida en §1.3. |
| D2 | ¿Llamada aparte o dentro del Consultor? | **Aparte**, en el mismo job: el prompt del Consultor ya es largo y gemma rinde peor con más tareas. Con gemma es gratis (~7 s); se suma a la estimación de `consult`. |
| D3 | ¿Y si la autora va directo a «Los actos» sin pedir preguntas? | El mismo paso corre al empezar `plan_outline` (y al armar los actos dentro de `full_generation`) si el final todavía no está resuelto. Sigue siendo parte de un comando explícito. |
| D4 | ¿Qué cuenta como «final decidido»? | Una respuesta en el criterio `final`: sacada de la idea, escrita o elegida por la autora, o el `Direction.ending` viejo. «Decidí vos» (la IA elige una opción) **también** cuenta: la autora lo aceptó. |
| D5 | ¿Cómo se marca «sacado de la idea»? | Con una marca en `asked` (como `·no_aplica_rechazado` de la 670): sin columnas nuevas. «Cambiar» la quita. |
| D6 | Historias viejas con el final aparte (Yadira, el bosque) | Su `Direction.ending` sigue valiendo y se ve en «Preguntas» como hoy; al cambiarlo ahí, pasa al criterio (la fuente nueva). Usuario, 2026-10-22: se ve y se edita en «Preguntas». |
| D7 | ¿Revisar el final antes de los actos? | **No**: alcanza con poder corregirlo en «Preguntas» (usuario, 2026-10-22). |
| D8 | YAML (`export-yaml` / `import-yaml`) | Viaja como hoy (`direction.ending` + taller). Un YAML viejo con `ending` entra igual. |
| D9 | La ayuda de «¿De qué trata?» | **Invita a contar el final**, sin hacerlo obligatorio (usuario, 2026-10-22). |
| D10 | Un corte que arranca antes («la cosa agachada») | **Alcanza con «Cambiar»** en «Preguntas»; no se ajusta el prompt (usuario, 2026-10-22). |

---

## 4. Commands

```bash
make test
cd frontend && npm test && npx playwright test     # Firefox
SNAPSHOT_UPDATE=1 uv run pytest tests/...          # snapshots a propósito, diff revisado
uv run python scripts/research/690/medir_final.py data/dev/research_final/<salida>.json 2
make dev-status
```

## 5. Testing Strategy

- **Unit:** corte de la idea desde `inicio` (textual, con espacios distintos, no encontrado → sin final); `author_ending` con cada origen (criterio, `Direction.ending` viejo, nada); el bug de §1.1 (cambiar en «Preguntas» manda sobre `Direction.ending`); el paso no corre si la autora ya decidió el final.
- **Snapshots:** el prompt nuevo (`assistant_prompts`), y los de siempre **sin cambios** cuando el final viene de `Direction.ending` (mismo texto en el Planificador y la Voz).
- **Integración:** `consult` con el mock deja «Cómo termina» resuelto y marcado; `plan_outline` sin consulta previa también.
- **Front/E2E:** «Tu idea» sin el campo; «Preguntas» con la marca y «Cambiar».

---

## 6. SUCCESS CRITERIA

1. «Tu idea» no tiene «¿Cómo termina?»; las historias viejas conservan su final.
2. Con la idea que cuenta el final, después de «Que la IA me pregunte» el final aparece resuelto en «Preguntas» y la Voz cierra con él (prompt del último acto).
3. Con gemma, en las 9 historias de prod: detecta si hay final 9/9 y el corte es correcto en al menos 6 de 7 (lo medido).
4. Cambiar el final en «Preguntas» cambia lo que reciben el Planificador y la Voz (bug de §1.1).
5. Snapshots revisados; tests y E2E en verde; dev con el cambio.

## 7. BOUNDARIES

- **Always:** el final de la autora manda; la IA solo con comandos explícitos; textos en `config/`.
- **Ask first:** corridas pagas; cambiar el criterio `final` del molde (banco de criterios).
- **Never:** inventar un final que no está en la idea; borrar `Direction.ending` de las historias; columnas nuevas o migraciones.

## 8. OPEN QUESTIONS

Ninguna: resueltas en D9 y D10.

---

## 9. PLAN (2026-10-22)

Relevado en `feat/spec-690-final-desde-la-idea` (`53951d1`). Principio: **un solo lugar para el final** y, para las historias que ya tienen su final, prompts **iguales a hoy**.

### 9.1 Decisiones nuevas que salieron de la revisión

| # | Riesgo encontrado | Decisión recomendada |
|---|---|---|
| D11 | **Cómo se guarda el final sacado de la idea** sin que el resto lo trate distinto. | Criterio `final` con estado `intencional` (como hoy con `Direction.ending`: el Consultor no lo evalúa y las decisiones lo listan como «decidido por el autor») y la marca `·de_la_idea` en `asked` (como `·no_aplica_rechazado`, D12 de la 670). Con `cumple` no sirve: `decisions_block` toma el último `asked` como la pregunta y mostraría la marca. |
| D12 | **La idea cambia después de sacar el final.** | Si el final tiene la marca y su texto **ya no está** en la idea, se vuelve a sacar en la próxima ronda (o al armar los actos). Si sigue estando, no se toca. Sin guardar nada más. |
| D13 | **«Que la IA lo vuelva a preguntar» en el final** lo vaciaría y la ronda siguiente lo volvería a sacar de la idea: el botón no haría nada. | `reopen` del final suma la marca `·final_preguntar`: ya no se saca de la idea; el Consultor lo pregunta. |
| D14 | **El bug de §1.1:** `initial_items` pisa el final con `Direction.ending` en cada ronda. | Solo lo copia si el criterio **no tiene respuesta** (historias viejas). Lo que la autora cambió en «Preguntas» manda. |
| D15 | Quién manda entre el criterio y `Direction.ending`. | `context.author_ending(story)`: la respuesta del criterio `final` (`cumple` o `intencional`, con texto); si no hay, `Direction.ending`. Lo usan el Planificador (`ending_fixed`, la decisión `final` en el último acto), el Verificador, la Voz (`_function`), `story_block` y «lo del autor» (Spec-680). Con el mismo texto, los prompts no cambian. |
| D16 | El tiempo estimado de «Que la IA me pregunte» sube ~7 s con gemma. | `estimated_seconds.consult` y `plan_outline` +10 en los perfiles con el consultor en gemma (la mediana de los jobs reales corrige sola después, Spec-510). |

### 9.2 S1 — Un solo lugar para el final (D14, D15), sin UI

| Lugar | Cambio | Precaución |
|---|---|---|
| `context.py` | `author_ending(story)` (D15) | Test con cada origen |
| `planner.py` (`plan`, `_acts_block`), `verifier.py:87`, `outline_narrator._function`, `context.story_block`, `repetition_check.known_text`, `recursos_gastados.author_text` | leen `author_ending` en vez de `Direction.ending` / `ending_intentional` | Snapshots **idénticos** (las historias de los tests traen el final en `Direction.ending`) |
| `workshop_rules.initial_items` | copia `Direction.ending` solo si el criterio no tiene respuesta (D14) | Test del bug: cambiar el final en «Preguntas» → el Planificador y la Voz reciben el nuevo |

### 9.3 S2 — La IA saca el final de la idea (B, D1–D3, D11–D13)

| Lugar | Cambio |
|---|---|
| `config/prompts_generation/authoring_final{,_system}.md` (nuevos) | El prompt medido (variante 2): `{cuenta_final, inicio}` |
| `src/application/services/authoring/final_de_la_idea.py` (nuevo) | `FinalDeLaIdea.ensure(story) -> list[WorkshopItem] | None`: no hace nada si el final ya está decidido por la autora o tiene `·final_preguntar`; si tiene `·de_la_idea` y sigue en la idea, tampoco (D12). Si no: llama, busca `inicio` en la idea (espacios normalizados) y corta hasta el final; si no lo encuentra, nada (nunca inventa) |
| `authoring_jobs.consult_runner`, `plan_outline_runner`; `GenerateStoryUseCase._plan` | Corren `ensure` antes del Consultor / Planificador y guardan el criterio |
| `workshop_rules.reopen` | En `final`, suma `·final_preguntar` (D13) |
| `mock_structured.py` | Respuesta para el esquema nuevo: la última oración de la idea |
| `llm_core_definitions.yaml` | D16 |
| `scripts/research/690/medir_final.py` | Pasa a usar el servicio (mismo prompt de `config/`): la medición repite §1.3 con el código real |

**Tests:** corte (textual, espacios, no encontrado), D12, D13, que no corra con el final decidido, `consult` y `plan_outline` con el mock dejan el final resuelto y marcado, snapshot del prompt nuevo en `assistant_prompts`.

### 9.4 S3 — La UI

| Lugar | Cambio |
|---|---|
| `direccion.ejs`, `asistente.js` | Sin «¿Cómo termina?»; la ayuda de «¿De qué trata?» invita a contar el final (D9) |
| `authoring_router._direction` | Conserva el `Direction.ending` guardado (el formulario ya no lo trae) |
| `_state` | Cada ítem trae `de_la_idea` |
| `_taller_contenido.ejs` | «Cómo termina» con el chip «De tu idea» y una pista («Lo sacamos de tu idea. Si no es así, tocá «Cambiar».») |
| Tests | Vitest de las dos vistas; E2E: el flujo completo sin el campo (el final sale de la idea con el mock) y «Cambiar» el final; fixtures del asistente (`UPDATE_FIXTURES=1`, diff revisado) |

### 9.5 S4 — Cierre

Repetir la medición con el servicio real (gratis, gemma) y anotarla; CLAUDE.md (Spec-550 H1 ahora: el final sale de la idea o de «Preguntas»); PR a `development`.

### 9.6 Slices

1. **S1 — Un solo lugar para el final** (arregla el bug; sin cambios visibles).
2. **S2 — La IA saca el final de la idea.**
3. **S3 — La UI** (sale el campo, la marca en «Preguntas»).
4. **S4 — Medición y cierre.**

Cada slice cierra con tests en verde y dev con el cambio.

---

## 10. TASKS (2026-10-22)

Tests: `make test`, `cd frontend && npm test`, `npx playwright test` (Firefox), `make lint`. Todo gratis: el consultor de prod es gemma local.

### S1 — Un solo lugar para el final (D14, D15)

- **T1.1** `context.author_ending(story)`: la respuesta del criterio `final` (`cumple` o `intencional`, con texto, solo de los criterios del molde) o, si no hay, `Direction.ending`. **Hecho cuando:** tests con cada origen y sin final.
- **T1.2** Leen `author_ending`: `planner.plan` (la decisión `final` en el último acto) y `_acts_block` (`ending_fixed`), `verifier.verify`, `outline_narrator._function`, `context.story_block`, `repetition_check.known_text`, `recursos_gastados.author_text`. **Hecho cuando:** todos los snapshots **idénticos** (sin `SNAPSHOT_UPDATE`).
- **T1.3** `workshop_rules.initial_items`: copia `Direction.ending` solo si el criterio `final` no tiene respuesta (D14). **Hecho cuando:** test del bug: con `Direction.ending` = A y el criterio cambiado a B en «Preguntas», el Planificador y la Voz reciben B y una ronda nueva no lo pisa.
- **T1.4** Cierre: tests y lint en verde; dev al día.

### S2 — La IA saca el final de la idea (D1–D3, D11–D13, D16)

- **T2.1** `authoring_final_system.md` y `authoring_final.md` con el prompt medido (variante 2); `final_de_la_idea.py` con `FinalDeLaIdea.ensure(story)`: no corre con el final decidido por la autora, con `·final_preguntar`, ni con `·de_la_idea` si el texto sigue en la idea (D12); si corre, `{cuenta_final, inicio}` → corte desde `inicio` (espacios normalizados) hasta el final de la idea → criterio `final` `intencional` + `·de_la_idea`; si `inicio` no está en la idea, nada. **Hecho cuando:** tests de cada caso con un LLM guionado; snapshot del prompt en `assistant_prompts`.
- **T2.2** `mock_structured`: para el esquema nuevo, la última oración de la idea.
- **T2.3** `consult_runner`, `plan_outline_runner` y `GenerateStoryUseCase._plan` corren `ensure` antes y guardan el criterio. **Hecho cuando:** tests de integración: `consult` y `plan_outline` con el mock dejan «Cómo termina» resuelto y marcado; con el final ya decidido, no se llama al LLM de más.
- **T2.4** `workshop_rules.reopen` en `final` suma `·final_preguntar` (D13). **Hecho cuando:** test: reabrir y volver a consultar → el Consultor lo pregunta, no se saca de la idea.
- **T2.5** `estimated_seconds` (D16). `medir_final.py` usa el servicio.
- **T2.6** Cierre: tests y lint; dev: «Que la IA me pregunte» en una historia de la copia de prod (con gemma, gratis) y ver el final en «Preguntas».

### S3 — La UI (A, D)

- **T3.1** `direccion.ejs` y `asistente.js` sin «¿Cómo termina?»; ayuda de «¿De qué trata?» que invita a contar el final (D9); `_direction` conserva el `Direction.ending` guardado. **Hecho cuando:** test de API: el autoguardado sin `ending` no borra el de una historia vieja.
- **T3.2** `_state`: `de_la_idea` por ítem; `_taller_contenido.ejs`: chip «De tu idea» y la pista en «Cómo termina». **Hecho cuando:** Vitest de las dos vistas; `sin-jerga` y `gramatica-visual` en verde; fixtures del asistente regenerados con el diff revisado.
- **T3.3** E2E: el flujo completo sin el campo (el final sale de la idea con el mock) y «Cambiar» el final; `visual-snapshots` sin `ending` en el formulario.
- **T3.4** Cierre: dev: «Tu idea» y «Preguntas» de «Los forasteros» (copia de prod).

### S4 — Medición y cierre

- **T4.1** `medir_final.py` con el servicio real sobre las 9 historias, 2 corridas (gemma, gratis). **Hecho cuando:** resultados en §11 contra el criterio 3 de §6.
- **T4.2** CLAUDE.md (Spec-550 H1 → el final sale de la idea o de «Preguntas»; `author_ending`; job `consult`), memoria, PR a `development`.

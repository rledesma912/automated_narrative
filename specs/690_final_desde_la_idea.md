# SPEC-690: El final sale de la idea («¿Cómo termina?» se va de «Tu idea»)

**Fecha:** 2026-10-22
**Tipo:** SDD — UI del asistente + Consultor (una llamada más) + de dónde leen el final el Planificador, el Verificador y la Voz
**Estado:** PLAN (esperando OK); SPECIFY aprobado 2026-10-22
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

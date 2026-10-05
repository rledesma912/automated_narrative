# SPEC-640: La Voz cuenta una anécdota, no escribe literatura

**Fecha:** 2026-10-05
**Tipo:** SDD — calidad de la prosa de la Voz
**Estado:** S1–S3 ✅ (2026-10-05) en dev; falta la lectura a ciegas de Yael (criterio 2). D1–D4 con lo recomendado (OK del usuario 2026-10-05)
**Rama:** `feat/spec-640-voz-anecdota` (desde `development`, `4253c48`)
**Extiende:** Spec-470 (oficio de la Voz), Spec-590 (prosa según la prueba con usuarias), Spec-600 (Voz en Sonnet 5.5), Spec-530 §8.3 (control de repetición).

---

## ASSUMPTIONS

1. La máxima del pipeline (CLAUDE.md, 2026-09-27) sigue: la Voz recibe un arnés **simple y asertivo**; lo que solo aparece en la prosa se **detecta después y se muestra**, nunca se corrige solo. Cada regla o chequeo nuevo previene un error visto de verdad: acá, los ejemplos de la hija (H1, H2).
2. Los textos que lee la Voz viven en `config/prompts_generation/` (Spec-620); nada en Python.
3. El perfil activo sigue siendo `hibrido-sonnet55` (Voz en Sonnet 5.5, effort `low`, sin `temperature`). No se cambia de modelo en esta spec.
4. Medir cuesta plata real (~US$ 0,09 por relato, Spec-600 §7): cada corrida con `--yes` se avisa antes.
5. Quien juzga es la usuaria (la hija, autora de «El engaño del diablo»); las métricas solo ayudan a ver si el cambio fue en la dirección correcta.

---

## OBJECTIVE

Que el relato suene a **alguien contando algo que le pasó** («lo más anécdota posible»), no a un cuento escrito: sin metáforas ni personificaciones, con comparaciones de todos los días y pocas, y sin las muletillas que la IA repite entre relatos.

---

## 1. HALLAZGOS (comentario de la hija, 2026-10-05)

> «A veces se pone MUY LITERARIO, cuando tiene que sonar lo más realista posible, lo más "anécdota" posible.»

### H1 — Imágenes literarias · **prompt + detección**

Ejemplos que marcó, todos de «el engaño del diablo» (prod, 01/10, Sonnet 5.5). Están en `macro_beat` (texto original de la Voz), o sea: no son de su corrección.

| Frase | Acto | Qué tiene de literario |
|---|---|---|
| «con la linterna de Juan abriendo un círculo amarillo que temblaba sobre la roca» | 2 | imagen pictórica (la luz «abre» y «tiembla») |
| «las paredes y el techo se iluminaron de un naranja furioso … llamas que subían como una cortina» | 3 | adjetivo afectivo para un color, comparación de escritor |
| «hasta que la oscuridad se lo tragó» | 2 | personificación |
| «Juan bajó la linterna como si le pesara» | 3 | «como si» de efecto |

**Qué pasa hoy:** `voice_craft.md` pide contar «como alguien que se lo cuenta a otra persona», pero **no dice nada de las imágenes**: prohíbe solo oraciones cortadas, nombrar el miedo y 11 clichés fijos. Sonnet 5.5 cumple lo de las oraciones completas y compensa con imágenes.

**Medido (2026-10-05, relatos de Sonnet 5.5 en prod y dev):**

| Relato | Palabras | «como si» | «como un/una …» |
|---|---|---|---|
| prod · el engaño del diablo (01/10) | 1 733 | 4 | 1 |
| prod · NO TE DETENGAS EN EL BOSQUE (01/10) | 2 273 | 7 | 2 |
| dev · Bosque (30/09 01:43) | 3 306 | 25 | 11 |
| dev · Bosque (30/09 07:53) | 3 190 | 26 | 8 |
| dev · Bosque (02/10) | 2 252 | 7 | 0 |

Las personificaciones («la oscuridad se lo tragó», «el silencio se cerró») no se cuentan bien con una regla; las comparaciones sí.

### H2 — Muletillas que «pone siempre» · **lista de frases prohibidas**

- «Y entonces pasó lo peor.» Está en el texto actual de «el engaño del diablo», pero **no en `macro_beat`**: puede ser de una regeneración o de la corrección. La familia sí se repite en lo de la IA: «Lo peor fue como a las cuatro…» (diablo, antes de corregir), «esos ojos eran lo peor» (dev, dos veces), «y eso era lo peor» (dev, 02/10).
- «Nadie se esfuma en dos minutos.» Una vez, en el acto 2 del diablo (`macro_beat`).

Con solo 5 relatos de Sonnet en la base, «siempre» no se puede confirmar con datos; se toma la palabra de la usuaria (es quien lee todos).

---

## 2. PROPUESTA

### P1 — Registro de anécdota en el oficio de la Voz (`voice_craft.md`) · H1

Una sección nueva, corta y asertiva, **«CONTALO COMO UNA ANÉCDOTA»**:
- Describí las cosas como las diría alguien en una sobremesa: qué se veía, qué se escuchaba, qué hiciste. Sin metáforas: la oscuridad no traga, la luz no tiembla, los colores no están furiosos.
- Comparaciones solo con cosas de todos los días, y pocas (ver D2).
- Ejemplo «así no / así sí» con un caso parecido a los de la hija, **sin sus palabras exactas** (si no, la Voz las copia; mismo criterio que el ejemplo actual).

### P2 — Frases prohibidas (`voice_cliches.txt`) · H2

Sumar a la lista que ya ve la Voz y que ya revisa el control de repetición (por raíz):
- «pasó lo peor», «lo peor fue», «eso era lo peor»
- «nadie se esfuma»
- «la oscuridad se lo tragó»
Se marcan en el panel del relato sin cambios de código.

### P3 — Aviso de «muy literario» en el control de repetición · H1 (ver D3)

`repetition_check.py` cuenta las comparaciones por acto («como si», «como un/una») y avisa cuando pasan un tope, con hasta 3 ejemplos, igual que las oraciones cortadas (Spec-590 F). Solo se muestra; no regenera solo. Al regenerar el acto, vuelve a la Voz por `_avoid` como el resto.

### P4 — Que la usuaria sume sus propias frases (ver D4)

Hoy, para prohibir una frase hay que editar `voice_cliches.txt` y hacer `make deploy` (la config va en la imagen). Ella es quien las encuentra.

---

## 3. DECISIONES (2026-10-05: aprobadas con lo recomendado)

- **D1 — Alcance del registro.** (a) Prohibir metáforas y personificaciones del todo. (b) Permitirlas solo como lo diría la persona («estaba oscuro como boca de lobo»). **Recomendado: (a) en el prompt**, porque las expresiones de todos los días igual salen solas y lo que molesta es lo de escritor.
- **D2 — Tope de comparaciones.** Una por acto como máximo (en el prompt y como tope del aviso P3). **Recomendado: 1 por acto** (el diablo hoy tiene ~1; el Bosque de dev, ~5).
- **D3 — ¿Sumar el aviso P3?** **Recomendado: sí**: el error se vio de verdad, se mide sin IA y le sirve a ella en «Corregir el relato» con «Buscar».
- **D4 — Frases propias desde la pantalla (P4).** (a) Ahora: en «Corregir el relato», marcar una frase → «Que la IA no la use más» → lista guardada en la base, que se suma a la de `voice_cliches.txt` en el prompt y en el control. (b) Más adelante, si después de P1–P3 siguen apareciendo. **Recomendado: (b)**. P1–P3 son chicos y se miden; P4 toca esquema, API y UI.

- **D5 — «¿Cómo lo cuenta?» = «Literario» (2026-10-05, decisión del usuario): se quita.** La guía de oficio pide una anécdota en todas las historias, y esa opción pedía lo contrario («prosa literaria cuidada: imágenes precisas»): la Voz habría recibido dos órdenes opuestas y el aviso de comparaciones habría marcado lo que el autor eligió. Quedan «caso», «confesión» y «crónica seca», las tres de anécdota, así que la regla sigue en la guía general (vale también para historias sin «cómo lo cuenta», p. ej. importadas) y no hace falta repetirla en cada opción. Ninguna historia de prod ni de dev la usaba; una con `telling: literario` guardado no rompe: la Voz no recibe línea de estilo. Lo vigila `test_ninguna_forma_de_contarlo_pide_prosa_literaria`.

---

## 4. CRITERIOS DE ÉXITO

1. Con la historia «el engaño del diablo» (escaleta exportada de prod), 2 corridas antes y 2 después con `evaluate_voice.py`:
   - las comparaciones por acto bajan a ≤ 1 en promedio;
   - cero apariciones de las frases de P2;
   - sin retroceso en lo que ya se mide: oraciones cortadas, diálogo, clichés, palabras por acto (250–500, Spec-590).
2. **Lectura a ciegas de la hija:** de un acto en sus dos versiones (antes / después, sin decirle cuál es cuál), elige la que «suena más a anécdota». Éxito: elige la nueva en la mayoría.
3. Snapshots de la Voz actualizados a propósito (`SNAPSHOT_UPDATE=1`) y un test que falla si la sección del registro deja de aparecer.

---

## 5. PLAN

### S1 — Medir antes (sin cambios de prompt)
- `export-yaml` de «el engaño del diablo» desde prod → `scripts/research/640/el_engano_del_diablo.yaml`.
- `voice_metrics.py`: métrica nueva de comparaciones por acto (la misma función que usará P3) y conteo de las frases de P2.
- Línea de base: `evaluate_voice.py --input … --runs 2 --profile hibrido-sonnet55 --yes` (~US$ 0,20, se avisa antes). Evidencia en `scripts/research/640/base/`.

### S2 — Prompt y frases (P1, P2)
- `voice_craft.md` (sección nueva) y `voice_cliches.txt`.
- Snapshots de `voice_prompts.json` / `pipeline_prompts.json` + test de la sección.
- Medición «después» (~US$ 0,20) en `scripts/research/640/despues/`, con comparación en esta spec.
- Las dos versiones de un acto para la lectura a ciegas (criterio 2).

### S3 — Aviso en el panel (P3) · si D3 = sí
- `repetition_check.py`: comparaciones por acto con tope y ejemplos; mensaje en `core_messages.yaml` (`repeticion`); vuelve a la Voz por `_avoid`.
- Panel del relato y «Corregir el relato» lo muestran como los demás avisos (`relato_panel.ejs`, el corrector).
- Tests: pytest del chequeo y del `_avoid`, Vitest de la vista.

### Cierre
- `CLAUDE.md` (Prompt System / Control de repetición), tests en verde, `make dev-status`, URL de `storymaker.test`, PR a `development`. Prod solo con `make deploy` si el usuario lo pide.

### Riesgos
- **Prosa plana:** sin imágenes, la tensión puede caer. El ejemplo «así sí» tiene que mostrar un detalle concreto que inquiete (lo que ya pide la Spec-470), no una descripción gris. Lo valida la lectura a ciegas.
- **Copia del ejemplo:** la Voz tiende a copiar las palabras del ejemplo; se escribe con otra escena.
- **Ruido en P3:** «como» tiene otros usos («como a las cuatro», «como siempre»); se cuenta solo «como si» y «como un/una + sustantivo», y se prueba contra los 5 relatos actuales antes de fijar el tope.

---

## 6. TASKS

### S1 — Medir antes · ✅ 2026-10-05
- [x] `export-yaml` de prod (sobre una copia de la DB) → `scripts/research/640/el_engano_del_diablo.yaml`; importada en dev (`e2b77304-…`), con la escaleta completa (10 llamadas por relato, sin rearmar).
- [x] `repetition_check.comparisons()` («como si» / «como un/una» + hasta 4 palabras, sin diálogo) y en `voice_metrics.py` (`comparaciones`, `comparaciones_detalle`, por acto).
- [x] 2 relatos con el prompt de antes, en dev (no en una DB temporal: así Yael los lee en storymaker.test). `scripts/research/640/medir.py` → `base/`.

### S2 — Prompt y frases · ✅ 2026-10-05
- [x] `voice_craft.md`: «CONTALO COMO UNA ANÉCDOTA» + un segundo ejemplo «así no / así sí» (otra escena: farol y viento).
- [x] `voice_cliches.txt`: «pasó lo peor», «lo peor fue», «eso era lo peor», «nadie se esfuma», «la oscuridad se lo tragó».
- [x] Snapshots `voice_prompts.json` / `pipeline_prompts.json`; `test_el_snapshot_cubre_todas_las_secciones` vigila la sección.
- [x] 2 relatos con el prompt nuevo, en dev → `despues/`.

### S3 — Aviso en el panel · ✅ 2026-10-05
- [x] `ActRepetition.comparisons` / `comparison_count` / `too_literary` (desde la 2.ª, `COMPARISONS_PER_ACT = 1`); en `GET …/repetition`.
- [x] Al regenerar vuelve a la Voz: fragmento `voz/evitar/comparaciones.md` (`_avoid`).
- [x] Panel del relato («N comparaciones», con ejemplos) y «Corregir el relato» (cada ejemplo con «Buscar»).
- [x] Tests: `test_repetition_check.py`, `test_voice_metrics.py`, `test_outline_narrator.py`, `test_authoring_api.py`, `relatos.view.test.ts`. pytest 886, Vitest 378, Playwright 67.

### D5 — Sin «Literario» · ✅ 2026-10-05
- [x] `authoring_options.yaml` sin la opción; comentario en `Direction.telling`; test del catálogo. pytest 887, Vitest 378, Playwright 67.

### Pendiente
- [ ] Lectura de Yael (criterio 2, simplificado 2026-10-05): en dev queda solo la versión de las 10:49 (`ff2375b8`); la compara con la que ya leyó y corrigió en prod. Las otras tres se borraron de dev; sus textos están en `base/` y `despues/`.
- [ ] PR a `development`; prod con `make deploy` si el usuario lo pide.

---

## 7. RESULTADOS (2026-10-05, Sonnet 5.5, «el engaño del diablo» en dev)

| Versión (dev) | Prompt | Palabras | Comparaciones (por acto) | Cortadas | Diálogo | Muletillas P2 |
|---|---|---|---|---|---|---|
| 05/10 10:44 (`f4ccc4b5`) | antes | 2 249 | 5 (0·1·1·2·1) | 4 % | 0 | «lo peor fue», «se lo tragó» |
| 05/10 10:46 (`e7d00400`) | antes | 2 243 | 8 (1·0·4·3·0) | 1 % | 0 | — |
| 05/10 10:49 (`ff2375b8`) | después | 2 170 | 4 (1·0·1·2·0) | 1 % | 0 | — |
| 05/10 10:51 (`e268d623`) | después | 2 262 | 6 (1·1·1·3·0) | 2 % | 1 | — |

- Comparaciones: 6,5 → 5 por relato (1,3 → 1,0 por acto). El acto 4 (el encierro en la chata) sigue con 2–3: es donde la Voz más «adorna».
- Muletillas: 0 después (antes, 2 en una de las dos).
- Sin retroceso en cortadas ni palabras; aparece 1 frase de diálogo en una versión (ruido, a mirar si se repite).
- A ojo (acto 3): antes «un brillo … como una brasa metida en un hueco», «una risa baja que se fue hinchando»; después «pasé la linterna por toda la pared y no había ningún otro hueco», «me dio vergüenza haber sospechado algo de un chico». Lo literario que no se cuenta con regla (personificaciones) bajó a la vista; lo confirma —o no— la lectura de Yael.
- Costo: 4 relatos ≈ US$ 0,36.

# SPEC-490: Exportar un relato a `.md` para el TTS (EV-7)

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development)
**Estado:** DONE (2026-09-24) — export verificado en `audiogen`; las pausas entre actos esperan un arreglo en `audiogen` (fuera de alcance)
**Roadmap:** EV-7 (exportar el relato para el guion de YouTube).

---

## ASSUMPTIONS

1. El archivo exportado se usa como **entrada de `audiogen`** (proyecto TTS del usuario, `/mnt/LLM/apps/audiogen`), no para leerlo ni editarlo a mano.
2. **Un solo formato: `.md`**. Lleva el título del relato, los rótulos de acto y la prosa, y **nada más**: ni ficha, ni metadatos, ni comandos propios de `audiogen` (`[motor=…]`, `[voice=…]`, `Prosodia:`). La voz y el motor los agrega el usuario del lado de `audiogen`.
3. Se exporta **desde la web**: un botón «Descargar .md» en el panel de cada variante de relato (`relato_panel.ejs`), junto a «Copiar Relato». Sin comando CLI.
4. Se exporta **una variante** (`generated_narrative`) tal como está guardada, incluidos los actos regenerados (Spec-430). No se regenera ni se consulta al LLM.
5. `audiogen` es de solo lectura para esta spec: no se toca su código. El contrato se deduce de su parser (`src/audiogen/application/services/markdown_parser.py`).
6. De paso se arregla **«Copiar Relato»**, que hoy copia también el texto de los botones de cada acto (§2.4).

---

## OBJECTIVE

Que la esposa y la hija del usuario pasen un relato generado al TTS **con un clic**, sin copiar, pegar ni limpiar el texto a mano, y **sin que se pierdan frases en el audio**.

**Éxito:** el `.md` descargado, pasado tal cual a `./scripts/generate.sh input/<archivo>.md` de `audiogen`, se narra completo: cada párrafo de prosa se convierte en un segmento con texto, el título y los rótulos no se leen, y hay una pausa entre actos.

---

## 1. HALLAZGOS

### 1.1 En `audiogen` (el consumidor)

| Hallazgo | Consecuencia para el export |
|---|---|
| Cada línea no vacía es un segmento; las vacías se ignoran. | Un párrafo por línea. Un salto de línea simple dentro de un párrafo lo parte en dos segmentos (tolerable, pero cambia la prosodia). |
| **Salta en silencio** las líneas que empiezan con `#`, `-`, `*` o `>`. | `# Título` y `## Acto N` no se leen (bien). Pero **un diálogo con guion (`- ¿Quién anda?`) o un párrafo que arranca en cursiva (`*No mires.*`) desaparecen del audio.** |
| `[pause=<ms>]` en línea propia genera silencio. | Sirve para separar los actos. |
| Las líneas `^\[…\]$` son comandos; un comando desconocido que calce con un patrón fallaría. | Un párrafo que sea solo `[algo]` se interpretaría como comando: no se exporta así. |
| El texto pasa por `preprocess()` antes de sintetizarse. | Los asteriscos de énfasis a mitad de línea podrían leerse o romper la prosodia: se quitan. |

### 1.2 En `automated_narrative`

| Hallazgo | Consecuencia |
|---|---|
| `GeneratedNarrative.content` ya viene consolidado como `## Acto N\n\n<prosa>` (`_consolidate_content`). | El export parte de ahí: no hace falta leer los beats. |
| El título de la variante es `«<título historia> · AAAA-MM-DD HH:MM»` (`_default_title`). | El `# Título` del archivo usa el **título de la historia** (sin la fecha); la fecha va solo en el nombre del archivo. |
| Ya existe `GET /generated-narratives/{id}/text` (JSON `{text}`), sin uso de descarga. | Se agrega un endpoint de descarga; el existente no cambia. |
| El frontend es el único origen del browser; `/api/*` se proxya al Core (`api_proxy.ts`). | El botón puede ser un enlace directo al endpoint del Core vía `/api/…` con `download`. |
| Prod y dev no tienen hoy relatos generados guardados. | La frecuencia real de líneas con `-`/`*`/`>` se mide con relatos de `scripts/evaluate_voice.py` durante la implementación. |

---

## 2. CAMBIOS PROPUESTOS

### 2.1 Formato del `.md` exportado

```markdown
# El monte prohibido

## Acto 1

Primer párrafo de prosa, en una sola línea.

—¿Quién anda ahí? —pregunté.

[pause=1500]

## Acto 2

…
```

Reglas (determinísticas, sin LLM):

1. Primera línea: `# <título de la historia>`.
2. Cada acto: `## Acto N` y su prosa. Entre un acto y el siguiente, una línea `[pause=1500]`.
3. **Un párrafo por línea:** los saltos simples dentro de un párrafo se unen con un espacio; los párrafos se separan con una línea en blanco.
4. **Ninguna línea de prosa empieza con `#`, `-`, `*`, `>` ni es solo `[…]`:**
   - Guion de diálogo al inicio (`-`, `–`) → raya `—`.
   - Énfasis Markdown (`*texto*`, `**texto**`, `_texto_`) → se quitan los marcadores y queda el texto.
   - `>` o `#` al inicio de una línea de prosa → se quitan.
   - Separadores sueltos (`---`, `***`, `* * *`) → se eliminan.
5. Codificación UTF-8, fin de línea `\n`, termina con un salto de línea.

### 2.2 Backend

- Un formateador puro en `application` (p. ej. `NarrativeScriptFormatter.to_markdown(title, content) -> str`) con las reglas de §2.1. Sin dependencias de infraestructura; es lo que se testea a fondo.
- Endpoint `GET /api/v1/generated-narratives/{id}/export.md`: `text/markdown; charset=utf-8` con `Content-Disposition: attachment; filename="<slug-título>-<AAAA-MM-DD-HHMM>.md"` (slug sin acentos ni espacios; fecha de creación de la variante en hora AR). 404 si no existe, 400 si el id es inválido.

### 2.3 Frontend

- Botón **«Descargar .md»** en `relato_panel.ejs`, al lado de «Copiar Relato», con el mismo estilo. Es un `<a href="/api/v1/generated-narratives/<id>/export.md" download>`: sin JS nuevo.
- Mientras un acto de esa variante se regenera (`regenerating`), el botón queda deshabilitado, como los de «Regenerar acto».

### 2.4 Arreglo de «Copiar Relato»

Hoy `copyRelatoContent()` (`public/js/relatos.js`) copia el `innerText` de `#relato-content-<id>`, que contiene los botones de cada acto: el texto copiado incluye «Regenerar» tras cada rótulo (confirmado en `relato_panel.ejs`).

- La vista marca con `data-copy-part` las partes que se copian: preámbulo, rótulo `Acto N` y prosa de cada acto.
- `copyRelatoContent()` arma el texto con esas partes, en orden, separadas por una línea en blanco. Los botones no se copian.
- Copiar da lo que se ve en pantalla («Acto 1», prosa…), no el `.md` para el TTS: sirve para pegar en cualquier lado.

---

## BOUNDARIES

- **Siempre:** formateo determinístico y testeado; el contenido guardado en la DB no se modifica (el export transforma solo la salida).
- **Preguntar antes:** cambiar el formato de `_consolidate_content` o el endpoint `/text`; tocar el repo `audiogen`.
- **Nunca:** llamar al LLM para limpiar el texto; agregar dependencias nuevas (el slug y la limpieza se hacen con la librería estándar); cambios de esquema de DB.

---

## TESTING

- **Unit (pytest):** el formateador con casos de cada regla de §2.1 (guion de diálogo, cursiva al inicio y a mitad de línea, `>`, separadores, saltos simples, párrafo `[…]`, acto vacío, título con acentos) y el slug del nombre de archivo.
- **Contrato con `audiogen`:** un test que recorre el `.md` exportado con las **mismas reglas de salto** del parser de `audiogen` (líneas `#`/`-`/`*`/`>` y comandos `[…]`) y verifica que **todo** párrafo de prosa sobrevive como segmento. Replica la regla; no importa `audiogen`.
- **API (pytest):** 200 con headers correctos, 404, 400.
- **E2E (Playwright):** en el panel de una variante, el botón descarga un `.md` cuyo nombre y primera línea son los esperados, y «Copiar Relato» copia sin «Regenerar».
- **Manual (una vez):** pasar un relato exportado por `audiogen` y escuchar que no falte nada.

---

## SUCCESS CRITERIA

1. Desde el panel de una variante, un clic descarga `<slug>-<fecha>.md`.
2. El archivo cumple §2.1; ninguna línea de prosa queda en una forma que `audiogen` saltee.
3. El texto narrado (sin rótulos) es el de la variante, palabra por palabra, salvo los marcadores quitados en §2.1.4.
4. «Copiar Relato» copia rótulos y prosa, sin el texto de los botones.
5. `make lint`, `make test`, Vitest y Playwright en verde.

---

---

## DECISIONES (2026-09-24)

1. Pausa entre actos: `[pause=1500]`.
2. Rótulo: `## Acto N`, sin el nombre del acto.
3. El arreglo de «Copiar Relato» entra en esta spec (§2.4).

---

## PLAN

### Estrategia

De adentro hacia afuera: primero el formateador puro (ahí está el riesgo de perder texto en el audio), después el endpoint y por último la UI. Cada slice deja la suite en verde y va en su propio commit.

### Decisiones técnicas

| Tema | Decisión |
|---|---|
| Dónde vive el formateo | `src/application/services/narrative_script_formatter.py`: funciones puras `to_tts_markdown(title, content) -> str` y `export_filename(title, created_at) -> str`. Parte el `content` por los encabezados `## Acto N`, el formato que produce `_consolidate_content`. |
| Título | El de la historia (`story_repo.get_by_id(narrative.story_template_id).title`). Si la historia ya no existe, el de la variante sin el sufijo ` · fecha`. |
| Caso de uso | Método nuevo `GenerateNarrativesUseCase.export_tts_markdown(narrative_id) -> tuple[str, str] \| None` (nombre de archivo, contenido). Ya tiene `narrative_repo` y `story_repo`. |
| Endpoint | `GET /api/v1/generated-narratives/{id}/export.md` en `narrative_router.py`, con el mismo manejo de 400/404 que `/text`. `Response(media_type="text/markdown; charset=utf-8")` con `Content-Disposition: attachment; filename="…"`. El slug es ASCII, así que no hace falta `filename*`. |
| Slug | `unicodedata.normalize("NFKD")`, sin diacríticos, `[^a-z0-9]+` → `-`, recortado a 60 caracteres; `relato` si queda vacío. Fecha `AAAA-MM-DD-HHMM` en hora AR. |
| Proxy | `/api/*` ya pasa los headers sin alterarlos (`proxy_passthrough.test.ts`); se agrega un caso para `Content-Disposition`. |
| Botón | `<a … download hx-boost="false">` con `btn-forge-outline` e ícono `download` (lucide). Sin `hx-boost="false"`, el `hx-boost` del layout convierte el clic en un swap AJAX y no hay descarga (lo detectó el E2E). Con `regenerating`, sin `href` y con `aria-disabled="true"`. |
| Copiar | `data-copy-part` en la vista; `copyRelatoContent()` hace `querySelectorAll("[data-copy-part]")` → `innerText.trim()` → `join("\n\n")`. |

### S0 — Formateador

`narrative_script_formatter.py` con las reglas de §2.1 y el nombre de archivo. Tests unitarios por regla y test de contrato con las reglas de salto de `audiogen`.

### S1 — Endpoint de descarga

Caso de uso y endpoint `export.md`. Tests de API (200 con headers y cuerpo, 404, 400) y caso del proxy para `Content-Disposition`.

### S2 — UI: descargar y copiar

Botón «Descargar .md», `data-copy-part` en `relato_panel.ejs` y el nuevo `copyRelatoContent()`. Test de vista (Vitest, `relatos.view.test.ts`) y E2E (`relatos.spec.ts`): la descarga (nombre y primera línea) y la copia sin «Regenerar».

### S3 — Verificación real y cierre

Exportar relatos generados con `scripts/evaluate_voice.py` (gemma3), contar cuántas líneas corrige cada regla y pasar uno por `audiogen` (la escucha la hace el usuario). Actualizar `CLAUDE.md` (endpoint) y cerrar la spec. PR a `development`.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| La Voz produce formas no previstas (listas numeradas, `—` pegado a `*`…). | El test de contrato es genérico (ninguna línea de prosa salteable); S3 mide sobre relatos reales y suma reglas si aparece algo. |
| Quitar `_` como énfasis rompe palabras con guion bajo. | Solo se quita `_texto_` delimitado por espacio o puntuación. Caso de test. |
| `innerText` depende del layout, y Vitest corre en `node` sin DOM (no hay jsdom y no se agregan dependencias). | El test de vista verifica los `data-copy-part` sobre el HTML; la copia real se prueba en E2E con Chromium. |
| El `download` de un enlace proxyado no respeta el nombre. | El nombre sale del `Content-Disposition` del Core; el E2E verifica `download.suggestedFilename()`. |

---

## TASKS

Formato: **Acceptance** / **Verify** / **Files**. Checkpoint por slice: `make lint` + `make test` (+ Vitest y Playwright desde S1, que agrega un endpoint que usa el frontend) en verde → commit con tu OK.

### S0 — Formateador

- [x] **T0.1:** Partir el relato consolidado en actos.
  - Acceptance: `split_acts(content) -> list[tuple[int, str]]` a partir de los encabezados `## Acto N` (y el legado `## Beat N`); el texto antes del primer encabezado se descarta si está vacío o se conserva como preámbulo sin número; un acto sin prosa se omite.
  - Verify: pytest con el `content` que produce `_consolidate_content` y casos borde (sin encabezados, acto vacío, preámbulo).
  - Files: `src/application/services/narrative_script_formatter.py`, `tests/unit/application/services/test_narrative_script_formatter.py`
- [x] **T0.2:** Limpiar la prosa de cada acto (§2.1 reglas 3 y 4).
  - Acceptance: un párrafo por línea (saltos simples → espacio, párrafos separados por línea en blanco); guion de diálogo inicial (`-`, `–`) → `—`; se quitan `**…**`, `*…*` y `_…_` (este último solo delimitado por espacio o puntuación); se quitan `>` y `#` iniciales; se eliminan los separadores (`---`, `***`, `* * *`); un párrafo que es solo `[…]` pierde los corchetes. La prosa sin marcas sale idéntica.
  - Verify: pytest, un caso por regla + un párrafo real sin marcas que no cambia + una palabra con `_` interno que no cambia.
  - Files: los de T0.1.
- [x] **T0.3:** Armar el `.md` completo.
  - Acceptance: `to_tts_markdown(title, content)` → `# <título>`, cada acto con `## Acto N` y su prosa, `[pause=1500]` entre actos (no después del último), UTF-8 con `\n` y salto final.
  - Verify: pytest comparando la salida completa de un relato de 3 actos con el esperado.
  - Files: los de T0.1.
- [x] **T0.4:** Nombre de archivo.
  - Acceptance: `export_filename(title, created_at)` → `<slug>-AAAA-MM-DD-HHMM.md`; slug ASCII en minúsculas sin diacríticos (`ñ` → `n`), `[^a-z0-9]+` → `-`, sin guiones en los bordes, máx. 60 caracteres, `relato` si queda vacío; la hora en zona AR aunque `created_at` venga en otra zona.
  - Verify: pytest («El monte prohibido», título con `¿?` y `ñ`, título vacío, título largo, `created_at` en UTC).
  - Files: los de T0.1.
- [x] **T0.5:** Test de contrato con `audiogen`.
  - Acceptance: un helper de test replica la regla de salto del parser de `audiogen` (línea vacía, empieza con `#`/`-`/`*`/`>`, o calza `^\[…\]$`); sobre la exportación de un relato «hostil» (diálogos con guion, cursivas al inicio, `>`, separadores, `[…]`), cada párrafo de prosa de la entrada sobrevive como segmento, y solo el título, los rótulos y los `[pause=1500]` se saltean o son comandos.
  - Verify: pytest.
  - Files: `tests/unit/application/services/test_narrative_script_audiogen_contract.py`
- [x] **Checkpoint S0:** lint + pytest → commit.

### S1 — Endpoint de descarga

- [x] **T1.1:** Caso de uso.
  - Acceptance: `GenerateNarrativesUseCase.export_tts_markdown(narrative_id)` → `(filename, markdown)` con el título de la historia; si la historia no existe, el título de la variante sin ` · fecha`; `None` si la variante no existe.
  - Verify: pytest con repos de prueba (historia existente, historia borrada, variante inexistente).
  - Files: `src/application/use_cases/generate_narratives_use_case.py`, `tests/unit/application/use_cases/test_export_tts_markdown.py`
- [x] **T1.2:** Endpoint.
  - Acceptance: `GET /api/v1/generated-narratives/{id}/export.md` → 200, `text/markdown; charset=utf-8`, `Content-Disposition: attachment; filename="…"` y el `.md` como cuerpo; 400 con id inválido; 404 si no existe.
  - Verify: pytest con `httpx.ASGITransport` sobre una DB temporal.
  - Files: `src/presentation/routers/narrative_router.py`, `tests/integration/test_narrative_export_api.py`
- [x] **T1.3:** Proxy.
  - Acceptance: `Content-Disposition` y `Content-Type` del Core llegan intactos al browser vía `/api/*`.
  - Verify: Vitest, un caso nuevo en `proxy_passthrough.test.ts`.
  - Files: `frontend/tests/integration/proxy_passthrough.test.ts`
- [x] **Checkpoint S1:** lint + pytest + Vitest → commit.

### S2 — UI: descargar y copiar

- [x] **T2.1:** Botón «Descargar .md».
  - Acceptance: en `relato_panel.ejs`, junto a «Copiar Relato», `<a href="/api/v1/generated-narratives/<id>/export.md" download>` con `btn-forge-outline` e ícono `download`; con `regenerating`, sin `href` y con `aria-disabled="true"`.
  - Verify: Vitest en `relatos.view.test.ts` (href correcto; deshabilitado durante la regeneración).
  - Files: `frontend/src/views/partials/relato_panel.ejs`, `frontend/tests/unit/views/relatos.view.test.ts`
- [x] **T2.2:** Marcar las partes a copiar.
  - Acceptance: `data-copy-part` en el preámbulo, en cada rótulo `Acto N` y en cada bloque de prosa; los botones «Regenerar» no lo tienen ni quedan dentro de un elemento que lo tenga.
  - Verify: Vitest en `relatos.view.test.ts` (cantidad y orden de partes; ningún botón dentro de una parte).
  - Files: `frontend/src/views/partials/relato_panel.ejs`, `frontend/tests/unit/views/relatos.view.test.ts`
- [x] **T2.3:** Nuevo `copyRelatoContent()`.
  - Acceptance: arma el texto con `[data-copy-part]` del panel (`innerText.trim()`, unidos con línea en blanco); sin partes o sin texto → aviso en consola y no copia; se mantienen el fallback `execCommand` y el feedback del botón.
  - Verify: E2E (T2.4).
  - Files: `frontend/public/js/relatos.js`
- [x] **T2.4:** E2E.
  - Acceptance: en `/historia/<id>/relatos`, «Descargar .md» baja un archivo cuyo `suggestedFilename()` termina en `.md` y cuya primera línea es `# <título de la historia>`; «Copiar Relato» deja en el portapapeles un texto con «Acto 1» y sin «Regenerar».
  - Verify: `npx playwright test relatos.spec.ts --reporter=line` (permiso `clipboard-read` en el contexto).
  - Files: `frontend/tests/e2e/relatos.spec.ts`
- [x] **Checkpoint S2:** lint + pytest + Vitest + Playwright completo → commit.

### S3 — Verificación real y cierre

- [x] **T3.1:** Medir sobre relatos reales.
  - Acceptance: exportar los relatos de una corrida de `scripts/evaluate_voice.py` (gemma3, 2 relatos, en background) y contar cuántas líneas tocó cada regla de §2.1.4; ninguna línea de prosa salteable por `audiogen` en la salida. Si aparece una forma no prevista, se agrega la regla y su test.
  - Verify: script de medición en el scratchpad; resultados en la sección RESULTADOS de esta spec.
  - Files: `specs/490_exportar_relato_para_tts.md` (+ formateador y tests si hace falta una regla)
- [x] **T3.2:** Prueba en `audiogen` (usuario).
  - Acceptance: el usuario pasa un `.md` exportado por `./scripts/generate.sh` y confirma que no falta texto y que las pausas entre actos se oyen.
  - Verify: escucha manual.
  - Files: —
- [x] **T3.3:** Documentación y cierre.
  - Acceptance: `CLAUDE.md` lista el endpoint `export.md` y el botón; la spec pasa a DONE con resultados; roadmap EV-7 hecho.
  - Verify: lectura.
  - Files: `CLAUDE.md`, `specs/490_exportar_relato_para_tts.md`
- [x] **Checkpoint S3:** suite completa en verde → commit → push → PR `feat/ev-7-exportar-guion` → `development`.

---

## RESULTADOS (2026-09-24)

**T3.1 — relatos reales.** 4 relatos de «El monte prohibido» con `scripts/evaluate_voice.py --runs 2` (perfil `ollama-gemma3-12b`, variantes `sin` y `con` guía de oficio), ~8.000 palabras en total:

| Relato | Actos | Reglas que actuaron | Palabras entrada / salida | Líneas que `audiogen` saltearía |
|---|---|---|---|---|
| con_1 | 5 | — | 1989 / 1989 | 0 |
| con_2 | 5 | — | 1967 / 1967 | 0 |
| sin_1 | 5 | 1 salto simple dentro de un párrafo | 2070 / 2070 | 0 |
| sin_2 | 5 | — | 2057 / 2057 | 0 |

- Con el prompt actual (Spec-470), `gemma3:12b` escribe los diálogos **entre comillas** (“…”), no con guion, y no usa Markdown en la prosa: casi ninguna regla de §2.1.4 se activa. Las reglas quedan como red de seguridad (otros modelos, la Voz en Claude, cambios de prompt), cubiertas por el test de contrato.
- No apareció ninguna forma no prevista: no hizo falta sumar reglas.

**T3.2 — `audiogen`.** `el-monte-prohibido-2026-09-24-0909.md` (exportado de `con_1`) por `./scripts/generate.sh` con el motor por defecto (`kokoro`, voz `ef_dora`):

- **El texto llega completo.** El parser tomó **47 bloques = 43 párrafos + 4 `[pause=1500]`**: ninguna línea salteada. 177 micro-segmentos, `failed_segments: []`, `master.wav` de 12,7 min.
- **Las pausas no suenan: bug de `audiogen`.** `BatchOrchestrator.process_segments` descarta los segmentos sin texto (`if segment.text is None: continue`, `batch_orchestrator.py:131`), que es lo que el parser produce para `[pause=ms]`. El master no tiene ningún silencio ≥ 1 s (medido a −60 dBFS, piso de ruido −93 dB). El export cumple el DSL documentado en `audiogen`; el arreglo corresponde a ese repo (fuera de alcance, §BOUNDARIES).
- **Decisión (2026-09-24):** se cierra EV-7 con el export como está (`[pause=1500]` incluido); las pausas sonarán cuando `audiogen` procese los segmentos de pausa. Ese arreglo queda como spec aparte en el repo `audiogen`.


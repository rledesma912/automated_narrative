# SPEC-490: Exportar un relato a `.md` para el TTS (EV-7)

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development)
**Estado:** SPECIFY — pendiente de revisión
**Roadmap:** EV-7 (exportar el relato para el guion de YouTube).

---

## ASSUMPTIONS

1. El archivo exportado se usa como **entrada de `audiogen`** (proyecto TTS del usuario, `/mnt/LLM/apps/audiogen`), no para leerlo ni editarlo a mano.
2. **Un solo formato: `.md`**. Lleva el título del relato, los rótulos de acto y la prosa, y **nada más**: ni ficha, ni metadatos, ni comandos propios de `audiogen` (`[motor=…]`, `[voice=…]`, `Prosodia:`). La voz y el motor los agrega el usuario del lado de `audiogen`.
3. Se exporta **desde la web**: un botón «Descargar .md» en el panel de cada variante de relato (`relato_panel.ejs`), junto a «Copiar Relato». Sin comando CLI.
4. Se exporta **una variante** (`generated_narrative`) tal como está guardada, incluidos los actos regenerados (Spec-430). No se regenera ni se consulta al LLM.
5. `audiogen` es de solo lectura para esta spec: no se toca su código. El contrato se deduce de su parser (`src/audiogen/application/services/markdown_parser.py`).

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
2. Cada acto: `## Acto N` y su prosa. Entre un acto y el siguiente, una línea `[pause=<ms>]` (valor en §OPEN QUESTIONS).
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
- **E2E (Playwright):** en el panel de una variante, el botón descarga un `.md` cuyo nombre y primera línea son los esperados.
- **Manual (una vez):** pasar un relato exportado por `audiogen` y escuchar que no falte nada.

---

## SUCCESS CRITERIA

1. Desde el panel de una variante, un clic descarga `<slug>-<fecha>.md`.
2. El archivo cumple §2.1; ninguna línea de prosa queda en una forma que `audiogen` saltee.
3. El texto narrado (sin rótulos) es el de la variante, palabra por palabra, salvo los marcadores quitados en §2.1.4.
4. `make lint`, `make test`, Vitest y Playwright en verde.

---

## OPEN QUESTIONS

1. **Pausa entre actos:** ¿`[pause=1500]` (1,5 s) está bien, o preferís otro valor o ninguna pausa?
2. **Rótulo de acto:** ¿`## Acto N` alcanza, o preferís los nombres de los actos (p. ej. `## Acto 1 — …`)? No se leen igual; es solo para orientarse en el archivo.
3. **Arreglo de «Copiar Relato»:** hoy copia el `innerText` de `#relato-content-<id>`, que contiene los botones de cada acto: el texto copiado incluye «Regenerar» tras cada rótulo (confirmado en `relato_panel.ejs`). Quedó fuera de alcance según tu respuesta; ¿lo dejamos anotado como pendiente aparte?

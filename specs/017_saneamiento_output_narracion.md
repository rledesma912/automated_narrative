# Spec 017: Saneamiento del Output y Flujo Narrativo

## Objetivo

Corregir cuatro problemas detectados al comparar el archivo de entrada
`input_stories/el_monte_prohibido.md` con su salida generada
`output_stories/El_Monte_Prohibido_17042026210459.md`:

1. El output incluye un bloque de metadatos (Protagonistas, Relator, Escenario, etc.) que no debe aparecer.
2. Los encabezados de beats usan el resumen completo como título — deben ser `## Acto N`.
3. Al menos el Beat 1 fue generado en inglés — la generación debe ser siempre en español.
4. La sinopsis de la historia **no se inyecta en el prompt de la Voz**, por lo que el LLM narra sin conocer hacia dónde va la historia.

---

## Diagnóstico técnico

### Problema 1 y 2 — `MarkdownRenderer`

Archivo: `src/infrastructure/renderers/markdown_renderer.py`

```python
# Estado actual (líneas 12–36)
md += f"**Protagonistas:** {story.protagonista}\n"
md += f"**Relator:** {story.relator}\n"
md += f"**Escenario:** {story.escenarios}\n"
md += f"**Atmósfera:** {story.atmosfera}\n\n"
md += f"_{story.sinopsis}_\n\n"
# ...
md += f"## {beat.number}. {beat.summary}\n\n"  # encabezado = resumen completo
```

```
# Estado deseado
# Solo título + actos
md = f"# {story.title}\n\n"
md += f"## Acto {beat.number}\n\n"
```

### Problema 3 — Idioma en prompts

Archivos: `config/prompts_generation/voice.md` y `config/prompts_generation/system.md`

Ninguno de los dos tiene instrucción explícita de idioma. El modelo (llama3.1:8b)
puede responder en inglés cuando recibe contexto mezclado o cuando el
system prompt no fuerza el idioma.

### Problema 4 — Sinopsis ausente en prompt de Voz

En `src/application/services/prompt_builder.py`, `build_beat_prompt()` formatea
`voice.md` con estos campos: `title`, `relator`, `persona_gramatical`, `atmosphere`,
`protagonistas`, `escenarios`, `beat_number`, `total_beats`, `beat_summary`,
`previous_context`, `journal_context`, `reglas`.

**`sinopsis` no está en la lista.** El template `voice.md` tampoco tiene el placeholder
`{sinopsis}`. La Voz no sabe adónde va la historia.

---

## Hitos y tareas

### Hito 1 — Renderer: solo título y actos

**Objetivo:** El Markdown exportado debe contener únicamente el título (`# Título`)
y los actos numerados (`## Acto N`) con su prosa. Sin metadatos.

**Criterio de aceptación:**
- El archivo generado no contiene líneas con `**Protagonistas:**`, `**Relator:**`,
  `**Escenario:**`, `**Atmósfera:**`, sinopsis en cursiva ni `**Reglas:**`.
- Cada beat aparece como `## Acto 1`, `## Acto 2`, … `## Acto N`.

**Tareas:**

- [ ] **1.1** — Modificar `MarkdownRenderer.render()` para eliminar el bloque de metadatos.
  - Archivo: `src/infrastructure/renderers/markdown_renderer.py`
  - Eliminar líneas 12–25 (Protagonistas, Relator, Escenario, Atmósfera, sinopsis, reglas, `---`)
  - Acceptance: método `render()` solo construye `# {title}\n\n` + beats

- [ ] **1.2** — Cambiar el formato de encabezado de beat de `## N. {summary}` a `## Acto N`.
  - Archivo: `src/infrastructure/renderers/markdown_renderer.py`
  - Cambiar línea 36: `md += f"## {beat.number}. {beat.summary}\n\n"` → `md += f"## Acto {beat.number}\n\n"`
  - Acceptance: cada sección del Markdown exportado empieza con `## Acto N`

- [ ] **1.3** — Actualizar/crear test unitario para el renderer.
  - Archivo: `tests/unit/infrastructure/test_markdown_renderer.py`
  - Verificar: el output NO contiene `Protagonistas`, `Relator`, `Escenario`, `Atmósfera`, `sinopsis`, `Reglas`
  - Verificar: los encabezados siguen el patrón `## Acto \d+`
  - Verify: `pytest tests/unit/infrastructure/test_markdown_renderer.py -v`

---

### Hito 2 — Idioma: generación siempre en español

**Objetivo:** Todos los beats generados deben estar en español, independientemente
del modelo Ollama activo.

**Criterio de aceptación:**
- `voice.md` y `system.md` incluyen instrucción explícita: `ESCRIBE SIEMPRE EN ESPAÑOL`.
- Los tests de integración (o una generación real) producen prosa únicamente en español.

**Tareas:**

- [ ] **2.1** — Agregar instrucción de idioma en `voice.md`.
  - Archivo: `config/prompts_generation/voice.md`
  - En la sección `## INSTRUCCIONES OBLIGATORIAS`, agregar al inicio:
    ```
    ### Idioma
    - ESCRIBE SIEMPRE EN ESPAÑOL. Nunca en otro idioma.
    ```
  - Acceptance: la instrucción aparece antes de cualquier otra sección de instrucciones

- [ ] **2.2** — Agregar instrucción de idioma en `system.md`.
  - Archivo: `config/prompts_generation/system.md`
  - Agregar al inicio del prompt (después del frontmatter o primer encabezado):
    ```
    IDIOMA: Toda la narrativa debe estar escrita en español. Nunca uses otro idioma.
    ```
  - Acceptance: la instrucción está en la primera sección visible del prompt

---

### Hito 3 — Sinopsis: inyectarla en el prompt de la Voz

**Objetivo:** La Voz debe conocer la sinopsis completa para narrar con coherencia
de arco narrativo y no solo de beat a beat.

**Criterio de aceptación:**
- `voice.md` tiene el placeholder `{sinopsis}`.
- `build_beat_prompt()` pasa `sinopsis=story.sinopsis` al formateador.
- La sinopsis visible en el prompt del Beat 1 coincide con la del archivo de entrada.

**Tareas:**

- [ ] **3.1** — Agregar sección de sinopsis en `voice.md`.
  - Archivo: `config/prompts_generation/voice.md`
  - Dentro de `## HISTORIA BASE`, agregar debajo de `- Escenarios: {escenarios}`:
    ```
    - Sinopsis: {sinopsis}
    ```
  - Acceptance: el template tiene el placeholder `{sinopsis}`

- [ ] **3.2** — Pasar `sinopsis` en `build_beat_prompt()`.
  - Archivo: `src/application/services/prompt_builder.py`
  - En el bloque `if self._voice_template:`, agregar `sinopsis=story.sinopsis` al llamado a `.format()`
  - Acceptance: el log de debug `[PB] prompt (first 800 chars)` muestra la sinopsis

- [ ] **3.3** — Verificar el fallback de `build_beat_prompt()` (sin template).
  - Misma función, bloque `base = f"""NARRA EL BEAT...`
  - Agregar la sinopsis al contexto del fallback
  - Acceptance: el fallback incluye `Sinopsis: {story.sinopsis}`

- [ ] **3.4** — Agregar test que verifique que `build_beat_prompt()` incluye la sinopsis.
  - Archivo: `tests/unit/application/test_prompt_builder.py`
  - Verify: `pytest tests/unit/application/test_prompt_builder.py -v`

---

### Hito 4 — Verificación end-to-end del flujo de datos de entrada

**Objetivo:** Confirmar que todos los campos del YAML de entrada (`protagonist`,
`storyteller`, `atmosphere`, `scenarios`, `synopsis`, `rules`) llegan sin pérdida
al `PromptBuilder` y desde allí al LLM.

**Criterio de aceptación:**
- Test de integración que usa `el_monte_prohibido.md` como input, verifica que
  el `Story` creado tiene todos los campos correctos y que el prompt construido
  los contiene.

**Tareas:**

- [ ] **4.1** — Verificar mapeo en `MarkdownStoryParser`.
  - Archivo: `src/infrastructure/parsers/markdown_parser.py`
  - El mapeo actual es: `protagonist` → `protagonista`, `storyteller` → `relator`,
    `atmosphere` → `atmosfera`, `scenarios` → `escenarios`, `synopsis` → `sinopsis`, `rules` → `reglas`
  - Leer el parser y confirmar que no hay truncamiento ni pérdida de campo
  - Acción: agregar logging a nivel DEBUG en `parse()` que muestre los campos extraídos

- [ ] **4.2** — Test unitario del parser con `el_monte_prohibido.md`.
  - Archivo: `tests/unit/infrastructure/test_markdown_parser.py`
  - Verificar que el objeto `MarkdownStoryData` devuelto tiene: title correcto,
    protagonista no vacío, relator="Irene", atmosfera no vacío, sinopsis no vacía,
    5 reglas
  - Verify: `pytest tests/unit/infrastructure/test_markdown_parser.py -v`

- [ ] **4.3** — Smoke test de generación completo (modo real, no mock).
  - Comando: `uv run python -m src generate --input el_monte_prohibido.md --real`
  - Revisar logs de debug para confirmar que `[PB] prompt (first 800 chars)` muestra
    los datos correctos de entrada
  - Revisar el archivo generado: solo `# El Monte Prohibido`, beats en español,
    encabezados `## Acto N`

---

## Orden de implementación recomendado

```
Hito 1 (Renderer)  →  Hito 3 (Sinopsis)  →  Hito 2 (Idioma)  →  Hito 4 (E2E)
```

Los primeros dos hitos son cambios de código puro sin dependencias entre sí.
El Hito 2 es solo edición de archivos de configuración.
El Hito 4 valida el sistema completo y cierra el ciclo.

---

## Boundaries

- **Always do:** Correr `pytest tests -v` antes de marcar un hito como completo.
- **Ask first:** Cambios en el esquema de la base de datos o en la interfaz `LLMProvider`.
- **Never do:** Modificar archivos fuera del alcance de cada hito sin crear una nueva tarea.

---

## Archivos involucrados

| Archivo | Hito |
|---------|------|
| `src/infrastructure/renderers/markdown_renderer.py` | 1.1, 1.2 |
| `tests/unit/infrastructure/test_markdown_renderer.py` | 1.3 |
| `config/prompts_generation/voice.md` | 2.1, 3.1 |
| `config/prompts_generation/system.md` | 2.2 |
| `src/application/services/prompt_builder.py` | 3.2, 3.3 |
| `tests/unit/application/test_prompt_builder.py` | 3.4 |
| `src/infrastructure/parsers/markdown_parser.py` | 4.1 |
| `tests/unit/infrastructure/test_markdown_parser.py` | 4.2 |

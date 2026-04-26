# Spec 050 — Mejora de visualización del archivo debug_prompts_responses

## Objetivo

Mejorar la legibilidad del archivo `debug_prompts_responses_YYYYMMDDHHMM.md` que se genera con `--debug`. Los cambios son puramente de formato markdown — no cambia ninguna lógica de negocio ni de parsing.

## Cambios al DebugMarkdownRenderer

### 1. Separación visible entre bloques

Se añade `---` al final de **cada** bloque dentro de `_call_section`. Hoy ya existe `---` entre la sección de parámetros de historia y la primera llamada, pero entre los bloques internos de cada llamada (componente, parámetros, system prompt, prompt, raw, normalizada, parser, timing) no hay separador.

**Después:**
```
## Llamada 1 — STORY_ANALYST —

### Componentes y Parámetros de Inferencia
StoryAnalystService (story_analyst_service.py)
model: `qwen2.5:14b`  temperature: 0.3  num_ctx: 6144  num_predict: 700
system: `story_analyst_system_compact.md`  user: `story_analyst_compact.md`

---
### System Prompt
...
---
### Prompt Enviado
...
---
### Respuesta Normalizada
...
---
### Resultado del Parser
Estado: OK  Raw: 1234  Norm: 1100  Diff: -10.8%

---
### Timing
LLM elapsed: 2.34s

---
```

### 2. Componentes y Parámetros de Inferencia: sección unificada

Se unifica "Componente" + "Parámetros de Inferencia" en una sola sección. Sin tablas, todo en líneas simples.

**Antes:**
```markdown
### Componente
`StoryAnalystService`

### Parámetros de Inferencia
| Param | Valor |
|---|---|
| model | `qwen2.5:14b` |
| temperature | 0.3 |
...
```

**Después:**
```markdown
### Componentes y Parámetros de Inferencia
StoryAnalystService (story_analyst_service.py)
model: `qwen2.5:14b`  temperature: 0.3  num_ctx: 6144  num_predict: 700
system: `story_analyst_system_compact.md`  user: `story_analyst_compact.md`
```

Primera línea: clase + archivo entre paréntesis. Segunda línea: parámetros en línea de pares.

**Regla:** si la concatenación de valores supera ~80 caracteres, se recurre a la tabla para evitar overflow en terminals estrechas.

### 3. Eliminar sección "Respuesta Raw"

Se elimina completamente el bloque de "Respuesta Raw". Solo se muestra "Respuesta Normalizada".

**Antes:**
```markdown
### Respuesta Raw
...
---
### Respuesta Normalizada
...
```

**Después:**
```markdown
### Respuesta Normalizada
...
```

### 4. Resultado del Parser: línea compacta

Hoy usa negritas sueltas en líneas separadas. Se consolida en una línea:

**Antes:**
```markdown
### Resultado del Parser
**Estado:** OK  
**Raw chars:** 1234 | **Norm chars:** 1100 | **Diferencia:** -10.8%
```

**Después:**
```markdown
### Resultado del Parser
Estado: OK  Raw: 1234  Norm: 1100  Diff: -10.8%
```

### 5. Timing: línea única

**Antes:**
```markdown
### Timing
- Elapsed LLM: 2.34 s
```

**Después:**
```markdown
### Timing
LLM elapsed: 2.34s
```

### 6. Tabla de resumen: retainerla

La tabla de resumen al final de sesión (`## Resumen de Sesión`) es útil con valores alineados — se conserva intacta. Es el único lugar donde la tabla de varias columnas tiene sentido por legibilidad.

### 7. CSS de tunear el output (markdown + terminal)

Si se usa un renderer que soportar CSS (ej: vista previa en terminal con colour, o conversión a HTML), las siguientes reglas mejoran la visualización:

```css
/* Tipografía y estructura */
body {
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 10pt;
  line-height: 1.5;
  max-width: 90ch;
}

/* Headers */
h1 {
  font-size: 14pt;
  color: #1e40af;
  border-bottom: 2px solid #1e40af;
  padding-bottom: 0.2em;
}
h2 {
  font-size: 12pt;
  color: #1d4ed8;
  border-bottom: 1px solid #bfdbfe;
  padding-bottom: 0.15em;
}
h3 {
  font-size: 10pt;
  color: #1e3a5f;
  margin-top: 0.8em;
}

/* Separadores */
hr {
  border: none;
  border-top: 1px solid #cbd5e1;
  margin: 0.8em 0;
}

/* Code blocks */
pre {
  border-left: 3px solid #2563eb;
  padding: 0.5em 1em;
  background: #f8fafc;
  border-radius: 0 4px 4px 0;
  font-size: 9pt;
  overflow-x: auto;
}
code {
  font-family: inherit;
  font-size: inherit;
}

/* Párrafos de resultado compacto */
h3 + p:only-child,
h3 + p:first-of-type {
  font-size: 9pt;
  color: #475569;
}
```

## Implementación

### Archivo a modificar

`src/infrastructure/renderers/debug_renderer.py`

### Método `_call_section` — nuevo layout

```python
def _call_section(self, idx: int, r: LLMCallRecord) -> list[str]:
    beat_label = f"Beat #{r.beat_number}" if r.beat_number is not None else "—"
    role_upper = r.role.upper()
    lines = [
        f"## Llamada {idx} — {role_upper} {beat_label}",
        "",
        "### Componentes y Parámetros de Inferencia",
        f"{r.source_component} ({r.source_file})",
        self._inline_params(r),
        "",
        "---",
    ]

    if r.narrative_context:
        lines += [
            "### Narrative Context (pre-baked)",
            "```",
            r.narrative_context,
            "```",
            "",
            "---",
        ]

    lines += self._prompt_block("System Prompt", r.system_prompt or "_(ninguno)_")
    lines += self._prompt_block("Prompt Enviado", r.user_prompt)
    lines += self._prompt_block("Respuesta Normalizada", r.normalized_response)

    lines += self._parser_result(r)
    lines += self._timing(r)
    lines += ["---", ""]
    return lines

def _inline_params(self, r: LLMCallRecord) -> str:
    """Genera línea de pares si cabe en ~80 chars, si no tabla."""
    parts = [f"model: `{r.model}`", f"temperature: {r.temperature}"]
    if r.num_ctx is not None:
        parts.append(f"num_ctx: {r.num_ctx}")
    if r.num_predict is not None:
        parts.append(f"num_predict: {r.num_predict}")
    if r.system_prompt_file:
        parts.append(f"system: `{r.system_prompt_file}`")
    if r.user_prompt_file:
        parts.append(f"user: `{r.user_prompt_file}`")

    line = "  ".join(parts)
    if len(line) <= 90:
        return line
    # Fallback tabla
    return self._params_table(r)

def _params_table(self, r: LLMCallRecord) -> str:
    rows = [
        f"| model | `{r.model}` |",
        f"| temperature | {r.temperature} |",
    ]
    if r.num_ctx is not None:
        rows.append(f"| num_ctx | {r.num_ctx} |")
    if r.num_predict is not None:
        rows.append(f"| num_predict | {r.num_predict} |")
    if r.system_prompt_file:
        rows.append(f"| system_prompt_file | `{r.system_prompt_file}` |")
    if r.user_prompt_file:
        rows.append(f"| user_prompt_file | `{r.user_prompt_file}` |")
    return "| Param | Valor |\n|---|---|\n" + "\n".join(rows)

def _parser_result(self, r: LLMCallRecord) -> list[str]:
    raw_chars = len(r.raw_response)
    norm_chars = len(r.normalized_response)
    diff_pct = ((raw_chars - norm_chars) / raw_chars * 100) if raw_chars else 0.0
    return [
        "### Resultado del Parser",
        f"Estado: {r.parser_result}  Raw: {raw_chars}  Norm: {norm_chars}  Diff: {diff_pct:.1f}%",
        "",
        "---",
        "",
    ]

def _timing(self, r: LLMCallRecord) -> list[str]:
    return [
        "### Timing",
        f"LLM elapsed: {r.elapsed_s:.2f}s",
        "",
    ]
```

## Testing

- `tests/unit/infrastructure/test_debug_renderer.py` — Verificar que `_call_section` produce `---` entre cada bloque y que `_inline_params` retorna línea cuando valores cortos, tabla cuando largos.
- Verificar que la tabla de resumen (`## Resumen de Sesión`) no se modifica.
- Verificar que no existe bloque "Respuesta Raw" en la salida.

## Success Criteria

1. `_call_section()` produce `---` entre cada bloque (componentes y params → system prompt → prompt → normalizada → parser → timing).
2. `_inline_params()` genera línea de pares cuando `len(line) <= 90`, tabla cuando no.
3. Sección unificada "Componentes y Parámetros de Inferencia": `StoryAnalystService (story_analyst_service.py)` + línea de params en una línea.
4. Sin bloque "Respuesta Raw" — solo "Respuesta Normalizada".
5. Resultado del Parser: `Estado: OK  Raw: 1234  Norm: 1100  Diff: -10.8%` en una línea.
6. Timing: `LLM elapsed: 2.34s` en una línea.
7. Tabla de resumen intacta.
8. `make lint` pasa.
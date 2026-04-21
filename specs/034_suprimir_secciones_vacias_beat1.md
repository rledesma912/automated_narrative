# Spec 034 — Suprimir Secciones Vacías en Beat #1 (VOZ y Journal)

**Estado:** IMPLEMENTED  
**Fecha:** 2026-04-19  
**Rama destino:** `fix_flow_ollama_local`  
**Motivación:** En la primera iteración del pipeline (Beat #1), los prompts de VOZ y Journal incluyen secciones que sólo tienen sentido a partir del beat #2. Las secciones vacías consumen tokens innecesarios y peor aún, envían al LLM instrucciones contradictorias (ej: "mantén consistencia con el estado anterior" cuando no hay estado anterior).

---

## 1. Diagnóstico

### VOZ Beat #1 (debug Llamada 2)

El prompt incluye:
```
--- LO QUE PASÓ ANTES ---
Sin contexto anterior

--- ESTADO DEL RELATO ---
Sin memoria narrativa aún
```

Estas secciones no aportan información. La instrucción de continuidad ("CONECTA con el beat anterior") también confunde.

### Journal Beat #1 (debug Llamada 3)

El prompt incluye la sección:
```
## ESTADO ANTERIOR (del beat anterior)
- Últimos eventos: Sin eventos registrados
- Misterios sin resolver: Sin misterios
- Estado físico/emocional: Sin estado registrado
```

Y en las REGLAS:
```
- Mantener consistencia con el estado anterior
- Si no hay cambios relevantes, mantener el valor anterior
```

Estas reglas instruyen al LLM a "preservar" un estado que no existe, lo que puede inducir respuestas que fabrican un estado previo ficticio.

---

## 2. Diseño de la solución

El fix es condicional: Python decide si incluir o no estas secciones según el número de beat / presencia de journal anterior, y pasa el bloque completo (header + contenido) como una sola variable al template.

### 2.1 VOZ — ambos templates

**`voice_compact.md`** — reemplazar:
```
--- LO QUE PASÓ ANTES ---
{previous_context}

--- ESTADO DEL RELATO ---
{journal_context}
```
Por:
```
{context_section}
```

**`voice.md`** — reemplazar:
```
## CONTEXTO ANTERIOR
{previous_context}

## MEMORIA NARRATIVA (Journal)
{journal_context}
```
Por:
```
{context_section}
```

En `build_beat_prompt()` (`prompt_builder.py`):
```python
if beat.number == 1:
    context_section = ""
else:
    # compact
    context_section = (
        f"--- LO QUE PASÓ ANTES ---\n{previous_context}\n\n"
        f"--- ESTADO DEL RELATO ---\n{journal_context}"
    )
    # frontier (mismo patrón, distintos headers)
    context_section = (
        f"## CONTEXTO ANTERIOR\n{previous_context}\n\n"
        f"## MEMORIA NARRATIVA (Journal)\n{journal_context}"
    )
```

La variante se selecciona con el mismo `variant` que ya se calcula en ese método.

### 2.2 Journal — `journal.md`

Reemplazar la sección completa `## ESTADO ANTERIOR` por `{previous_state_section}`.  
Reemplazar las dos reglas por `{consistency_rules}`.

En `build_journal_prompt()`:
```python
if previous_journal is None:
    previous_state_section = ""
    consistency_rules = ""
else:
    previous_state_section = (
        "## ESTADO ANTERIOR (del beat anterior)\n"
        f"- Últimos eventos: {prev_last_events}\n"
        f"- Misterios sin resolver: {prev_unresolved}\n"
        f"- Estado físico/emocional: {prev_state}"
    )
    consistency_rules = (
        "- Mantener consistencia con el estado anterior\n"
        "- Si no hay cambios relevantes, mantener el valor anterior"
    )
```

---

## 3. Cambios de código

### 3.1 `src/application/services/prompt_builder.py`

| Método | Cambio |
|---|---|
| `build_beat_prompt()` | Calcular `context_section` condicionado en `beat.number == 1`; pasar al `format()` en lugar de `previous_context` y `journal_context` separados |
| `build_journal_prompt()` | Calcular `previous_state_section` y `consistency_rules` condicionados en `previous_journal is None`; pasar al `format()` |

### 3.2 Templates

| Archivo | Cambio |
|---|---|
| `config/prompts_generation/voice_compact.md` | Reemplazar 2 secciones de contexto por `{context_section}` |
| `config/prompts_generation/voice.md` | Reemplazar `## CONTEXTO ANTERIOR` + `## MEMORIA NARRATIVA` por `{context_section}` |
| `config/prompts_generation/journal.md` | Reemplazar `## ESTADO ANTERIOR` por `{previous_state_section}`; reemplazar las 2 reglas por `{consistency_rules}` |

---

## 4. Success Criteria

| Criterio | Verificación |
|---|---|
| VOZ Beat #1 no incluye secciones de contexto vacías | Debug Llamada 2: ausencia de `--- LO QUE PASÓ ANTES ---` |
| Journal Beat #1 no incluye ESTADO ANTERIOR ni reglas de consistencia | Debug Llamada 3: ausencia de `## ESTADO ANTERIOR` |
| VOZ Beat #2+ sí incluye las secciones con contenido real | Debug Llamada 4: presencia de `--- LO QUE PASÓ ANTES ---` con texto |
| Journal Beat #2+ sí incluye ESTADO ANTERIOR | Debug Llamada 5: presencia con valores del beat anterior |
| Tests unitarios pasan | `pytest tests/unit/ -v` → 200+ OK |

---

## 5. Boundaries

### Always Do
- La variable `{context_section}` siempre se pasa al `format()`, incluso si es `""` — evitar `KeyError`.
- Mismo para `{previous_state_section}` y `{consistency_rules}`.

### Never Do
- No modificar el fallback inline de `build_beat_prompt()` (el que usa el bloque `base =` cuando no hay template).
- No cambiar la lógica de `_build_previous_context()` ni `_build_journal_context()` — siguen construyendo los strings como antes; sólo cambia si se inyectan al template.

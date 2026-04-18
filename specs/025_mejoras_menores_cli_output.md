# SPEC 025: Mejoras menores — CLI output, naming, config y reglas

## Estado

> Borrador — pendiente OK del usuario para avanzar a PLAN

---

## 1. Requerimientos

### R1 — Log de modelos y temperaturas al inicio

Al arrancar la generación, mostrar en consola los parámetros LLM activos:

```
🎬  NarrativeForge — El Monte Prohibido
📐  Modelo: Tohur/natsumura-storytelling-rp-llama-3.1:8b  |  Director: 0.4  |  Voz: 0.6  |  Journal: 0.3
────────────────────────────────────────
```

**Dónde:** nuevo método `ProgressReporter.config_summary(model, director_t, voz_t, journal_t)`.  
**Quién lo llama:** `_generate_async()` en `commands.py`, después de crear el reporter y antes de `runner.run_full()`.

---

### R2 — Formato de tiempo mm:ss si >= 60s

Helper privado `_fmt_time(s: float) -> str` en `progress.py`:

```python
def _fmt_time(s: float) -> str:
    if s < 60:
        return f"{s:.1f}s"
    return f"{int(s) // 60}:{int(s) % 60:02d}"
```

Aplicar en todos los `{elapsed:.1f}s` de `ProgressReporter`. `SilentReporter` no necesita cambios.

---

### R3 — Sincronizar `.env.sample` con `config.py`

**Faltante detectado:** `BEATS_DEFINITION_FILE` está en `config.py` pero no en `.env.sample`.

**Huérfano detectado:** `DEFAULT_TOTAL_ACTS=5` está en `.env.sample` pero no en `config.py` (residuo pre-Spec 021).

Cambios:
- Agregar a `.env.sample`: `BEATS_DEFINITION_FILE=config/llm_beats_definition.yaml`
- Eliminar de `.env.sample`: `DEFAULT_TOTAL_ACTS=5`

---

### R4 — Formato de nombre del archivo generado

**Actual:** `El_Monte_Prohibido_18042026143022.md` → `strftime("%d%m%Y%H%M%S")`  
**Nuevo:** `el_monte_prohibido_202604181430.md` → `strftime("%Y%m%d%H%M")`

Reglas:
- Título en minúsculas
- Sin segundos
- Año primero (orden ISO)

**Dónde:** `_write_markdown()` en `commands.py`:

```python
timestamp = datetime.now().strftime("%Y%m%d%H%M")
safe_title = (
    "".join(c for c in story.title if c.isalnum() or c in (" ", "-", "_"))
    .strip()
    .replace(" ", "_")
    .lower()
)
output_path = output_dir / f"{safe_title}_{timestamp}.md"
```

---

### R5 — Forzar aplicación de reglas en voice.md

**Diagnóstico:** Las reglas están en `voice.md` como listado pasivo bajo `## REGLAS DE LA HISTORIA`, pero `## INSTRUCCIONES OBLIGATORIAS` no tiene ninguna directiva que fuerce al LLM a aplicarlas activamente. El LLM las lee como contexto, no como restricciones de ejecución.

**Fix en `voice.md`:** Agregar subsección en `## INSTRUCCIONES OBLIGATORIAS`:

```markdown
### Reglas de personaje
- ANTES de escribir, revisá las REGLAS DE LA HISTORIA arriba.
- Si una regla define el comportamiento de un personaje (ej. "Ricardo ignora lo sobrenatural"), reflejalo en sus acciones, diálogos o pensamientos en este beat.
- Las reglas son restricciones activas, no sugerencias.
```

**Fix en `planner.md`:** Mover la sección `## Reglas de la historia` al final, justo antes de `## Instrucciones de salida`, para que sea la última información antes del output (los LLMs priorizan instrucciones al final).

---

## 2. Archivos afectados

| Archivo | Cambio |
|---|---|
| `src/cli/progress.py` | Agregar `_fmt_time()`, nuevo método `config_summary()`, aplicar `_fmt_time` en todos los tiempos |
| `src/cli/commands.py` | Llamar `reporter.config_summary(...)`, actualizar `_write_markdown()` con nuevo formato |
| `.env.sample` | Agregar `BEATS_DEFINITION_FILE`, eliminar `DEFAULT_TOTAL_ACTS` |
| `config/prompts_generation/voice.md` | Agregar subsección "Reglas de personaje" en INSTRUCCIONES OBLIGATORIAS |
| `config/prompts_generation/planner.md` | Mover sección reglas al final antes de instrucciones de salida |

---

## 3. Criterios de éxito

- [ ] Consola muestra modelo y temperaturas al inicio de cada generación
- [ ] Tiempos < 60s siguen mostrando `X.Xs`; >= 60s muestran `m:ss`
- [ ] `.env.sample` tiene todas las variables de `config.py` y ninguna huérfana
- [ ] Archivos generados tienen formato `titulo_yyyyMMddhhmm.md`
- [ ] Las reglas del input aparecen reflejadas en el comportamiento de los personajes en el relato (validación manual)

---

## 4. Boundaries

| Categoría | Regla |
|---|---|
| **Never Do** | Modificar `SilentReporter` — es no-op intencional |
| **Never Do** | Cambiar el esquema de DB para este spec |
| **Ask First** | Si el prompt de voice.md necesita más cambios estructurales para mejorar calidad |

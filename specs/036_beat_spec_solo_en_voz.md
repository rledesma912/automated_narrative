# Spec 036 — Beat Spec Solo en VOZ, Mapper Puramente Extractivo

**Estado:** IMPLEMENTED  
**Fecha:** 2026-04-19  
**Rama destino:** `fix_flow_ollama_local`  
**Motivación:** Las restricciones dramáticas de cada beat (must, must_not, state_change, success_signal) pertenecen a la fase de GENERACIÓN, no a la de PLANIFICACIÓN. El mapper tiene una única responsabilidad: dividir la sinopsis en N segmentos, uno por acto. Saber "qué debe evitar" cada acto no le ayuda a extraer — esa información llega al LLM demasiado pronto y puede distorsionar el mapeo. VOZ ya recibe el spec del beat actual en cada iteración (implementado en Spec 033). Este spec elimina las constraints del mapper.

---

## 1. Estado actual

### `synopsis_mapper_compact.md`
No usa `{beats_spec_with_constraints}` pero tiene **constraints hardcodeadas** en la sección `ACTOS:`:
```
Acto 1:
- establecer situación base
- introducir advertencia o anomalía sutil

Acto 2:
- romper advertencia o regla
- introducir anomalía concreta
...
```
Estas descripciones son esencialmente una reescritura manual del `must` de cada beat, incrustada en el template.

### `synopsis_mapper.md` (frontier)
Usa `{beats_spec}` (nombre, intent, must, must_not, state_change, success_signal de todos los beats) e instruye al LLM explícitamente:
```
- La oración DEBE respetar el `must` del acto e incluir sus elementos clave.
- La oración NO DEBE violar el `must_not` del acto bajo ninguna circunstancia.
```

### VOZ (ambos templates)
`{beat_spec}` = `_format_beat_spec_for_beat(beat.number, variant)` → restricciones SOLO del beat actual en cada iteración. **Ya funciona correctamente.**

### `build_synopsis_mapper_prompt()` en `PromptBuilder`
Computa y pasa `beats_spec_with_constraints` aunque ya no lo usa el compact template. Sigue pasando `beats_spec` para el frontier.

---

## 2. Diseño

### Principio
El mapper recibe solo lo necesario para SEGMENTAR: cuántos actos hay y sus nombres/intents de alto nivel. Sin must, must_not, state_change ni success_signal.

### 2.1 `synopsis_mapper_compact.md` — nueva versión

Eliminar la sección `ACTOS:` con las constraints hardcodeadas. Reemplazarla por la lista de actos sin restricciones, generada desde `{beats_spec_compact}`:

```
ACTOS:
{beats_spec_compact}
```

Donde `{beats_spec_compact}` renderiza a:
```
Acto 1 (exposicion): establecer normalidad y sembrar una fisura
Acto 2 (accion_ascendente): activar el conflicto mediante transgresion
Acto 3 (climax): forzar reconocimiento del horror
Acto 4 (accion_descendente): llevar al protagonista al colapso y reaccion
Acto 5 (desenlace): cerrar con escape incompleto y secuela
```

Solo nombre e intent — sin constraints. El template resultante:

```
SINOPSIS:
{sinopsis}

CONTEXTO:
Narradora: {relator}
Personajes: {protagonistas}
Atmósfera: {atmosfera}

ACTOS:
{beats_spec_compact}

INSTRUCCIONES:

Dividí la sinopsis en exactamente {num_beats} actos.

Para cada acto:
- seleccioná el fragmento más representativo de la sinopsis
- condensalo en una sola oración
- mantené fidelidad semántica total

REGLAS:

- Cada línea debe derivarse directamente de la sinopsis
- Podés condensar, pero no reinterpretar
- Usá acciones, percepciones o eventos observables
- No uses lenguaje abstracto

ANCLAJE:

- Cada acto debe basarse principalmente en un párrafo de la sinopsis
- Solo combiná párrafos si es estrictamente necesario

FORMATO DE RESPUESTA:

1. ...
2. ...
3. ...
4. ...
5. ...
```

### 2.2 `synopsis_mapper.md` (frontier) — nueva versión

Reemplazar `{beats_spec}` (completo con constraints) por `{beats_spec_compact}` (solo nombres e intents).

Eliminar las instrucciones que referencian `must` y `must_not`:
```
# ELIMINAR:
- La oración DEBE respetar el `must` del acto e incluir sus elementos clave.
- La oración NO DEBE violar el `must_not` del acto bajo ninguna circunstancia.
```

### 2.3 `build_synopsis_mapper_prompt()` en `PromptBuilder`

Eliminar el cálculo y pasaje de `beats_spec_with_constraints` y `beats_spec` — ya no los usan los templates. Solo queda `beats_spec_compact`:

```python
def build_synopsis_mapper_prompt(self, story: "Story") -> str:
    ...
    beats_spec_compact = self._format_beats_spec_compact()

    return template.format(
        title=story.title,
        sinopsis=story.sinopsis,
        protagonistas=story.protagonista,
        relator=story.relator,
        escenarios=story.escenarios,
        atmosfera=story.atmosfera,
        reglas=reglas_str,
        num_beats=self.num_beats,
        beats_spec_compact=beats_spec_compact,
    )
```

Se pueden eliminar también `_format_beats_spec()` y `_format_beats_spec_with_constraints()` de `PromptBuilder` si ya no los usa ningún template activo. Verificar antes de borrar.

---

## 3. Archivos críticos

| Archivo | Cambio |
|---|---|
| `config/prompts_generation/synopsis_mapper_compact.md` | Reemplazar sección ACTOS hardcodeada por `{beats_spec_compact}` |
| `config/prompts_generation/synopsis_mapper.md` | Reemplazar `{beats_spec}` por `{beats_spec_compact}`; eliminar referencias a must/must_not en instrucciones |
| `src/application/services/prompt_builder.py` | `build_synopsis_mapper_prompt()`: eliminar `beats_spec` y `beats_spec_with_constraints` del format(); verificar si `_format_beats_spec()` y `_format_beats_spec_with_constraints()` quedan huérfanos |

---

## 4. Lo que NO cambia

- `{beat_spec}` en VOZ — sigue igual, recibe las constraints completas del beat actual en cada iteración.
- `_format_beat_spec_for_beat()` — no se toca.
- `_format_beats_spec_compact()` — no se toca (se usa en el mapper).
- El parser de beats y el flujo de orquestación — sin cambios.

---

## 5. Success Criteria

| Criterio | Verificación |
|---|---|
| Mapper prompt compact no contiene "Debe incluir" ni "No debe incluir" | Debug Llamada 1: ausencia de esas frases |
| Mapper prompt frontier no contiene `must` ni `must_not` ni instrucciones que los referencien | Debug Llamada 1 con perfil frontier |
| VOZ Beat #1 sigue recibiendo `{beat_spec}` con constraints | Debug Llamada 2: presencia de "Debe incluir" |
| Tests pasan | `pytest tests/unit/ -v` |

---

## 6. Boundaries

### Always Do
- El template compact sigue recibiendo `{beats_spec_compact}` para que el mapper sepa qué "tipo" de momento extraer de la sinopsis.
- Verificar que `_format_beats_spec()` sigue siendo usado por algún template antes de eliminarlo.

### Never Do
- No eliminar `{beat_spec}` de los templates de VOZ.
- No modificar `_format_beat_spec_for_beat()`.

# Spec 028: Fix Director — Parser Robusto + Formato de Planner

## Objetivo

Corregir dos bugs encadenados que anulan completamente la dirección narrativa:

1. **Bug de parser**: `_parse_beats()` usa un regex `^(\d+)` que no matchea el formato
   real que producen los modelos (`N.1 Summary`, `1) Summary`, etc.) → todos los beats
   caen en FALLBACK genérico (`"Beat #X generado automáticamente"`).
2. **Bug de prompt**: `planner.md` especifica el formato como `N. [summary del acto en
   una oración]` (descripción abstracta) en vez de un ejemplo concreto → el modelo
   interpreta `N` como variable y genera `N.1`, `N.2`.

**Consecuencia confirmada en log (línea 8096):**
```
[WARNING] [DIRECTOR] FALLBACK: no se pudo parsear la respuesta, se usan 5 beats genéricos.
```
La Voz recibe `Resumen: Beat #X generado automáticamente` → no tiene guidance de
contenido → el modelo escribe toda la historia en cada beat.

### Resultado objetivo

Después de este fix:
- El Director genera beats con formato concreto (ej. `1. La familia llega a la casa...`)
- El parser los lee correctamente sin FALLBACK
- La Voz recibe summaries reales específicos a cada escena
- Los beats kortados a mitad de frase desaparecen (`num_predict` ajustado)

---

## Diagnóstico detallado

### Bug 1 — Regex frágil en `_parse_beats()`

```python
# director_use_case.py:61 — ACTUAL (roto)
match = re.match(r"^(\d+)", line)
```

Formatos que produce el mismo modelo (mistral) en distintas ejecuciones:

| Formato observado | Matchea `^(\d+)` |
|---|---|
| `1. Summary texto` | ✅ |
| `N.1 Summary texto` | ❌ (empieza con `N`) |
| `1) Summary texto` | ✅ |
| `Beat 1: Summary texto` | ❌ |
| `**1.** Summary texto` | ❌ |

El modelo que falló (mistral para rol director) produjo `N.1`, `N.2`. El regex nunca matchea.
Resultado: 5 beats genéricos vacíos de contenido.

### Bug 2 — Formato abstracto en `planner.md`

```markdown
# ACTUAL (planner.md línea 22):
- Formato exacto: `N. [summary del acto en una oración]`
```

El modelo interpreta `N` como nombre de variable (placeholder) y escribe:
```
N.1 La familia llega a la casa...
N.2 La fiesta se extiende...
```

Un ejemplo concreto (`1. La familia llega`, `2. La fiesta se extiende`) elimina la ambigüedad.

### Bug 3 — `num_predict=800` insuficiente para el rol voz

Medido en log: la Voz genera ~2700 chars (~450 palabras) antes de ser cortada.
Con `num_predict=800` tokens (~400-500 palabras en español), todos los beats
terminan a mitad de frase:
- Beat 1: `"parecía que viniera de allá arriba"`
- Beat 2: `"Soledad se agit"`
- Beat 3: `"Entonces"`

El voice.md pide 150-300 palabras pero el modelo RP sigue escribiendo más allá del límite de palabras porque no tiene un token de parada natural. `num_predict` es el único freno real.

---

## Solución

### Hito 1 — Parser defensivo en `_parse_beats()`

Reemplazar el regex único por una **cadena de patrones** que prueba formatos en orden
de especificidad y extrae el número de beat y el summary:

```python
_BEAT_PATTERNS = [
    re.compile(r"^N\.(\d+)\s+(.+)"),            # N.1 Summary
    re.compile(r"^\*{0,2}(\d+)\.\*{0,2}\s+(.+)"),  # 1. / **1.** Summary
    re.compile(r"^(\d+)\)\s+(.+)"),              # 1) Summary
    re.compile(r"^Beat\s+(\d+)[:\-\.]\s*(.+)", re.IGNORECASE),  # Beat 1: Summary
    re.compile(r"^(\d+)\s+(.+)"),                # 1 Summary (sin separador)
]
```

La función `_parse_beats()` itera cada línea y prueba los patrones en orden.
Si ninguno matchea en ninguna línea, **y solo entonces**, activa el FALLBACK.

Además: el FALLBACK debe loggear el raw response completo en WARNING, no solo
los primeros caracteres, para facilitar el diagnóstico.

### Hito 2 — Formato concreto en `planner.md`

Reemplazar la instrucción abstracta por un ejemplo concreto de dos líneas:

```markdown
# ANTES:
- Formato exacto: `N. [summary del acto en una oración]`

# DESPUÉS:
- Formato exacto — una línea por acto, número seguido de punto y espacio:
  1. La protagonista llega al lugar y recibe una advertencia vaga.
  2. La transgresión ocurre: ignoran la advertencia y se adentran en el peligro.
  (los ejemplos son genéricos — escribe el tuyo específico a esta historia)
- Sin encabezados, sin explicaciones, sin texto fuera de las {num_beats} líneas.
```

El few-shot de 1-2 líneas es la técnica más efectiva para modelos pequeños que
ignoran instrucciones abstractas de formato.

### Hito 3 — Ajuste de `num_predict` en perfiles Ollama

En `config/llm_core_definitions.yaml`, perfil `ollama-natsumura` (y análogos):

```yaml
voz:
  num_predict: 1200   # era 800 — suficiente para 300 palabras + margen
```

Justificación: 300 palabras en español ≈ 450-500 tokens. Con 800 el modelo se
corta a ~350 palabras. Con 1200 hay margen para que los stop sequences (si el
modelo los respeta) sean el freno principal, no el límite de tokens.

---

## Archivos involucrados

| Archivo | Hito | Operación |
|---|---|---|
| `src/application/use_cases/director_use_case.py` | 1 | Refactor `_parse_beats()` |
| `config/prompts_generation/planner.md` | 2 | Fix formato → ejemplo concreto |
| `config/llm_core_definitions.yaml` | 3 | Ajustar `num_predict` voz |

---

## Tests

### Hito 1 — Tests del parser

Archivo: `tests/unit/application/test_director_use_case.py` (actualizar existentes + agregar)

Casos a cubrir:

```python
# Formatos que DEBEN parsear correctamente:
"N.1 La familia llega a la casa de María y recibe la advertencia."
"1. La familia llega a la casa de María y recibe la advertencia."
"1) La familia llega a la casa de María y recibe la advertencia."
"Beat 1: La familia llega a la casa de María y recibe la advertencia."
"**1.** La familia llega a la casa de María y recibe la advertencia."

# Caso de respuesta completa con 5 beats mezclados (test de integración del parser):
RESPONSE_N_FORMAT = """
N.1 La familia llega a la casa.
N.2 La fiesta se extiende hasta la noche.
N.3 En el monte los sonidos comienzan.
N.4 Aparece la figura imposible.
N.5 La presión cede y salen al amanecer.
"""
# → debe producir 5 beats sin FALLBACK

# Caso FALLBACK: respuesta completamente ilegible
"Lorem ipsum sin números ni formato reconocible"
# → debe activar FALLBACK y logear el raw response
```

### Hito 2 — Test de smoke del planner prompt

Verificar que el template renderizado de `planner.md` contiene la instrucción
de formato corregida (sin `N. [summary]`):

```python
def test_planner_prompt_no_abstract_format():
    builder = PromptBuilder()
    story = make_test_story()
    prompt = builder.build_planner_prompt(story)
    assert "N. [summary" not in prompt
    assert "1." in prompt  # el ejemplo concreto está presente
```

---

## Criterios de aceptación

- [x] `pytest tests/unit/application/test_create_story_plan.py -v` — 13 passed
- [x] Suite completa `pytest tests/ -q` — 174 passed
- [ ] Ejecución real con `ollama-natsumura` → log no muestra la línea `[WARNING] [DIRECTOR] FALLBACK`
- [ ] El beat_prompt de la Voz muestra `Resumen:` con texto real (no `"Beat #X generado automáticamente"`)
- [ ] Los beats generados no terminan a mitad de frase (num_predict ajustado)

---

## Fuera de alcance

- Prompt variants por modelo (`prompt_variant` en perfiles YAML) — spec separado (029)
- Ajuste de `previous_context` (150 chars) — puede mejorar en spec de coherencia
- Corrección de "personajes fuera de escena" (María en el coche) — requiere spec de diseño
- Confusión "mi madre" / "madre de Ricardo" — requiere mejora de sinopsis o prompt de Voz

---

## Relación con specs previos

- **Spec 026/027**: este fix no cambia la arquitectura YAML ni los perfiles. Solo corrige el parser y el prompt de planner dentro de la arquitectura existente.
- **Spec 014** (`prompts_beats_refactor`): el `planner.md` ya fue refactorizado allí; este spec solo ajusta la instrucción de formato, no la estructura del template.

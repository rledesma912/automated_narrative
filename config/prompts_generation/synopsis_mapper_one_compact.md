<!-- variante: compact | rol: mapper (user, map_one) | cargado por: build_synopsis_mapper_one_prompt() -->
# ARQUITECTO DE BEAT (Acto {macro_beat_id})

Tu tarea es diseñar la estructura técnica del **Acto {macro_beat_id}: {beat_name}**.
Sos el puente entre la sinopsis y la narración literaria.

## CONTEXTO ESPECÍFICO DE ESTE ACTO
- **ATMÓSFERA:** {atmosphere}
- **INTENTO NARRATIVO:** {beat_intent}
- **ESCENARIO DESIGNADO:** {active_scenario}

### REGLAS ACTIVAS QUE DEBEN MANIFESTARSE
{active_rules}

### FRAGMENTO DE SINOPSIS (EVENTOS BASE)
{synopsis_slice}

{prev_snapshot_section}

## ANCLAJES NARRATIVOS
- **Principal:** {anchor_principal}
- **Contexto:** {anchor_contexto}

---

## INSTRUCCIONES DE DISEÑO
1. **Segmentación Fina:** Analiza el fragmento de sinopsis y extrae los eventos concretos que deben ocurrir.
2. **Integración de Reglas:** Describe cómo las reglas activas afectan a los personajes o al entorno en este momento preciso.
3. **Coherencia Atmosférica:** Asegúrate de que los eventos reflejen la atmósfera ({atmosphere}).
4. **No anticipar:** No incluyas eventos que pertenecen a fragmentos posteriores de la sinopsis.

## FORMATO DE RESPUESTA (ESTRICTO)

ESCENARIO: [Nombre exacto del escenario activo]

EVENTOS:
- [Descripción técnica del primer evento, integrando reglas/atmósfera]
- [Descripción técnica del segundo evento, integrando reglas/atmósfera]
- [etc...]

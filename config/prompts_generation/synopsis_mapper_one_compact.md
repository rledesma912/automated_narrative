<!-- variante: compact | rol: mapper (user, map_one) | cargado por: build_synopsis_mapper_one_prompt() -->
# ARQUITECTO DE BEAT (Acto {macro_beat_id})

Tu tarea es diseñar la estructura técnica del **Acto {macro_beat_id}: {beat_name}**.
Sos el puente entre la sinopsis y la narración literaria.

## CONTEXTO ESPECÍFICO DE ESTE ACTO
- **TIPO DE ACTO:** {beat_type}
- **INTENCIÓN:** {beat_intent}
- **INTENSIDAD:** {beat_intensity}
- **ESCENARIO DESIGNADO:** {active_scenario}

### REGLAS ACTIVAS QUE DEBEN MANIFESTARSE
{active_rules}

### FRAGMENTO DE SINOPSIS (EVENTOS BASE)
{synopsis_slice}

{prev_snapshot_section}

## ANCLAJES NARRATIVOS
- **Principal:** {anchor_principal}
- **Contexto (guía atmosférica — NO incluir como eventos):** {anchor_contexto}

---

## INSTRUCCIONES DE DISEÑO
1. **Segmentación Fina:** Analiza el FRAGMENTO DE SINOPSIS y extrae solo los eventos que ocurren en el ESCENARIO DESIGNADO.
2. **Integración de Reglas:** Describe cómo las reglas activas afectan a los personajes o al entorno en este momento preciso.
3. **Coherencia Atmosférica:** Asegúrate de que los eventos reflejen la atmósfera ({atmosphere}).
4. **No anticipar:** No incluyas eventos que pertenecen a fragmentos posteriores de la sinopsis.
5. **Un solo escenario (Mandatorio):** Tu respuesta debe contener EXACTAMENTE UN bloque ESCENARIO: el escenario designado. Está prohibido mencionar o incluir eventos que ocurran fuera de los límites físicos de este escenario. Si la sinopsis mezcla lugares, debes realizar una poda estricta y quedarte solo con lo que sucede en el lugar asignado. La filtración de eventos de escenarios futuros o pasados se considera un fallo crítico de arquitectura.
6. **Transferencia Léxica Invariable:** Es obligatorio preservar el vocabulario específico del usuario. Si la sinopsis usa términos específicos para objetos, vehículos o herramientas (ej: 'sulki', 'facón', 'bláster'), ese término es una **Palabra Clave Invariable**. No la simplifiques, no la traduzcas a genéricos (auto, cuchillo, arma) ni la omitas. La pérdida de un objeto físico en este paso se considera un fallo crítico.
7. **Transiciones:** Si el fragmento describe una salida o partida desde el ESCENARIO DESIGNADO, incluyela como el último evento del bloque con los detalles concretos que menciona la sinopsis.

## FORMATO DE RESPUESTA (ESTRICTO)

ESCENARIO: {active_scenario}

EVENTOS:
- [Primer evento concreto que ocurre, en una oración directa]
- [Segundo evento concreto, en una oración directa]
- [etc. Solo eventos, sin meta-comentarios entre paréntesis]

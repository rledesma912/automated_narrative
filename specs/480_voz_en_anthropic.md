# SPEC-480: La Voz en Anthropic (EV-2)

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development)
**Estado:** SPECIFY — borrador, pendiente de OK
**Roadmap:** EV-2. Sigue a Spec-470 (EV-3), que dejó como techo del modelo local la gramática torpe y los errores de continuidad.

---

## ASSUMPTIONS

1. **Solo la Voz** pasa a Claude; Analyst, Mapper y Journal siguen en Ollama (`gemma3:12b`). La Voz es donde se nota la prosa y son 5 de las 16 llamadas.
2. El resto del pipeline, los prompts de Spec-470 (compact) y las entidades de Spec-450 no cambian. La Voz en Claude usa la variante de prompt **compact**, la misma que hoy, para comparar solo el modelo.
3. Se usa el SDK oficial `anthropic` (ya es dependencia, 0.96.0) y la `ANTHROPIC_API_KEY` del `.env`.
4. El perfil local actual (`ollama-gemma3-12b`) sigue siendo el activo hasta que la evaluación muestre que vale la pena; el cambio de perfil activo en prod se decide con los números.
5. Cada relato generado con Claude cuesta dinero: **toda corrida de evaluación se aprueba antes** con su costo estimado.

---

## OBJECTIVE

Mejorar la calidad de la prosa (lo que las relatoras notan) donde el modelo local ya no da más: frases mal armadas («El taxi toco la puerta de barro», «Alargar la manta sobre los chiquitos, sentí algo áspero»), formas no rioplatenses («Rezad»), errores de continuidad («conversando con su madre» en el sulki, cuando María quedó en la casa) y el esquive de la lista de clichés con variantes («me heló el alma»).

**Éxito:** en la evaluación de Spec-470 (`scripts/evaluate_voice.py`), la Voz en Claude mantiene o mejora las métricas (clichés ≤ 1, parentescos 0, narradora en 3ra persona 0, frases repetidas ≤ 2) y la lectura manual confirma menos errores de gramática y continuidad, con un **costo por relato** conocido y aceptado.

---

## 1. HALLAZGOS EN EL CÓDIGO

| Hallazgo | Consecuencia |
|---|---|
| `LLMFactory.get_provider()` crea **un solo adapter** para todo el pipeline, según `provider` del perfil. | El perfil híbrido `anthropic-opus-voz` no funciona: el Mapper y el Journal piden `qwen2.5:14b` y la llamada iría a la API de Anthropic. |
| `AnthropicAdapter` manda `temperature` salvo a `claude-opus-4*`. | Claude Opus 5 y Sonnet 5 **rechazan** los parámetros de sampling (400). |
| Lee `response.content[0].text`. | En Opus 5 el pensamiento adaptativo viene activo por defecto: el primer bloque puede ser de razonamiento, no el texto. |
| No mira `stop_reason`. | Un `refusal` (clasificadores de seguridad) o un corte por `max_tokens` pasarían como prosa vacía o truncada. |
| El perfil usa `claude-opus-4-7` / `claude-sonnet-4-6`. | Generación anterior; los vigentes son Claude Opus 5 y Sonnet 5. |

---

## 2. CAMBIOS PROPUESTOS

### 2.1 Proveedor por rol

- Cada rol de un perfil puede declarar su `provider` (`roles.voz.provider: anthropic`); si no lo declara, usa el del perfil.
- Un adapter enrutador (`RoleRoutingAdapter`) implementa `LLMProvider` y despacha cada llamada al adapter del rol (todas las llamadas ya pasan `role`, incluido el Journal desde el arreglo de Spec-450 S3). `LLMFactory` lo usa cuando el perfil mezcla proveedores; con un solo proveedor, nada cambia.

### 2.2 `AnthropicAdapter` al día

- Sin `temperature` / `top_p` / `top_k` para los modelos que no los aceptan (Opus 5, Sonnet 5, Opus 4.7+).
- `thinking` y `effort` configurables por rol en el perfil (`thinking: adaptive|disabled`, `effort: low|medium|high`).
- El texto se arma con **los bloques `text`** de la respuesta, no con `content[0]`.
- `stop_reason`: `refusal` → error claro (con la categoría); `max_tokens` → error claro (no se persiste un acto truncado).
- `max_tokens` desde `num_predict` del rol (hoy fijo en 4096).
- Uso de tokens (`usage`) registrado en el log y en el debug collector, para medir el costo real.

### 2.3 Perfil híbrido

Perfil nuevo (o `anthropic-opus-voz` corregido): los roles de `ollama-gemma3-12b` para Analyst, Mapper y Journal, y la Voz en Claude. **No se activa en prod** hasta decidirlo con la evaluación.

### 2.4 Evaluación

`scripts/evaluate_voice.py` suma `--profile <perfil>` y reporta el **costo por relato** (tokens de entrada/salida de la Voz × precio del modelo).

---

## 3. COSTO ESTIMADO

Base: medición de Spec-470 (la Voz recibe ~1900–2900 tokens por llamada según las entidades; escribe ~450–530 palabras ≈ 700–900 tokens), 5 llamadas por relato. El tokenizer de Claude puede contar hasta ~1,35× más que el de gemma; se toma el peor caso.

| Modelo | Precio (entrada / salida, US$ por millón) | Sin pensamiento | Con pensamiento adaptativo (+~1000 tokens de salida por acto) |
|---|---|---|---|
| **Claude Opus 5** (`claude-opus-5`) | 5 / 25 | ~US$ 0,20 por relato | ~US$ 0,33 por relato |
| **Claude Sonnet 5** (`claude-sonnet-5`) | 2 / 10 | ~US$ 0,08 por relato | ~US$ 0,13 por relato |

Cuenta por relato: entrada ~2400 tokens (gemma) × 1,35 ≈ 3240 por acto → ~16.200; salida ~700 × 1,35 ≈ 950 por acto → ~4.750; el pensamiento suma ~5000 de salida. En Claude Opus 5 el pensamiento adaptativo está **activo por defecto**.

La evaluación completa (2 corridas × sin/con entidades = 4 relatos) costaría **~US$ 0,80–1,30 con Opus 5** o **~US$ 0,30–0,55 con Sonnet 5**, más una corrida corta de prueba. Los costos reales se miden en la evaluación (§2.4).

---

## BOUNDARIES

- **Siempre:** aprobar el costo de cada corrida de evaluación antes de lanzarla; medir con el mismo arnés de Spec-470; tests con el SDK simulado (sin llamadas reales).
- **Consultar antes:** activar el perfil híbrido en prod; cambiar de modelo.
- **Nunca:** mandar datos de las historias a otro proveedor que no sea el elegido; hardcodear la API key.

---

## OPEN QUESTIONS

1. **Modelo de la Voz:** ¿Claude Opus 5 (~US$ 0,20–0,33 por relato) o Claude Sonnet 5 (~US$ 0,08–0,13)? ¿O evaluamos los dos?
2. **Pensamiento:** para prosa creativa, ¿probamos con pensamiento adaptativo (más caro, puede planificar mejor el acto) o sin él?
3. **Presupuesto de la evaluación:** ¿aprobás ~US$ 1–2 para la evaluación completa (según las respuestas anteriores)?
4. **Prod:** si la evaluación convence, ¿el perfil híbrido pasa a ser el activo en prod, o queda como opción para elegir por relato?

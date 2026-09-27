# SPEC-560: Asistente — procesamiento y reglas

**Fecha:** 2026-09-27
**Tipo:** SDD (Spec-Driven Development) — calidad del pipeline del asistente
**Estado:** SPECIFY — análisis en curso: se suman temas; cada uno con diagnóstico, propuesta y decisión del usuario
**Rama:** `feat/analisis-asistente-ui-logica`
**Extiende:** Spec-530 (asistente, escaleta y pipeline del relato). La UI del asistente va en Spec-550.

---

## ASSUMPTIONS

1. Los hallazgos salen de la primera generación con esta versión («La presencia del colectivo», en dev, con `gemma3:12b`).
2. El pipeline es el de Spec-530: Planificador → Verificador → por acto, Voz (`outline_voice*.md`) + Memoria (`outline_journal*.md`). La Voz no ve la prosa de los otros actos: solo la escaleta del acto y la memoria acumulada.
3. Cada cambio de prompt se mide con `scripts/evaluate_voice.py` antes y después, y cambia el snapshot de prompts a propósito (`SNAPSHOT_UPDATE=1`).
4. Cambios de esquema de la DB: sin migraciones; en prod, `export-yaml` → DB nueva → `import-yaml` (CLAUDE.md). Se prefieren soluciones que no cambien el esquema.

---

## OBJECTIVE

Que el relato salga **hilado** (sin saltos entre actos), **sin repeticiones** y con **todos los puntos narrativos cubiertos**, y que cada campo del asistente tenga un propósito claro para el autor.

---

## 1. TEMAS

### A1 — Salto entre actos: el Acto 2 no cuenta cómo se llegó desde el Acto 1 · **propuesta a decidir**

**Lo que ve el usuario:** el Acto 2 arranca con «La terminal estaba vacía», sin contar cómo se pasó del final del Acto 1 a ese momento. Propone un campo o una pregunta sobre qué ocurre entre acto y acto, incluso cuánto tiempo pasa.

**Qué recibe hoy la Voz para empezar un acto** (`OutlineNarrator.voice_prompts`, `outline_voice.md`):
- «LO QUE YA PASÓ (no lo vuelvas a contar)»: la memoria, 2–3 frases de **hechos** por acto anterior, y el **estado** del protagonista al final del acto anterior (una frase).
- Los hechos del acto, «AL TERMINAR EL ACTO» (`change_to`) y el escenario.
- **No recibe** «cómo empieza el acto» (`change_from`): el Planificador lo escribe, pero la Voz nunca lo ve.
- **No recibe** cuánto tiempo pasó ni cómo se llegó al lugar: no existe en la escaleta.
- **No recibe** cómo terminó la prosa del acto anterior (su último párrafo): la memoria es un resumen de hechos, no el tono ni la última imagen.
- La instrucción «no lo vuelvas a contar» empuja a saltar directo a los hechos nuevos, sin puente.

**Propuesta:**
1. **Puente en la escaleta** (actos 2–5): «**Cómo llega acá**» — cuánto tiempo pasó y qué pasó entre el final del acto anterior y el primer hecho de este («Esa misma noche, después de dejar el micro en el galpón, José vuelve caminando a la terminal»). Lo propone el Planificador; el autor lo edita.
   - **Opción a (sin cambio de esquema, recomendada):** reusar `change_from` («cómo está la situación al empezar»), que hoy nadie usa en la Voz: el Planificador lo escribe como puente (tiempo + cómo llega) y la UI lo muestra como «Cómo llega acá».
   - **Opción b:** campos nuevos (`bridge`, `time_elapsed`) en `act_outline`: más explícito, pero cambia el esquema (export/import en prod).
2. **La Voz recibe el puente** en una sección «CÓMO SE LLEGA A ESTE ACTO» con la instrucción de **abrir el acto contándolo en pocas líneas** antes de los hechos.
3. **La Voz recibe el final del acto anterior**: sus últimas 2–3 oraciones, textuales («ASÍ TERMINÓ EL ACTO ANTERIOR — seguí desde acá, sin repetirlo»), para continuar la voz y la imagen. Sin llamadas extra al LLM.
4. **El Verificador controla la continuidad:** regla (actos 2–5 sin puente → aviso) y chequeo de la IA («el acto empieza en un lugar o momento que no se explica desde el final del anterior»).

**Costo:** 0 llamadas extra; prompts de la Voz y del Planificador algo más largos.

### A2 — Al regenerar un acto, ¿la Voz sabe qué frases no repetir? · **no; propuesta a decidir**

**Lo que ve el usuario:** el panel del Acto 3 marca frases repetidas. Si lo regenera, ¿al modelo le llega qué no repetir?

**Hoy** (`RegenerateBeatVozUseCase`):
- La Voz recibe la memoria **hasta el acto anterior**, con su lista «YA USADO» (`used_motifs`): imágenes y frases que la Memoria **eligió** como reconocibles. **No** recibe lo que detectó el control de repetición (`repetition_check.py`: las frases de 4 palabras que repite de actos anteriores, los clichés y los nombres inventados). Pueden no coincidir: por eso la repetición se escapa.
- Tampoco sabe qué tenía la versión que se está descartando.
- Después de regenerar, **la memoria de ese acto no se actualiza**: los actos siguientes quedaron escritos con la memoria de la versión vieja (y si se regeneran después, la siguen usando).

**Propuesta:**
1. **Pasarle a la Voz los hallazgos del control de repetición** de ese acto, en una sección «EN LA VERSIÓN ANTERIOR DE ESTE ACTO REPETISTE / USASTE — NO LO VUELVAS A HACER»: frases repetidas (con el acto de origen), clichés y nombres inventados. Es determinístico: 0 llamadas extra.
2. **Actualizar la memoria del acto** después de regenerarlo (1 llamada extra a la Memoria), para que lo que venga después parta de la versión nueva.
3. **Avisar en el panel** que los actos siguientes se escribieron con la versión anterior (sin regenerarlos solos: la IA nunca corre sola).
4. En la generación completa, el control de repetición **no** vuelve a la Voz (no hay versión anterior); la prevención sigue siendo «YA USADO».

### A3 — ¿Hay un proceso que detecte puntos de la narrativa que faltan? · **parcial; propuesta a decidir**

**Pregunta del usuario:** ¿la IA interpreta si faltan beats (puntos de la narrativa) para completar la historia?

**Qué hay hoy:**
- **Estructura fija de 5 actos** (`llm_beats_definition.yaml`): cada acto tiene una función (1 exposición: normalidad + inquietud sutil; 2 acción ascendente: activar el conflicto por una transgresión; 3 clímax: forzar el reconocimiento del horror; 4 acción descendente: colapso y reacción; 5 desenlace). El Planificador llena cada acto con 3–5 hechos siguiendo esa función.
- **Taller** (nivel Dirección): qué busca el protagonista, qué arriesga, qué lo expone, historia secreta, final.
- **Verificador — reglas:** acto sin hechos; acto que termina igual que empieza; persona fuera del elenco; siembra que ningún acto retoma.
- **Verificador — IA:** dónde aparece cada decisión del autor; hechos repetidos o adelantados; lo que se guarda y nunca se revela; personas fuera del elenco.

**Lo que nadie controla:**
- Que **cada acto cumpla su función** (que el Acto 2 tenga de verdad la transgresión, que el 3 sea un clímax y no otra escalada).
- La **continuidad causal y temporal entre actos** (A1).
- Los **criterios de nivel escaleta** que planteaba la Spec-530 (§4: «Cambio», «Revelación»…) quedaron solo como reglas sueltas; no hay taller de escaleta.

**Propuesta:** sumar al Verificador (en la misma llamada, sin costo extra) dos chequeos con aviso por acto:
1. **Función del acto:** «el acto no cumple su función: <función>; falta <qué>».
2. **Continuidad:** «el acto empieza en un lugar o momento que no se explica desde el final del anterior» (A1.4).

Los avisos se ignoran como los demás (Spec-550 H10).

### A4 — «Se guarda para después»: ¿para qué sirve? ¿hace falta? · **propuesta a decidir**

**Pregunta del usuario:** qué objetivo persigue el campo y si es necesario.

**Qué hace hoy (`act_outline.held_back`):**
- Es **lo que el acto sabe pero todavía no cuenta**, para revelarlo en un acto posterior: el suspenso y la revelación (por ejemplo, que la mujer murió en ese micro, o por qué se le aparece a José).
- La **Voz** lo recibe como «NO REVELES TODAVÍA: …» en ese acto.
- El **Verificador** avisa si algo guardado nunca se revela después.
- Lo propone el Planificador («qué información se reserva para un acto posterior»; vacío en el Acto 5).

**Es útil** —en terror, lo que se retiene es la mitad del efecto—, pero hoy no se entiende: el nombre no dice «para quién» ni «hasta cuándo», y se confunde con «siembra/retoma».

**Propuesta:**
- **Mantenerlo y explicarlo:** «**Lo que todavía no se cuenta**» + pista: «La Voz no lo revela en este acto; se tiene que revelar en uno posterior».
- **Mostrar dónde se revela:** «Se revela en el Acto N» (o un aviso si ninguno lo revela), para que se vea el recorrido.
- Diferenciarlo en pantalla de «siembra» (un detalle que se muestra ahora y cobra sentido después) y «retoma».

---

## 2. DECISIONES

- **A1:** ✅ decidido (2026-09-27) — **campo nuevo** «Cómo llega acá» en los actos 2–5 (columna nueva en `act_outline`; en prod, export/import de las historias) y **sí** se le pasan a la Voz las últimas 2–3 oraciones del acto anterior (con la indicación de no repetirlas).
- **A2:** pendiente — recomendación: 1 + 2 + 3.
- **A3:** ✅ decidido (2026-09-27) — se suma solo el chequeo de **continuidad** (regla: actos 2–5 sin «Cómo llega acá»; IA: el acto arranca en un lugar o momento que no se explica desde el anterior). El de **función del acto** queda afuera por ahora.
- **A4:** pendiente — recomendación: mantener, renombrar, explicar y mostrar dónde se revela.

---

## 3. CÓMO SE MIDE

- «La presencia del colectivo» y las historias de referencia de `evaluate_voice.py`, antes y después: frases repetidas entre actos (4-gramas), clichés, nombres inventados y —nuevo— **aperturas sin puente** (actos 2–5 cuya primera oración no se conecta con el cierre del anterior; revisión manual sobre una muestra).
- Regenerar el Acto 3 de un relato con repeticiones marcadas: la versión nueva no repite las frases señaladas.

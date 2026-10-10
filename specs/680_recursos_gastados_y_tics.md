# SPEC-680: Recursos gastados del género y tics de la IA

**Fecha:** 2026-10-10
**Tipo:** SDD — calidad (Planificador, Verificador, Voz, control de repetición)
**Estado:** SPECIFY (esperando OK)
**Rama:** `feat/spec-680-recursos-gastados` (desde `development`, `404085f`)
**Extiende:** Spec-470 (clichés de la Voz), Spec-530 §8.3 (control de repetición), Spec-640 (anécdota, comparaciones), Spec-670 (moldes; su medición en §7).

---

## ASSUMPTIONS

1. Hay dos niveles distintos y hoy solo uno está cubierto:
   - **Frases gastadas de la prosa** («un escalofrío recorrió mi espalda»): **resuelto** desde la Spec-470 (`voice_cliches.txt`, 20 frases; el control de repetición las marca; 0 en las mediciones de la 650).
   - **Recursos gastados en lo que pasa** (huellas enormes, perros que ladran y se callan de golpe, una sombra enorme, ojos que brillan, golpes en la puerta): **sin cubrir**. Los arma el Planificador como hechos y la Voz los cuenta tal cual.
2. La máxima del pipeline: lo conceptual se resuelve antes (en «Los actos»); lo que solo aparece en la prosa se **detecta después y se muestra, nunca se corrige solo**. Cada regla nueva previene un error que se vio de verdad.
3. Lo que el autor escribió o eligió manda: si en su idea o en sus respuestas hay «huellas», no es un recurso gastado de la IA.
4. Textos en `config/` (Spec-620), avisos en tono coloquial (Spec-580).

---

## OBJECTIVE

Que los hechos y la prosa no caigan en lo de siempre:

**A. Recursos gastados del género (en «Los actos»).** Una lista de recursos de manual que el Planificador evita y que la revisión marca cuando aparecen, para que la historia busque señales propias de su lugar y sus personajes (como el balde de lata que salió con el giro en la medición de la 670).

**B. Tics de la IA en la prosa: enumerar de a tres.** La hija del usuario notó que la IA «enumera siempre tres cosas». Es un tic documentado de la escritura con IA (la «regla de tres» o *tricolon* aplicada de forma automática); el problema no es la figura sino su repetición mecánica.

---

## 1. Relevamiento (2026-10-10)

### 1.1 Recursos gastados (medición de la Spec-670, §7)

La misma idea («La laguna oscura») con tres moldes, actos armados por Claude: aparecen en **los tres**, sin importar el molde.

| Molde | Menciones de manual | Cuáles |
|---|---|---|
| La de siempre | 5 | huellas (3), golpes (2) |
| Algo viene por nosotros | 7 | huellas, sombra, golpe, perros que ladran, chapoteo (2), rasca |
| Algo viene por nosotros + giro | 5 | huellas (3), golpe, perros que ladran |

En la prueba de la S1 (Claude) y en los actos de gemma: «huellas enormes», «el brillo de unos ojos», «una sombra enorme», «una figura oscura que desaparece al acercarse», «los perros del vecino ladran sin parar».

### 1.2 Enumerar de a tres (en la prosa de la Voz)

Contadas con un patrón estricto («A, B y C», cada ítem de hasta 4 palabras) en 5 relatos (8 042 palabras): **33**, unas **4 cada 1 000 palabras**, alrededor de **7 por relato**. Ejemplos: «unas luces amarillas, chiquitas y fijas», «Eran hondas, con tres dedos largos y anchos», «me acerqué al vidrio, apoyé las manos en el marco frío, entrecerré los ojos». El patrón todavía cuenta algunos falsos positivos (p. ej. «entre El Cruce y La Esperanza»): se afina en el PLAN.

Fuentes sobre el tic: [GPTZero — The Rule of Three](https://gptzero.me/news/the-rule-of-three/), [tropes.fyi — Tricolon abuse](https://tropes.fyi/tropes/tricolon-abuse), [Kompozy — AI Tells Index](https://kompozy.io/research/ai-tells-index) (índice curado, no un estudio), [LilysAI — La epidemia de escritura con IA](https://lilys.ai/es/notes/ai-writing-20260102/ai-writing-epidemic). Todas coinciden en que la figura es legítima y el problema es el uso reflejo; ninguna mide su frecuencia en un modelo concreto.

---

## 2. Qué se construye

### A. Recursos gastados (Planificador + revisión)

- **`config/recursos_gastados.yaml`** (nuevo): cada recurso con un nombre, las raíces que lo detectan (como `voice_cliches.txt`) y una línea de por qué está gastado. Arranca con los vistos: huellas enormes, perros que ladran / se callan de golpe, sombra o figura enorme que desaparece, ojos que brillan en la oscuridad, golpes en la puerta en la noche, la luz que parpadea, el silencio repentino de los animales.
- **Planificador:** un bloque «RECURSOS GASTADOS (no los uses como hechos; si hace falta una señal, buscá una propia de este lugar y estos personajes)». Lo que el autor ya escribió (idea, respuestas, la amenaza) no entra en la lista para esa historia.
- **Revisión (sin IA, como las reglas del Verificador):** un aviso por acto cuando un hecho usa un recurso gastado que no viene del autor («Las huellas enormes ya se vieron en muchos cuentos: ¿hay una señal más de este lugar?»), con «Ignorar» como los demás avisos.
- **Medición:** `medir_moldes.py` lee la lista del YAML (hoy la tiene fija en el código).

### B. Enumerar de a tres (Voz + control de repetición)

- **Guía de oficio de la Voz** (`voice_craft.md`): una línea, como la de las comparaciones (Spec-640): no describir ni enumerar siempre de a tres; una cosa, dos, y de a tres solo cuando de verdad son tres.
- **Control de repetición:** cuenta las enumeraciones de tres por acto y avisa desde un umbral (con hasta 3 ejemplos), como las comparaciones y las oraciones cortadas. No corrige nada (máxima del pipeline). Al regenerar un acto, lo marcado vuelve a la Voz (`_avoid`).
- **Métrica** en `voice_metrics.py` para medir antes y después.

---

## 3. Decisiones

| # | Duda | Recomendación |
|---|---|---|
| D1 | ¿Qué quiso decir la hija con «enumera tres cosas»? | Confirmarlo con un ejemplo suyo antes de implementar B: puede ser la prosa (lo medido) o las preguntas con 3 opciones del asistente (que son 3 por diseño). |
| D2 | ¿Prohibir o evitar? | **Evitar**, con alternativa («buscá una señal propia»), y **marcar** lo que igual aparezca. Ningún recurso se borra solo. |
| D3 | ¿Y si el recurso lo eligió el autor? | Manda el autor: lo que está en su idea, sus respuestas o la ficha de la amenaza no se evita ni se marca (mismo criterio que `_motifs_for` de la Voz). |
| D4 | Umbral de las tríadas | Aviso desde la **tercera** del acto (una o dos son naturales en una anécdota); se ajusta con la medición. |
| D5 | Medición | Antes/después con `medir_moldes.py` (solo actos, ~US$ 0,10) para A, y `evaluate_voice.py` (relato corto, ~US$ 0,15) para B; las dos pagas, con aviso de costo y OK. |

---

## 4. SUCCESS CRITERIA

1. En la medición de la 670 repetida (mismos 3 moldes), las menciones de recursos gastados en los hechos bajan **al menos a la mitad**, sin perder hechos concretos.
2. Lo que escribió el autor nunca se marca ni se evita (test).
3. Las enumeraciones de tres en la prosa bajan (meta: menos de 2 cada 1 000 palabras) sin subir las oraciones cortadas ni el diálogo.
4. Los avisos de los dos tipos aparecen en «Los actos» y en el panel del relato, con «Ignorar» (A) y sin corregir nada solo.
5. Snapshots actualizados a propósito; guardianes y tests en verde; dev con el cambio.

## BOUNDARIES

- **Always:** listas en `config/`; detectar y mostrar, nunca corregir solo; respetar lo que escribió el autor.
- **Ask first:** corridas pagas; cambiar el registro de la Voz más allá de una línea de la guía.
- **Never:** reescribir la prosa automáticamente; prohibir algo que el autor eligió.

## OPEN QUESTIONS

- D1: el ejemplo de la hija.
- ¿La lista de recursos gastados la amplía el usuario (como la de clichés) o solo el desarrollo? Propuesta: un YAML editable por quien desarrolla; más adelante, si hace falta, desde la pantalla.

# Spec-770 S2: los actos con las palabras de la autora

**Fecha:** 2026-11-21 · **Perfil:** `openai-sol` (GPT-5.6 Sol) · **Costo:** US$ 0,576 (tope US$ 0,60)

Script: `scripts/research/760/medir_ideas_largas.py`, con la medida nueva `palabras_nuevas`: la parte de las palabras (de 5 letras o más) de los hechos que no aparece en nada de lo que escribió la autora (idea, respuestas, personajes y lugares). Números en `resultados_prompt_nuevo.json` (prompt de S1) y `resultados_ajuste.json` (con el ajuste). No se guarda ningún texto de las autoras.

## Ideas largas (las del «ritual», Corto)

| Idea | Prompt viejo: eco · palabras nuevas | Prompt nuevo: eco · palabras nuevas · hecho más largo | Con el ajuste |
|---|---|---|---|
| 1 (868 palabras) | 67 % · 30 % | **96 %** · 6 % · 657 car. | — |
| 2 (950) | 43 % · 41 % | **94 %** · 8 % · 536 | — |
| 3 (917) | 58 % · 32 % | **85 %** · 5 % · 487 | **93 %** · 7 % · 449 |

- El objetivo era ≥ 70 % y Yael llegaba al 72 % a mano: **se cumple de sobra**.
- Los hechos suman 654 a 703 palabras, menos que la idea. Ningún hecho pasa de 800 caracteres.
- El final queda en el último acto en todas las corridas. Los avisos visibles van de 0 a 2, como antes.

## Ideas cortas («la cabeza del cajón» 279 palabras, «la entidad de la ventana» 284; Corto)

| | En prod (armadas en octubre, antes de GPT-5.6 Sol) | Prompt de S1 | Con el ajuste |
|---|---|---|---|
| Palabras de hechos | 152 · 302 | 537 · 401 | **498 · 384** |
| Palabras nuevas | 58 % · 60 % | 51 % · 42 % | **46 % · 35 %** |

- El prompt de S1 pedía «de 2 a 4 oraciones» por hecho, y con poca idea eso obliga a rellenar. **Ajuste:** el largo de cada hecho sigue a cuánto contó el autor (con poco, una o dos oraciones).
- **No se cumple** «los hechos no suman más palabras que la idea». Un Corto pide 10 u 11 hechos y 280 palabras no alcanzan para llenarlos. Antes también se inventaba (58–60 % de palabras nuevas), pero en hechos cortos, y el resto lo agregaba la Voz al escribir. Ahora lo que agrega la IA es menos en proporción y queda a la vista en «Los actos», donde la autora lo puede cambiar.

## El relato («Culpable», Corto, con los actos del ajuste)

- **1.192 palabras** (316 · 577 · 290). La meta es ~1.050: queda un 13 % arriba. Con los hechos que había reescrito Yael salía entre 1.360 y 1.540.
- El detalle de la autora **llega a la prosa**: «Todas tenían los ojos abiertos. Las bocas se movían…», el agua en los pulmones, los puntos rojos, el Volkswagen escarabajo, «que no se hiciera la víctima», las disculpas.
- Costo del relato: US$ 0,11 (Voz 0,075 · Memoria 0,035).

## Lo que queda abierto

- El ajuste se midió en 1 de las 3 ideas largas, para no pasar el tope de gasto.
- Hay que corregir el criterio de las ideas cortas en la spec (D5).

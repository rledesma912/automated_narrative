# Spec-760 S3: cuánto de una idea larga llega a los actos

**Fecha:** 2026-11-21 · **Perfil:** `openai-sol` (GPT-5.6 Sol) · **Costo:** US$ 0,482 (el tope de la spec era US$ 0,30; el usuario aprobó seguir con la segunda corrida)

Las 3 ideas del «ritual» (868, 950 y 917 palabras), sobre copias de la base de prod. Script: `medir_ideas_largas.py`; números en `resultados_medio.json` y `resultados_corto.json`. No se guarda ningún texto de las autoras.

**Eco** = oraciones de la idea (de más de 6 palabras) que tienen al menos el 40 % de sus palabras de 5 letras o más en los hechos. Es una cuenta gruesa, sirve para comparar.

## Resultados

| Idea | Corto de prod (editado por la autora) | Corto armado por la IA | Media armada por la IA |
|---|---|---|---|
| 1 | 78 % · 739 palabras de hechos | 67 % · 489 | 67 % · 545 |
| 2 | 65 % · 663 | 43 % · 437 | 41 % · 466 |
| 3 | 72 % · 565 | 58 % · 449 | 77 % · 665 |
| **Promedio** | **72 %** | **56 %** | **62 %** |

- El final de la idea quedó en el último acto en los 9 casos menos uno (idea 2, Corto de la IA).
- La IA sigue `hechos_max` (Corto 3 · 5 · 3; Media 5 por acto) y escribe más o menos lo mismo en cualquier largo: **440 a 670 palabras de hechos** para ideas de ~900.
- Tiempo: ~17 s por armado y revisión. Costo: ~US$ 0,07 por historia.

## Qué dice

1. **Lo que se perdía lo recuperaba la autora a mano.** El Corto de prod tiene 16 puntos más de eco que el de la IA, porque la autora volvió a meter su texto en los hechos hasta chocar con el tope de 400 caracteres. La autora (Yael) lo confirmó el 2026-11-21. S2 le saca ese tope.
2. **La Media no hace entrar la idea.** En promedio deja 6 puntos más que el Corto, con mucha variación: igual en la idea 1, peor en la 2 y mejor en la 3. La IA resume igual en los dos largos, y una nota que diga «probá con Media para que entre todo» prometería algo que no pasa.
3. **Lo que decide cuánto de la idea llega es cuánto resume el Planificador**, no el largo. Mejorarlo es cambiar su prompt (o sus topes de hechos), y eso queda fuera de esta spec (§5).

## Notas del método

- Una primera corrida tomó gemma3 local, porque `uv run` no lee el `.env`, y se descartó. Para el perfil real hay que exportar el `.env` (`set -a; . ./.env; set +a`).
- La corrida de la Media pidió además un `verify_outline` aparte, y el Verificador corrió dos veces por historia. `plan_outline` ya revisa, así que el script ya no lo pide.

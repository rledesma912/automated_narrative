# Spikes E4 + E5: fundir el personaje, ronda 2

_2026-11-23. Script: `e4b_fundir.py`. Las salidas y grillas están en `e4b/salidas/` (fuera de git): `grilla_torre.png`, `grilla_mansion.png`, y de cerca `cerca_torre.png` y `cerca_mansion.png` (py | d1 igualado | d2 igualado, s22)._

## Qué cambió respecto de la ronda 1

Seguimos con «Qwen hace una cosa, Python el resto». Se aplicaron los puntos 1 a 4 de la propuesta:

1. **Python prepara la figura antes de componer:** una curva gamma con techo del 80 %, la misma idea que E3c. Se busca la gamma que deja la media de la figura en 1,7 × el brillo del anillo de fondo que la rodea, con un piso de 30/255 para que se lea a 120 px. Además: grano σ 4, borde del alfa difuminado 1,2 px y, si la figura pisa el piso, una sombra de contacto dibujada (elipse negra difuminada, 75 %).
2. **La instrucción a Qwen es acotada:** tocar solo la figura (bordes, sombreado, cómo le cae la luz del lugar) y dejar oscura la sombra de contacto. No cambiar el fondo, no aclarar nada, no agregar niebla, brillo ni luz.
3. **Python iguala la exposición antes de pegar:** lleva la media y el desvío de cada canal de la salida de Qwen a los del original, medidos en el anillo **fuera** de la máscara (4 % del alto).
4. **La máscara es chica y el borde más ancho:** se probaron d1 y d2, con un difuminado de 16 px hacia adentro (en la ronda 1 era de 8).

Se corrieron 2 escenas × 3 semillas: 6 llamadas a Qwen, de ~55 s cada una (la primera tardó 115 s porque cargaba el modelo), con un pico de ~10,9 GB.

## Medidas

| | Ronda 1 | Ronda 2, d1 igualado | Ronda 2, d2 igualado |
|---|---|---|---|
| Diferencia fuera de la máscara | 0,0 | **0,0** (las 24 combinaciones) | 0,0 |
| Halo: brillo agregado en la franja de máscara que no es figura (0–255) | visible a ojo (aura o «sábana») | **0,2–0,5** (criatura) · 0,2–1,1 (nena) | 0,6–1,0 · 0,5–3,1 |
| Cambio de los bordes dentro de la figura | 19–27 | **8,8–9,4** (criatura) · 17,9–18,9 (nena) | 19–21 · 21–22 |

Igualar la exposición siempre baja el halo y el cambio de la figura frente a la salida cruda.

## Lo que se ve

1. **El halo desapareció.** En ninguna de las 12 combinaciones con igualado se ve una forma de máscara alrededor de la figura.
2. **Lo que más cambió fue que la figura se oscurece en Python.** Con eso solo (`py`), la figura ya entra en la luz del lugar. Le falta el «pegado fino»: en la criatura se ve un filete oscuro en el contorno y en la nena el grano queda como textura arriba de la figura.
3. **Qwen acotado + igualado (d1) le suma el acabado:** el contorno se funde, los pies de la criatura se pierden en la oscuridad del piso (hace de sombra de contacto) y la nena gana un modelado de luz más fotográfico, sin el grano encima. No cambia la figura (los bordes cambian la mitad que en la ronda 1).
4. **d2 deja que Qwen redibuje de más:** en la criatura engrosa las piernas, cambia las manos y apaga un poco los ojos, y aparece un filete claro tenue. **d1 es mejor.**
5. **La sombra de contacto dibujada casi no se nota en estos dos fondos** porque el piso ya es negro. Hay que volver a mirarla con un piso más claro (E6, con otras luces).

## Regla propuesta (E5, para `arte.yaml`)

- Antes de componer: gamma con techo del 0,80, media de la figura en 1,7 × la del lugar y piso de 30. Grano σ 4. Sombra de contacto dibujada solo si la figura pisa el piso.
- Máscara: alfa dilatado 1 % del alto, más una elipse de sombra al pie (si pisa el piso). Borde difuminado de 16 px hacia adentro.
- Qwen acotado (el prompt pasaría a `config/miniatura/prompts/fundir.md`) → igualar la exposición en el anillo exterior → pegar.
- La franja «abajo» o «abajo_derecha» se decide en E6, cuando haya luces con lado.

## Checkpoint

Según la spec, quedan por ver **el usuario y Yael**: ¿la figura «está» en el lugar? Se comparan `py`, `d1 igualado` y `d2 igualado` en `cerca_*.png`. Si `py` alcanza para ellos, nos ahorramos un paso de Qwen (~55 s por variación).

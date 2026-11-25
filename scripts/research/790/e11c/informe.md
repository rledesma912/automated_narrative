# E11c — El escenario inventa gente y casas (Spec-790 T6.3 → T3.3)

_2026-11-24_

## Pregunta

En la tanda 3 de «El halloween de Peter» el escenario trae una caseta que no está en el boceto de
Yael. ¿Es contaminación del proceso o una causa en las entradas?

## Contaminación: no

El escenario rehecho desde cero, en otro proceso, con el mismo boceto, prompt y semilla (990851)
que usó el arnés, da la misma imagen: diferencia media 2/255 con `piezas/escenario_crudo.png`
(Qwen) y 1,8/255 con `piezas/escenario.png` (Z-Image). Cambiar una oración del prompt da otra
imagen (8/255).

## Causas

1. **Qwen:** la descripción cruda dice «…que hace que el personaje resalte del fondo» → dibuja una
   persona (3 de 3 semillas con el prompt de hoy; 0 de 3 aclarando que el lugar está vacío).
2. **Z-Image** no ve el boceto: redibuja el 45 % de la imagen de Qwen oscurecida y rellena la
   oscuridad con lo que sugiere el texto. `fotografiar_escenario.md` (de E3c: mansión y torre)
   nombra «weathered wood, old stone, roof tiles» y «no lit windows» → casas y ventanas.
3. **Negaciones:** con cfg 1 «no X» suma X. La lista «do not add buildings, cabins, houses…»
   trajo casas en 2 de 3. Sin nombrar nada ni «nobody», apareció una persona sentada (una mancha
   de planta del boceto).

## Variantes (grillas en `salidas/grilla.png` y `salidas/grilla_negativo.png`)

| Variante | Gente | Casas | Tiempo Z-Image |
|---|---|---|---|
| hoy | 3/3 | 2/3 | ~43 s |
| nuevo (Qwen «lugar vacío» + Z «no agregues casas…») | 0/3 | 2/3 | ~43 s |
| positivo / salvaje (sin nombrar casas ni gente) | 1/3 | 0/3 | ~43 s |
| **llm** (describe lo que hay, en positivo) | **0/3** | **0/3** | ~43 s |
| neg15 / neg20 (negativo real, cfg 1,5 / 2) | 0/3 | 2/3 | ~82 s |

## Propuesta

T3.3: la IA de texto separa personaje, lugar vacío y relación, y escribe los prompts en positivo
(D27, D28). Las plantillas de imagen quedan sin negaciones.

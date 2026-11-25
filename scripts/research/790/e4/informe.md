# Spikes E4 + E5 — Fundir el personaje con la máscara (Spec-790 §10.0, §2.5) — ronda 1

_2026-11-23. Script: `e4_fundir.py`. Compuestos, máscaras, salidas de Qwen y grillas en `e4/salidas/` (fuera de git)._

## Pregunta

Con el personaje (E2) pegado por Python sobre el escenario (E3c), ¿un fundido **solo dentro de una máscara automática** lo integra (luz, niebla, sombra de contacto) sin tocar el resto? ¿Qué máscara (E5)?

## Qué se corrió

- **Composición en Python:** la criatura (`torre_piel`) parada en el piso del bosque de la torre y la nena (`mansion`) de la cintura para arriba frente a la mansión; plano medio (75 % del alto), a la izquierda (x = 0,28).
- **E4 `zona`:** Python recorta la zona del personaje con margen → Qwen-Edit 2511 + Lightning con la instrucción de fundir (oscuridad, niebla, sombra de contacto, sin cambiar la figura ni agregar nada) → Python pega de vuelta **solo dentro de la máscara**, con el borde difuminado hacia adentro.
- **E4 `global` (control):** Qwen-Edit sobre la composición entera, sin máscara.
- **E5:** dilatación del alfa 1 / 2 / 4 % del alto × franja de sombra «abajo» / «abajo_derecha» (elipse al pie), todo en Python sobre la misma salida de `zona`.
- 2 escenas × 3 semillas: 12 llamadas a Qwen, ~74 s cada una (la zona y la imagen entera tardan lo mismo: Qwen escala todo a ~1 MP), ~10,5 GB de pico.

## Medidas

| | Resultado |
|---|---|
| Diferencia fuera de la máscara (`zona`) | **0,0 en las 36 combinaciones**: el fondo queda idéntico, como pide la spec |
| Fondo cambiado por el control `global` | **23–33 / 255** de diferencia media: corre todo el fondo, como en el video de ILM |
| Cambio de los bordes dentro de la figura | 19–22 (criatura) y 24–27 (nena); sube con la dilatación |

## Lo que se ve

1. **El pegado con máscara funciona como mecánica** (el fondo intacto, cero costuras afuera), pero **el fundido de Qwen no sirve así:** Qwen **aclara toda la zona** (le agrega niebla y luz), y al pegarla dentro de la máscara queda un **halo claro con la forma de la máscara** alrededor de la figura. Con d4 es una «sábana» gris; con d1/d2, un aura. En la criatura, la «sombra de contacto» salió como un **círculo de luz** en el piso, no como sombra.
2. **El control `global` es el que más «mete» a la figura en el lugar** (la niebla la envuelve, se oscurece, tiene sombra), pero **cambia toda la escena** (más niebla, más luz, otro tono): es justo lo que la spec quería evitar.
3. **La figura casi no se oscureció** dentro de la máscara: la nena sigue más iluminada que la mansión.
4. **Ninguna máscara (E5) se puede elegir todavía:** el problema no es el tamaño sino que lo editado y el fondo tienen distinta exposición.

## Próxima ronda (propuesta, sin correr)

Todo dentro de la idea «Qwen hace una cosa, Python el resto»:
1. **Igualar la exposición en Python antes de pegar:** llevar el brillo y el contraste de la zona editada a los del original en el anillo fuera de la máscara (media y desvío por canal, o histograma). Saca el halo sin IA.
2. **Instrucción más acotada:** «no cambies el fondo ni su brillo, no agregues niebla ni luz; solo oscurecé la figura para que coincida con el lugar y poné una sombra oscura bajo los pies».
3. **Oscurecer la figura en Python antes de componer** (la misma curva de E3c, más suave): como en E3c, lo que entra manda.
4. Máscara chica (d1–d2) con el borde difuminado más ancho.
5. Si sigue sin alcanzar: la sombra de contacto la dibuja Python (elipse oscura difuminada) y Qwen solo integra los bordes; IC-Light queda como alternativa (preguntar antes, por la licencia).

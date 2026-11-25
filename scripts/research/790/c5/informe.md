# Spike C5: color desaturado o blanco y negro (D23)

_2026-11-23. Script: `c5_color.py`. Hojas en `c5/salidas/` (fuera de git): `hoja_torre.jpg` y `hoja_coneja.jpg`. Cada hoja tiene una fila desaturada, una en blanco y negro y una con las piezas en color tal como salen._

## Pregunta

Si las piezas se generan en color desaturado, ¿la versión desaturada se parece a la de Yael? ¿Y el blanco y negro hecho por Python queda igual de bien que antes?

## Qué se corrió

- **Las piezas, rehechas en color.** Se usó el mismo camino que E1 + E2 + E3c, cambiando solo el pedido de «black and white» por «muted desaturated colors with a cold blue-teal night tint»:
  - personaje con Qwen + BiRefNet: ~115 s;
  - escenario con Qwen → curva de oscuridad → Z-Image 0,45: ~2 min en total.
  - Fueron 2 semillas por caso.
- **Las 4 plantillas de C3**, sin título (D22) y con el fundido.
- **Desaturado por Python:**
  - Se baja la saturación de todo **menos los acentos cálidos**: tono rojo-naranja-amarillo, saturado y brillante (la calabaza, las velas).
  - El tope es la mediana de las 36 miniaturas recientes de Yael: **40/255** de saturación media en lo que no es negro. Medida en ese mismo período: el cuartil bajo da 17 y el alto, 73.
- **Blanco y negro:** escala de grises de la misma imagen.

## Lo que se ve

1. **Qwen y Z-Image no desaturan aunque se lo pidan.** Las piezas salen con un **teal fuerte**: saturación de 97 a 197 sobre 255. Por eso la desaturación tiene que hacerla Python, que deja todas en 39–40 sin excepción.
2. **Hay que cuidar los acentos.** La primera versión bajaba la saturación pareja y la calabaza quedaba gris. Con la máscara de acentos cálidos, **la calabaza y las velas quedan naranjas y el resto apagado**, que es lo que hace Yael en la de Halloween.
3. **El blanco y negro por Python queda como el de antes**, con la ventaja de que se puede cambiar de opción sin volver a generar.
4. **Un prompt se coló.** Para la criatura de la torre, el prompt nombraba de ejemplo «una vela, una calabaza encendida» y **Qwen le agregó una vela y una calabaza** a la imagen del personaje. El recorte no las metió en la composición, pero el prompt ya quedó corregido: ahora dice «solo una luz que ya esté en la descripción conserva el color cálido». Falta volver a correrlo.
5. **El escenario de la torre trajo una cabaña iluminada** abajo, que no estaba en el boceto. Es lo mismo que pasaba en E3 con la luz: Z-Image a 0,45 inventa luces cuando parte de una imagen en color.
6. **Sigue faltando la luz (E6).** En color y en blanco y negro, las nuestras siguen siendo oscuras de punta a punta. Las de Yael tienen una zona clara detrás de la figura.

## Propuesta

- **D23 queda así:** se genera en color, Python desatura hasta 40/255 respetando los acentos cálidos, y el blanco y negro sale de esa misma imagen. Son dos versiones sin costo extra de GPU.
- El tope de 40 y el tamaño de los acentos van a `arte.yaml` y se ajustan con Yael.

## Checkpoint con Yael

¿El desaturado con la calabaza encendida es el color que ella busca? ¿Le sirve el blanco y negro?

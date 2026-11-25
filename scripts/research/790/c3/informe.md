# Spike C3: el compositor (las 4 plantillas)

_2026-11-23. Script: `c3_compositor.py`. Hojas en `c3/salidas/` (fuera de git): `hoja_torre.jpg` y `hoja_coneja.jpg`, con la real de Yael, las 4 opciones y todas a 120 px._

## Pregunta

Con las piezas ya armadas (el escenario de E3c y el personaje de E2), ¿las 4 plantillas de Yael (D21) dan 4 miniaturas distintas que parezcan del canal, con el título en una esquina sin tapar la escena ni la cara?

## Qué se corrió (todo por Python, salvo dos llamadas a la GPU)

1. **Lo importante del escenario:** BiRefNet sobre el escenario, una llamada por caso. Marca la torre (6 % del cuadro) y la mansión (18 %).
2. **Por plantilla:**
   - se ubica la figura: `A_der`/`A_izq` al 92 % del alto; `C_primer_plano` con el 70 % de arriba de la figura, cortada por el borde de abajo; `B_lugar` al 50 %, en el plano medio;
   - si la figura tapa lo importante, **se espeja el escenario**: con eso la torre y la mansión quedan siempre a la vista;
   - se oscurece la figura y se funde (E4 ronda 2: Qwen en la zona, igualar la exposición, pegar con d1).
3. **El título:** las reglas de C2 más la bajada chica, en la **esquina** que menos tapa. El costo suma la cara (peso 4: el 22 % de arriba de la figura), la figura (1) y lo importante del escenario (1,5). La esquina de la duración está prohibida: ni un píxel del título puede caer ahí. Del lado de la figura se alinea a la derecha.

**Tiempos:** 8 fundidos de ~80 s cada uno (el primero, 110 s, cargando el modelo). Por tanda de 4: **~5 min y medio solo de fundido.**

## Lo que funciona

- **Salen 4 composiciones claramente distintas** por historia, y se distinguen a 120 px.
- **El título va siempre a una esquina** y nunca tapa la cara, la figura ni la torre o la mansión. Ninguno cayó en la esquina de la duración (en la primera pasada pasaba, por un chequeo flojo; quedó corregido).
- **El espejo del escenario** resuelve que la figura no tape lo importante, sin IA.
- **El número solo arriba**, cuando el título tiene 2 líneas o menos, se parece a la #5 de Yael.

## Lo que falta para parecerse a Yael

1. **La luz es lo que más falta.** Las de Yael tienen una zona clara detrás (niebla iluminada, luna, una ventana), con la figura recortada en oscuro contra eso, y un acento cálido encendido (la calabaza, una vela, los ojos). Las nuestras son oscuras de punta a punta: a 120 px quedan como una mancha, y las de ella se destacan. **Esto es E6** (la luz de cada opción), que ahora pasa a ser lo más importante.
2. **El título es más chico y más fino:** el de ella ocupa ~45 % del ancho, con contorno negro y una letra más pesada; el nuestro, ~35 %, con sombra difusa. Se arregla en Python: tamaño mínimo por plantilla y contorno negro.
3. **El primer plano de la criatura** casi no se distingue de `A_der`: es flaca, y con el 70 % de arriba sigue siendo un cuerpo entero. El recorte tendría que depender de la figura (cabeza y torso: ~45 % en una figura alta y flaca, ~70 % en una de cintura para arriba).
4. **El fundido de Qwen casi no se nota a este tamaño.** Como cuesta 80 s por opción, conviene medir en C4 o E6 si una opción solo con Python (`py` de E4) alcanza en tamaño miniatura.

## Checkpoint con Yael

¿Las 4 se reconocen como «sus» composiciones (el lugar de la figura y el título en la esquina)? Lo de la luz y el título ya está anotado arriba como pendiente.

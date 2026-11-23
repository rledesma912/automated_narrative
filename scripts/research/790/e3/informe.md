# Spike E3 — Ilustrar el escenario (Spec-790 §10.0)

_2026-11-23. Script: `e3_escenario.py` (reusa los grafos de E1). Imágenes, grillas y `medidas.json` en `e3/salidas/` (fuera de git)._

## Pregunta

¿El boceto del escenario se vuelve un fondo 16:9 con el arte del canal, reconocible como el dibujo de Yael? ¿Hace falta agrandar?

## Insumos

Dos bocetos de escenario de Yael (JPG de WhatsApp, 1280 × 720, fondo gris):
- `torre_escenario.png`: un bosque de pinos visto desde arriba de las copas, con una torre de vigilancia a la derecha y montañas detrás;
- `mansion_escenario.png`: una mansión victoriana de frente, con escalera, dos velas y dos calabazas talladas, un camino que serpentea, árboles a la izquierda y álamos a la derecha.

## Variantes (2 bocetos × 3 semillas)

| Variante | Qué es |
|---|---|
| `qwen_b` | La ganadora de E1 (Qwen-Edit 2511 + Lightning, arte completo, ahora con los sentidos y «nobody in the scene»), a la resolución que elige `FluxKontextImageScale` (~1392 × 752) |
| `qwen_b_1024` | ídem a 1024 × 576, agrandada a 1280 × 720 con Lanczos en Python (el único agrandador instalado es RealESRGAN para anime: no sirve para foto) |
| `zcn_lite_90` | Z-Image Turbo + Fun ControlNet Union lite, fuerza 0,9, el boceto como *scribble* (en escenarios la silueta podía pesar más que el detalle) |

## Medidas (RTX 3060, GPU libre)

| Variante | Segundos (frío → caliente) | VRAM pico |
|---|---|---|
| `qwen_b` | 68–110 → **~57** | 9,4–11,0 GB |
| `qwen_b_1024` | 66 → ~47 | 10,1–10,9 GB |
| `zcn_lite_90` | 52–62 → ~49 | 9,6–11,2 GB |

## Lo que se ve

1. **`qwen_b` a su resolución es el más fiel al boceto.** La casa y la torre en el mismo lugar y del mismo tamaño, el camino que serpentea, las velas y las calabazas al pie de la escalera, los árboles de cada lado, las montañas. El arte se ve: noche, luna, niebla baja, grano, viñeta.
2. **A 1024 × 576 Qwen cambia el encuadre:** corre y achica la mansión, y a la torre le suma cielo y montañas. Ahorra ~10 s, pero se aleja del boceto. **No hace falta agrandar:** la salida nativa ya pasa los 1280 × 720 de la miniatura.
3. **El ControlNet lite** sigue el trazado general con una luz más de foto (ventanas encendidas, luna), pero pierde detalles (calabazas chicas, la casa cambia de forma). Igual que en E1: silueta sí, detalle no. **Queda descartado** y se puede borrar de disco (8,7 GB entre lite y completo) si el usuario quiere.
4. **El bosque queda más «ilustrado» que la mansión** (pinos muy recortados, como siluetas). Se ajusta en E4/E6, al fundir y reiluminar, no acá.

## Propuesta

- **Ganador: `qwen_b` a su resolución**, ~57 s. Usa **el mismo grafo que el personaje**: el workflow exportado pasa a llamarse `config/miniatura/workflows/boceto_a_imagen/` y lo usan las dos recetas (`ilustrar_personaje`, `ilustrar_escenario`), que solo cambian el prompt.
- Sin paso `agrandar` para el escenario.
- Siguiente: E2 (recortar el personaje) y después E4 + E5 (fundir con la máscara).

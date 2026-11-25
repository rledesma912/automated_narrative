# E11 — La figura parece un render, no una foto (Spec-790 T6.3)

_2026-11-24_

## Pregunta

El personaje de `qwen_b` sale como render 3D de videojuego. ¿Se lo puede llevar a foto sin perder
la forma no humana del boceto? (Riesgo marcado por el usuario: que lo humanice.)

## Variantes

Boceto de «El halloween de Peter» (descripción de Yael) y la criatura alta de E1, semillas 11/22/33,
fondo gris como la pieza del arnés.

- `base`: `qwen_b` como hoy.
- `foto_35/45/55`: `base` → Z-Image img2img (prompt de foto con flash de una criatura real).
- `qwen_foto`: el prompt de Qwen en clave foto con flash.
- `qwen_foto_z45`: `qwen_foto` → Z-Image 0,45.

Grillas: `e11/salidas/grilla_peter.png`, `e11/salidas/grilla_torre.png`.

## Medidas

Qwen ~57 s (≈ 80 s en frío), Z-Image ~43 s, VRAM pico ~10,6 GB. Un paso de Z-Image sobre el
personaje sumaría ~45 s a la tanda (~11 min).

## Lo que se ve

- **No lo humaniza.** En ninguna variante aparece una cara o un cuerpo humano.
- **A 0,55 lo animaliza y pierde el boceto:** Peter pasa a tener hocico de perro y pierde la
  sonrisa enorme de dientes; la criatura alta se vuelve esqueleto (la trampa de material de E1).
  0,55 queda fuera.
- **0,35–0,45 conservan la forma** (orejas, sonrisa, nariz picuda, garras, proporciones).
- **Pero ninguna parece foto de cámara trampa.** Todas cambian de «render de videojuego» a
  **«foto de una figura de colección o un muñeco de látex»**: piel con textura, ojos amarillos de
  plástico, luz de estudio, fondo limpio. `qwen_foto` y `qwen_foto_z45` son las de mejor material
  (piel arrugada, húmeda, manchada), con la forma intacta.
- La causa probable: **una criatura sola sobre fondo gris de estudio** el modelo la lee como foto
  de producto. Lo que hace «real» a las del canal está en la relación con el lugar: oscuridad,
  flash que cae en la niebla, grano, la figura a medio ver.

## Propuesta

1. Adoptar el prompt de `qwen_foto` (mejor material, mismo tiempo, sin paso extra) — a confirmar con Yael.
2. **E11b:** el paso de foto, pero sobre la **composición** (figura ya pegada en el escenario
   oscuro), no sobre la pieza sola: Z-Image img2img a 0,25 / 0,35 sobre la imagen compuesta sin
   color, con prompt de cámara trampa. Riesgo: cambia algo del escenario (D15 lo dejaba intacto);
   se mide.
3. La LoRA (Anything2Real / Anything_to_Real_Characters_2511, Apache-2.0 según su ficha) queda
   para después: está entrenada para pasar personajes a **personas** reales, justo el riesgo de
   humanizar, y el problema de «foto de producto» seguiría.

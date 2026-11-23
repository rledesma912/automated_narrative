# Spike E1 — Ilustrar el personaje (Spec-790 §10.0)

_2026-11-22. Script: `e1_personaje.py`. Imágenes, grillas y `medidas.json` en `e1/salidas/` (fuera de git)._

## Pregunta

¿Un boceto de Yael se vuelve un personaje terminado, con el arte del canal, **reconocible** como su dibujo y sobre fondo liso (para recortarlo en E2)?

## Insumos

Dos bocetos de personaje de Yael, exportados de SAI2 como **JPG de WhatsApp, 1280 × 720, líneas negras sobre fondo gris, sin transparencia**:
- `torre_personaje.png`: una criatura altísima de brazos larguísimos y dedos largos;
- `mansion_personaje.png`: una nena con máscara de conejo rota, que sostiene una calabaza tallada.

La descripción en inglés simula la que propondría la IA desde el relato (paso 1 del flujo). El arte sale del borrador de `arte.yaml` (§2.2).

## Variantes (2 bocetos × 3 semillas: 11, 22, 33)

| Variante | Qué es | Modelo (licencia) |
|---|---|---|
| `qwen_a` | Qwen-Edit 2511 + Lightning 4 pasos, instrucción corta | instalado (Apache-2.0) |
| `qwen_b` | ídem, instrucción con el arte completo (estilo, luz, textura) | ídem |
| `zimg_75` / `zimg_90` | Z-Image Turbo img2img desde el boceto, denoise 0,75 / 0,90 | instalado (Apache-2.0) |
| `ztxt` | Z-Image Turbo solo desde el texto (control: sin boceto) | ídem |
| `zcn_lite_70/90`, `zcn_full_70/90` | Z-Image Turbo + **Fun ControlNet Union 2.1 (2602, 8 pasos)**, lite (2 GB) y completo (6,7 GB), fuerza 0,7 / 0,9. El boceto pasa a *scribble* en Python (líneas blancas sobre negro, el fondo = la mediana) | **bajado con OK** (Apache-2.0), `models/model_patches/` |
| `torre_piel` × (`qwen_a`, `qwen_b`, `zcn_*_90`) | La criatura con la descripción **sin «skeletal» ni «visible ribs»** («grey skin stretched tight over the ribs… a living creature, not a skeleton») | — |

## Medidas (RTX 3060 12 GB, GPU sin audiogen generando)

| Variante | Segundos (frío → caliente) | VRAM pico (toda la placa) |
|---|---|---|
| Qwen-Edit 2511 | 77–119 → **~56** | 9,2–10,5 GB |
| Z-Image texto | 26 → 25 | 9,0–10,9 GB |
| Z-Image img2img (8 pasos) | 61 → 42 | 9,0–11,1 GB |
| Z-Image + ControlNet lite | 50–62 → **~48** | 9,7–11,3 GB |
| Z-Image + ControlNet completo | 65–78 → **~63** | **~11,0 GB siempre** (al límite) |

## Lo que se ve

1. **Qwen-Edit es el único que respeta el boceto de Yael.** Pose, proporciones, ubicación en el cuadro y los **detalles del dibujo**: la estrella y las grietas de la máscara, el mechón, las mangas abullonadas, la calabaza con su sonrisa, los dedos larguísimos y los pies largos de la criatura. En las 12 imágenes por boceto se reconoce el dibujo.
2. **Z-Image solo (texto o img2img) no sirve para esto.** El boceto es muy tenue para el img2img: hace una nena genérica y un **esqueleto de museo** de proporciones normales. Como control confirma que el boceto aporta: sin él se pierde todo lo de Yael.
3. **El ControlNet de Z-Image sigue la silueta pero pierde los detalles.** Los brazos largos y la postura quedan; la estrella, las grietas y los dedos no. Se ve **más a foto de verdad** que Qwen, pero con fondos oscuros con textura (peor para recortar). Entre fuerza 0,7 y 0,9 casi no hay diferencia; entre lite y completo tampoco, y el completo está al límite de la VRAM. **No pasa.**
4. **`qwen_b` (con el arte completo) le gana a `qwen_a`:** más luz dura, grano, viñeta y suciedad; más cerca de las miniaturas del canal. `qwen_a` queda más limpio, como de estudio.
5. **La descripción manda en el material:** con «skeletal / visible ribs», Qwen hace una criatura de huesos expuestos, con pinta de render. Con `torre_piel` sale una criatura de piel gris tirante sobre las costillas, viva, que se parece más a lo que dibujó Yael. **La descripción que propone la IA tiene que evitar palabras que cambian el material** (esqueleto, metal, piedra…) salvo que el relato lo diga.
6. **Lo que todavía no tiene ninguna:** el aspecto de **foto nocturna real**. Qwen se ve a veces como render 3D o foto de estudio. Esto se resuelve más adelante: al fundir con el escenario (E4) y en la reiluminación (E6), no acá. E1 solo tiene que dar la figura fiel y recortable.
7. **El fondo liso sale bien en Qwen** (gris parejo con viñeta en `qwen_b`, con una sombra en el piso). La viñeta y la sombra son para mirar en E2.

## Ajustes a la spec

- **T7 (subida del boceto):** Yael exporta con fondo (gris), sin transparencia. La subida acepta PNG o JPG **con o sin fondo**, no solo PNG RGBA. Qwen-Edit no necesita transparencia.
- **Prompt de `miniatura` (paso 1):** la descripción del personaje evita palabras que cambian el material, salvo que salgan del relato.

## Propuesta (para el checkpoint con el usuario y Yael)

- **Ganador: `qwen_b`** (Qwen-Edit 2511 + Lightning, instrucción con el arte completo), ~56 s en caliente, ~10,5 GB de pico.
- La descripción como en `torre_piel`.
- Descartados: Z-Image texto / img2img y el ControlNet de Z-Image (lite y completo). El ControlNet queda en disco por si sirve en E3 (escenarios: ahí la silueta importa más que el detalle).
- **No hace falta bajar** xinsir Union SDXL ni Qwen-Image + InstantX: Qwen-Edit ya da lo que pide el criterio.
- Tras el OK: exportar el grafo en formato API con su `params.yaml` y README (T10) y seguir con E2 (recortar) y E3 (escenario).

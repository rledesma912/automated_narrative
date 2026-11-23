# Spike E2 — Recortar el personaje (Spec-790 §10.0)

_2026-11-23. Script: `e2_recortar.py`. Máscaras, recortes y grillas en `e2/salidas/` (fuera de git)._

## Pregunta

¿El recorte del personaje de E1 sale limpio: dedos larguísimos, orejas, pelo, bordes oscuros sobre el gris del fondo liso?

## Variantes (6 personajes: `torre_piel` y `mansion`, `qwen_b`, semillas 11, 22 y 33)

| Variante | Qué hace |
|---|---|
| **a** | BiRefNet (nodos propios de ComfyUI, `birefnet.safetensors`, MIT): la máscara tal cual |
| b | BiRefNet + refinado en Python, solo con Pillow: apertura morfológica (saca manchitas sueltas), borde 2 px adentro y difuminado de 1,2 px |

Cada recorte se miró sobre negro, sobre blanco y sobre un escenario oscuro de E3c (el uso real), con el borde a 100 % y a 200 %, y la miniatura a 120 px. Qwen-Image-Layered (c) no se probó: el criterio era probarlo solo si (a) y (b) fallaban.

## Medidas

BiRefNet: **~0,8 s** por recorte (1,9 s en frío), **~1,9 GB** de VRAM. Lo más barato de toda la cadena.

## Lo que se ve

1. **BiRefNet solo sale limpio en los 6.** Los dedos de la criatura salen separados uno por uno, con las puntas; las orejas de la máscara, enteras y con sus grietas; el pelo de la nena, con su borde. **La sombra del piso y la viñeta quedan afuera**, y sobre blanco no se ve halo gris.
2. **El refinado empeora:** el borde 2 px adentro **corta la punta de los dedos finos**, y el difuminado ablanda todo el contorno. No hace falta: el fondo liso de E1 ya le deja a BiRefNet un borde fácil.
3. Sobre el escenario oscuro de E3c, el recorte pegado se ve «pegado»: más iluminado que la escena y sin sombra de contacto. Eso lo resuelven E4/E5 (fundir con la máscara) y E6 (reiluminar), no el recorte.
4. `numpy` y `scipy` no están en el venv del proyecto: el refinado se hizo solo con Pillow para no sumar dependencias (Pillow ya está).

## Propuesta

- **Ganador: BiRefNet solo**, sin refinar. Workflow `config/miniatura/workflows/recortar/` (formato API + `params.yaml` + README). Python arma el PNG con alfa.
- Qwen-Image-Layered no hace falta: no se baja.
- Siguiente: E4 + E5 (fundir el personaje en el escenario con la máscara automática).

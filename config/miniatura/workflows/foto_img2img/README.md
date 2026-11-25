# foto_img2img

El escenario de Qwen (fiel al boceto pero «ilustrado») → **foto real de noche, oscura y con niebla**, cambiando poco. Lo usa la receta `fotografiar_escenario`.

- **Sale de los spikes E3b y E3c** (`scripts/research/790/e3b/informe.md`), variante `previo_45`. Elegido por el usuario y Yael el 2026-11-23.
- **Va después de dos pasos:** `ilustrar_escenario` (workflow `boceto_a_imagen`, Qwen: qué va y dónde) y la **curva de oscuridad en Python** (gamma 1,6, techo 75 %, sin IA). Al 45 %, Z-Image sigue el brillo de la imagen que recibe: por eso se oscurece antes y no en el prompt.
- **Modelo:** `checkpoints/z-image-turbo-fp8-aio.safetensors` (Z-Image Turbo, Apache-2.0).
- **Parámetros:** 8 pasos, cfg 1, `dpmpp_sde` + `beta`, shift 3, denoise 0,45. Salida 1344 × 768.
- **Medido en la RTX 3060:** ~44 s ya cargado, ~9–10,8 GB de VRAM de pico.
- **El prompt:** `config/miniatura/prompts/fotografiar_escenario.md` (D17): foto real, muy oscura, niebla espesa, sin luces encendidas ni objetos de más, materiales reales.
- **Reexportar:** abrir `workflow.api.json` en ComfyUI, cambiar, «Export (API)» y verificar que los nodos de `params.yaml` sigan existiendo (lo cuida el test de S2).

## También el personaje (E11, 2026-11-24)

El personaje de Qwen respeta el boceto pero sale como render de videojuego. El arnés lo pasa por este mismo grafo con `prompts/fotografiar_personaje.md` (foto con flash, «no es humano: conserva su forma») y `arte.yaml` → `personaje.cambio_foto` (0,50), antes de recortarlo. ~45 s más por personaje (se reusa mientras no cambien el boceto ni la descripción). Informe en `scripts/research/790/e11/informe.md`.

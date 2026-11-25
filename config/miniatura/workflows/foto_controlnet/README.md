# foto_controlnet

El escenario de Qwen (fiel al boceto pero «de dibujo») → **foto real de noche**, reinterpretando todo y conservando el lugar. Lo usa el paso «fotografiar escenario» desde T6.6 (antes, `foto_img2img` a 0,45).

- **Sale del spike E11i** (`scripts/research/790/e11i_controlnet_con_libertad.py`, variante `cn75_f60`, 2026-11-25). A 0,45 sin guía, Z-Image conservaba las hojas planas que copia Qwen (tanda 5 de Peter); con más libertad sin guía perdía la composición (E11f). Con el ControlNet fijando las líneas del boceto, Z-Image puede cambiar mucho (0,75) y el lugar sigue siendo el de Yael.
- **Entradas:** el escenario oscurecido (curva de Python, como antes) y el **boceto como scribble**: líneas blancas sobre negro, lo arma Python (`imagen.scribble`).
- **Modelos:** `checkpoints/z-image-turbo-fp8-aio.safetensors` y `model_patches/Z-Image-Turbo-Fun-Controlnet-Union-2.1-2602-8steps.safetensors` (Apache-2.0).
- **Parámetros:** 8 pasos, cfg 1, `dpmpp_sde` + `beta`, shift 3, denoise 0,75, fuerza del ControlNet 0,6 (a 0,8 vuelven las manchas del boceto). Salida 1344 × 768.
- **Medido en la RTX 3060:** ~65 s por escenario (unos 20 s más que `foto_img2img`).
- **Reexportar:** abrir `workflow.api.json` en ComfyUI, cambiar, «Export (API)» y verificar que los nodos de `params.yaml` sigan existiendo.

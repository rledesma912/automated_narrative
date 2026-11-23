# boceto_a_imagen

Un boceto de Yael → la imagen terminada con el arte del canal. Lo usan dos recetas, que solo cambian el prompt:

- **`ilustrar_personaje`:** el personaje **sobre fondo liso** (para recortarlo después). Spike E1, variante `qwen_b`.
- **`ilustrar_escenario`:** el escenario 16:9, vacío (el personaje se suma después). Spike E3, variante `qwen_b` a su resolución.

Elegido por el usuario y Yael el 2026-11-23 (E1). Informes en `scripts/research/790/e1/informe.md` y `e3/informe.md`.

- **Plantilla de origen:** Qwen-Image-Edit 2511 de Comfy-Org (la misma que usa `cw2d-art`), con la LoRA Lightning de 4 pasos.
- **Modelos** (todos Apache-2.0):
  - `diffusion_models/qwen_image_edit_2511_int8_convrot.safetensors`;
  - `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors`;
  - `vae/qwen_image_vae.safetensors`;
  - `loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors`.
- **Medido en la RTX 3060:** ~56 s ya cargado (70–120 s en frío), 9,4–11 GB de VRAM de pico. Salida ~1392 × 752 (la elige `FluxKontextImageScale` según el boceto): **no hace falta agrandar** para la miniatura de 1280 × 720. Forzar 1024 × 576 cambia el encuadre (E3).
- **El prompt** (en inglés):
  - personaje: «Turn this rough pencil sketch into a finished image of the same character, keeping exactly the pose, the proportions, the silhouette and the position in the frame of the sketch.» + la descripción + estilo, luz y textura de `arte.yaml` + el fondo liso;
  - escenario: «Turn this rough pencil sketch into a finished image of the same place, keeping exactly the composition, the perspective, the layout and the position and size of every element of the sketch.» + la descripción + el arte completo (con los sentidos) + «Nobody in the scene».
  - La descripción **no usa palabras que cambian el material** (esqueleto, metal…) salvo que vengan del relato (E1, `torre_piel`).
- **El boceto** puede venir con fondo (Yael exporta de SAI2 con fondo gris).
- **Reexportar:** abrir `workflow.api.json` en ComfyUI, cambiar, «Export (API)» y verificar que los nodos de `params.yaml` sigan existiendo (lo cuida el test de S2).

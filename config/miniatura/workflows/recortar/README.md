# recortar

El personaje sobre fondo liso (de `ilustrar_personaje`) → **su máscara** (blanco = figura). Python arma el PNG con alfa (la máscara como canal alfa del original), sin refinar.

- **Sale del spike E2** (`scripts/research/790/e2/informe.md`): BiRefNet solo. El refinado en Python (achicar el borde y difuminar) **empeora**: corta la punta de los dedos finos y ablanda el borde.
- **Modelo:** `background_removal/birefnet.safetensors` (BiRefNet, MIT), con los nodos propios de ComfyUI (`LoadBackgroundRemovalModel` + `RemoveBackground`).
- **Medido en la RTX 3060:** ~0,8 s (1,9 s en frío), ~1,9 GB de VRAM.
- **Reexportar:** abrir `workflow.api.json` en ComfyUI, cambiar, «Export (API)» y verificar que los nodos de `params.yaml` sigan existiendo (lo cuida el test de S2).

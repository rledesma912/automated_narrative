# Spike E3b — Escenarios como foto real (Spec-790 §10.0, pedido de Yael)

_2026-11-23. Script: `e3b_realista.py`. Imágenes, grillas y `medidas.json` en `e3b/salidas/` (fuera de git)._

## Pregunta

Los escenarios de E3 salían «cartoon lúgubre», tipo Coraline. Yael quiere que el boceto sea solo la guía de qué va y dónde, y que la imagen sea **una foto real**: una mansión real, pinos reales, una caseta real, sin pinta de render. ¿Qué camino lo logra sin perder el boceto? (Solo escenarios y fondos: el personaje de E1 queda como está.)

## Variantes (2 bocetos × 3 semillas; parten de las salidas `qwen_b` de E3)

| Variante | Qué hace | Segundos (caliente) |
|---|---|---|
| `qwen_foto` | Qwen-Edit en un paso desde el boceto, prompt de foto real (cámara, lente, materiales) sin las palabras que estilizan | ~58 |
| `qwen_x2` | `qwen_b` → segunda pasada de Qwen-Edit: «convertí esta imagen en una foto real» | ~75 |
| **`zimg_45`** | `qwen_b` → **Z-Image Turbo img2img, denoise 0,45**, prompt de foto real | **~44** |
| `zimg_60` | ídem, denoise 0,60 | ~44 |
| `zcn_gris` | `qwen_b` como control «gray» del Fun ControlNet lite de Z-Image, fuerza 0,6 | ~51 |

VRAM pico: 9–11,2 GB en todas.

## Lo que se ve

1. **Qwen-Edit no sale del estilo del boceto.** Con el prompt de foto (`qwen_foto`) los pinos siguen como helechos dibujados. La segunda pasada (`qwen_x2`) empeora: contraste quemado, puntos blancos y manchas. Pedirle «foto real» a Qwen no alcanza: conserva el estilo de la imagen que recibe.
2. **El control «gray» copia demasiado** (`zcn_gris`): repite las texturas de Qwen, incluidos los pinos dibujados. La mansión mejora un poco, el bosque no.
3. **`zimg_45` lo resuelve:** Qwen pone **qué va y dónde** (fiel al boceto) y Z-Image le pone **materiales reales** cambiando poco. La mansión es de piedra y madera gastada, con balcones de hierro; los pinos tienen agujas, ramas y corteza; la torre es de madera con su escalera; niebla y luna de foto nocturna. El encuadre de Yael se conserva.
4. **`zimg_60` es todavía más real, pero se aleja del boceto:** inventa una cabaña y una base de piedra en la torre, y cambia la forma de la casa.
5. **Lo que todavía hace `zimg_45`:** suma objetos chicos que no estaban (calabazas de más, un banco, un cartel, unas piedras). Se puede bajar con «nothing else» en el prompt, o probar 0,40. Es un detalle, no cambia la escena.

## Propuesta (para el checkpoint con el usuario y Yael)

- **Escenario en dos pasos** (D15, una tarea por llamada):
  1. `ilustrar_escenario`: Qwen-Edit desde el boceto, como en E3 (qué va y dónde);
  2. **`fotografiar_escenario`** (receta nueva): Z-Image Turbo img2img, denoise 0,45, prompt de foto real (materiales reales, «not an illustration, not a 3D render»).
- Tiempo del escenario: ~57 s + ~44 s ≈ **1 min 40 s** en caliente.
- Plantillas (D17): `prompts/escenario.md` (el de E3) y `prompts/fotografiar_escenario.md` (el de foto real de este set).
- Descartados: `qwen_foto`, `qwen_x2`, `zcn_gris`, `zimg_60`. El ControlNet de Z-Image ya no hace falta en ningún paso.
- El personaje sigue con `qwen_b` (E1), sin el paso de foto.

## E3c — Menos luces, más oscuro y con niebla (`e3c_oscuro.py`, 2026-11-23)

El usuario y Yael aprobaron `zimg_45`, pero piden **menos luces, lugares más oscuros y con niebla**. Cada variante parte de `qwen_b` (E3), con 2 bocetos × 3 semillas, ~44 s cada una:

| Variante | Qué hace | Resultado |
|---|---|---|
| `oscuro_45` | Prompt de noche muy oscura, niebla espesa, sin luces ni objetos de más; descripción sin «lit». Z-Image 0,45 | Casi igual a E3b: **al 45 % manda el brillo de la imagen de Qwen**, no el prompt |
| `oscuro_55` | ídem, 0,55 | Un poco más oscuro, pero se aleja del boceto (cambia la casa, mete abedules) |
| **`previo_45`** | **Python oscurece la imagen de Qwen antes** (curva: gamma 1,6, techo 75 %) + prompt oscuro, Z-Image 0,45 | **Oscuro, con niebla que se traga el fondo, la luna velada y casi sin luces**; sigue fiel al boceto y real. Quedan las velas y las ventanas de la cabina, chicas |
| `oscuro_45_curva` | `oscuro_45` + curva de oscuridad en Python después (sin GPU) | Más oscuro, pero las luces siguen igual de marcadas: la curva baja todo parejo, no saca luces |

**Lo que se ve:** la luz se decide antes, en la imagen que recibe Z-Image. Oscurecer en Python **antes** del paso de foto funciona; pedirlo en el prompt o oscurecer después, no. Las luces que quedan vienen de Qwen (velas encendidas y luz en la cabina, que el boceto y la descripción piden).

**Propuesta:** `ilustrar_escenario` (Qwen) → **curva de oscuridad en Python** → `fotografiar_escenario` (Z-Image 0,45, prompt oscuro). Si quedan luces de más, el siguiente ajuste es la descripción del paso de Qwen (velas apagadas, cabina sin luz), no el paso de foto.

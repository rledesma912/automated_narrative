# SPEC-790: Miniaturas para YouTube: de los bocetos de Yael a 4 miniaturas para elegir

**Fecha:** 2026-11-22 (tercera versión, con el flujo que armaron el usuario y Yael)
**Tipo:** SDD (super spec): investigación, dominio nuevo, orquestación de ComfyUI y sección nueva del sitio
**Estado:** IMPLEMENT (OK el 2026-11-22). Hechos: S0a (T0.1–T0.3) y los spikes E0, E1 y E3 (con E3b/E3c). E2 ✅ (OK al recorte). E4/E5 ✅ (ronda 2, OK del usuario y Yael). **Nuevo (2026-11-23): el compositor que aprende de las miniaturas recientes de Yael** (§1.8, §2.11, spikes C1–C4); en curso C1. `arte.yaml` borrador en §2.2 (T0.A), con Q11–Q14 respondidas.
**Rama propuesta:** `feat/spec-790-miniaturas` (desde `development`)
**Extiende:** Spec-610 (del relato al video), Spec-450 (la amenaza), Spec-460 (jobs y bus), Spec-510 (tiempo estimado), Spec-620 (textos en `config/`), Spec-540 (dev siempre publicado).
**Antecedente fuera del repo:** `cw2d-art` (pipeline de arte del juego con ComfyUI, archivado el 2026-11-15 en el commit `55c08f9`).

---

## ASSUMPTIONS

1. **Quién la usa.** Yael, que lee los relatos y arma las miniaturas del canal.
   - Dibuja con una **XP-Pen** en **Paint Tool SAI 2** y exporta PNG. También tiene Krita.
   - Trabaja **desde otra PC**: sube sus bocetos con un campo del formulario.
   - La pantalla sigue el tono de la Spec-580 (coloquial, sin jerga).
2. **No es un editor de imágenes.** Es un **flujo de carga**, como el del relato: campos y bocetos → el sistema corre solo → **4 miniaturas** para que Yael elija. Componentes HTML del sitio, sin lienzo, capas visibles ni arrastrar.
3. **Las capas existen, por detrás.** El personaje armado desde su boceto, el escenario armado desde su boceto y el título generado por código se componen en un flujo final. Yael tiene en la cabeza que su boceto del personaje **se suma después** a la composición general.
4. **La figura principal es la entidad/monstruo o el protagonista**: la IA propone cuál y Yael lo confirma o lo cambia. **La calabaza no aparece**, salvo que se pida (hay una imagen de referencia para ese caso).
5. **El arte es uno solo para todo el canal:** un YAML que define el estilo, la luz, la paleta y los sentidos, y que es la parte del prompt común a **todas** las miniaturas. Se arma a partir de un lote de 5 miniaturas actuales que pasa el usuario.
6. **El título lo genera el código** con la fuente configurada (gratis, la pasa el usuario), nunca la IA.
7. **ComfyUI corre en la PC del usuario** (host, `:8188`) y comparte la RTX 3060 de 12 GB con audiogen. **Se turnan:** este flujo no usa audio, pero no puede correr mientras audiogen ocupa la GPU (§2.6).
8. **El canal está por monetizar** (1 000 suscriptores): solo modelos con licencia que permita uso comercial (D9).
9. **La IA nunca corre sola** (CLAUDE.md): cada paso con IA es un comando de Yael, corre como job, con el modal y el tiempo estimado.

## OBJECTIVE

Que Yael elija la figura principal, ajuste su descripción, suba el boceto de ese personaje y el del escenario, escriba el título, y reciba **4 miniaturas terminadas** con el arte del canal, para elegir la que lleva a YouTube.

**Éxito:**
- Sin abrir ComfyUI ni un editor, Yael obtiene 4 miniaturas de 1280 × 720 (JPG de menos de 2 MB) para un episodio real y descarga la que elige.
- En las 4 se reconocen **su personaje y su escenario**: los bocetos se notan.
- Las 4 tienen el **arte del canal** (el del YAML): puestas al lado de las 5 actuales, parecen de la misma serie.
- El título sale exacto (acentos, «ñ») con la fuente del canal, se lee en tamaño celular y no tapa la duración (abajo a la derecha).

---

## 1. INVESTIGACIÓN

### 1.1 Lo que ya hay en la casa (relevado el 2026-11-22)

| Pieza | Estado |
|---|---|
| **ComfyUI** | v0.28.3 en `/mnt/LLM/apps/comfyUI`, corriendo en `0.0.0.0:8188` (venv propio, `start.sh`). Nodos: Manager, Impact-Pack, IPAdapter_plus y alkaid. |
| **GPU** | RTX 3060 de 12 GB, compartida con `audiogen-qwen3-vllm`. 62 GB de RAM, que permiten descargar modelos de la GPU a la RAM. |
| **Modelos de imagen** | Z-Image Turbo (fp8 AIO e int8), Flux schnell fp8, SDXL base, SD 1.5, Qwen-Image-Edit-2511 int8 + Lightning de 4 pasos, Flux Kontext dev fp8 y Wan 2.2 Fun Control 5B. |
| **Modelos auxiliares** | BiRefNet (recorte), SAM vit-b, ControlNet depth y openpose SDXL, IP-Adapter plus SDXL + CLIP-ViT-H y RealESRGAN x4 anime. |
| **Disco** | 360 GB libres en `/mnt/LLM`. |
| **Python** | Pillow 12 en el proyecto (llega por WeasyPrint). Fuentes OFL en `assets/fonts/`. |
| **Gráficos en el host** | Blender 5.2.2 LTS (también con MCP), Krita, resvg 0.46, ImageMagick 7.1 y tesseract 5.5 (solo `eng`, le falta `spa`). Están **en el host, no en la imagen de Docker**. |
| **Docker** | Los contenedores llegan al host con `host.docker.internal:host-gateway`, como hoy a Ollama. |
| **Jobs, modal y bus** | `JobManager`, `EventBus`, `ia-modal.js` y el tiempo estimado (Spec-460, 510) sirven tal cual. |
| **Datos de la historia** | Título, idea, las entidades con ficha y `reveal_level` (Spec-450), los lugares con descripción (Spec-710), los actos. |

**`cw2d-art` dejó resuelto el cliente.** El patrón de su `tools/cw2d/comfy.py` (commit `55c08f9`, ADR 0001) tiene tres piezas:
- **Workflow en formato API con un mapa de parámetros** (`workflow.api.json` + `params.yaml`). El código nunca edita el grafo, y un parámetro que apunta a un nodo inexistente falla al cargar.
- **`ComfyClient`**: `upload_image`, `queue`, `wait` y `download`.
- **Registro de cada corrida**: hash del workflow, parámetros y semillas.

Se reusa el diseño, sin copiar el repo del juego.

**Por qué ComfyUI se archivó en `cw2d-art`.** El juego pedía el mismo personaje idéntico en decenas de cuadros de 144 px, y no hubo forma de mantenerlo estable. **Una miniatura es lo contrario:** una sola imagen grande, donde variar es bueno y una persona elige entre tres.

### 1.2 Por qué «ComfyUI solo» no alcanza, y qué es el arnés

Lo que falla al hacer la miniatura entera en un grafo de ComfyUI:

1. **Un grafo gigante hace todo a la vez.** Si la entidad sale mal, se rehace todo y cambia también el fondo.
2. **Las letras.** La difusión escribe mal en español: acentos, «ñ», letras que se deforman.
3. **La memoria.** Tres modelos grandes en un grafo no entran en 12 GB.
4. **No es para Yael.** Los nodos son para quien arma workflows.

**El arnés da vuelta el esquema: divide y triunfarás.** Cada llamada a ComfyUI es un workflow chico que hace **una sola tarea**: ilustrar un boceto, recortar, agrandar, reiluminar el escenario, fundir la figura en una máscara. **La secuencia la decide Python, por código:**
- qué workflow corre;
- con qué entrada, que suele ser la salida del anterior;
- qué se revisa entre un paso y el siguiente;
- qué se hace si un paso falla.

Ningún workflow encadena tareas adentro. Es la «composición o collage en pasos» de los videos que vio el usuario, con Python como director (D15).

**La cadena de una tanda** (cada caja es una llamada aparte a ComfyUI, salvo las marcadas «Python»):

```
PERSONAJE                                   ESCENARIO
 boceto ─▶ [ilustrar_personaje] ─▶ revisión  boceto ─▶ [ilustrar_escenario] ─▶ revisión
           (sobre fondo liso)       Python             (16:9, qué va y dónde)  Python
        ─▶ [recortar] ─▶ revisión                  ─▶ Python: curva de oscuridad
        ─▶ [agrandar] (si hace falta)              ─▶ [fotografiar_escenario] ─▶ revisión
                                                      (foto real, oscura, con niebla; E3b/E3c)

POR CADA UNA DE LAS 4 VARIACIONES
 [reiluminar_escenario] (la luz de la variación, solo el escenario; o Python si alcanza, E6)
 Python: componer (escenario + personaje con encuadre y lado) + máscara automática
         (alfa del recorte dilatado + franja de sombra hacia abajo)
      ─▶ [fundir] (inpaint SOLO dentro de la máscara: luz, perspectiva y sombra de contacto)
 Python: volver a pegar el fondo original fuera de la máscara ─▶ revisión ─▶ título ─▶ chequeos ─▶ JPG
```

Son unas **11 a 15 llamadas por tanda** (2–3 del personaje, 2 del escenario, y 4 × reiluminar + fundir). En «Armar otras 4», solo las de la parte de abajo. El camino viene del video del compositor de ILM (§1.5): fundir con máscara en lugar de armonizar toda la imagen.

### 1.3 Herramientas evaluadas

| Herramienta | Qué aporta | Veredicto |
|---|---|---|
| **API HTTP de ComfyUI** + el patrón de `cw2d` | Encolar, esperar, bajar resultados y avance por WebSocket | **Se usa.** |
| SDK oficial de Comfy / API v2 | Contrato v2 para backends con muchos workflows | No por ahora: es una capa más para un solo usuario. |
| **Z-Image Turbo** (instalado) | Imágenes rápidas desde texto | **Se usa** para lugar y entidad cuando no hay boceto. |
| **ControlNet** (scribble/lineart/depth SDXL; los dos últimos instalados) | Respetar la composición o el contorno de un boceto | **Se usa** para pasar del boceto de Yael a imagen. Falta bajar el de scribble/lineart (con licencia comercial). |
| **Qwen-Image-Edit-2511** + Lightning (instalado) | Editar con instrucciones: «convertí este boceto en una ilustración», «que la entidad tenga la luz del lugar» | **Se usa** como segunda vía de boceto a imagen, para reiluminar el escenario y para fundir el personaje con máscara (§2.5). |
| **Qwen-Image-Layered** | Parte una imagen en capas RGBA (Apache 2.0) | **Ya no es central:** el personaje y el escenario llegan en bocetos separados. Queda como reserva del spike E2. El ComfyUI de la casa (0.28.3) ya trae sus nodos: no hace falta la nightly. |
| IC-Light v1 (fbc) | Reilumina una figura según el fondo | Alternativa si Qwen no funde bien (E4). |
| LoRA Fusion de Qwen-Edit 2509 (dx8152) | Funde un objeto pegado con el fondo: luz, perspectiva y sombras (§1.5) | **Licencia dudosa** (Apache-2.0 en la ficha, CC-BY-NC en un commit): no se usa hasta confirmarla. Se prueba si anda con la 2511 |
| **BiRefNet** (instalado, MIT) | Recorta la entidad del fondo | **Se usa.** |
| RealESRGAN (instalado) | Agranda sin perder nitidez | **Se usa** si una parte sale chica. |
| **Pillow** | Componer, letras simples, viñeta y chequeos | **Se usa.** Determinista y testeable sin GPU. |
| **SVG + resvg** | Estilos de letras diseñados una vez y llenados por el script | **Se usa** (§2.4). |
| **Blender** (instalado, con MCP) | Letras 3D con material y luz | **Opcional** (S7). MCP para diseñar el estilo con Claude, script para cada episodio. |
| **tesseract** | OCR para verificar que el título se lee | **Se usa** con letras estilizadas, con `tesseract-ocr-spa` (preguntar antes). |
| `psd-tools` | Leer el PSD que exporta SAI | **No hace falta:** Yael exporta PNG desde SAI2. |
| Krita + krita-ai-diffusion | Pintar con IA en vivo | **Fuera del flujo**: Yael dibuja en SAI y sube el boceto. |
| n8n | Orquestación visual | No: el proyecto ya tiene jobs, bus y modal. |
| Flux Kontext dev (instalado) | Ediciones por instrucción | **No:** licencia no comercial y el canal va a monetizar (D9). |

### 1.8 Las 124 miniaturas del canal (2026-11-23)

Se bajaron las 124 miniaturas públicas del canal (`yt-dlp` + `i.ytimg.com`, 121 a 1280 × 720) a `scripts/research/790/insumos/canal_yt/` (fuera de git; `ids.txt` va de la más nueva a la más vieja). A ojo, con hojas de contacto:

- **Pocas plantillas, repetidas:** (A) figura grande de un lado y el título del otro, la más común; (B) figura chica y lejos, y el lugar manda (torre, ruta, mar); (C) primer plano de una cara; (D) título en dos alturas: el tema arriba y una frase gancho abajo, en la esquina opuesta; (E) título grande al centro con la figura atrás (las más viejas).
- **El título va por niveles:** un rótulo chico («HISTORIAS DE TERROR», «RECOPILACIÓN», el sello torcido «MÉXICO»), la frase con las palabras fuertes grandes y las de enlace chicas, **una palabra de acento en color** y los números («3», «5») gigantes, ocupando dos líneas.
- **El texto de la miniatura es un gancho, no el título del video** («SIGUE ESTAS REGLAS PARA SOBREVIVIR» en el video de la torre de vigilancia).
- **Evolución:** el acento pasó de rojo a naranja; las más nuevas tienen la figura más grande, el título más grande y más color (luces cálidas).
- **Yael quiere como patrón las más recientes** (2026-11-23): las plantillas salen de esas y las viejas quedan solo para ver la evolución.

### 1.4 Tendencias de miniaturas en 2026

Casi todo viene de blogs de empresas que venden herramientas de miniaturas o análisis. **Los estudios con números (vidIQ, BrightBean) mezclan todos los nichos** y no separan el terror narrado, así que sirven como dirección general, no como dato del nicho. Por eso **se descarta la conclusión sobre caras** (el 69 % de vidIQ sale de otros nichos). En este canal, **la figura central es la entidad del relato**.

| Tendencia | Evidencia | Qué tomamos |
|---|---|---|
| **Menos texto.** | vidIQ (500 videos, todos los nichos): mediana de 5 palabras. BrightBean (puntaje propio): mejor con 2–4. 1of10: el texto se achica, sin datos. | **2 a 4 palabras**, con aviso desde 6. |
| **Un solo foco y mucho contraste.** | Para canales de terror sin cara: una imagen fuerte que cuente la historia de un vistazo, una sola luz en un cuadro oscuro (Miraflow, sin datos). | **Tres elementos:** el lugar, la entidad y la frase. Contraste de las letras ≥ 7:1. |
| **Se mira en el celular.** | Lo detallado se pierde a 120 px (varias fuentes, sin citar origen). | Cada idea se muestra también a 120 px; márgenes seguros. |
| **Abajo a la derecha va la duración.** | Todas las guías. | Esa zona queda libre siempre. |
| **Prueba A/B en YouTube** («Probar y comparar»). | Hasta 3 miniaturas por video, gana la de más tiempo de reproducción. Si una es menor que 1280 × 720, YouTube baja todas a 854 × 480 (una sola fuente). | Yael elige **1 a 3 de las 4** para la prueba, todas de 1280 × 720. |
| **Serie reconocible.** | vidIQ y Miraflow recomiendan mantener letra y color de acento (sin datos). | **El arte del canal** en `config/miniatura/arte.yaml` (§2.2). |
| **«Look IA» genérico.** | Sin datos de rechazo. | Partir de los dibujos de Yael es lo que distingue (hipótesis). |

**Formato:** 1280 × 720 (16:9), mínimo 640 de ancho, JPG/PNG de hasta 2 MB (Kapwing, TechSmith).

### 1.5 Lo que muestran los dos videos que pasó el usuario (2026-11-22, con `ytctx`)

**«QWEN AI Compositing in ComfyUI!»** (Comfy Compositing, un compositor de ILM; [video](https://www.youtube.com/watch?v=np99SCBUNo4)). Es el más útil: confirma el camino y le corrige un punto.

- **El problema del camino «armonizar todo».** Con el workflow por defecto de Qwen-Image-Edit 2509 + la LoRA *Fusion* (que funde un objeto pegado con el fondo: perspectiva, luz y sombras), el resultado se ve bien, pero **el fondo se corre, cambia de color y pierde nitidez** [00:00:31]. Es justo el riesgo de nuestro `armonizar`.
- **La solución: inpaint con máscara.** Composición tosca → máscara alrededor del objeto, **un poco más grande e incluyendo donde van a caer las sombras** → Qwen-Edit + Fusion + Lightning de 4 pasos **solo dentro de la máscara**, así el resto no se toca [00:02:12], [00:05:51]. Si la sombra sale corta, se agranda la máscara y se vuelve a correr [00:08:48]. Así se resuelven luz, perspectiva y sombras de contacto en un solo paso [00:09:18], [00:11:24].
- **Su cadena:** recorte automático del sujeto [00:03:35] → composición tosca a ~1024 px [00:03:12] → máscara → fundir → guardar.
- **Divide y triunfarás, dicho por él:** el workflow es pesado (lo corre en una 5090 con 128 GB de RAM). Recomienda **partirlo en workflows separados** y pasar la imagen de uno a otro: «con 8 GB alcanza para los tres primeros pasos por separado» [00:11:35], [00:12:19]. Es D15.
- **Para nosotros:**
  - la máscara la dibuja **Python, sola**: el alfa del recorte, dilatado, más una franja hacia abajo para la sombra;
  - después del inpaint, Python **vuelve a pegar el fondo original fuera de la máscara**, así el fondo queda intacto y nítido (*paste-back*).
  - **Licencia de la LoRA Fusion** ([dx8152/Qwen-Image-Edit-2509-Fusion](https://huggingface.co/dx8152/Qwen-Image-Edit-2509-Fusion)): la ficha actual dice Apache-2.0, pero un commit del repo dice CC-BY-NC-4.0. Por D9, hasta confirmar el historial **se trata como dudosa**. Además es para la 2509 y tenemos la 2511 (se prueba si anda). Sin ella, se usa Qwen-Edit con instrucción, en la misma máscara.

**«New Visual Compositing Canvas for ComfyUI!»** (GeekatPlay; [video](https://www.youtube.com/watch?v=ZUlZ4Ay1t7s)). Un nodo de lienzo dentro de ComfyUI con tres piezas:
- **El lienzo:** se arrastra la imagen de un personaje, se dibuja una línea para el terreno y se agregan notas numeradas («Rocky hill with long yellow grass», «Beautiful sunset») [00:00:13]–[00:00:35].
- **El ensamble:** el lienzo se renderiza como una **imagen de layout** [00:02:10], y un VLM escribe el prompt final citando «Picture 1 = layout, Picture 2 = el personaje» [00:02:18].
- **La generación:** un modelo de imagen **multirreferencia** genera una sola imagen que respeta el layout y al personaje; al mover el personaje en el lienzo, se mueve en la imagen [00:02:58]–[00:03:17].

- **Para nosotros:**
  - **La interfaz no:** es un lienzo de edición, lo que el usuario descartó para Yael (D2).
  - **La idea sí, como alternativa:** Python puede armar ese layout solo (el boceto del escenario con el boceto del personaje ubicado según la variación, más notas con lo de la historia) y pedirle a un modelo multirreferencia (Qwen-Edit 2511 acepta varias imágenes) que lo pinte entero.
  - **El costo:** es **una llamada que hace mucho**, lo contrario de D15. Por eso entra solo como **variante de comparación** (E10), no como camino principal.
  - **El modelo del video** (MiniMax H3, con un VLM de 32B) no entra en 12 GB ni tiene licencia clara: se prueba con Qwen-Edit 2511.

### 1.6 Workflows de referencia con modelos libres (2026-11-22)

Workflows y modelos publicados que hacen lo mismo que los videos con **licencia que permite uso comercial**, o marcados cuando no está clara. Sirven de **punto de partida** para cada receta: se abren en ComfyUI, se recortan a una sola tarea (D15) y se exportan en formato API.

**La regla para los nodos custom:** donde un workflow de referencia necesita un nodo custom para recortar, enmascarar o pegar, eso lo hace Python. ComfyUI solo recibe la imagen ya preparada.

| Parte del flujo | Referencia | Modelos y licencia | Para qué receta / spike |
|---|---|---|---|
| **Fundir con máscara y volver a pegar** (lo del video de ILM, sin la LoRA dudosa) | [Masked repaint con Qwen 2511: recortar el bloque, editarlo y pegarlo](https://dev.to/ai-ksk/qwen-2511-masked-repaint-crop-the-masked-block-edit-with-a-reference-paste-it-back-seamlessly-51ac); [RebelTortuga/comfyui-free-local-qwen-image-edit](https://github.com/RebelTortuga/comfyui-free-local-qwen-image-edit) (modo «composite por máscara»); [Eric_Qwen_Edit_Experiments](https://github.com/EricRollei/Eric_Qwen_Edit_Experiments) (vacía la zona, edita y pega con borde difuminado); [axiomgraph: Qwen 2511 Inpainting](https://github.com/axiomgraph/ComfyUIWorkflow) | Qwen-Image-Edit-2511 + Lightning (Apache-2.0, instalados) | `fundir`, E4. **Qwen-Edit no tiene entrada de máscara nativa**: rehace todo el cuadro. Por eso el patrón es **recortar el bloque del personaje con margen → editar solo ese recorte → pegarlo con la máscara difuminada**. Python hace el recorte y el pegado. Además, editar un recorte chico **usa menos VRAM** |
| Inpaint sin entrenamiento, para cualquier modelo | [LanPaint](https://github.com/scraed/LanPaint) (dice soportar Qwen-Edit 2511) | El modelo que se use | Variante de E4 si el recorte y pegado deja costuras |
| **Layout multirreferencia** (lo del video de GeekatPlay, en local) | [Plantilla oficial de Qwen-Image-Edit-2511](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511) (hasta 3 imágenes de referencia); [FLUX.2 klein 4B](https://docs.comfy.org/tutorials/flux/flux-2-klein) (edición con una o varias referencias, versión destilada rápida) | Qwen-Edit 2511: Apache-2.0. FLUX.2 klein **4B: Apache-2.0** (la 9B es no comercial: fuera). klein entra en ~8–13 GB; ya hay en disco su VAE (`flux2-vae`) y su codificador (`qwen_3_4b`), falta el modelo | E10. Con 3 referencias: 1 = layout que arma Python, 2 = el personaje de E1, 3 = una de las 5 miniaturas como estilo (E7). **Antecedente:** en `cw2d-art`, klein 4B se evaluó para hojas de personaje y **se descartó por calidad** frente a Qwen-Edit 2511. Acá es candidato secundario |
| **Boceto → imagen** | [Qwen-Image InstantX Union ControlNet](https://comfy.org/hub/workflows/qwen-image-instantx-union-controlnet-9829786b38f5/) (canny, soft edge, depth, pose); ControlNet Union SDXL de xinsir (scribble, lineart, canny, depth…); Qwen-Edit 2511 con instrucción («convertí este boceto en…») | InstantX Union: **Apache-2.0** (pide Qwen-Image base, que **no está en disco**). xinsir Union SDXL: Apache-2.0 (no está; están su depth y su openpose). Qwen-Edit 2511: instalado. **Fuera:** Qwen-Image 2.1 Fun ControlNet (lineart + scribble), con pesos **no comerciales** | `ilustrar_personaje` y `ilustrar_escenario`, E1 y E3. El boceto de Yael entra como *soft edge* o *canny* (InstantX), como *scribble* o *lineart* (xinsir) o directo como imagen a editar (Qwen-Edit) |
| **Reiluminar el escenario** | LoRA de reiluminado para Qwen-Edit 2509 ([Comfy-Org](https://comfy.org/hub/models/local/qwen-image-edit-2509-relight/), de dx8152); [QIE-2511-MP-AnyLight](https://huggingface.co/mario-d-robot/QIE-2511-MP-AnyLight) («aplicá la luz de la imagen 2 a la imagen 1»); [LightingRemap](https://hapticpaper.github.io/learning_gallery/models/2026-01-17--lightingremap-alpha) | **Licencias sin confirmar** en las tres: se verifican antes de bajar, y si no son claras quedan fuera (D9) | `reiluminar_escenario`, E6. **AnyLight es la más interesante:** la luz de la variación podría salir de una **imagen de referencia de luz** (por ejemplo, una de las 5 miniaturas) en vez de un texto. Sin LoRA: Qwen-Edit con instrucción, o color en Python |
| Reiluminar la figura según el fondo | [IC-Light](https://github.com/lllyasviel/IC-Light) v1 (`fbc`) | v1: CreativeML OpenRAIL-M según fuentes secundarias, a confirmar en el repo oficial. **v2: no comercial (fuera)** | Alternativa de `fundir`, E4 |
| Recortar | BiRefNet (instalado) | MIT | `recortar`, E2 |
| Separar en capas | Qwen-Image-Layered | Apache-2.0. **Ya lo soporta el ComfyUI de la casa** (0.28.3 tiene `EmptyQwenImageLayeredLatentImage`): no hace falta la nightly | Reserva de E2 |

**Lo que cambia en el plan por esta búsqueda:**
- `fundir` trabaja sobre un **recorte** de la zona del personaje, con margen, y Python lo pega de vuelta (§2.5).
- **Más variantes en los spikes:**
  - E1/E3 suman InstantX Union y xinsir Union SDXL;
  - E6 suma AnyLight si su licencia es clara;
  - E10 suma klein 4B.
- **No hace falta actualizar ComfyUI a la versión nightly** para Qwen-Image-Layered ni para klein: la 0.28.3 ya los trae. Se confirma en E0.
- **Lo que hay que bajar** (preguntando antes, con su licencia):
  - Qwen-Image base, para InstantX: unos 20 GB en fp8;
  - InstantX Union;
  - xinsir Union SDXL;
  - klein 4B fp8;
  - las LoRAs de luz que pasen el control de licencia.

### 1.7 El arte del canal según sus miniaturas (2026-11-22, T0.A)

El usuario dejó **8 miniaturas actuales** en `imagenes/` (movidas a `scripts/research/790/insumos/miniaturas_canal/`, fuera de git, T0.3). Las de abajo se nombran por su título.

| Miniatura | Figura | Escena y luz | Título |
|---|---|---|---|
| NUNCA ROMPAS LAS REGLAS (1600 × 1023) | entidad flaca encorvada, de perfil, ojo ámbar que brilla, izquierda | campo de pasto alto de noche, luna llena, nubes; tinte verde azulado frío | serif blanca, 3 líneas a la derecha, «LAS» chica; textura gastada |
| 3 RELATOS DE ENCUENTROS CON SKINWALKERS (1600 × 1023) | criatura con cráneo de ciervo y astas, ojos blancos, izquierda | bosque oscuro, niebla al pie; blanco y negro | serif blanca, 3 líneas abajo a la derecha, «DE» y «CON» chicas |
| NO TE DUERMAS DURANTE LA GUARDIA | **dos figuras:** el guardia de espaldas con linterna (centro) y la entidad pálida gritando en la puerta (izquierda) | pasillo abandonado, haz de linterna; blanco y negro, grano fuerte, calavera tenue en la pared | serif blanca a la derecha sobre **pincelada negra**, «LA» chica |
| 3 HISTORIAS DE PUEBLOS CON DOPPELGÄNGERS | dos nenas iguales de blanco, de frente, izquierda | calle de tierra de un pueblo, niebla, contraluz; casi blanco y negro | «3» gigante en dos líneas; «DOPPELGÄNGERS» en **naranja con brillo**; pincelada negra arriba a la derecha |
| 3 ENCUENTROS CON SERES EXTRAÑOS | criatura altísima, flaca y pálida, lit por un flash, derecha | banquina con pasto seco de noche; aspecto de foto con flash o de cámara trampa | «3» naranja con brillo; título abajo a la izquierda sobre pincelada |
| 3 RELATOS DE TERROR | silueta detrás de un vidrio empañado, ojos blancos, mano apoyada, derecha | ventana de noche, contraluz; blanco y negro | «3» gigante, «TERROR» en **rojo**; **franja de abajo**: «HISTORIAS DE TERROR **RECOPILACIÓN**» (amarillo pálido) |
| COMIDA RÁPIDA | entidad flaca de ojos blancos (izquierda) y un food truck iluminado (derecha) | ruta con niebla, luz fría azulada | «COMIDA RÁPIDA» en rojo, **sans condensada**, arriba sobre pincelada; «HISTORIAS DE TERROR» serif; franja de abajo «RELATOS DE **SKINWALKERS**» |
| ENCUENTROS CON FANTASMAS | nene con sonrisa y ojos que brillan, linterna en la mano, izquierda | sendero de selva bajo la lluvia; blanco y negro con un toque verde | título rojo en **sans condensada** arriba a la derecha; «HISTORIAS DE TERROR» serif; bajada abajo a la derecha |

**Medido sin IA** (Pillow sobre las 8):
- brillo medio de 22 a 74 sobre 255;
- del 38 % al 87 % de los píxeles muy oscuros;
- saturación casi nula en 6 de 8: **blanco y negro o casi**.
- **Dos de las 8 no son 16:9** (1600 × 1023): eran viejas; las nuevas salen a 1280 × 720.

**Lo que se repite (el arte):**
1. **Fotográfico, no pintado:** foto nocturna de terror, blanco y negro o desaturada con un tinte frío (verde azulado o azul). Grano fuerte, viñeta muy oscura en los bordes, textura sucia o rayada.
2. **Una sola luz dura:** luna, linterna, flash, contraluz de ventana o niebla iluminada. Negros profundos.
3. **La figura:** casi siempre **la entidad**, flaca, de miembros largos, cadavérica o en silueta, con **ojos que brillan** (6 de 8), ocupando del 60 % al 90 % del alto. Va de un lado, y el título del otro: la figura a la izquierda en 6 de 8.
4. **Lugares:** bosque, campo de pasto alto, pasillo abandonado, calle de pueblo, banquina, ventana. Niebla baja en la mitad de los casos.
5. **El título:**
   - serif en mayúsculas, blanca, con brillo o sombra suave;
   - **jerarquía de tamaños:** las palabras fuertes grandes y las de enlace («de», «con», «la», «las») al ~55 %;
   - los números («3») gigantes, ocupando dos líneas;
   - **una palabra en color de acento** con brillo (naranja o rojo);
   - muchas veces sobre una **pincelada negra** con borde roto, detrás del bloque de texto.
6. **Franja de serie** (3 de 8): una banda negra fina abajo con un rótulo chico («HISTORIAS DE TERROR RECOPILACIÓN», «RELATOS DE SKINWALKERS»), con una palabra en amarillo pálido.
7. **Abajo a la derecha:** 3 de 8 ponen texto ahí (la franja o la bajada). YouTube tapa esa zona con la duración: el chequeo lo va a avisar.

**La fuente:** el usuario eligió **Noto Serif SC ExtraBold** (Google Fonts, licencia OFL).
- En la PC hay **Noto Serif CJK SC Bold**, que no es ExtraBold, y cubre el español: Latin-1 completo, con «ÑÁÉÍÓÚÜ¿¡».
- La ExtraBold hay que bajarla (T0.3, preguntando antes) y comprobar en E8 que sus glifos latinos son iguales.
- **Dos de las 8 usan además una sans condensada en rojo** («COMIDA RÁPIDA», «ENCUENTROS CON FANTASMAS»). Queda como pregunta (Q11).

**Preguntas que abrió** (§9; respondidas el 2026-11-22 con las propuestas: solo la serif, franja opcional abajo a la izquierda, una sola figura, acento naranja):
- **Q11:** ¿solo la serif, o también la sans condensada para la palabra de acento?
- **Q12:** ¿la franja de serie de abajo va (con un texto fijo de `arte.yaml` o un campo), y dónde, si no puede ir abajo a la derecha?
- **Q13:** ¿una segunda figura (como el guardia y la entidad, o las nenas)? El flujo de hoy tiene una sola figura principal.
- **Q14:** ¿el color de acento es uno solo (naranja o rojo), o se elige por miniatura?

---

## 2. PROPUESTA

### 2.1 El flujo (el del usuario y Yael, 2026-11-22)

```
 1. ¿QUIÉN VA?          2. EL PERSONAJE        3. EL ESCENARIO        4. EL TÍTULO        5. LAS 4 MINIATURAS
 ─────────────          ──────────────         ──────────────         ────────────        ───────────────────
 [Que la IA lea         boceto de ese          boceto de todo         campo de texto      [Armar las 4] (job):
  el relato] propone:   personaje (PNG)        el escenario (PNG)     (precargado con     arma el personaje y el
 entidad/monstruo o     → ComfyUI lo arma      + cómo es el lugar     el de la historia)  escenario, compone,
 protagonista + cómo                           (precargado, editable) → lo dibuja el      funde, pone el título
 es (editable)                                 → ComfyUI lo arma      código              → 4 imágenes → elige 1 a 3
                                  ▲ arte.yaml: la parte del prompt común a TODAS las miniaturas ▲
```

1. **¿Quién va en la miniatura?**
   - **«Que la IA lea el relato»** (botón, job `thumbnail_read`, ~US$ 0,01) propone la figura principal, **la entidad/monstruo o el protagonista**, con un motivo corto, más tres textos:
     - la **descripción de esa figura** sacada del relato;
     - la **descripción del lugar** principal;
     - una **frase de título** alternativa, por si el título de la historia es largo.
   - Yael confirma o cambia la figura y edita las descripciones.
   - Sin tocar el botón, todo se completa a mano: la figura queda en «La entidad» si la historia tiene una, y la descripción del lugar se precarga con el primer lugar de la historia (Spec-710).
   - **Las descripciones dicen cómo es** la figura o el lugar, no lo que pasa, así que no adelantan el final.
2. **El personaje.** Yael sube el **boceto de ese personaje** (PNG, obligatorio). ComfyUI lo arma: lo convierte en una ilustración con el arte del canal y la descripción, y lo recorta. Ella lo dibuja sabiendo que después **se suma a la composición general**.
3. **El escenario.** Yael sube el **boceto de todo el escenario** (PNG, obligatorio) y revisa «Cómo es el lugar». ComfyUI lo arma con el arte del canal.
4. **El título.** Precargado con el título de la historia, editable, en 1 o 2 líneas, con aviso desde 6 palabras. El código lo dibuja con la fuente y el estilo de `arte.yaml`, sin IA.
5. **Las 4 miniaturas.** «Armar las 4» (job `thumbnail_build`, con confirmación y tiempo estimado):
   1. Escribe los prompts en inglés con una llamada de texto: arte + descripciones.
   2. Arma el personaje y el escenario en ComfyUI, si no están armados o cambió su boceto o su descripción.
   3. Compone 4 veces, cada una con **una variación del arte** (luz, encuadre, lado de la figura) y otra semilla.
   4. Funde el personaje en cada composición (solo dentro de una máscara que arma Python, §2.5) y pone el título encima.
   5. Corre los chequeos y guarda **4 JPG**.

   Después, Yael **elige de 1 a 3** (la prueba A/B de YouTube admite hasta 3) y descarga cada una, o un zip con las elegidas. **«Armar otras 4»** reusa el personaje y el escenario ya armados y solo rehace la composición, con otras semillas. Cambiar un boceto o una descripción rehace esa parte en la próxima tanda.

**Lo que corre por detrás**, sin que Yael lo vea:
- las capas;
- los prompts;
- el recorte;
- el fundido;
- las variaciones;
- los chequeos (§2.7).

**Camino de emergencia** (D-Q4): si falta un boceto, el botón avisa («Falta el boceto del escenario») y ofrece «Armarlo sin boceto». Esa parte se hace desde su descripción, con el arte del canal.

### 2.2 El arte del canal: `config/miniatura/arte.yaml`

Es lo que **comparten todas** las miniaturas, sin importar la historia: paleta y acento, luz, sentidos, textura, negativos comunes, composición, las 4 variaciones y el título. Aunque cambien la historia y los bocetos, eso se mantiene: es lo que hace que las miniaturas parezcan de la misma serie.

**Un prompt por paso (D17, 2026-11-23).** El **estilo** no es común: cada paso tiene su plantilla en `config/miniatura/prompts/<paso>.md` y toma de `arte.yaml` **solo los campos que le sirven** (`{luz}`, `{sentidos}`…). El personaje y el escenario se ven distintos a propósito:
- **personaje** (`personaje.md`): el texto de `qwen_b` (E1) tal como les gustó al usuario y a Yael: **no se toca**;
- **escenario** (`escenario.md` + `fotografiar_escenario.md`): **foto real** de un lugar real, oscura y con niebla (una mansión real, árboles reales, una caseta real; nada de «cartoon lúgubre» ni render). El boceto solo guía qué va y dónde. Pedido de Yael tras E3: Qwen arma la escena, Python la oscurece y Z-Image la vuelve foto (E3b/E3c);
- más adelante `fundir.md` y `reiluminar.md`, cada uno con lo suyo.

```
prompts/<paso>.md  ←  {descripción de la historia} + campos de arte.yaml que pide el paso + {variación}
```

Así, ajustar el realismo del fondo no puede romper al personaje aprobado, y lo común (acento, título, variaciones) sigue en un solo lugar. Como en el relato (Spec-620), el texto que lee la IA vive en `config/` y no en Python.

**Las miniaturas actuales** (8, en §1.7) sirven **dos veces** (D-Q10):
- para escribir los textos del YAML;
- como **referencia visual** que reciben los modelos: 1 o 2 de ellas, por IP-Adapter o como imagen de referencia de Qwen-Edit, si en el spike E7 mejoran el parecido sin copiar la composición.

Las imágenes quedan **fuera de git**, en `data/<env>/miniaturas/_arte/`, y el YAML las nombra.

**Borrador** (T0.A, sacado de las 8 miniaturas de §1.7; se ajusta en los spikes E6–E8 y con Yael):

```yaml
# El arte del canal: lo comparten TODAS las miniaturas. Lo leen los pasos de ComfyUI
# (en inglés). Se edita solo en el repo (D-Q8), mirando las miniaturas del canal (§1.7).
version: 1
referencias_visuales:          # D-Q10 / E7: archivos en data/<env>/miniaturas/_arte/ (fuera de git)
  - { archivo: nunca_rompas_las_reglas.jpg, peso: 0.3 }
  - { archivo: no_te_duermas_durante_la_guardia.jpg, peso: 0.3 }

# El estilo NO va acá: cada paso lo pone en su plantilla de prompts/ (D17).
luz: >-
  A single hard light source (moonlight, a flashlight beam, a camera flash or a backlit
  window), deep crushed blacks, most of the frame in shadow, the figure partly lit.
paleta:
  acento: "#FF6A1A"            # Q14: naranja con brillo, uno solo (rojo #D10A0A queda como alternativa)
  prompt: >-
    Monochrome or almost monochrome, cold teal or blue tint at most, no warm colors
    except small light sources.
sentidos: >-
  Cold damp night air, low fog close to the ground, dead silence, the feeling of being
  watched from the dark.
textura: >-
  Heavy film grain, strong dark vignette on all edges, dirty scratched texture,
  slight blur in the background.

negativos: >-
  text, letters, watermark, logo, color, saturated colors, gore, blood, extra limbs,
  extra fingers, cartoon, painting, illustration, bright daylight, people in the background.

variaciones:                   # D-Q2 / E6: una por imagen de la tanda (exactamente 4)
  - { luz: "full moon behind clouds, cold teal tint", encuadre: plano_medio, lado: izquierda }
  - { luz: "flashlight beam from the side, black and white", encuadre: primer_plano, lado: izquierda }
  - { luz: "harsh camera flash from the front, like a trail camera", encuadre: plano_general, lado: derecha }
  - { luz: "backlit fog, the figure as a silhouette with glowing eyes", encuadre: plano_medio, lado: derecha }

composicion:
  encuadres: { primer_plano: 0.95, plano_medio: 0.75, plano_general: 0.6 }
  lados: { izquierda: 0.28, derecha: 0.72 }   # el título va siempre del lado opuesto
  titulo: { lado: opuesto_a_la_figura, alto_max: 0.6, margen: 0.04 }
  esquina_libre: { lado: abajo_derecha, ancho: 0.2, alto: 0.15 }
  mascara: { dilatacion: 0.02, franja_sombra: 0.12, borde_pegado: 8 }

titulo:                        # §2.4
  fuente: NotoSerifSC-ExtraBold   # OFL; en assets/fonts/ (T0.3)
  motor: pillow                # o svg si E8 lo pide (pincelada con textura)
  mayusculas: true
  color: "#FFFFFF"
  brillo: { color: "#FFFFFF", radio: 6, opacidad: 0.35 }
  palabras_chicas: [de, del, con, la, las, el, los, en, y, a, al, un, una]   # al 55 %
  escala_palabras_chicas: 0.55
  numero_grande: true          # un número al principio ocupa dos líneas
  resaltada: { color: acento, brillo: { radio: 10, opacidad: 0.6 } }
  pincelada:                   # banda negra con borde roto detrás del bloque
    usar: true
    archivo: pincelada_1.png   # textura en _arte/ (o hecha con SVG, E8)
    opacidad: 0.85
  franja_serie:                # Q12: banda fina de abajo con rótulo chico
    usar: false
    texto: "HISTORIAS DE TERROR"
    resaltada_color: "#F2E6A0"

calabaza: { archivo: calabaza.png, lado: abajo_izquierda, alto: 0.35 }
```

**Las plantillas de cada paso** (`config/miniatura/prompts/`, en inglés, con huecos `str.format` como los fragmentos del relato):

| Plantilla | Huecos | Estado |
|---|---|---|
| `personaje.md` | `{descripcion}` (la luz y la textura de E1 quedan escritas en la plantilla, tal como se aprobaron) | **Hecho:** el de `qwen_b` (E1), aprobado: fiel al boceto, fondo liso |
| `escenario.md` | `{descripcion}` (el arte de E3 queda escrito en la plantilla) | **Hecho:** el de Qwen en E3, qué va y dónde |
| `fotografiar_escenario.md` | `{descripcion}` | **Hecho:** foto real muy oscura, niebla espesa, sin luces encendidas ni objetos de más (E3c, `previo_45`) |
| `fundir.md`, `reiluminar.md` | los que pidan E4 y E6 | Pendientes |

Los textos de ejemplo del borrador viejo (`personaje.entidad`, `personaje.protagonista`, `escenario`) se van: la descripción la propone la IA desde el relato (paso 1), y no usa palabras que cambian el material salvo que vengan del relato (E1).

**Reglas de los archivos:**
- `arte.yaml` lo valida un esquema al arrancar (como los moldes, Spec-670): textos no vacíos, exactamente 4 variaciones, encuadres y lados conocidos, y la fuente en `assets/fonts/`.
- Cada plantilla de `prompts/` se carga con su lista de huecos; un hueco que no está en `arte.yaml` ni en lo de la historia falla al arrancar.
- Un test verifica que cada paso de ComfyUI recibe **su** plantilla con los campos del arte que pide y su variación.
- Cambiar el arte o un prompt es cambiar estos archivos, no el código. Viajan en la imagen de Docker, como los prompts del relato.

### 2.3 La pantalla (componentes del sitio, sin editor)

- **Menú lateral:** ítem nuevo **«Miniaturas»**. Lleva a `/miniaturas`, con las historias que tienen relato y un chip por historia: «Sin miniatura», «Con miniaturas» o «Elegida».
- **Desde «El relato»:** la acción «Armar la miniatura» lleva a `/miniaturas/{story_id}`.
- **`/miniaturas/{story_id}`** es una página con las 5 secciones del flujo en orden, con autoguardado (`guardado.js`):

| Sección | Campos y acciones |
|---|---|
| **1. ¿Quién va en la miniatura?** | Botón «Que la IA lea el relato»; opción `.opcion-forge` «La entidad» / «El protagonista», con la que propuso la IA marcada con un chip y su motivo en una pista; «Cómo es» (texto largo, editable) |
| **2. El personaje** | Subir el boceto (PNG, hasta 20 MB), con vista previa y «Cambiar»; pista: «Dibujalo solo, sin fondo: después se suma al escenario» |
| **3. El escenario** | Subir el boceto (PNG); «Cómo es el lugar» (texto, editable) |
| **4. El título** | Texto (1 o 2 líneas), con nota desde 6 palabras; casilla «¿Aparece la calabaza?», apagada |
| **5. Las miniaturas** | «Armar las 4» (`ForgeConfirm.ask` con el tiempo estimado, como escribir un relato, Spec-660). Debajo, las 4 tarjetas de la última tanda, cada una con la imagen grande, la de 120 px, una casilla «Elegir» (hasta 3) y las notas de aviso. Después, «Descargar las elegidas» y «Armar otras 4». Las tandas anteriores quedan en links chicos («Tanda 1 · 2»), para volver a una |

- **Durante un job:** el modal genérico (`ia-modal.js`) con las etapas (`leyendo`, `prompts`, `personaje`, `escenario`, `componiendo`, `esperando_gpu`) y «Imagen 2 de 4».
- **Tono:**
  - no aparecen «ComfyUI», «workflow», «prompt» ni «capa»;
  - `sin-jerga.view.test.ts` cubre las vistas nuevas;
  - lo que se le pidió a la IA se ve en un desplegable «Lo que le pedimos a la IA».
- **Gramática visual** (Spec-550 H9) y textos en vistas y `core_messages.yaml`.

### 2.4 El título (por detrás)

**El contrato de todos los motores:**
- Entra: las líneas, la zona y el estilo de `arte.yaml`.
- Sale: un PNG con alfa del tamaño del lienzo y las cajas de cada letra, que usan los chequeos.

| Motor | Cómo | Cuándo |
|---|---|---|
| `pillow` | Fuente del canal + contorno + sombra | **Desde el inicio**; el de por defecto |
| `svg` | Plantilla SVG llenada por el script, renderizada con resvg (en el Dockerfile) | Desde el inicio, si el arte del canal lo pide (degradés, texturas, brillos) |
| `blender` | `blender -b … --python render.py`, letras 3D con fondo transparente, en el host | Más adelante (S7), si suma |
| `comfy` | La máscara de las letras pasa por ControlNet o Qwen-Edit («de niebla», «de ramas»), con chequeo de OCR | Más adelante (S7), si suma |

- **La forma sale siempre de la fuente.** La IA, como mucho, viste una máscara que ya la tiene.
- **El título va encima y después del fundido.**
- **MCP o script:** el MCP sirve para **diseñar** un estilo con Claude (sobre todo en Blender) y se guarda en `config/`. Cada miniatura corre un **script**, sin MCP.

### 2.5 Fundir el personaje (por detrás, con máscara)

Viene del video del compositor de ILM (§1.5): **no se armoniza la imagen entera**, porque corre el fondo, le cambia el color y le quita nitidez. Se funde **solo la zona del personaje**.

1. **La máscara la arma Python** desde el alfa del recorte: dilatada unos píxeles (el borde) y extendida con una **franja de sombra** del lado contrario a la luz de la variación. Los tamaños salen de E5 y viven en `arte.yaml`.
2. **`fundir`**: Python recorta el bloque de la composición que contiene la máscara, con margen, y lo manda a Qwen-Edit 2511 + Lightning. Qwen-Edit no tiene entrada de máscara: edita el recorte entero (§1.6). La instrucción, fija en `config/`, pide integrar la figura con la luz, la perspectiva y las sombras del lugar, sin agregar nada. Editar un recorte chico usa menos VRAM y tarda menos.
3. **Python pega el recorte editado de vuelta, solo dentro de la máscara**, con un borde difuminado. Fuera de la máscara queda el original, idéntico y nítido.
4. **Revisión:** si dentro de la máscara la figura cambió demasiado (diferencia de estructura con el compuesto, umbral en `config/`), se queda el compuesto sin fundir y la tarjeta lo dice.

**Alternativas** si Qwen no rinde (E4): la LoRA Fusion, si se confirma su licencia, o IC-Light.

**La luz de la variación** se aplica antes, al escenario (`reiluminar_escenario` o ajuste de color en Python, según E6), porque el fundido ya no toca el fondo.

### 2.6 La GPU por turnos

- **Uno por vez:** los pasos de ComfyUI se encolan de a uno, con `POST /free` después de cada modelo grande.
- **Antes de cada paso**, el job compara la VRAM libre (`GET /system_stats`) con lo que pide la receta (`recetas.yaml`).
  - Si no alcanza, queda **«Esperando que se libere la compu de las imágenes»** y reintenta cada 30 s, hasta 10 min (en `config/`).
  - Después, falla con un mensaje coloquial.
  - **Nunca toca audiogen.**
- **Sin ComfyUI:** `/health` lo informa. «Armar las 4» se apaga con la nota «La compu que hace las imágenes está apagada», y el resto del formulario sigue andando.
- **Dónde está ComfyUI:** `COMFY_URL` en `.env` / `.env.prod` (`http://host.docker.internal:8188`). Dev y prod usan el mismo ComfyUI.

### 2.7 Los chequeos (sin IA)

| Chequeo | Regla | Si falla |
|---|---|---|
| Tamaño y peso | 1280 × 720, JPG < 2 MB | se corrige solo |
| Esquina de la duración | nada del título ni del personaje en la esquina libre de `arte.yaml` | el título prueba otra zona; el personaje se corre dentro de su lado; si no alcanza, aviso |
| Contraste del título | ≥ 7:1 contra lo que tiene detrás | más contorno o sombra, dentro de los topes del estilo; si no, aviso |
| Márgenes | título dentro del margen | se corrige solo |
| Palabras | aviso desde 6 | aviso |
| Se lee el título | OCR (`spa`) a 320 px, solo con motor `comfy` | aviso |

**Lo que se arregla solo** (D8) es lo de diseño que no cambia lo que se ve. Lo demás queda como **nota** en la tarjeta, y nunca bloquea la descarga.

### 2.8 Por detrás: el documento de la miniatura

```python
@dataclass
class ThumbnailInput:                     # lo que cargó Yael
    figure: Literal["entidad", "protagonista"]
    figure_proposed: str | None; figure_reason: str | None   # lo que propuso la IA (Q1)
    figure_description: str
    place_description: str
    title: str
    with_pumpkin: bool
    character_sketch: str | None          # archivo subido
    scene_sketch: str | None

@dataclass
class Part:                               # personaje o escenario armado (interno)
    kind: Literal["personaje", "escenario"]
    file: str                             # PNG (el personaje con alfa)
    input_hash: str                       # boceto + descripción + arte: si no cambió, se reusa
    recipe: str; prompt: str; params: dict; seed: int; workflow_hash: str; seconds: float

@dataclass
class Image:                              # una de las 4
    variation: dict                       # la de arte.yaml
    seed: int
    fused: bool                           # si se fundió (o quedó el compuesto, §2.5)
    file: str                             # miniatura.jpg
    warnings: list[str]
    chosen: bool

@dataclass
class Batch:                              # una tanda de 4
    n: int; parts: dict[str, Part]; images: list[Image]; created_at: str

@dataclass
class Thumbnail:                          # una por historia
    id: str; story_id: str
    input: ThumbnailInput
    batches: list[Batch]
```

- **Tabla nueva** `thumbnail` (id, story_id único, data JSON, created_at, updated_at; FK a `story` con borrado en cascada) en `init_db()`, sin migración.
- **Archivos** en `data/<env>/miniaturas/`:
  - `_arte/`: las referencias visuales y la calabaza;
  - `<story_id>/bocetos/`;
  - `<story_id>/partes/<hash>.png`;
  - `<story_id>/tandas/<n>/<i>.jpg`.
- **Trazabilidad:** cada parte e imagen guarda la receta, el prompt, el hash del workflow, los parámetros y la semilla.

### 2.9 La IA de texto (rol `miniatura`)

- **Rol:** `miniatura` en los perfiles. En `openai-sol`, GPT-5.6 Sol sin razonamiento; en los de Claude, Sonnet 5.5.
- **`thumbnail_read` (Q1)**, salida estructurada:
  - `figura` (`entidad` | `protagonista`);
  - `motivo`;
  - `como_es_la_figura`;
  - `como_es_el_lugar`;
  - `titulo_corto`.

  **Lee:** título, idea, la ficha de la entidad, quién narra, los lugares y **el relato** (la última versión), con la instrucción de describir el aspecto y no los hechos.
- **Prompts de imagen (dentro de `thumbnail_build`):** una llamada que pasa las descripciones al inglés y las encaja con el arte. Salida estructurada: `personaje`, `escenario` y las `luces` de las 4 variaciones adaptadas al lugar. La plantilla y lo fijo del arte los pone el código; la IA solo escribe lo propio de la historia.
- **Prompts y fragmentos** en `config/miniatura/prompts/` (Spec-620), con su snapshot `thumbnail_prompts.json`.
- **Costo:** ~US$ 0,02 por miniatura, una llamada por botón.

### 2.11 El compositor (2026-11-23, pedido de Yael)

Yael sube sus bocetos y el gancho, y el sistema **compone como ella**, con **4 composiciones distintas**. No se entrena ningún modelo: el «conocimiento de compositor» sale de **medir su catálogo**.

1. **El catálogo** (`config/miniatura/catalogo.yaml`, generado por un script y revisado a mano): cada plantilla de Yael (§1.8), con los rangos medidos en las recientes. Para la figura: lado, alto, si va cortada. Para el título: zona, cantidad de líneas, alto de cada nivel. Además, el rótulo y el acento, y las miniaturas de ejemplo. Se mide sin IA de texto: BiRefNet para la figura (E2), OCR para las letras (Tesseract `spa`) y Pillow para los colores. Si Yael sube miniaturas nuevas, se vuelve a medir.
2. **El título por niveles:** qué palabra va de acento, cuáles chicas, dónde cortar las líneas, el rótulo y el número. Lo decide la IA de texto que ya lee el relato (§2.9) o reglas, según C2. Lo dibuja Pillow.
3. **Lo que no se tapa:** el alfa de la figura, **lo importante del escenario** (BiRefNet sobre el escenario armado: la torre, la mansión) y la esquina de la duración.
4. **Las 4 opciones (D21):** una por cada plantilla de hoy (`A_der`, `A_izq`, `C_primer_plano`, `B_lugar`). Python ajusta cada una al caso (dónde va el título para no tapar lo importante, el tamaño exacto de la figura). Las 4 miniaturas varían **la composición**; la luz y la semilla, como segunda variación.
5. **Juez local** (opcional, según C4): `gemma3:12b`, con visión, ordena las candidatas al lado de 3 o 4 miniaturas de Yael.
6. **Plan B:** si ninguna de las 4 es la que imaginaba Yael, un **boceto de composición** con dos colores (rojo = figura, azul = título) que Python lee. Se suma solo si hace falta después de C3.

**Qué no:** entrenar una LoRA con las miniaturas. Tienen texto, rehace la imagen entera y pierde los bocetos de Yael (D15), y en la 3060 no entra. Queda para el estilo, más adelante, si E7 no alcanza.

### 2.10 Producción y dev

- **ComfyUI no es parte del deploy.** `make deploy-check` avisa, sin bloquear, si no responde.
- **Respaldo:** `data/prod/miniaturas/` se suma al respaldo de `make deploy`.
- **Lo que viaja en la imagen:** workflows, recetas, `arte.yaml` y la fuente (OFL o gratis con licencia que lo permita).
- **Modelos:** se listan en `config/miniatura/modelos.yaml` con su licencia; al arrancar se avisa si falta alguno.
- **Dev** usa el mismo ComfyUI y guarda en `data/dev/miniaturas/`.

---

## 3. COMMANDS

```bash
make test
make lint
cd frontend && npm test
cd frontend && npx playwright test miniatura        # E2E con MockComfy y LLM mock (Firefox)
cd /mnt/LLM/apps/comfyUI && ./start.sh              # ComfyUI de la casa (:8188)
curl -s localhost:8188/system_stats                 # ¿responde? ¿cuánta VRAM libre?
uv run python scripts/research/790/e1_ilustrar_personaje.py --boceto <png>   # un script por spike (E0–E9)
make dev-status
```

## 4. ESTRUCTURA

```
src/domain/thumbnail.py
src/application/services/miniatura/
  arte.py            → carga y valida arte.yaml
  lectura.py         → thumbnail_read (figura, descripciones, título corto)
  prompts.py         → los prompts de imagen: plantilla del paso (prompts/<paso>.md) + campos de arte.yaml + lo de la historia + variación
  arnes.py           → la tanda: partes (con reuso por hash) → 4 × (reiluminar → componer + máscara → fundir → paste-back) → título → chequeos
  compositor.py      → compone (Pillow, puro)
  titulo/            → contrato + motores pillow, svg (blender, comfy más adelante)
  chequeos.py
  gpu.py             → turno de la GPU
src/infrastructure/adapters/comfy/  client.py · workflow.py · mock.py
src/infrastructure/database/repositories/thumbnail_repository.py
src/presentation/routers/thumbnail_router.py
config/miniatura/   arte.yaml · recetas.yaml · modelos.yaml · workflows/<receta>/ · prompts/
frontend/src/views/miniaturas/   index.ejs · historia.ejs · _seccion_*.ejs · _imagen.ejs
frontend/src/controllers/miniaturas.controller.ts
```

**Recetas de ComfyUI** (una tarea cada una; los candidatos se eligen en los spikes de §10.0):

| Receta | Una sola tarea | Entra → sale | Candidatos | Spike |
|---|---|---|---|---|
| `ilustrar_personaje` | el boceto del personaje → ilustración con el arte, **sobre fondo liso** | PNG boceto + prompt → PNG | ControlNet scribble/lineart SDXL; Qwen-Edit 2511 + Lightning | E1 |
| `recortar` | separar la figura del fondo | PNG → máscara (Python arma el PNG con alfa) | **BiRefNet solo**, sin refinar (workflow `recortar`) | E2 |
| `ilustrar_escenario` | el boceto del escenario → imagen 16:9: **qué va y dónde** | PNG boceto + prompt → PNG | **Qwen-Edit 2511 + Lightning** (workflow `boceto_a_imagen`, el mismo que el personaje) | E3 ✅ |
| *(Python)* `oscurecer` | curva de oscuridad (gamma 1,6, techo 75 %), sin IA | PNG → PNG | — | E3c ✅ |
| `fotografiar_escenario` | el escenario oscurecido → **foto real** de noche, oscura y con niebla, cambiando poco | PNG + prompt → PNG | **Z-Image Turbo img2img, denoise 0,45** (workflow `foto_img2img`) | E3b/E3c ✅ |
| `agrandar` | subir resolución sin cambiar nada | PNG → PNG ×2 | RealESRGAN | E3: **no hace falta para el escenario** (sale de ~1344 × 768); queda por si el personaje lo pide |
| `reiluminar_escenario` | cambiar la luz del escenario a la de la variación, sin tocar su composición | PNG + luz → PNG | Qwen-Edit 2511 (+ LoRA de reiluminado si su licencia es clara); o ajuste de color en Python | E6 |
| `fundir` | integrar el personaje pegado: luz, perspectiva y sombra de contacto, **solo dentro de una máscara** que arma Python; afuera se vuelve a pegar el original | PNG compuesto + máscara + prompt → PNG | Qwen-Edit 2511 + Lightning (+ LoRA Fusion si su licencia se confirma); IC-Light como alternativa | E4 |
| `personaje_texto` / `escenario_texto` | emergencia sin boceto: ilustrar desde la descripción | prompt → PNG | Z-Image Turbo | E1/E3 |

**API (prefijo `/api/v1`):**

| Método | Ruta | Para qué |
|---|---|---|
| `GET` / `PUT` | `/stories/{id}/thumbnail` | leer y guardar los campos (autoguardado) |
| `POST` / `DELETE` | `/stories/{id}/thumbnail/sketches/{personaje\|escenario}` | subir o quitar un boceto (PNG, hasta 20 MB) |
| `PUT` | `/stories/{id}/thumbnail/batches/{n}/images/{i}/chosen` | elegir o soltar (hasta 3) |
| `GET` | `/stories/{id}/thumbnail/batches/{n}/images/{i}.jpg?w=` | la imagen, o su versión chica |
| `GET` | `/stories/{id}/thumbnail/chosen.zip` | las elegidas |

**Jobs nuevos:**
- `thumbnail_read`.
- `thumbnail_build`, con `{solo_composicion: bool}`: «Armar las 4» / «Armar otras 4».

## 5. CODE STYLE

El de la casa: Clean Architecture, sin textos en Python (Spec-620), dataclasses y Pydantic, nombres en castellano en lo nuevo. El compositor, el título y los chequeos son puros, así que se testean sin GPU.

## 6. TESTING STRATEGY

- **Unitarios:**
  - `arte.yaml` (el esquema y los casos que fallan);
  - compositor contra imágenes de referencia (`tests/fixtures/miniatura/`, `UPDATE_FIXTURES=1`), una por variación;
  - el título con acentos, «ñ» y «¿¡»;
  - cada chequeo y cada arreglo automático;
  - `WorkflowTemplate`: todos los `params.yaml` válidos;
  - `ComfyClient` contra un servidor falso;
  - el turno de la GPU.
- **Prompts:**
  - snapshots de `thumbnail_read` y de los prompts de imagen;
  - un test que falla si a un paso de ComfyUI le falta el arte o su variación;
  - otro que falla si `thumbnail_read` no lleva la instrucción de describir el aspecto y no los hechos.
- **Integración:** los jobs con `MockComfy` y el LLM mock, de punta a punta:
  - salen 4 JPG de 1280 × 720 y menos de 2 MB, cada uno con su variación;
  - «otras 4» no vuelve a armar las partes;
  - cambiar un boceto rehace solo esa parte;
  - se eligen hasta 3.
- **Front:**
  - Vitest para vistas, `sin-jerga`, `gramatica-visual`, `no-hardcoded-colors` y `no-native-dialogs`;
  - E2E en Firefox: leer el relato (mock), cambiar la figura, subir los dos bocetos, título, armar (mock), elegir 2 y descargar.
- **Con GPU (manual):** los spikes E0–E9 y la prueba con Yael.

## 7. BOUNDARIES

- **Siempre:**
  - textos en `config/` y vistas;
  - la IA solo con comando explícito y modal;
  - cada parte e imagen trazable;
  - tests en verde y dev al día en cada checkpoint, con la URL de `storymaker.test`.
- **Preguntar antes:**
  - actualizar ComfyUI (no debería hacer falta: la 0.28.3 trae Qwen-Image-Layered y klein);
  - bajar modelos (Qwen-Image-Layered ya aprobado; el resto, con su licencia: Qwen-Image base + InstantX Union, xinsir Union SDXL, FLUX.2 klein 4B, LoRAs de luz, IC-Light);
  - instalar nodos custom;
  - sumar dependencias (resvg en el Dockerfile, `tesseract-ocr-spa`);
  - levantar un ayudante en el host (Blender);
  - tocar el respaldo de `make deploy`;
  - pruebas con API por encima de US$ 0,20;
  - commitear la fuente o imágenes del canal;
  - deploy.
- **Nunca:**
  - una pantalla que emule un editor de imágenes;
  - que la IA invente la forma de las letras;
  - modelos sin licencia comercial clara;
  - tocar audiogen para liberar la GPU;
  - que un GET lance trabajo en la GPU;
  - commitear bocetos, miniaturas o pesos de modelos;
  - borrar tandas sin que Yael lo pida.

---

## 8. DECISIONES

| # | Decisión | Estado |
|---|---|---|
| D1 | ComfyUI es una pieza del arnés: cada workflow hace una sola cosa; Python ordena, compone, pone el título y chequea | Aprobada |
| D2 | **Flujo de carga en 5 pasos → job → 4 imágenes**, sin editor ni capas a la vista | **Usuario, 2026-11-22** |
| D3 | Bocetos por campo del formulario, en PNG (Yael exporta PNG desde SAI2) | **Usuario, 2026-11-22** |
| D4 | La figura principal es **la entidad/monstruo o el protagonista**: la propone la IA y decide Yael. La calabaza solo si se marca (con su imagen de referencia) | **Usuario, 2026-11-22** |
| D5 | Las descripciones dicen cómo es la figura o el lugar, no lo que pasa (no adelantan el final) | Aprobada |
| D6 | **Un solo arte para todo el canal**, en `arte.yaml`: la parte del prompt común a todas las miniaturas, sacada de 5 miniaturas actuales | **Usuario, 2026-11-22** |
| D7 | Una miniatura por historia, con varias tandas de 4 | Aprobada |
| D8 | Lo de diseño que no cambia lo que se ve se arregla solo; lo demás es aviso | Aprobada |
| D9 | Solo modelos con licencia comercial; Flux Kontext dev fuera | **Usuario, 2026-11-22** |
| D10 | GPU por turnos con audiogen, sin tocarlo | **Usuario, 2026-11-22** |
| D11 | El título lo genera el código con la fuente del canal (`pillow` o `svg`); `blender` y `comfy` quedan para más adelante; MCP para diseñar, script para cada miniatura | **Usuario, 2026-11-22** |
| D12 | Blender, si entra, corre en el host con un ayudante | Aprobada |
| D13 | Sin análisis de la «tendencia nueva» | **Usuario, 2026-11-22** |
| D14 | Se descarta el dato de caras (otros nichos) | **Usuario, 2026-11-22** |
| D15 | **Divide y triunfarás:** cada llamada a ComfyUI hace una sola tarea; la secuencia, las entradas, las revisiones entre pasos y qué hacer si algo falla los decide Python, por código. Ningún workflow encadena tareas | **Usuario, 2026-11-22** |
| D16 | Un spike por cada parte del flujo (E0–E9), con su checkpoint, antes de construir | **Usuario, 2026-11-22** |
| D17 | **Un prompt por paso** en `config/miniatura/prompts/<paso>.md`; `arte.yaml` guarda solo lo común (paleta, luz, sentidos, textura, negativos, composición, variaciones, título). El personaje sigue como en E1; los escenarios y fondos son **foto real** | **Usuario y Yael, 2026-11-23** |
| D-Q1 | Botón «Que la IA lea el relato» (job corto); sin tocarlo, todo se completa a mano | **Usuario, 2026-11-22** |
| D-Q2 | Entre las 4 cambian la semilla y una variación del arte (luz, encuadre, lado), de `arte.yaml` | **Usuario, 2026-11-22** |
| D-Q3 | Todo corre en un job; «Armar otras 4» reusa personaje y escenario; cambiar un boceto rehace esa parte | **Usuario, 2026-11-22** |
| D-Q4 | Los dos bocetos son obligatorios; sin boceto, «Armarlo sin boceto» como emergencia | **Usuario, 2026-11-22** |
| D-Q5 | El lado del personaje lo deciden las variaciones de `arte.yaml` | **Usuario, 2026-11-22** |
| D-Q6 | Título precargado con el de la historia, editable, aviso desde 6 palabras | **Usuario, 2026-11-22** |
| D-Q7 | Yael elige de 1 a 3 de las 4 | **Usuario, 2026-11-22** |
| D-Q8 | `arte.yaml` se edita solo en el repo | **Usuario, 2026-11-22** |
| D-Q9 | Campo «Cómo es el lugar», precargado y editable | **Usuario, 2026-11-22** |
| D-Q11–Q14 | Solo la serif (Noto Serif SC ExtraBold); franja de serie opcional, apagada, texto fijo, abajo a la izquierda; una sola figura (segundo boceto si Yael lo pide); acento único naranja con brillo | **Usuario, 2026-11-22** |
| D18 | **El compositor aprende del catálogo de Yael** (sus miniaturas medidas, sin entrenar modelos) y propone **4 composiciones distintas** con las plantillas que mejor encajan. Reemplaza a D-Q2 y D-Q5: las 4 varían la composición (plantilla, lado, encuadre) y, en segundo lugar, la luz | **Usuario y Yael, 2026-11-23** |
| D19 | **El patrón son las miniaturas más recientes** | **Yael, 2026-11-23** |
| D20 | El título es parte de la composición: va por niveles (rótulo, frase, acento, número) y no tapa la figura ni lo importante del escenario | **Usuario, 2026-11-23** |
| D21 | **Las 4 opciones son las 4 plantillas de hoy**, una cada una: `A_der` (figura grande a la derecha, título a la izquierda), `A_izq` (el espejo), `C_primer_plano` y `B_lugar` (figura chica, manda el lugar). La de dos bloques (junio y julio) queda afuera. Sale de C1 | **Usuario, 2026-11-23** |
| D22 | **Las miniaturas salen sin título** (por ahora): Yael decide el color o el filtro del personaje y del ambiente antes de poner el texto, y el texto lo pone ella. La composición igual **deja libre la esquina del título** de cada plantilla. C2 (el título) queda guardado para más adelante | **Yael, 2026-11-23** |
| D23 | **Opción de color en el formulario:** «Color desaturado» o «Blanco y negro». Las piezas se generan siempre en color desaturado; el blanco y negro lo hace Python al final (sin volver a generar) | **Yael, 2026-11-23** (cómo: propuesta de Claude) |
| D24 | Se descarga **solo la imagen compuesta** (sin piezas sueltas) | **Usuario y Yael, 2026-11-23** |
| D25 | **El tono sale del lugar, siempre frío y desaturado:** bosque → verde, mar o agua → azul, y así (toda la imagen, no solo la figura). **Halloween es la excepción:** el personaje en naranja y el fondo gris (C5b). La IA que lee el relato propone el tono según el lugar y Yael lo confirma | **Yael, 2026-11-23** |
| D-Q10 | Las miniaturas sirven para el texto del YAML y, si mejoran en el spike E7, como referencia visual | **Usuario, 2026-11-22** |

**D-Q5:** la opción simple «¿De qué lado va?» quedó como posibilidad si Yael dibuja el escenario con el hueco pensado. No entra de inicio; se suma solo si lo pide en la prueba.

## 9. PREGUNTAS

No quedan abiertas. Lo que falta son **insumos** que pasa el usuario:

| Insumo | Para qué | Bloquea |
|---|---|---|
| ✅ Las miniaturas actuales del canal (llegaron 8, 2026-11-22, en `imagenes/`) | Escribir `arte.yaml` y elegir las referencias visuales | E6, E7 |
| ✅ La fuente: Noto Serif SC ExtraBold (OFL, Google Fonts; falta bajarla) | El título | E8 |
| 1 o 2 pares de bocetos de Yael (personaje + escenario) de una historia | Probar los caminos de boceto a imagen | E1, E3 (y todo lo que sigue) |
| La imagen de referencia de la calabaza | La casilla | S5 (no bloquea antes) |

---

## 10. PLAN (fase PLAN, 2026-11-22; OK de la spec el mismo día)

### 10.0 Spikes: uno por cada parte del flujo (antes de construir)

Cada parte del flujo que pasa por ComfyUI se valida **sola**, con su propio spike, antes de encadenarla. Un spike contesta **una pregunta**, compara pocas variantes y termina con un **sí / no / cambiar el camino**.

**Qué se reusa de cada spike:** el workflow que gana, exportado en formato API con su `params.yaml` y su README, pasa tal cual a `config/miniatura/workflows/`. El script del spike (`scripts/research/790/eN_*.py`) es descartable. La evidencia (números y miniaturas chicas) va en `scripts/research/790/eN/informe.md`, con las imágenes fuera de git.

**Cómo se mide en todos:**
- segundos por llamada (en frío y en caliente) y VRAM pico (`/system_stats` antes y después; `nvidia-smi` en paralelo);
- 3 semillas por variante;
- el **juicio del usuario y de Yael** sobre una grilla de resultados (Claude arma la grilla y anota lo que ve, pero no decide la calidad: ver la memoria «mediciones sin validación del usuario»);
- tope de tiempo por spike: **medio día**. Si se pasa, se para y se reporta.

| Spike | Pregunta | Variantes | Éxito (para pasar al siguiente) | Necesita |
|---|---|---|---|---|
| **E0. Conexión** | ¿El sitio, desde su contenedor, maneja ComfyUI de punta a punta? | Cliente async (`httpx`): subir, encolar, seguir el avance por WebSocket o por *polling* de `/history`, bajar, `/free`, VRAM libre, error de un nodo, ComfyUI apagado, dos pedidos a la vez con el lock | Ida y vuelta desde `narrative-api-dev` con un workflow trivial (cargar y guardar una imagen). Los errores llegan legibles. Se mide cuánto suma la ida y vuelta por llamada. El lock serializa. Se confirma que la 0.28.3 tiene los nodos de Qwen-Image-Layered y de FLUX.2 klein (sin nightly) | Nada (no usa bocetos) |
| **E1. Ilustrar el personaje** | ¿Un boceto de Yael se vuelve un personaje terminado, con el arte, **reconocible** como su dibujo? | (a) Qwen-Edit 2511 + Lightning con instrucción (instalado: va primero); (b) ControlNet Union SDXL de xinsir (scribble/lineart) con 3 fuerzas; (c) Qwen-Image + InstantX Union (soft edge/canny); (d) Z-Image desde texto, como control sin boceto (§1.6). Siempre sobre fondo liso | Con 2 bocetos y 3 semillas, en la mayoría el usuario y Yael reconocen el boceto **y** les sirve la terminación. Se elige una variante y su fuerza | 1–2 bocetos de personaje y un `arte.yaml` borrador (de las 5 miniaturas). Preguntar antes de bajar xinsir Union, Qwen-Image base e InstantX Union |
| **E2. Recortar** | ¿El recorte del personaje de E1 sale limpio (pelo, garras, humo, bordes oscuros)? | (a) BiRefNet; (b) BiRefNet + refinado de borde en Python (erosión y difuminado); (c) Qwen-Image-Layered (el ComfyUI de la casa ya lo soporta; preguntar antes de bajar el modelo) | Sobre las salidas ganadoras de E1, bordes sin halo ni pedazos faltantes, vistos a 100 % y a 120 px. Si (a) o (b) alcanzan, (c) no se prueba | Salidas de E1 |
| **E3. Ilustrar el escenario** | ¿El boceto del escenario se vuelve un fondo 16:9 con el arte, reconocible? ¿Hace falta agrandar? | Las variantes de E1 que pasaron, a 1344 × 768 y a 1024 × 576 + `agrandar` | Reconocible y terminado en la mayoría. Se elige resolución nativa o agrandado | 1–2 bocetos de escenario |
| **E4. Fundir** | Con el personaje pegado por Python sobre el escenario, ¿un inpaint **solo dentro de una máscara automática** lo integra (luz, perspectiva, sombra de contacto) sin tocar el resto? | (a) Qwen-Edit 2511 + Lightning con instrucción sobre el **recorte** de la zona del personaje, pegado de vuelta con la máscara (alfa dilatado + franja de sombra) (§1.6); (a') igual, con LanPaint si quedan costuras; (b) lo mismo + LoRA Fusion, si su licencia se confirma y anda con la 2511; (c) IC-Light (preguntar antes de bajarlo); (d) control: armonizado global sin máscara, para ver el problema del video | El usuario y Yael ven la figura «dentro» del lugar, con sombra, y el fondo queda igual al original fuera de la máscara (diferencia de píxeles ≈ 0). Se fijan la dilatación y la franja de sombra de la máscara | Salidas de E2 y E3 |
| **E5. La máscara** (sin ComfyUI) | ¿Qué máscara da mejores sombras sin pisar el fondo? | Dilatación del alfa (3 tamaños) × franja de sombra (según el lado de la luz de la variación: abajo, abajo-izquierda, abajo-derecha) | Se elige una regla de máscara por variación, para `arte.yaml`. Va junto con E4 | Salidas de E4 |
| **E6. Las 4 variaciones** | ¿Las 4 luces de `arte.yaml` dan 4 imágenes **distintas y de la misma serie**? Como el fondo ya no se toca al fundir, ¿la luz se cambia antes, en el escenario? | (a) `reiluminar_escenario` con Qwen-Edit por variación (con instrucción, o con la LoRA de reiluminado o AnyLight si pasan el control de licencia, usando una imagen de referencia de luz), después fundir; (b) solo ajuste de color en Python sobre el escenario, después fundir; (c) una sola luz y que varíen encuadre y lado | Las 4 se distinguen a 120 px y las 4 parecen del canal al lado de las 5 actuales. Se elige (a), (b) o (c) | Salidas de E4 y las 5 miniaturas |
| **E7. Estilo del canal** | ¿Sumar 1–2 de las 5 miniaturas como **referencia visual** mejora el parecido sin copiar la composición? | E1, E3 y E4 ganadores, con y sin referencia (IP-Adapter en SDXL; imagen de referencia en Qwen-Edit), con 2 pesos | Mejora el parecido a ojo del usuario y de Yael, sin copiar encuadres ni figuras de las referencias. Si no mejora, solo queda el texto de `arte.yaml` | Las 5 miniaturas |
| ~~**E8. Título**~~ → lo reemplaza **C2** (2026-11-23) | ¿El título con la fuente del canal se lee a 120 px sobre las imágenes de E6? ¿Alcanza Pillow o hace falta SVG? | `pillow` con contorno y sombra; `svg` si el estilo de las 5 lo pide | Se lee a 120 px sobre las 4. Decide T8 (resvg en la imagen, sí o no) | La fuente y las salidas de E6 |
| **C1. El catálogo de Yael** (sin ComfyUI; BiRefNet sí) | ¿Se pueden medir sus miniaturas y sacar sus plantillas con rangos? | Figura: BiRefNet (caja, lado, alto, cortada). Texto: Tesseract `spa` (cajas por línea, alto) más heurística de brillo y color para el acento. Agrupar en plantillas, solo con las recientes | Una hoja por plantilla con sus ejemplos y rangos. Yael dice «sí, así compongo». Las medidas, revisadas a ojo en una muestra, no fallan en más de 1 de cada 5 | Las 124 miniaturas (§1.8) |
| **C2. El título a la Yael** (sin ComfyUI) | ¿El sistema arma el título por niveles como ella? | Reglas (palabras de enlace chicas, la última fuerte de acento, números gigantes) contra la IA de texto con ejemplos de sus títulos; dibujado con Pillow y Noto Serif SC ExtraBold | Con los ganchos reales de sus miniaturas recientes, coincide con lo que hizo ella en el acento y en los cortes de línea en la mayoría. Se lee a 120 px | C1 y la fuente |
| **C3. El compositor** | Con las piezas de la torre y de la coneja, ¿4 plantillas distintas dan 4 miniaturas que parecen del canal? | Puntaje de las plantillas (lo que no se tapa con BiRefNet sobre el escenario, el tamaño de la figura, el largo del gancho) → componer → fundir (E4 ronda 2) → título (C2) | Yael las pone **al lado de sus miniaturas reales de esas dos historias**: las 4 parecen suyas y son distintas entre sí | C1, C2, E4 |
| **C5. Color desaturado o blanco y negro** (D23) | ¿El personaje y el escenario salen bien en color desaturado, y el blanco y negro por Python queda igual de bien que el de antes? | Los prompts de E1/E3/E3c con «muted desaturated colors, cold blue-teal tint» y los acentos cálidos solo en las luces reales; la saturación se baja en Python hasta la mediana de las recientes de Yael (40/255); el blanco y negro, en escala de grises | Las 4 plantillas sin título, en las dos versiones, al lado de las de Yael: el usuario y Yael eligen | E1, E3c, C3 |
| **C4. El juez local** (opcional) | ¿`gemma3:12b` con visión elige la misma que Yael? | Ordenar las 4 de C3, con y sin miniaturas de ejemplo | Coincide con Yael en la primera o la segunda. Si no, queda fuera | C3 |
| **E9. La cadena por Python** | ¿Encadenadas por un script de Python (E1 → E2 → E3 → compositor ×4 → E4 ×4 → título), las partes andan juntas, dentro de la VRAM, en un tiempo razonable y por turnos con audiogen? | La cadena completa con los ganadores, en tres condiciones: GPU libre, audiogen cargado sin generar y audiogen generando | Sin errores de memoria. Tiempo total medido (da `estimated_seconds`). `/free` entre pasos alcanza. Con audiogen generando, el script espera y retoma | Todos los anteriores |
| **E10. Layout multirreferencia** (comparación) | ¿Gana una sola llamada que pinta todo desde un layout armado por Python (escenario + personaje ubicado + notas), como el lienzo del video de GeekatPlay? | Qwen-Edit 2511 con 3 referencias (1 = layout, 2 = personaje de E1, 3 = una miniatura del canal como estilo); FLUX.2 klein 4B destilado con las mismas referencias (preguntar antes de bajarlo; en `cw2d-art` se descartó por calidad) | Solo se adopta si gana con claridad a la cadena de E9 en parecido a los bocetos **y** al arte, sin perder control. Si no, queda descartado y anotado (D15) | E1, E3 y E9 |

**Orden:**

```
E0 ──────────────────────────────────────────────┐   (se puede hacer ya: no necesita insumos)
E1 ─▶ E2 ─┐                                       │
E3 ───────┴─▶ E4+E5 ─▶ E6 ─▶ E7 ─▶ E8 ─▶ E9 ─▶ (E10) ─┴─▶ S1…
```

**Desde el 2026-11-23** (D18): `C1 ─▶ C2 ─▶ C3 ─▶ (C4)`, después de E4. E8 lo reemplaza C2. **E6 cambia:** las 4 ya varían la composición; E6 solo decide si además varía la luz (opciones (b) o (c)).

- **E0** no depende de nada.
- **E1 y E3** son independientes entre sí.
- **E7** puede adelantarse apenas estén E1 y E3, si las 5 miniaturas llegan antes.

**Checkpoint por spike:** al terminar cada uno se muestra la grilla y el informe, y se decide **sí / no / cambiar el camino** antes de seguir con el siguiente. Si un spike da «no» en todas sus variantes, se replantea esa parte del flujo antes de gastar en las siguientes. Por ejemplo, si ningún camino respeta el boceto del personaje, se evalúa entrenar una LoRA del estilo de Yael o que el personaje entre «tal cual» y solo se armonice.

### 10.1 Componentes y de qué depende cada uno

```
  E0 conexión ─┐
  E1–E9 spikes ┴─▶ workflows ganadores + arte.yaml v1 + umbral + tiempos      (§10.0, un checkpoint por spike)
        │
        ├──▶ S1 arte + dominio + compositor + título + chequeos   (puro, sin GPU ni IA)
        ├──▶ S2 ComfyUI: cliente + recetas + mock + turno de GPU  (sale de E0 y E9)
        └──▶ S3 IA de texto: rol `miniatura`, leer el relato, prompts de imagen
                     │            │            │
                     └────────────┴────────────┴──▶ S4 la tanda: arnés + jobs + API ──▶ S5 pantalla ──▶ S6 afinar con Yael
                                                         S7 título con estilo (opcional) · S8 producción y docs ──▶ S9 prueba real y deploy
```

| Componente | Capa | Archivos | Depende de |
|---|---|---|---|
| **Arte** | application | `services/miniatura/arte.py`, `config/miniatura/arte.yaml` | — |
| **Dominio** | domain | `domain/thumbnail.py` | — |
| **Repositorio y archivos** | infrastructure | `repositories/thumbnail_repository.py`, `storage/miniaturas.py` (rutas bajo `data/<env>/miniaturas/`), tabla en `init_db()` | Dominio |
| **Compositor** | application | `services/miniatura/compositor.py` | Arte |
| **Título** | application | `services/miniatura/titulo/{contrato,pillow,svg}.py` | Arte (fuente y estilo) |
| **Chequeos y arreglos** | application | `services/miniatura/chequeos.py` | Compositor y título (cajas) |
| **Cliente de ComfyUI** | infrastructure | `adapters/comfy/{client,workflow,mock,fake_server}.py` | — |
| **Recetas** | config + application | `config/miniatura/{recetas,modelos}.yaml`, `config/miniatura/workflows/<receta>/`, `services/miniatura/recetas.py` | Cliente |
| **Turno de GPU** | application | `services/miniatura/gpu.py` | Cliente (`/system_stats`, `/free`) |
| **IA de texto** | application + config | `services/miniatura/{lectura,prompts}.py`, `config/miniatura/prompts/`, rol `miniatura` en `llm_core_definitions.yaml` | Arte, `LLMFactory` |
| **Arnés** | application | `services/miniatura/arnes.py` | Todo lo anterior |
| **Jobs** | presentation | `presentation/thumbnail_jobs.py`, `JobKind.THUMBNAIL_READ/BUILD`, `JobStage` nuevas, `DEFAULT_ESTIMATED_SECONDS` | Arnés, `JobManager` |
| **API** | presentation | `routers/thumbnail_router.py`, `schemas/thumbnail.py`; `job_router` despacha los kinds nuevos | Repositorio, jobs |
| **Pantalla** | frontend | `controllers/miniaturas.controller.ts`, `views/miniaturas/*`, `public/js/miniatura.js`, ítem en `sidebar.ejs`, acción en `relato_acciones.ejs` | API |

### 10.2 Decisiones técnicas de esta fase

| # | Decisión | Por qué |
|---|---|---|
| T1 | **Los jobs de miniatura no pasan por `structure_enabled`** (el apagado por largo de la Spec-740). Usan el perfil por defecto (`LLM_PROFILE`), no el del largo de la historia | Una miniatura no escribe prosa: apagar la IA de un largo no debería apagar sus miniaturas. Se documenta en `job_router` |
| T2 | **El cliente de ComfyUI es asíncrono** (`httpx.AsyncClient`, ya en el proyecto) y sigue el avance por **WebSocket** (`/ws?clientId=`), con `GET /history/{id}` como respaldo si el WebSocket se corta. La librería de WebSocket se elige en S2: `websockets` si hace falta sumarla (preguntar), o *polling* de `/history` cada 1 s, que no suma nada | El `JobManager` corre en el loop de FastAPI; el cliente de `cw2d` es sincrónico (`requests`) |
| T3 | **Un paso de ComfyUI a la vez en todo el sistema** (un `asyncio.Lock` de proceso en `gpu.py`), aparte del «un job por historia» | Dos historias con miniaturas a la vez competirían por la misma GPU |
| T4 | **El reuso de partes es por hash** de lo que las define: boceto (sha256 del archivo) + descripción + prompt final + receta + hash del workflow + la parte de `arte.yaml` que usan. El archivo es `partes/<hash>.png` | «Armar otras 4» y «cambiar un boceto rehace esa parte» salen solos, sin banderas |
| T5 | **Las 4 composiciones se arman en Python** (Pillow), con encuadre y lado de la variación; **por imagen, la GPU solo reilumina el escenario (si E6 lo pide) y funde la zona del personaje** | Menos tiempo de GPU por tanda: 2 partes + 4 × (reiluminar + fundir); armonizados |
| T6 | **Los archivos se sirven desde la API** (`FileResponse`) y el front los pide por el proxy `/api` | Sin carpeta pública nueva en Express; los permisos y las rutas quedan en un solo lugar |
| T7 | **Subida de bocetos:** `UploadFile` de FastAPI (`python-multipart`, ya está). Solo PNG/JPG (se valida con Pillow, no por extensión), hasta 20 MB, **con o sin fondo** (E1: Yael exporta con fondo gris y sin transparencia; Qwen-Edit no la necesita). Se guarda normalizado a PNG RGBA, con el lado mayor en 2048 px como máximo | El proxy de Express ya pasa el cuerpo sin parsear; Pillow descarta archivos que no son imágenes |
| T8 | **resvg entra en el Dockerfile** (binario estático de la release oficial, con la versión fija) solo si el spike E8 confirma que el título necesita `svg`. Si alcanza con `pillow`, `svg` pasa a S7 | No sumar dependencias que no se usan |
| T9 | **`MockComfy`** devuelve PNG fijos por receta (`tests/fixtures/miniatura/comfy/`) con una demora configurable. Lo usan los tests, el E2E y dev con `COMFY_MOCK=1` | E2E y CI sin GPU; también sirve para probar la pantalla en dev con la GPU ocupada |
| T10 | **Los workflows se exportan desde la interfaz de ComfyUI en formato API** y se versionan con su `params.yaml` y un README (qué hace, modelos, de qué plantilla sale), como en `cw2d` | Mantenerlos es reexportar y correr el test que valida `params.yaml` |
| T11 | **El rol `miniatura`** se declara en los cuatro perfiles: en `openai-sol`, GPT-5.6 Sol con `reasoning_effort: none`; en los de Claude, Sonnet 5.5 sin pensar (`between_tools`); en el local, gemma, solo para probar | Igual que se sumaron `guion` y `revisor` |
| T12 | **Las imágenes del canal** (`_arte/`: referencias y calabaza) se cargan a mano en `data/<env>/miniaturas/_arte/`. Un chequeo al arrancar avisa si `arte.yaml` nombra un archivo que no está | Quedan fuera de git (boundary) y fuera de la imagen de Docker |

### 10.3 Slices

Cada slice cierra con `make test` + `make lint` + `npm test` en verde, `make dev-status` en verde (tras `make dev-db` o `make dev-rebuild` si hace falta) y, desde S5, la URL de `storymaker.test` y qué mirar.

#### S0. Los spikes E0–E9 (§10.0). **Bloquean todo.**
- E0 se puede hacer sin insumos; E1–E9 esperan las 5 miniaturas, la fuente y los bocetos.
- Salen: los workflows ganadores en `config/miniatura/workflows/` (formato API + `params.yaml` + README), un `arte.yaml` v1, las reglas de la máscara y el umbral del fundido, si van las referencias visuales, la decisión T8 y los `estimated_seconds`.
- Cada spike tiene su checkpoint con el usuario.

#### S1. Arte, dominio, compositor, título y chequeos (puro)
- **Qué se construye:**
  - `arte.py`: modelo Pydantic de `arte.yaml` (exactamente 4 variaciones, encuadres y lados conocidos, fuente presente) y el `arte.yaml` de los spikes en `config/miniatura/`;
  - `domain/thumbnail.py` (§2.8), la tabla `thumbnail` en `init_db()`, `thumbnail_repository.py` y `storage/miniaturas.py` (rutas, normalización de bocetos, T7);
  - `compositor.py`: escenario de fondo, personaje con encuadre y lado, calabaza si va, y una composición por variación;
  - `titulo/`: contrato, `pillow` y `svg` si T8, con ajuste a 1–2 líneas y cajas por letra;
  - `chequeos.py`: los de §2.7 y los arreglos (zona del título, contorno, corrimiento del personaje, peso del JPG).
- **Tests:**
  - el esquema de `arte.yaml`, con casos que fallan;
  - el compositor contra referencias, una por variación (`UPDATE_FIXTURES=1`);
  - el título con «¿Qué hay en el sótano?», «ñ» y una línea larga;
  - cada chequeo pasa y falla;
  - cada arreglo deja el chequeo en verde;
  - el repositorio, de ida y vuelta.
- **Cierre:** `make dev-db` (tabla nueva). Sin pantalla todavía.

#### S2. ComfyUI desde el sitio
- **Qué se construye:**
  - `adapters/comfy/client.py` (T2): `system_stats`, `upload_image`, `queue`, avance y `wait`, `download`, `free`;
  - errores coloquiales en `core_messages.yaml` (`miniatura.comfy_apagado`, `miniatura.comfy_fallo`);
  - `workflow.py` (`WorkflowTemplate` con `params.yaml`);
  - `mock.py` (T9) y `fake_server.py` (servidor HTTP falso para testear el cliente);
  - `recetas.py`, que lee `recetas.yaml` (receta → workflow, parámetros que toma, VRAM que pide, si recorta) y `modelos.yaml`; al arrancar avisa de modelos o workflows faltantes;
  - `gpu.py` (T3 y §2.6): lock, espera de VRAM con reintento y tope, y `free` después de los pasos grandes;
  - `COMFY_URL` y `COMFY_MOCK` en `config.py`, `.env` y `.env.prod`, y `/health` con `comfy: ok | apagado`.
- **Tests:**
  - cada `params.yaml` apunta a nodos y entradas que existen;
  - el cliente contra el servidor falso (cola, error de ejecución, timeout, WebSocket cortado → `/history`);
  - la espera de GPU (alcanza, espera y alcanza, espera y se rinde);
  - el lock con dos pedidos a la vez.
- **Verifica en dev:** un script corre `escenario_boceto` contra el ComfyUI real desde el contenedor de dev (`host.docker.internal`).

#### S3. IA de texto
- **Qué se construye:**
  - el rol `miniatura` en los perfiles (T11);
  - `lectura.py`: el esquema de §2.9 y el prompt en `config/miniatura/prompts/leer_relato.md`, que lee la historia, la entidad y la última versión del relato;
  - `prompts.py`: arma el prompt de cada paso con **su plantilla de `prompts/` (D17) + los campos de arte que pide + lo de la historia (IA) + variación (código)**; la llamada de texto devuelve `personaje`, `escenario` y las 4 `luces` en inglés;
  - `mock_structured.py`, con las respuestas de los dos esquemas.
- **Tests:**
  - los snapshots `thumbnail_prompts.json` (leer el relato y los prompts de imagen de una historia de fixture, con las 4 variaciones);
  - cada prompt de imagen contiene el estilo, la luz, la paleta, los sentidos, la textura y los negativos del arte;
  - la instrucción de «aspecto, no hechos» está en la lectura;
  - `test_prompts_fuera_del_codigo` sigue en verde.

#### S4. La tanda: arnés, jobs y API
- **`arnes.py`:**
  - `leer(story)` → `ThumbnailInput` propuesto;
  - `armar(thumbnail, solo_composicion)`:
    1. prompts (IA de texto);
    2. partes (reuso por hash, T4; si falta un boceto y Yael eligió «sin boceto», la receta `_texto`);
    3. 4 × (reiluminar el escenario → componer + máscara → fundir → paste-back → revisión con umbral → título → chequeos y arreglos → JPG);
    4. guarda la tanda.
  - Publica etapas y «Imagen n de 4».
- **Jobs:**
  - `JobKind.THUMBNAIL_READ` y `THUMBNAIL_BUILD`, más las `JobStage` (`leyendo`, `prompts`, `personaje`, `escenario`, `componiendo`, `esperando_gpu`);
  - `thumbnail_jobs.py` (como `video_jobs.py`), con el despacho en `job_router` y la validación (sin bocetos y sin «sin boceto» → 422 con mensaje);
  - T1, y `DEFAULT_ESTIMATED_SECONDS` con los valores de E9.
- **API:** el router de §4 (leer y guardar campos, subir y quitar bocetos, elegir, imágenes y zip), con 409 y `X-Job-Id` si hay un job activo, como en el asistente.
- **Tests:**
  - de punta a punta con `MockComfy` y el LLM mock: 4 JPG de 1280 × 720 y menos de 2 MB, cada uno con su variación;
  - «otras 4» no llama a las recetas de partes;
  - cambiar el boceto del escenario rehace solo el escenario;
  - elegir 4 → 422;
  - subir un archivo que no es imagen → 422;
  - con ComfyUI apagado, el job falla con el mensaje coloquial.
- **Verifica en dev con la GPU:** una tanda real de una historia de dev, por la API.

#### S5. La sección «Miniaturas»
- **Front:**
  - `miniaturas.controller.ts` con `/miniaturas` (lista con chips) y `/miniaturas/:storyId` (las 5 secciones, §2.3), con `loadEstimates` y los fragmentos para refrescar sin recargar (como el asistente, Spec-630 B5);
  - `public/js/miniatura.js` (UMD): subida con vista previa, autoguardado con `guardado.js`, elegir hasta 3, y engancharse al job activo al recargar;
  - el modal genérico (`ia-modal.js`);
  - el ítem «Miniaturas» en el menú y «Armar la miniatura» en `relato_acciones.ejs`;
  - los textos en las vistas y `core_messages.yaml`.
- **Tests:**
  - Vitest: `miniatura.js` (límite de 3, subida, errores) y la vista;
  - los guardianes: `sin-jerga` (que cubra `views/miniaturas/`), `gramatica-visual`, `no-hardcoded-colors`, `no-native-dialogs` y `palette-contrast`;
  - E2E en Firefox con mock: el flujo entero, recargar a mitad del job y que se vuelva a enganchar.
- **Checkpoint con Yael en dev:** `https://storymaker.test/miniaturas/<id>`, con una historia real y sus bocetos.

#### S6. Afinar con Yael
- Ajustar `arte.yaml` (textos, variaciones, encuadres, pesos de referencia) mirando las tandas reales al lado de las 5 actuales. Solo config, salvo bugs.
- El camino «Armarlo sin boceto» y la calabaza, con su imagen en `_arte/`.
- **Tests:** snapshots regenerados a propósito, con el diff revisado.

#### S7. Título con estilo (solo si S6 lo pide)
- Una sesión de diseño (Claude por MCP en Blender, o SVG) a partir de lo que pida Yael.
- Motor `blender` (con el ayudante en el host; preguntar antes) y/o `comfy` con OCR (`tesseract-ocr-spa`, preguntar antes).
- Si no hace falta, se cierra sin hacer nada y queda anotado.

#### S8. Producción y docs
- **`deploy_prod.sh`:** respaldo de `data/prod/miniaturas/` junto al de la DB (`tar` con fecha, sin las tandas descartadas si pesan mucho: se decide mirando el tamaño); aviso (sin bloquear) en `deploy-check` si ComfyUI no responde.
- **Producción:** `COMFY_URL` en `.env.prod` y `_arte/` cargado en `data/prod/miniaturas/`.
- **Docs:** `CLAUDE.md` (sección Miniaturas, jobs, tabla, rol, `COMFY_URL`, comandos) y el README de `config/miniatura/` (cómo sumar o reexportar un workflow).

#### S9. Prueba real y cierre
- Yael arma la miniatura de un episodio real en dev, elige y la sube a YouTube. Se ajustan los textos de pantalla.
- PR `feat/spec-790-miniaturas` → `development` → `main`, y `make deploy` con OK.

### 10.4 Qué puede ir en paralelo

- **S1, S2 y S3** no dependen entre sí (dominio y compositor / cliente de ComfyUI / prompts). Se pueden hacer en ramas cortas sobre la rama de la spec, o en serie en ese orden.
- **S4** necesita las tres; **S5**, la API de S4.
- **S6 y S7** dependen del uso real.

### 10.5 Riesgos técnicos de la implementación

| Riesgo | Dónde aparece | Mitigación |
|---|---|---|
| El WebSocket de ComfyUI desde el contenedor | S2 | Respaldo con *polling* de `/history` (T2); se prueba primero desde el contenedor de dev |
| Un workflow exportado cambia de ids de nodo al reexportarlo | S2, S6 | `params.yaml` por nombre de nodo validado en tests; README con cómo reexportar |
| Una tanda larga con uvicorn recargando en dev (Spec-540) | S4, S5 | Avisarlo en la pantalla de dev como hoy; en prod no pasa |
| Imágenes que llenan el disco de prod | S8 | Medir el tamaño de una tanda en S4; si pesa, guardar solo los JPG y las partes de las tandas elegidas |
| El esquema de `arte.yaml` queda chico al afinar | S6 | Campos opcionales con valor por defecto; versión en `version:` |
| La pantalla tienta a sumar controles de edición | S5, S6 | Boundary «nunca» y la revisión del usuario en el checkpoint |

### 10.6 Checkpoints con el usuario

1. Después de **cada spike E0–E9**: la grilla, el informe y «sí / no / cambiar el camino». Sin el OK de E9 no se construye nada.
2. Después de **S4**: una tanda real por la API, vista como imágenes sueltas.
3. Después de **S5**: Yael en `storymaker.test`.
4. Después de **S6**: si hace falta S7.
5. **Deploy** (S9).

## 11. TASKS

Cada tarea se completa en una sesión y tiene su **Acepta** (qué tiene que pasar) y su **Verifica** (cómo se comprueba).

**Al cierre de cada slice:**
- `make test`, `make lint` y `cd frontend && npm test` en verde;
- `make dev-status` en verde (antes, `make dev-db` o `make dev-rebuild` si hace falta);
- desde S5, la URL de `storymaker.test` y qué mirar.

**En todos los spikes:**
- los scripts son descartables y viven en `scripts/research/790/`;
- las imágenes van fuera de git (`scripts/research/790/**/salidas/` en `.gitignore`);
- se preguntan antes las descargas, con su licencia;
- **cada spike cierra con un checkpoint con el usuario y Yael**: grilla, informe y «sí / no / cambiar el camino».

### S0a — Base de los spikes

- [x] **T0.1 — Rama y spec**
  - Acepta: rama `feat/spec-790-miniaturas` desde `development`, con la spec commiteada.
  - Verifica: `git log -1` en la rama.
- [x] **T0.2 — Herramientas comunes de los spikes** (`scripts/research/790/comun.py`)
  - Acepta:
    - un cliente mínimo de ComfyUI (subir, encolar, esperar, bajar, `/free`, `/system_stats`), descartable y sin importar `src/`;
    - medición de segundos y VRAM pico (`/system_stats` + muestreo de `nvidia-smi`);
    - grilla de resultados con Pillow (variante × semilla, etiquetada, más una fila a 120 px);
    - plantilla de `informe.md`.
  - Verifica: corre contra el ComfyUI de la casa con un workflow trivial (cargar y guardar) y arma una grilla.
- [x] **T0.3 — Lugar de los insumos**
  - Acepta:
    - `scripts/research/790/insumos/` en `.gitignore`, con un README de qué va: las 5 miniaturas, la fuente, los bocetos de personaje y escenario, y la calabaza;
    - `data/dev/miniaturas/_arte/` creada.
  - Verifica: `git status` no muestra imágenes.
  - **Hecho (2026-11-22):**
    - las 8 miniaturas están en `insumos/miniaturas_canal/`;
    - la fuente Noto Serif SC ExtraBold quedó en `insumos/fuentes/`: instancia de peso 800 sacada de la variable de Google Fonts (OFL), con el español verificado.

### S0b — Spikes (§10.0)

- [x] **T0.E0 — Conexión** (no necesita insumos)
  - Acepta:
    - desde `narrative-api-dev`, ida y vuelta con un workflow trivial vía `host.docker.internal:8188`;
    - avance por WebSocket, y por *polling* de `/history` si el WebSocket se corta;
    - un error de nodo y ComfyUI apagado dan mensajes legibles;
    - dos pedidos a la vez quedan en serie con un lock;
    - se mide cuánto suma la ida y vuelta por llamada;
    - se confirman en la 0.28.3 los nodos de Qwen-Image-Layered y de FLUX.2 klein.
  - Verifica: `scripts/research/790/e0/informe.md` y checkpoint.
  - **Hecho (2026-11-22):**
    - todo anda igual desde el host y desde `narrative-api-dev`;
    - WebSocket 0,02 s por ida y vuelta, *polling* 1 s como respaldo;
    - los tres errores llegan legibles;
    - el lock serializa;
    - Z-Image en frío llega a 10,9 GB de VRAM (justo), y `/free` la devuelve toda;
    - están todos los nodos, también `ZImageFunControlnet`, nuevo candidato para E1/E3;
    - `websockets` ya está en el contenedor (transitiva).
- [x] **T0.A — `arte.yaml` borrador** (necesita las 5 miniaturas)
  - Acepta:
    - Claude describe las 5 (estilo, luz, paleta, sentidos, textura, encuadres, ubicación y estilo del título) y escribe el borrador de §2.2, con 4 variaciones y reglas de máscara iniciales;
    - el usuario lo corrige.
  - Verifica: OK del usuario al borrador.
  - **Hecho (2026-11-22):** 8 miniaturas analizadas (§1.7) y borrador en §2.2, con Q11–Q14 respondidas.
- [x] **T0.E1 — Ilustrar el personaje**
  - Acepta:
    - variantes (a) Qwen-Edit 2511 con instrucción, (b) xinsir Union SDXL, (c) Qwen-Image + InstantX Union y (d) Z-Image como control;
    - (b) y (c) se bajan solo con OK y licencia verificada;
    - 2 bocetos × 3 semillas, siempre sobre fondo liso;
    - grilla, tiempos y VRAM;
    - el ganador exportado en formato API con su `params.yaml` y README.
  - Verifica: informe `e1/` y checkpoint (¿se reconoce el boceto y sirve la terminación?).
  - **Hecho (2026-11-23, OK del usuario y Yael a `qwen_b`):** 2 bocetos de Yael × 3 semillas × 9 variantes (+ la criatura con otra descripción). Gana `qwen_b` (Qwen-Edit 2511 + Lightning con el arte completo, ~56 s, ~10,5 GB): el único que respeta los detalles del boceto. Z-Image (texto, img2img) y su Fun ControlNet Union 2.1 (bajado con OK, Apache-2.0) siguen la silueta pero pierden los detalles: fuera. No hace falta bajar xinsir ni InstantX. La descripción evita palabras que cambian el material («skeletal» → esqueleto). Informe en `scripts/research/790/e1/informe.md`; el grafo en `config/miniatura/workflows/boceto_a_imagen/` (lo comparte con E3).
- [x] **T0.E2 — Recortar**
  - Acepta:
    - BiRefNet, BiRefNet + refinado en Python, y Qwen-Image-Layered solo si los dos primeros fallan;
    - bordes vistos a 100 % y a 120 px;
    - el ganador exportado.
  - Verifica: informe `e2/` y checkpoint.
  - **Hecho (2026-11-23, OK del usuario y Yael):** BiRefNet solo sale limpio en los 6 personajes de E1 (dedos con sus puntas, orejas, pelo; sin la sombra del piso ni halo), ~0,8 s y ~1,9 GB. El refinado en Python corta la punta de los dedos: fuera. Qwen-Image-Layered no hace falta. Workflow `config/miniatura/workflows/recortar/`; informe en `scripts/research/790/e2/informe.md`.
- [x] **T0.E3 — Ilustrar el escenario**
  - Acepta:
    - las variantes de E1 que pasaron, a 1344 × 768 y a 1024 × 576 + `agrandar`;
    - 2 bocetos × 3 semillas;
    - el ganador exportado, con la resolución elegida.
  - Verifica: informe `e3/` y checkpoint.
  - **Hecho (2026-11-23, OK del usuario y Yael):** gana `qwen_b` a su resolución (~1392 × 752, ~57 s), el más fiel al boceto; a 1024 × 576 Qwen cambia el encuadre y no hace falta agrandar. El ControlNet lite de Z-Image pierde detalle: fuera. Mismo grafo que el personaje (`boceto_a_imagen`, dos recetas). Informe en `scripts/research/790/e3/informe.md`.
  - **E3b/E3c (pedido de Yael: foto real, oscura, con niebla):** Qwen-Edit no sale del estilo del boceto aunque se le pida foto. Gana `previo_45`: Qwen → **curva de oscuridad en Python** → **Z-Image img2img 0,45** con prompt de foto oscura (~1 min 40 s por escenario). Al 45 % Z-Image sigue el brillo de lo que recibe: por eso se oscurece antes. Workflow `config/miniatura/workflows/foto_img2img/`; plantillas `prompts/escenario.md` y `prompts/fotografiar_escenario.md`. Informe en `scripts/research/790/e3b/informe.md`.
- [ ] **T0.E4/E5 — Fundir y la máscara**
  - Acepta:
    - composición tosca en Python;
    - máscara automática con 3 dilataciones × franjas de sombra según el lado de la luz;
    - fundido sobre el **recorte** de la zona con Qwen-Edit 2511 + Lightning, más pegado de vuelta;
    - variantes: LanPaint si quedan costuras, IC-Light (con OK) y, como control, el armonizado global;
    - la diferencia de píxeles fuera de la máscara es ≈ 0;
    - se proponen la regla de máscara y el umbral del fundido.
  - Verifica: informe `e4/` y checkpoint (¿la figura está «dentro» del lugar, con sombra?).
  - **Ronda 1 (2026-11-23), no pasa:** el pegado con máscara deja el fondo idéntico (diferencia 0,0 fuera de la máscara; el control global lo corre 23–33/255), pero Qwen aclara toda la zona y queda un halo con la forma de la máscara, y la «sombra» sale como un círculo de luz. Próxima ronda: igualar la exposición en Python antes de pegar, instrucción más acotada, oscurecer la figura antes de componer. Informe en `scripts/research/790/e4/informe.md`.
  - **Ronda 2 (2026-11-23), ✅ OK del usuario y Yael:** Python oscurece la figura antes de componer (gamma con techo de 0,80, media en 1,7 × la del lugar, con piso de 30), grano σ 4 y sombra dibujada si pisa el piso → Qwen con una instrucción acotada → **igualar la exposición** en el anillo fuera de la máscara → pegar con d1 y un borde de 16 px. Halo de 0,2–1,1/255 (antes se veía a ojo), fondo idéntico y la figura cambia la mitad que en la ronda 1. d2 redibuja de más. Informe en `scripts/research/790/e4b/informe.md`.
- [x] **T0.C1 — El catálogo de Yael**
  - Acepta: las miniaturas medidas (figura con BiRefNet, texto con Tesseract `spa`, colores); plantillas agrupadas **con las recientes** (D19) y sus rangos; una hoja por plantilla; el borrador de `catalogo.yaml`.
  - Verifica: informe `c1/` y checkpoint con Yael («¿así compongo?»).
  - **Hecho (2026-11-23):** la medición automática no pasa (BiRefNet sobre miniaturas terminadas marca la escena o la calabaza; el OCR lee mal), así que las 36 recientes se anotaron a ojo (`c1/anotacion.yaml`). Desde agosto domina la figura grande a la derecha con el título a la izquierda, y el acento es naranja desde septiembre. El usuario elige las 4 plantillas sin la de dos bloques (D21). Informe en `scripts/research/790/c1/informe.md`.
- [ ] **T0.C2 — El título a la Yael**
  - Acepta: reglas contra la IA de texto, comparadas con los ganchos reales de las recientes (acento y cortes de línea); dibujado con Pillow y la ExtraBold; se lee a 120 px.
  - Verifica: informe `c2/` y checkpoint.
  - **Corrido (2026-11-23), esperando el checkpoint:** las **reglas** ganan a qwen2.5:14b y a gemma3:12b locales en todo: acento 10/13, chicas 0,76/0,85, cortes idénticos 8/23 y todos a una línea de distancia como mucho; nunca cambian palabras. Se lee a 120 px. La fuente quedó en ExtraBold y solo con los caracteres latinos (`assets/fonts/NotoSerifSC-ExtraBold.ttf`, 116 KB, OFL). El tamaño del bloque y la bajada van en C3. Informe en `scripts/research/790/c2/informe.md`.
- [ ] **T0.C3 — El compositor**
  - Acepta: 4 composiciones distintas para la torre y la coneja (plantilla + lo que no se tapa + fundido de E4 + título de C2), al lado de las miniaturas reales de esas historias.
  - Verifica: informe `c3/` y checkpoint con Yael.
  - **Corrido (2026-11-23), esperando el checkpoint:** salen 4 composiciones distintas por historia. El título va siempre a una esquina, sin tapar la cara, la figura ni lo importante (BiRefNet sobre el escenario), y nunca bajo la duración. El escenario se espeja cuando la figura taparía lo importante. Fundido: ~80 s por opción (~5,5 min por tanda). **Falta:** la luz (Yael tiene una zona clara detrás y un acento cálido encendido; las nuestras quedan oscuras de punta a punta → E6 pasa a ser lo principal), el título más grande y con contorno, y un recorte de primer plano según la figura. Informe en `scripts/research/790/c3/informe.md`.
- [ ] **T0.C5 — Color desaturado o blanco y negro** (D23)
  - Acepta: piezas en color desaturado; las 4 plantillas sin título (D22) en desaturado y en blanco y negro; la saturación se mide contra las recientes de Yael.
  - Verifica: informe `c5/` y checkpoint con Yael.
  - **C5c (2026-11-23, D25):** el tono por lugar en toda la imagen, por Python (`c5c_tono_lugar.py`): grises → tinte por luminancia en verde, azul o gris frío, a fuerza 0,55 (0,9 quedaba demasiado fuerte), con los acentos cálidos intactos. Se distinguen y siguen siendo fríos. El borrador de tonos, con sus lugares, va a `arte.yaml`. Lo que más separa a las nuestras de las de Yael sigue siendo la luz (E6): ella tiene niebla iluminada y medios tonos; las nuestras son oscuras.
  - **C5b (2026-11-23, pedido de Yael: «el color es el que busca», pero en su #5 el personaje entero va en naranja):** medido en la #5, la figura tiene S 142 y tono ~15°, y el fondo S 1. Es un **tinte en dos partes**, hecho por Python con el alfa de la figura: el fondo gris o desaturado y la figura teñida por luminancia (naranja, rojo o frío, fuerza 0,85), con los acentos tal cual. Sin GPU, ~1 s por imagen. Se propone que el tono sea una opción por miniatura (`c5b_tinte.py`, hojas en `c5/salidas/tinte/`).
  - **Corrido (2026-11-23), esperando el checkpoint:** Qwen y Z-Image salen con un teal fuerte (saturación 97–197/255) aunque se les pida desaturado, así que **Python desatura hasta 40/255 respetando los acentos cálidos** (la calabaza y las velas quedan naranjas). El blanco y negro sale de esa misma imagen. El prompt del personaje nombraba una vela y una calabaza de ejemplo y Qwen las agregó: ya quedó corregido. Informe en `scripts/research/790/c5/informe.md`.
- [ ] **T0.C4 — El juez local** (opcional)
  - Acepta: `gemma3:12b` ordena las 4 de C3; se mide la coincidencia con Yael.
  - Verifica: informe `c4/`.
- [ ] **T0.E6 — Las 4 variaciones**
  - Acepta:
    - (a) reiluminar el escenario con Qwen-Edit, por instrucción, o con LoRA o AnyLight si pasan la licencia;
    - (b) color en Python;
    - (c) una sola luz, variando encuadre y lado;
    - las 4 al lado de las 5 actuales;
    - se ajustan las `variaciones` de `arte.yaml`.
  - Verifica: informe `e6/` y checkpoint (¿4 distintas y de la serie, a 120 px?).
- [ ] **T0.E7 — Referencias visuales**
  - Acepta:
    - E1, E3 y E4 ganadores, con y sin 1–2 miniaturas de referencia (IP-Adapter en SDXL, o referencia en Qwen-Edit), con 2 pesos;
    - se decide si quedan, y con qué peso, en `arte.yaml`.
  - Verifica: informe `e7/` y checkpoint.
- [ ] ~~**T0.E8 — Título**~~ → lo reemplaza T0.C2 (2026-11-23). Lo que sigue queda como referencia:
  - Acepta:
    - `pillow` con contorno y sombra sobre las 4 de E6, y `svg` si el estilo de las 5 lo pide;
    - se lee a 120 px;
    - se decide T8 (resvg en la imagen, sí o no).
  - Verifica: informe `e8/` y checkpoint.
- [ ] **T0.E9 — La cadena por Python**
  - Acepta:
    - un script encadena los ganadores (personaje → recorte → escenario → 4 × (reiluminar → componer + máscara → fundir → pegar) → título → JPG) con `/free` entre pasos;
    - se corre en tres condiciones: GPU libre, audiogen cargado y audiogen generando;
    - sin errores de memoria;
    - tiempo total medido;
    - con la GPU ocupada, el script espera y retoma.
  - Verifica: informe `e9/` (con `estimated_seconds` propuesto) y checkpoint.
- [ ] **T0.E10 — Layout multirreferencia** (comparación, opcional)
  - Acepta:
    - Qwen-Edit 2511 con 3 referencias (layout, personaje y estilo), y klein 4B con OK;
    - comparado contra la cadena de E9.
  - Verifica: informe `e10/` y checkpoint: se adopta solo si gana con claridad; si no, queda descartado y anotado.
- [ ] **T0.C — Cierre de los spikes**
  - Acepta:
    - los workflows ganadores en `config/miniatura/workflows/<receta>/` (formato API + `params.yaml` + README con la plantilla de origen);
    - `config/miniatura/modelos.yaml` con carpeta, archivo, origen, **licencia** y versión de ComfyUI;
    - `scripts/research/790/informe.md` consolidado;
    - decididos T8, la regla de máscara, el umbral del fundido, las referencias visuales y `estimated_seconds`;
    - la spec actualizada con lo que cambió.
  - Verifica: OK del usuario. **Sin este OK no arranca S1.**

### S1 — Arte, dominio, compositor, título y chequeos (puro)

- [ ] **T1.1 — `arte.py` y `arte.yaml`**
  - Acepta:
    - modelo Pydantic de §2.2 con validación (exactamente 4 variaciones, encuadres y lados conocidos, fuente en `assets/fonts/`, archivos de `_arte/` avisados si faltan);
    - el `arte.yaml` de T0.C en `config/miniatura/`.
  - Verifica: tests con el archivo real y casos que fallan.
- [ ] **T1.2 — Dominio y tabla**
  - Acepta:
    - `domain/thumbnail.py` (§2.8);
    - tabla `thumbnail` en `init_db()` (story_id único, FK en cascada);
    - `thumbnail_repository.py` (get/save por historia).
  - Verifica: test de ida y vuelta; `make dev-db`.
- [ ] **T1.3 — Archivos**
  - Acepta:
    - `storage/miniaturas.py`: rutas bajo `data/<env>/miniaturas/`;
    - normalización de bocetos (T7: Pillow valida, PNG RGBA, lado mayor ≤ 2048);
    - hash de partes (T4).
  - Verifica: tests (un archivo que no es imagen → error; mismo boceto y descripción → mismo hash).
- [ ] **T1.4 — Compositor**
  - Acepta:
    - escenario de fondo, personaje con encuadre y lado de la variación, y calabaza si va;
    - máscara de fundido (regla de T0.C);
    - recorte de la zona y pegado de vuelta con borde difuminado.
  - Verifica: referencias de imagen, una por variación (`UPDATE_FIXTURES=1`), y fuera de la máscara la diferencia es 0.
- [ ] **T1.5 — Título**
  - Acepta:
    - contrato (PNG con alfa + cajas por letra);
    - motor `pillow` con la fuente del canal, contorno, sombra, mayúsculas y 1–2 líneas;
    - `svg` si T8 dice sí.
  - Verifica: tests con «¿Qué hay en el sótano?», «ñ» y una línea larga, y las cajas coinciden con lo dibujado.
- [ ] **T1.6 — Chequeos y arreglos**
  - Acepta: los de §2.7, con sus arreglos (zona del título, contorno, corrimiento del personaje, márgenes, peso del JPG ≤ 2 MB a 1280 × 720).
  - Verifica: cada chequeo pasa y falla, y cada arreglo lo deja en verde.

### S2 — ComfyUI desde el sitio

- [ ] **T2.1 — Configuración y mensajes**
  - Acepta:
    - `COMFY_URL` y `COMFY_MOCK` en `config.py`, `.env` y `.env.example`;
    - mensajes `miniatura.*` en `core_messages.yaml` (apagado, falló, esperando la GPU, sin boceto).
  - Verifica: `test_prompts_fuera_del_codigo` en verde.
- [ ] **T2.2 — Cliente**
  - Acepta:
    - `adapters/comfy/client.py`, asíncrono con `httpx` (T2): `system_stats`, `upload_image`, `queue`, avance, `wait` (WebSocket o *polling*, según E0), `download` y `free`;
    - errores con mensaje coloquial;
    - `fake_server.py` para los tests.
  - Verifica: tests contra el servidor falso (cola, error de nodo, timeout, WebSocket cortado).
- [ ] **T2.3 — `WorkflowTemplate`**
  - Acepta: carga `workflow.api.json` + `params.yaml`, aplica solo parámetros declarados y falla con un nodo inexistente.
  - Verifica: un test recorre todos los workflows de `config/miniatura/workflows/`.
- [ ] **T2.4 — Recetas y modelos**
  - Acepta:
    - `recetas.yaml` (receta → workflow, entradas, VRAM que pide, si recorta), `recetas.py` y `modelos.yaml`;
    - aviso al arrancar si falta un modelo o un workflow.
  - Verifica: tests del cargador.
- [ ] **T2.5 — Turno de la GPU**
  - Acepta:
    - `gpu.py`: lock de proceso (T3), espera de VRAM con reintento cada 30 s y tope de 10 min (en `config/`), y `free` después de los pasos grandes;
    - no toca audiogen.
  - Verifica: tests (alcanza; espera y alcanza; se rinde con el mensaje; dos pedidos a la vez).
- [ ] **T2.6 — `MockComfy`**
  - Acepta: devuelve PNG fijos por receta (`tests/fixtures/miniatura/comfy/`) con demora configurable y se activa con `COMFY_MOCK=1`.
  - Verifica: tests del arnés y E2E lo usan.
- [ ] **T2.7 — `/health` y prueba real**
  - Acepta: `/health` informa `comfy: ok | apagado` sin bloquear lo demás.
  - Verifica: desde el contenedor de dev, `ilustrar_escenario` real contra el ComfyUI de la casa.

### S3 — IA de texto

- [ ] **T3.1 — Rol `miniatura`**
  - Acepta: declarado en los perfiles (T11) y `has_role` funciona.
  - Verifica: test de configuración; `/config/active-profile` lo muestra.
- [ ] **T3.2 — Leer el relato**
  - Acepta:
    - `lectura.py`, el esquema de §2.9 y el prompt en `config/miniatura/prompts/leer_relato.md`;
    - lee la historia, la entidad y la última versión del relato, con la instrucción de describir el aspecto y no los hechos;
    - respuesta en `mock_structured.py`.
  - Verifica: snapshot y test de la instrucción.
- [ ] **T3.3 — Prompts de imagen**
  - Acepta:
    - `prompts.py`: la plantilla del paso (`config/miniatura/prompts/<paso>.md`, D17) + los campos de arte que pide + lo de la historia (una llamada de texto: personaje, escenario y las 4 luces en inglés) + variación (código), más los negativos;
    - prompts en `config/miniatura/prompts/`.
  - Verifica:
    - snapshot `thumbnail_prompts.json`;
    - un test que falla si a un paso le falta el arte o su variación.

### S4 — La tanda: arnés, jobs y API

- [ ] **T4.1 — `arnes.leer`**
  - Acepta: arma el `ThumbnailInput` propuesto (figura, motivo, descripciones, título corto) sin pisar lo que Yael ya editó.
  - Verifica: tests con el LLM mock.
- [ ] **T4.2 — Las partes**
  - Acepta:
    - personaje (ilustrar → recortar → agrandar si hace falta) y escenario (ilustrar → agrandar), con reuso por hash (T4);
    - camino «sin boceto» con las recetas `_texto`.
  - Verifica: con `MockComfy`, una segunda corrida no llama a las recetas de partes, y cambiar un boceto rehace solo esa parte.
- [ ] **T4.3 — Las 4 imágenes**
  - Acepta:
    - por variación: reiluminar (según T0.C) → componer + máscara → fundir el recorte → pegar → revisión con umbral (si cambió demasiado, compuesto y nota) → título → chequeos y arreglos → JPG;
    - publica etapas e «Imagen n de 4».
  - Verifica: 4 JPG de 1280 × 720 y menos de 2 MB, cada uno con su variación y fuera de la máscara igual al escenario.
- [ ] **T4.4 — Jobs**
  - Acepta:
    - `JobKind.THUMBNAIL_READ/BUILD`, las `JobStage` nuevas y `thumbnail_jobs.py`;
    - el despacho y la validación en `job_router` (sin bocetos y sin «sin boceto» → 422) y la excepción de `structure_enabled` (T1);
    - `DEFAULT_ESTIMATED_SECONDS` con los valores de E9, y 409 con un job activo.
  - Verifica: tests del router y del job con mocks.
- [ ] **T4.5 — API**
  - Acepta: el router de §4 (campos con autoguardado, subir y quitar bocetos, elegir hasta 3, imágenes con `?w=`, zip), con 409 y `X-Job-Id` si hay un job activo.
  - Verifica: tests de integración (no imagen → 422; elegir 4 → 422; zip con las elegidas).
- [ ] **T4.6 — Tanda real en dev**
  - Acepta: una tanda real de una historia de dev, por la API, con la GPU.
  - Verifica: **checkpoint con el usuario**, con las imágenes sueltas.

### S5 — La sección «Miniaturas»

- [ ] **T5.1 — Lista y menú**
  - Acepta: ítem «Miniaturas» en `sidebar.ejs`; `/miniaturas` con las historias que tienen relato y el chip de estado.
  - Verifica: Vitest de la vista.
- [ ] **T5.2 — Secciones 1 a 4**
  - Acepta:
    - `/miniaturas/:storyId` con «¿Quién va?» (botón de leer el relato, opción, «Cómo es»), personaje, escenario (con «Cómo es el lugar») y título (con la casilla de la calabaza);
    - autoguardado (`guardado.js`) y subida con vista previa (`miniatura.js`, UMD).
  - Verifica: Vitest de `miniatura.js` y de la vista.
- [ ] **T5.3 — Sección 5**
  - Acepta:
    - «Armar las 4» con `ForgeConfirm.ask` y tiempo estimado;
    - modal con etapas;
    - 4 tarjetas (grande, 120 px, notas);
    - elegir hasta 3, «Descargar las elegidas», «Armar otras 4» y tandas anteriores;
    - se engancha al job activo al recargar.
  - Verifica: Vitest.
- [ ] **T5.4 — Desde «El relato»**
  - Acepta: «Armar la miniatura» en `relato_acciones.ejs`.
  - Verifica: Vitest de la vista.
- [ ] **T5.5 — Guardianes**
  - Acepta: `sin-jerga` cubre `views/miniaturas/` y `public/js/miniatura.js`; `gramatica-visual`, `no-hardcoded-colors`, `no-native-dialogs` y `palette-contrast` en verde.
  - Verifica: `npm test`.
- [ ] **T5.6 — E2E**
  - Acepta: en Firefox con mocks: leer el relato, cambiar la figura, subir los dos bocetos, título, armar, elegir 2, descargar, y recargar a mitad del job.
  - Verifica: `npx playwright test miniatura`.
- [ ] **T5.7 — Checkpoint con Yael**
  - Acepta: Yael usa `https://storymaker.test/miniaturas/<id>` con una historia real y sus bocetos.
  - Verifica: lo que diga Yael.

### S6 — Afinar con Yael

- [ ] **T6.1 — Ajustar el arte**
  - Acepta: `arte.yaml` (textos, variaciones, encuadres, máscara, pesos) ajustado mirando tandas reales al lado de las 5 actuales.
  - Verifica: snapshots regenerados a propósito y OK de Yael.
- [ ] **T6.2 — Sin boceto y la calabaza**
  - Acepta: «Armarlo sin boceto» de punta a punta; calabaza con su imagen en `_arte/`.
  - Verifica: tests del arnés y prueba en dev.

### S7 — Título con estilo (solo si S6 lo pide)

- [ ] **T7.1 — Decidir si va**
  - Acepta: con lo de S6, el usuario decide si hace falta.
  - Verifica: si no hace falta, se anota y se cierra S7.
- [ ] **T7.2 — Diseñar el estilo**
  - Acepta: sesión con Yael (MCP en Blender, o SVG), guardada en `config/miniatura/titulo/<estilo>/`.
  - Verifica: OK de Yael.
- [ ] **T7.3 — Motor `comfy` + OCR**
  - Acepta: receta `vestir_titulo` y chequeo de OCR (`tesseract-ocr-spa`, con OK).
  - Verifica: tests con mock y OCR.
- [ ] **T7.4 — Motor `blender`**
  - Acepta: ayudante en el host (con OK) y `render.py` por estilo.
  - Verifica: test marcado para correr solo con Blender.

### S8 — Producción y docs

- [ ] **T8.1 — Respaldo y aviso**
  - Acepta: `deploy_prod.sh` respalda `data/prod/miniaturas/` (con fecha, junto a la DB); `deploy-check` avisa, sin bloquear, si ComfyUI no responde.
  - Verifica: `make deploy-check` en una prueba en seco.
- [ ] **T8.2 — Configuración de prod**
  - Acepta: `COMFY_URL` en `.env.prod` y `_arte/` cargado en `data/prod/miniaturas/` (con OK).
  - Verifica: `/health` de prod después del deploy.
- [ ] **T8.3 — Docs**
  - Acepta:
    - `CLAUDE.md`: sección Miniaturas, jobs, tabla `thumbnail` (dieciocho tablas), rol `miniatura`, `COMFY_URL`, comandos y D15;
    - `config/miniatura/README.md`: cómo sumar o reexportar un workflow y cómo cambiar el arte.
  - Verifica: revisión del usuario.

### S9 — Prueba real y cierre

- [ ] **T9.1 — Episodio real**
  - Acepta: Yael arma, elige y sube la miniatura de un episodio en YouTube; se ajustan los textos.
  - Verifica: la miniatura publicada.
- [ ] **T9.2 — PR**
  - Acepta: `feat/spec-790-miniaturas` → `development` → `main`, con la spec al día (estado, tareas tildadas).
  - Verifica: CI y revisión.
- [ ] **T9.3 — Deploy**
  - Acepta: `make deploy` con OK del usuario.
  - Verifica: `/miniaturas` en `storymaker.prd`.

## 12. RIESGOS

| Riesgo | Mitigación |
|---|---|
| El boceto «se pierde» en la imagen armada | Dos caminos medidos en los spikes E1 y E3; el peso del boceto como parámetro de la receta |
| Las 4 no parecen de la serie | `arte.yaml` + referencias visuales, comparadas con las 5 actuales en los spikes E6–E7 y en S6 |
| El personaje pegado no se integra al escenario | Fundir con máscara (E4, como el video de ILM); agrandar la máscara; IC-Light como alternativa |
| El fundido cambia el fondo o la figura | El fondo no puede cambiar (paste-back fuera de la máscara); la figura, con umbral y vuelta al compuesto |
| La tanda es larga (2–3 partes + 4 × reiluminar y fundir) | Modal con etapas y tiempo; reuso de partes en «otras 4» |
| La GPU ocupada por audiogen | Espera con aviso y falla clara, sin tocar audiogen |
| ComfyUI se actualiza y rompe un workflow | `params.yaml` validado al arrancar y en tests; versión anotada en `modelos.yaml` |
| La pantalla se vuelve un editor | D2 y el boundary «nunca» |

## 13. FUENTES

- vidIQ, [YouTube Thumbnail Design Tips: Best Practices for 2026](https://vidiq.com/blog/post/youtube-thumbnail-design-tips/) (500 videos, todos los nichos).
- BrightBean, [YouTube Thumbnail Best Practices: What the Data Says in 2026](https://brightbean.xyz/blog/youtube-thumbnail-best-practices/) (puntaje propio, no CTR).
- 1of10, [YouTube Thumbnail Trends in 2026](https://1of10.com/blog/youtube-thumbnail-trends-2026/).
- Miraflow, [22 AI Halloween YouTube Thumbnail Prompts](https://miraflow.ai/blog/ai-halloween-youtube-thumbnail-prompts-2026) y [10 YouTube Thumbnail Trends in 2026](https://miraflow.ai/blog/youtube-thumbnail-trends-2026).
- Kapwing, [YouTube Thumbnail Sizes 2026](https://www.kapwing.com/resources/youtube-thumbnail-sizes-2025-aspect-ratios-resolution-and-font/); TechSmith, [YouTube Thumbnail Sizes](https://www.techsmith.com/blog/youtube-thumbnail-sizes/); Adobe Express, [YouTube thumbnails and titles guide](https://www.adobe.com/express/learn/blog/youtube-thumbnails-titles-guide); itechguides ([Test & Compare a 854 × 480](https://www.itechguides.com/?p=876582), una sola fuente).
- Comfy, [Qwen-Image-Layered](https://docs.comfy.org/tutorials/image/qwen/qwen-image-layered); QwenLM, [Qwen-Image-Layered](https://github.com/QwenLM/Qwen-Image-Layered); [arXiv 2512.15603](https://arxiv.org/abs/2512.15603).
- Comfy, [SDKs](https://docs.comfy.org/development/api-development/sdks) y [Run workflows](https://docs.comfy.org/development/run-workflows/overview).
- lllyasviel, [IC-Light](https://github.com/lllyasviel/IC-Light); dx8152, [Qwen-Image-Edit-2509-Relight](https://huggingface.co/dx8152/Qwen-Image-Edit-2509-Relight); Comfy Hub, [Relight Composited Product](https://comfy.org/hub/workflows/relight-composited-product-ae12a241076c/).
- Acly, [krita-ai-diffusion](https://github.com/Acly/krita-ai-diffusion) (evaluado, fuera del flujo).
- Workflows de referencia (§1.6): [DEV: Qwen 2511 masked repaint](https://dev.to/ai-ksk/qwen-2511-masked-repaint-crop-the-masked-block-edit-with-a-reference-paste-it-back-seamlessly-51ac); [RebelTortuga](https://github.com/RebelTortuga/comfyui-free-local-qwen-image-edit); [Eric_Qwen_Edit_Experiments](https://github.com/EricRollei/Eric_Qwen_Edit_Experiments); [axiomgraph](https://github.com/axiomgraph/ComfyUIWorkflow); [LanPaint](https://github.com/scraed/LanPaint); [Comfy: Qwen-Image-Edit-2511](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511); [Comfy: FLUX.2 klein](https://docs.comfy.org/tutorials/flux/flux-2-klein); [Comfy blog: klein 4B](https://blog.comfy.org/p/flux2-klein-4b-fast-local-image-editing); [Qwen-Image InstantX Union ControlNet](https://comfy.org/hub/workflows/qwen-image-instantx-union-controlnet-9829786b38f5/); [InstantX/Qwen-Image-ControlNet-Union](https://huggingface.co/InstantX/Qwen-Image-ControlNet-Union); [Qwen-Image 2.1 Fun ControlNet](https://comfyui-wiki.com/en/news/2026-09-24-qwen-image-2-1-fun-controlnet-union) (no comercial); [Qwen-Edit 2509 Relight](https://comfy.org/hub/models/local/qwen-image-edit-2509-relight/); [QIE-2511-MP-AnyLight](https://huggingface.co/mario-d-robot/QIE-2511-MP-AnyLight); [LightingRemap](https://hapticpaper.github.io/learning_gallery/models/2026-01-17--lightingremap-alpha); [IC-Light: licencias](https://comfyui-wiki.com/en/models/ic-light).
- Videos que pasó el usuario (analizados con `ytctx`): Comfy Compositing, [QWEN AI Compositing in ComfyUI!](https://www.youtube.com/watch?v=np99SCBUNo4); GeekatPlay, [New Visual Compositing Canvas for ComfyUI!](https://www.youtube.com/watch?v=ZUlZ4Ay1t7s); dx8152, [Qwen-Image-Edit-2509-Fusion](https://huggingface.co/dx8152/Qwen-Image-Edit-2509-Fusion).
- Antecedente local: `cw2d-art`, ADR 0001 y `tools/cw2d/comfy.py` en el commit `55c08f9`.

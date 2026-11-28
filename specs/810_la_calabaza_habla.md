# SPEC-810: La calabaza habla (spike local)

**Fecha:** 2026-11-26
**Tipo:** SDD: spikes de video (ComfyUI), sin cambios en el sitio
**Estado:** HECHO (spike cerrado el 2026-11-26 con OK del usuario: «cerralo así»).
**Rama:** `feat/spec-810-calabaza-habla` (desde `development`)
**Usa:** Spec-790 (`ComfyClient`, workflows exportados, D15), Spec-795 (el tablero, para ver los videos), Spec-800 (la cabeza que aprobó Yael).
**Después:** la voz de Lucas (clon en `audiogen`), Lucas actúa (Wan Animate), los reels.

---

## ASSUMPTIONS

1. Lo pidió el usuario el 2026-11-26: mientras Yael y Lucas votan el cuerpo de la calabaza (Spec-800), averiguar **si la calabaza puede hablar en local**: una imagen + un audio → un video con la boca sincronizada, en la RTX 3060 de 12 GB.
2. Es un **spike**: no se construye nada en el sitio. Sale una decisión (qué modelo, a qué resolución, cuánto tarda, cuánto dura un clip) y los workflows exportados, como en la 790.
3. **La cabeza es la de Yael** (`scripts/research/800/h1a3/salidas/ojos_py_70_200.png`: la calabaza de busto con auriculares y micrófono, cuencas negras y pupila violeta). El cuerpo todavía no se eligió: para hablar alcanza con el busto. El ganador de la 800 se prueba después con el mismo workflow.
4. **La voz no se juzga acá.** El audio de prueba es una frase de la calabaza (un intro corto, en rioplatense) con una voz que ya tiene `audiogen` (Qwen3-TTS, corriendo en :8091). La voz de Lucas es otra spec.
5. **Todo local y con licencia comercial** (el canal monetiza). Los tres candidatos la tienen (§3).
6. La GPU es compartida: con las miniaturas de Yael en prod y con `audiogen`. Los spikes corren cuando no hay un job de miniatura en curso, y liberan la VRAM al terminar.
7. Hay que **bajar modelos** (§3, entre 20 y 40 GB por candidato). Hay 349 GB libres en el disco y 62 GB de RAM (los modelos de 14B y 22B no entran enteros en 12 GB de VRAM: ComfyUI carga una parte en la RAM). Se baja solo con OK del usuario.

## OBJECTIVE

Saber, con videos de verdad en el tablero, si la calabaza de la cripta puede hablar en la compu de casa, con qué modelo, a qué calidad y a qué costo de tiempo.

**Éxito (lo juzgan el usuario, Yael y Lucas en el tablero):**
- La boca tallada se mueve con lo que dice: no hace falta lip sync perfecto (es una calabaza), pero sí que se note quién habla y cuándo calla.
- Sigue siendo **la misma calabaza**: el tallado, los ojos (cuencas negras, pupila violeta), los auriculares y el micrófono no cambian ni se deforman.
- Tiene vida: algo de movimiento de cabeza, del micrófono, de la luz; no una foto con la boca animada.
- Un clip de ~10 s sale en un tiempo razonable (a medir; referencia: una tanda de miniaturas tarda ~11 min).

## 1. Qué se prueba

| Spike | Modelo | Qué es | Pregunta |
|---|---|---|---|
| **V1** | **InfiniteTalk** (Wan 2.1 I2V 14B fp8 + InfiniteTalk single) | Hecho para hablar: imagen + audio → video con la boca sincronizada, clips largos por ventanas | ¿Entra en la 3060? ¿Mueve una boca tallada? |
| **V2** | **LTX-2.3** (22B fp8 + LoRA destilada, «imagen + audio → video») | El del video de Morfeo [00:02:47]: genera la escena y la boca con el audio, con prompt de movimiento | ¿Entra (22B, 27 GB)? ¿Da más vida que V1? |
| V3 (solo si V1 y V2 fallan) | Wan 2.2 S2V 14B fp8 | Imagen + audio → video, de Wan | — |

Cada spike, con la misma imagen y el mismo audio:
- **Dos formatos:** horizontal 832 × 480 (el video del canal) y vertical 480 × 832 (los reels).
- **Dos largos:** ~5 s y ~10 s (cuánto aguanta antes de deformarse).
- **Dos prompts de movimiento** (en positivo, D27 de la 790): «habla tranquilo al micrófono, mueve apenas la cabeza» y «se inclina hacia la cámara como contando un secreto».
- Se mide: entra o no (pico de VRAM y de RAM), segundos de cómputo por segundo de video, y se mira: boca, cara igual, ojos, auriculares, micrófono, movimiento, artefactos.

## 1b. El arnés (Python manda; ComfyUI, una tarea por llamada)

Pedido del usuario (2026-11-26): que el proceso de generación esté controlado por Python, no un solo workflow que lo resuelve todo. `scripts/research/810/arnes.py`:

1. **Audio:** mono 16 kHz, volumen normalizado (`loudnorm`), cortado en **tramos por las pausas** (el silencio más tardío que entra en `max_s`, 4 s de arranque).
2. **Imagen:** el encuadre horizontal o vertical se recorta con la cabeza ubicada siempre igual (las zonas de cabeza, ojos y boca salen del color: lo naranja denso y lo violeta).
3. **Un clip por tramo** (ComfyUI, `ClienteVideo`): semilla fija; sube audio e imagen, mide el tiempo y el pico de VRAM, baja el MP4.
4. **Chequeos por clip** (Python, sin IA): la parte de arriba de la cabeza no cambia (diferencia contra el primer cuadro), los ojos siguen oscuros con la pupila violeta (violeta en la zona de los ojos contra el inicio), la boca se mueve con la voz (correlación entre el movimiento de la boca y la energía del audio, cuadro a cuadro) y se mueve lo suficiente. Si no pasa: otra semilla, hasta 2 reintentos; queda todo anotado. Los umbrales arrancan a ojo y se calibran con lo que se vea.
5. **Armar** (ffmpeg): los tramos se unen con un **corte de cámara barato** (los impares en primer plano, zoom 1,25 sobre la cabeza: el «dinamismo» de Omni sin otra llamada) y siempre con **el audio original**, nunca el que devuelva el modelo.
6. **Registro:** `corrida.json` por corrida: tramos, cuadros, semillas, tiempos, VRAM, chequeos y cuál se eligió.

## 2. El audio de prueba
- Una frase de intro de la calabaza (~10 s), escrita con el estilo de `config/video/presentador.yaml`, por ejemplo: «Bienvenidos a mi cripta… Esta noche les traigo una historia que no van a querer escuchar solos. Pónganse cómodos… si pueden.»
- Con Qwen3-TTS de `audiogen` (`POST http://127.0.0.1:8091/v1/audio/speech`, la voz que mejor suene en castellano de las 9), a WAV mono. Si ninguna sirve, el usuario graba la frase con el celular (también vale para ver la boca con una voz real).
- No es la voz de Lucas y no se publica como voz del canal.

## 3. Lo que hay que bajar (con OK)

| Spike | Archivo | Peso | Licencia |
|---|---|---|---|
| V1 | `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ` | 15,5 GB | Apache 2.0 |
| V1 | `wan2.1_infiniteTalk_single_fp16` | 5,1 GB | Apache 2.0 |
| V1 | `lightx2v_I2V_14B_480p_cfg_step_distill_rank64` (LoRA, pocos pasos) | 0,7 GB | Apache 2.0 |
| V1 | `wav2vec2-chinese-base_fp16` + `Wan2_1_VAE_bf16` | 0,4 GB | Apache 2.0 / MIT |
| V1 | `umt5_xxl_fp8` | — | ya está |
| | **V1 total** | **~22 GB** | |
| V2 | `ltx-2.3-22b-dev-fp8` | 27,1 GB | LTX-2 Community (gratis por debajo de US$ 10 M al año; la salida es nuestra) |
| V2 | LoRA destilada 1.1 + upscaler ×2 | 3,5 GB | ídem |
| V2 | `gemma_3_12B_it_fp4_mixed` (codificador de texto) + su LoRA | 9,4 GB | Gemma Terms (uso comercial permitido) |
| | **V2 total** | **~40 GB** | |
| V3 | `wan2.2_s2v_14B_fp8_scaled` + `wav2vec2_large_english` | 17 GB | Apache 2.0 |

Las URLs salen de las plantillas oficiales de ComfyUI (`video_wan2_1_infinitetalk`, `video_ltx2_3_ia2v`, `video_wan2_2_14B_s2v`). Se bajan a `~/LLM/apps/comfyUI/models/<carpeta>/` con `curl -L`, una por una, verificando el tamaño.

## 4. Cómo se corre y se muestra
- Workflows de la plantilla, ajustados y exportados en formato API a `scripts/research/810/workflows/<v>/` (con su `params.yaml`, como `config/miniatura/workflows/`); un script por spike (`v1_infinitetalk.py`, `v2_ltx.py`) que usa `ComfyClient` (D15: una llamada = un clip).
- `ComfyClient` hoy baja imágenes; si el workflow guarda video (`SaveVideo` / MP4), se suma bajar el archivo de video (cambio chico en el cliente, con su test).
- Cada spike **publica en el tablero** una entrega con los clips en MP4 (lado a lado: horizontal y vertical, 5 y 10 s) y en «Qué mirar» lo medido (tiempo, VRAM, RAM). El tope del tablero es 20 MB por archivo: los clips de 10 s a 480p entran holgados.
- Informe por spike en `scripts/research/810/<v>/informe.md`.

## 5. Qué sale (la decisión)
- El modelo elegido (o ninguno: entonces se evalúa la nube alquilada, la idea del evolutivo de la 800).
- Resolución y largo de clip que funcionan, y cuánto tarda.
- Los workflows exportados, listos para la spec que los use (reels o «la calabaza presenta el episodio»).

## 6. Boundaries
- **Siempre:** una tarea por llamada a ComfyUI; liberar la VRAM al terminar; prompts en positivo; videos al tablero, no al chat.
- **Preguntar antes:** bajar cada modelo (§3); probar con la voz de Lucas.
- **Nunca:** modelos sin licencia comercial; subir la calabaza o los audios a un servicio externo; correr un spike mientras hay un job de miniatura en prod.

## 7. Decisiones (2026-11-26)
- **D1** Se baja V1 (~22 GB) ya; V2 después de ver V1 (el usuario: «dale con todo, necesito ver videos»).
- **D2** Voz de prueba: Qwen3-TTS de `audiogen` (voces `eric`, `ryan`, `uncle_fu`, con instrucción de voz grave y misteriosa). No es la voz del canal.
- **D3** Imagen: el busto con la cabeza de Yael (`h1a3/salidas/ojos_py_70_200.png`).
- **D5** Sin nube por ahora (usuario, 2026-11-26: «no tendré por el momento API ni IA frontera comprada»): nada de Omni ni GPU alquilada; el dinamismo sale del arnés local (poses por tramo, dirección de cámara en Python, fondo de cripta) y de comparar InfiniteTalk con LTX-2.3.
- **D4** Hardware medido: Ryzen 5 5600G, 62 GB de RAM, RTX 3060 12 GB en **PCIe 3.0 x16** (el cuello de botella al traer pesos de la RAM). ComfyUI carga en parte y trae el resto de la RAM en cada paso; `wanBlockSwap` y GGUF quedan como palancas si es lento.

## 8. Resultados de V1 (InfiniteTalk, 2026-11-26)
- **Entra:** pico de 6,4–9,7 GB de VRAM (ComfyUI trae de la RAM lo que falta). 832 × 480, 6 pasos con lightx2v.
- **Tiempo:** ~160–175 s de cómputo por segundo de video. Primer tramo (2,8 s): 7,5 min. El intro completo (13,8 s, 5 tramos): 84 min con reintentos, 38 min sin ellos.
- **Se ve:** la cabeza, el tallado y los ojos se sostienen en todos los tramos; la cabeza se mueve apenas; los cortes de plano (impares en primer plano) ocultan las uniones.
- **El chequeo de la boca no está calibrado:** «la boca sigue la voz» (correlación cuadro a cuadro) descartó las 3 semillas en 2 tramos. Causas probables: el micrófono tapa parte de la boca (entra en la zona), y el movimiento puede ir 1–3 cuadros adelantado o atrasado. Siguiente: medir con desfase (±3 cuadros) y sacar el micrófono de la zona; los umbrales se ajustan con lo que digan en el tablero.
- En el tablero: `2026-11-26-calabaza-habla-primera-prueba` y `2026-11-26-calabaza-habla-frase-completa`.

## 9. V1b y V2 (2026-11-26)
- **V1b** (InfiniteTalk + arnés con poses por tramo, cripta y dirección de cámara): 38 min el intro. Opinión de Yael y Lucas sobre el primero: «muy duro, poco dinámico» → poses, cámara y cripta. Después: la boca se mueve más pero le falta expresión; la voz de prueba es mala; el fondo queda lavado (la niebla y la luz de la dirección aclaran los negros).
- **V2** (LTX-2.3 22B fp8, dos pasadas, 832 × 448): **~7 min el intro de 13,8 s** (unos 30 s por segundo de video, 5 veces más rápido que InfiniteTalk), pico de 11,4 GB de VRAM (entra justo). Mueve más el cuerpo; en algunos tramos el tallado se aleja del de Yael.
- Los dos pierden la pupila violeta. El chequeo de la boca sigue sin servir (correlación ~0 o negativa en clips que se ven bien): hay que medirlo de otra forma (desfase, sin el micrófono en la zona) o confiar en el tablero.
- Próximos pasos posibles: hablar en primer plano y pegar la cara (más píxeles para la boca), bocas dibujadas de la hoja de expresiones con Rhubarb Lip Sync, Lucas actúa con Wan Animate; la voz real (Lucas) para juzgar la boca; corrección de color en Python para el fondo.

## 10. V3: la cara en primer plano y pegada (2026-11-26)
- LTX hace hablar solo la cabeza en un cuadrado de 512 × 512 (la boca 3–4 veces más grande) y Python la pega sobre el clip del cuerpo de V2. ~1 min por tramo de LTX + ~30 s de Python.
- **Detectar la cabeza por color no sirve sobre la cripta** (las velas y la luz cálida pasan por naranja): la cabeza se mide en la pose con fondo gris y se lleva al encuadre (`encuadre_rect`, `llevar`), y cuadro a cuadro se **sigue por la imagen** (`seguir`: el corrimiento que menos cambia el recorte en gris), no por el color.
- Resultado: los primeros planos ganan expresión (la sonrisa se estira, la boca cambia de forma) y conservan la cara de Yael; pegado, el tramo 1 se integra bien; el tramo 3 (la pose que se echa atrás, mucho movimiento del cuerpo) falla: escala y auricular fantasma. A mejorar: seguir también la escala, o generar el cuerpo con menos movimiento de cabeza cuando se pega la cara.
- **Opinión del usuario (2026-11-26):** los primeros planos sueltos le gustan mucho; la cara pegada, no (el tramo 3 «claramente quedó mal»); LTX sin pegar, sí.
- **V3b multicámara:** en vez de pegar, cada tramo tiene dos tomas sincronizadas (plano medio y primer plano, mismo audio) y Python corta entre ellas cada 1,5–2,5 s en el momento de menos voz, y en cada unión de tramos (`multicamara`). Sin GPU, segundos. El primer plano se recorta a 16:9 bajando el cuadro (ojos y boca adentro). Es el «dinamismo» de Omni hecho en la edición.

## 11. Conclusión (2026-11-26)

El spike respondió lo que tenía que responder: **la calabaza puede hablar en la compu de casa, con calidad aceptada por el usuario.**

- **Modelo: LTX-2.3** (22B fp8, dos pasadas, 832 × 448; 11,4 de 12 GB). Unos 30 s de cómputo por segundo de video. **InfiniteTalk, descartado** (5 veces más lento y más duro); sus modelos se borraron (~22 GB).
- **Lo que le da vida es el arnés**, no el modelo solo:
  1. una pose de inicio por tramo (Qwen-Edit, con la cabeza protegida) y el fondo de cripta;
  2. **dos tomas por tramo con el mismo audio**: el plano medio y el primer plano de la cara (512 × 512, la boca 3–4 veces más grande, donde gana la expresión);
  3. la **edición multicámara** en Python: cortes entre las dos tomas cada 1,5–2,5 s en los silencios y en cada unión de tramos, con cámara en mano, acercamientos, golpe de zoom en las palabras fuertes y la luz que titila; siempre el audio original.
- **Costo:** un intro de ~14 s, ~12 min (7 del plano medio, 5 de los primeros planos); la edición, segundos.
- **Descartado:** pegar la cara sobre el cuerpo (falla con mucho movimiento; el usuario: «claramente quedó mal»); el chequeo automático de la boca (correlación boca–voz: no distingue, el micrófono tapa la boca) → el juicio es el del tablero; la nube (D5).

**Pasa a las próximas specs:** la voz real (clon o grabación de Lucas; la de prueba es mala); rehacer las poses con el cuerpo que gane en la Spec-800; la pupila violeta que se pierde y la corrección de color del fondo (queda lavado); y construirlo de verdad (comando o sección, junto con los reels), con los workflows de `scripts/research/810/workflows/` (`ltx`) y el arnés (`arnes.py`).

# SPEC-610: Del relato al video: guion de lectura, la calabaza y el mapa de producción

**Fecha:** 2026-09-30
**Tipo:** SDD, feature nueva (después del relato)
**Estado:** SPECIFY, casi cerrado: D1–D16 decididas; quedan dos detalles de la calabaza (§6, D17–D18)
**Rama:** `feat/spec-610-guion-video` (desde `development`, `3753205`). **Se implementa después de la Spec-620** (D12): los prompts nuevos nacen como fragmentos Markdown.
**Depende de:** Spec-620 (prompts en Markdown), Spec-600 (la Voz en Claude), Spec-490 (export para el TTS), Spec-460 (jobs)

---

## PRINCIPIO

**El relato ya está escrito: el guion no lo reescribe.** Lo que se lee en el video es el texto final del relato, el que las usuarias editaron en la web. La IA lo **reparte y lo anota** (cómo se lee, dónde se corta, qué se ve en pantalla) pero no cambia sus palabras. Se verifica sin IA: el texto del guion, unido, es igual al relato.

**Sirve para producir, no para leer.** Cada documento responde lo que pregunta quien lo usa: quien graba (qué leo y cómo), quien hace la voz de la calabaza (qué pego en ElevenLabs) y quien edita (qué va en pantalla, en qué orden y cuánto dura). Nada de teoría.

**La IA nunca corre sola** (máxima del proyecto): armar el paquete es un comando explícito (job) con modal, como el resto.

**Ningún texto de prompt ni mensaje en Python** (Spec-620): los prompts nuevos son fragmentos en `config/prompts_generation/`; la ficha de la calabaza y los textos de la UI viven en `config/`.

---

## 1. OBJETIVO

El usuario sube relatos a un canal de YouTube. Cada episodio es una historia de **12 a 17 minutos**. Los relatos los **leen en voz alta sus hijos**, Yael si quien narra es mujer y Lucas si es hombre, y a veces Vale (D5, D10). Un presentador, **«la calabaza de la cripta»**, personaje 3D con voz propia en ElevenLabs, abre y cierra cada episodio. Hoy todo lo que va entre el relato y el video se hace a mano.

**Qué se construye:** desde el relato final, un **paquete de producción** de tres archivos (D13):

1. **Guion de lectura (PDF), para quien graba:** portada (título, quién lee, duración estimada) y el relato en bloques cortos, con una indicación de lectura por bloque, las palabras a remarcar y las pausas. Letra grande, pensado para leer frente al micrófono.
2. **La calabaza (.txt), para ElevenLabs:** la intro y el outro de ese episodio, listos para pegar, en su tono (§3.3).
3. **Mapa de producción (PDF), para quien edita:** cada momento del relato en orden, con su tiempo estimado, el bloque que se lee, qué va en pantalla (imagen fija, animación mínima o video), el prompt para generarlo, la transición y el sonido sugerido.

**Éxito:**
- Con el guion impreso, los chicos graban el relato sin marcar nada a mano.
- Quien hace la calabaza pega el .txt en ElevenLabs sin retocarlo.
- Quien edita arma el video siguiendo el mapa: cada imagen, animación o video tiene su lugar y su duración.
- El texto leído es **igual** al relato final (verificado sin IA).
- Las imágenes son del mismo mundo: misma paleta, misma luz, mismo tipo de lugar, sin personajes ni criaturas (D14).

---

## 2. LO QUE YA HAY Y LO QUE FALTA

| Pieza | Hoy | Falta |
|---|---|---|
| Relato final | `generated_narrative.content`; «Descargar .md» para el TTS (Spec-490) | **Editarlo en la web** (D4). La Spec-570 sacó el `PUT` de los actos y las usuarias editan el `.md` afuera. |
| Datos de la historia | Escaleta (escenario por acto, hechos), dirección, la amenaza con `reveal_level`, quién narra (`relator`) | Nada: dan los lugares de las imágenes y quién lee. |
| Jobs y modal | `JobManager`, `EventBus`, modal que bloquea | Un tipo nuevo: `video_script`. |
| Salida estructurada | `generate_structured()` con Pydantic, en los dos proveedores | El esquema del paquete. |
| Fragmentos de prompt | (Spec-620) | Los de esta spec. |
| PDF | No hay librería de PDF | Una, elegida en PLAN entre opciones del stack (D2). |

---

## 3. PROPUESTA

### 3.1 Editar el relato en la web (primer slice, D4)

En el panel de la variante: **«Editar el relato»**. Un área de texto por acto con el texto de la variante; se guarda la variante (`PATCH /generated-narratives/{id}`). Sin versiones ni historial. El control de repetición se recalcula sobre lo editado. Si ya hay un paquete, queda marcado **«armado con una versión anterior del relato»** (como `stale` en los actos).

### 3.2 El paquete (job `video_script`, Claude Sonnet 5.5, D3)

Un comando en el panel de la variante: **«Armar el guion para el video»**. Una llamada con salida estructurada (≈ US$ 0,05):

- **Entrada:** el relato final en actos y párrafos numerados; por acto, el escenario y la exposición de la amenaza; la ficha de la calabaza (§3.3); la «biblia visual» fija (§3.4); quién lee (propuesto sin IA desde el narrador, editable); la duración objetivo.
- **Salida por bloque de lectura:** `parrafos` (rango de párrafos, **no texto**: el texto sale del relato, así la IA no puede cambiarlo), `indicacion` (una línea: «despacio, casi en susurro»), `enfasis` (palabras que tienen que existir en el bloque), `pausa` (`ninguna` | `corta` | `larga`).
- **Salida por momento visual** (10–15 por episodio, D9): bloques que cubre, `tipo` (§3.4), `que_se_ve` (una línea en castellano para quien edita), `prompt_imagen` (inglés), `prompt_movimiento` (inglés, solo para animación y video), `transicion`, `sonido`.
- **Intro y outro de la calabaza** (§3.3).
- **Chequeos sin IA:** los rangos cubren todos los párrafos, en orden y sin saltos; cada énfasis existe en su bloque; entre 10 y 15 momentos visuales; ningún prompt menciona personas, siluetas ni criaturas (lista de palabras prohibidas en `config/`); el outro termina en «Buenas noches». Si falla, un reintento; si vuelve a fallar, el job falla con un mensaje claro.

**Duración estimada sin IA:** palabras / ritmo de lectura. Valor inicial **150 palabras por minuto** (lo que midió el TTS de audiogen el 2026-09-30: 2 204 palabras en 14 min 43 s); se calibra con el primer episodio grabado por los chicos. El guion avisa si el episodio pasa de 17 min.

### 3.3 La calabaza de la cripta (D6, D11, D15–D16)

**Ficha fija** en `config/presentador.yaml`: quién es (calabaza tallada con auriculares, ojos violetas que brillan, micrófono de estudio, sótano oscuro), cómo habla (**rioplatense**: «ustedes» al público y voseo cuando le habla a uno solo, «querés», «conozco a algunos de ustedes»), qué hace y los tres outros de ejemplo (abajo) como referencia de tono.

- **Intro (nueva; hoy no la hacen):** corta, ~20–30 s (50–80 palabras), **al estilo del guardián de la cripta**: da la bienvenida a su cripta con humor macabro, juega con el título o el lugar de la historia y presenta **solo la historia**, sin nombrar a quien lee (D16). No adelanta nada que no se sepa en el acto 1.
- **Outro (D6):** ~45–60 s (100–140 palabras), con la forma de los ejemplos:
  1. un comentario sobre lo que hizo el protagonista o lo que pasó, con un giro irónico;
  2. una pulla sarcástica al público («conozco a algunos de ustedes…»);
  3. un «consejo» de supervivencia que da miedo;
  4. una última frase inquietante;
  5. cierra siempre con **«Buenas noches»**.
- **Formato para ElevenLabs Multilingual v2 (D15):** sin etiquetas entre corchetes; el tono se marca con la puntuación (puntos suspensivos para las pausas, frases cortas para el remate).

**Outros de ejemplo (del canal, 2026-09-30):**

> «Me gusta pensar que Alejandro tuvo suerte. No por haber escapado de las criaturas, sino porque llegó al único lugar donde alguien sabía qué hacer. El hombre del almacén preguntó si tenían astas. Eso significa que probablemente ya había visto cosas mucho peores. Así que, si alguien les pregunta qué clase de criatura los persigue, sean precisos. Las diferencias pueden importar. Y si esa persona se tranquiliza al escuchar la respuesta… bueno, ustedes también pueden relajarse. Aunque, yo empezaría a buscar un lugar donde esconderme… solo por las dudas. Buenas noches.»

> «Hay que reconocer que el protagonista hizo bien en tapiar la ventana. Si algo lleva noches corriendo alrededor de tu casa, lo último que querés es tener una ventana abierta hacia el patio. Aunque conoz-co a algunos de ustedes: en lugar de tapiarla, estarían pegados al vidrio grabando al bicho para subir-lo a TikTok. Y probablemente discutirían en los comentarios si es un skinwalker o un perro raro. Pero recuerden algo: si una criatura lleva varios días observándolos desde afuera, quizá también esté aprendiendo de ustedes. Y espero que no haya aprendido a abrir ventanas. Buenas noches.»

> «La próxima vez que algo sobrenatural intente arrastrarlos debajo de la cama, recuerden: no todas las criaturas quieren matarlos. Algunas solamente quieren llevarlos a otro lugar. Lo cual, admito, no es mucho más tranquilizador. Pero si alguna vez sienten que el piso desaparece debajo de ustedes, busquen ayuda. Una mascota puede ser su mejor aliada. Porque allá afuera, algunas cosas conocen caminos alternativos para atra-parlos… caminos que solo los animales pueden ver. Buenas noches.»

### 3.4 Lo que va en pantalla (D9, D14, D7)

**Solo escenarios, insinuantes, sin personajes ni entidades** (D14, el tono que usan hoy los chicos): caminos turbios y desolados, noches oscuras con relámpagos, casas lúgubres vacías, espacios liminales. La amenaza se sugiere con el lugar (marcas en la tierra, una puerta entreabierta, luz que no debería estar), nunca se muestra. **10–15 momentos visuales** por episodio, con los momentos fuertes de cada acto asegurados.

**Tres tipos, intercalados al azar** (D14):

| Tipo | Qué es | Cómo se hace | Prompt |
|---|---|---|---|
| `imagen` | Imagen fija | ComfyUI (Flux schnell / Z-Image Turbo), Gemini o ChatGPT; zoom o paneo lento en la edición | `prompt_imagen` |
| `animacion` | Imagen con movimiento mínimo (niebla que se mueve, lluvia, una luz que titila, un relámpago lejano) | Imagen → video corto con poco movimiento | `prompt_imagen` + `prompt_movimiento` |
| `video` | Clip de 3–5 s (la cámara avanza por un camino, se acerca a una puerta) | Imagen → video | `prompt_imagen` + `prompt_movimiento` |

**El azar lo pone el código, no la IA:** la IA marca qué momentos son fuertes; el código reparte los tipos con una semilla por variante (reproducible: el mismo relato da el mismo mapa), con una mezcla de ~50 % imagen, ~35 % animación y ~15 % video (1–2 videos por episodio), sin dos videos seguidos y con un video o una animación en el momento más fuerte. La proporción vive en `config/`.

**Biblia visual fija** (en `config/`, sin IA): estilo (fotografía nocturna, grano, paleta fría y desaturada, una sola fuente de luz), formato **16:9** y la lista de palabras prohibidas. Va al principio de cada `prompt_imagen`, así todas las imágenes parecen del mismo mundo. Los prompts van **en inglés y en lenguaje natural**, una o dos oraciones sin listas de etiquetas ni pesos: sirven igual en Gemini, ChatGPT, Flux y Z-Image (D7).

**Modelo de video propuesto para ComfyUI** (el usuario pidió que lo proponga la spec): en la RTX 3060 de 12 GB entran dos opciones de imagen → video:
- **LTX-Video 2.x**: 8 GB mínimo y 12 GB recomendado; es el más rápido, y con eso alcanza para la animación mínima ([NVIDIA](https://www.nvidia.com/en-sg/geforce/news/rtx-ai-video-generation-guide/), [Hugging Face](https://huggingface.co/Lightricks/LTX-Video)).
- **Wan 2.2 TI2V-5B** en fp8 o GGUF: usa ~8–10 GB con offload. Da mejor calidad para los clips de video, pero tarda varios minutos por cada 5 s ([computingforgeeks](https://computingforgeeks.com/run-wan-video-generation-locally/), [Next Diffusion](https://www.nextdiffusion.ai/tutorials/how-to-run-wan22-image-to-video-gguf-models-in-comfyui-low-vram)).

**Recomendación:** LTX-Video para `animacion` y Wan 2.2 para los 1–2 `video`. Los `prompt_movimiento` se escriben genéricos (qué se mueve, cuánto y hacia dónde, cámara lenta) para que sirvan en los dos. Instalar los modelos en ComfyUI queda fuera de esta spec (§3.6).

### 3.5 Lo que se entrega

- **Guion de lectura (PDF)** y **mapa de producción (PDF)**: los genera el sitio (D2). La librería se elige en PLAN; siguiendo el stack, las opciones son desde el Core en Python o desde el frontend. Mismo tema visual que el sitio, versión para imprimir.
- **La calabaza (.txt):** intro y outro, separados y rotulados.
- **En el panel de la variante:** «Armar el guion para el video» (job) y, cuando está listo, los tres botones de descarga.
- **Guardado:** tabla `video_script` (variante, JSON del paquete, versión del relato con la que se armó, semilla, fecha). Rearmar reemplaza el anterior.

### 3.6 Lo que no entra

- Generar las imágenes, los videos, el audio o el video final (se hacen afuera). Mandar los prompts directo a ComfyUI queda como evolutivo (§8).
- Reescribir, resumir o «mejorar» el relato para el video.
- Subtítulos con tiempos exactos (los tiempos son estimados).
- Mostrar personajes o criaturas en las imágenes (D14: «al menos por ahora»; si cambia, va en otra spec).
- Simplificar la carga de la historia.

---

## 4. SOBRE REFORZAR EL CONTEXTO PARA LA VOZ FRONTIER

Pregunta del usuario (2026-09-30): si Sonnet supera las expectativas, ¿conviene enriquecer los datos que arma el modelo local para que el frontier escriba todavía mejor?

**Respuesta: queda como evolutivo.** Con la Voz en Claude, el techo pasa a ser la escaleta, que sigue armando gemma. Si aparecen problemas que vienen de ahí, la palanca más barata es **pasar el Planificador a Claude** (una llamada por relato, ~US$ 0,05), no sumar campos. La Spec-600 S1 no mostró problemas de la escaleta en la prosa.

---

## 5. RIESGOS

| Riesgo | Mitigación |
|---|---|
| La IA cambia el texto del relato | No lo devuelve: devuelve rangos de párrafos. |
| Una imagen muestra una persona o una criatura | Biblia visual con «no people, no figures, no creatures», chequeo de palabras prohibidas y reintento. |
| El chiste del outro no tiene gracia o repite los ejemplos | Los ejemplos van como referencia de **forma**, con la instrucción de no repetir frases; el usuario lo lee en S4. |
| Los tiempos estimados no coinciden con la grabación | Ritmo de lectura configurable; se calibra con el primer episodio. |
| El PDF suma una dependencia pesada a la imagen de prod | Se elige en PLAN con el peso de la imagen como criterio. |

---

## 6. DECISIONES

| # | Decisión | Estado |
|---|---|---|
| D1 | ¿El texto que se lee es el relato tal cual o adaptado? | ✅ **Tal cual** (el relato editado). La IA solo reparte y anota. |
| D2 | ¿Cómo sale el PDF? | ✅ (usuario, 2026-09-30) **Lo genera el sitio** («Descargar PDF»). Librería a elegir en PLAN, con opciones. |
| D3 | ¿Qué IA arma el paquete? | ✅ (usuario, 2026-09-30) **Claude Sonnet 5.5** (≈ US$ 0,05 por paquete). |
| D4 | ¿Cómo se edita el relato antes del guion? | ✅ (usuario, 2026-09-30) **En la web**, primer slice. |
| D5 | ¿Quién lee? | ✅ Un lector por episodio según quién narra: **Yael** (mujer), **Lucas** (hombre), a veces **Vale**. |
| D6 | ¿Qué hace la calabaza? | ✅ Personaje 3D que presenta y despide; al final un chiste sarcástico sobre la historia. |
| D7 | ¿Generador de imágenes? | ✅ Gemini / ChatGPT gratis y ComfyUI local (Flux schnell, Z-Image Turbo fp8) → prompts en inglés, lenguaje natural, 16:9. |
| D8 | ¿Duración? | ✅ Un episodio por historia, de 12 a 17 min. |
| D9 | ¿Cuántos momentos visuales? | ✅ (usuario, 2026-09-30) **10–15** por episodio. |
| D10 | ¿Leen en voz alta o TTS? | ✅ **En voz alta** (no hay un TTS gratis con el acento y el tono que buscan). |
| D11 | ¿Cuánto escribe la Voz? | ✅ ~2 000 palabras (hecho en la Spec-600 S1). El TTS lo leyó en 14 min 43 s. |
| D12 | ¿Spec-620 antes? | ✅ (usuario, 2026-09-30) **Sí, la 620 primero.** |
| D13 | ¿Cómo se reparten los documentos? | ✅ (usuario, 2026-09-30) **Tres archivos**: guion de lectura (PDF), la calabaza (.txt), mapa de producción (PDF). |
| D14 | ¿Qué va en pantalla? | ✅ (usuario, 2026-09-30) **Escenarios insinuantes, sin personajes ni entidades** («al menos por ahora»), intercalando **al azar** imágenes fijas, animaciones mínimas y algún video. |
| D15 | ¿Modelo de ElevenLabs? | ✅ (usuario, 2026-09-30) **Multilingual v2 u otro sin etiquetas**: el tono va en la puntuación. |
| D16 | ¿La intro presenta a quien lee? | ✅ (usuario, 2026-09-30) **No**: solo la historia. Intro nueva, corta, al estilo del guardián de la cripta. |
| D17 | Los ejemplos de outro cortan algunas palabras con guion («conoz-co», «subir-lo», «atra-parlos»). ¿Es a propósito para ElevenLabs (forzar la pronunciación o una pausa) y el generador tiene que hacerlo? | **Abierta.** |
| D18 | Los outros de ejemplo no piden like ni suscripción. ¿El pedido («para generar una comunidad más activa») va en el outro generado, o lo dice la calabaza en un cierre fijo aparte? | **Abierta.** |

---

## 7. PLAN (borrador, se detalla en PLAN)

| Slice | Qué |
|---|---|
| S0 | (Spec-620 hecha.) Fragmentos de esta spec, `presentador.yaml`, biblia visual y mezcla de tipos en `config/` |
| S1 | Editar el relato en la web (§3.1) |
| S2 | Job `video_script`: esquema, prompt (fragmentos), chequeos, reparto al azar de tipos, tabla `video_script` |
| S3 | Los tres archivos: PDF del guion, PDF del mapa, .txt de la calabaza; botones en el panel |
| S4 | Un paquete real de punta a punta (con un relato de prod); los chicos graban, quien edita arma el video; ajustes (ritmo de lectura, mezcla de tipos); docs |

---

## 8. EVOLUTIVOS (fuera de esta spec)

- **Mandar los prompts a ComfyUI desde la app** (imágenes y animaciones), vía su API, con los workflows de Flux / Z-Image / LTX / Wan.
- **Mostrar personajes o criaturas** en las imágenes, cuando el canal lo quiera (D14).
- **Reforzar la escaleta** (§4): pasar el Planificador a Claude si la prosa muestra problemas que vienen de ahí.

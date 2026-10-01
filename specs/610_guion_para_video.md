# SPEC-610: Del relato al video: guion de lectura, la calabaza y el mapa de producción

**Fecha:** 2026-09-30
**Tipo:** SDD, feature nueva (después del relato)
**Estado:** SPECIFY cerrado (D1–D18 decididas el 2026-09-30). PLAN después de implementar la Spec-620.
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

**Cómo se ve (D20, maqueta B):** «Editar el relato» abre una pantalla de **un acto a la vez**:
- **Izquierda:** los cinco actos con su nombre de pantalla («Cómo empieza»…), palabras, minutos y si tiene avisos. El acto elegido va resaltado.
- **Centro:** el acto en un cuadro de texto grande con la letra del relato (`.prose-forge`), los párrafos separados por una línea en blanco. Arriba, en gris, «Así terminó el acto anterior» con sus últimas palabras. Abajo, botones para ir al acto anterior y al siguiente con sus nombres.
- **Derecha:** palabras y minutos del acto, los avisos del control de repetición con «Buscar en el texto» (selecciona la frase en el cuadro) y «Regenerar el acto».
- **Arriba de todo:** la duración del episodio. Es una regla de 0 a 20 min con la franja de 12–17 y cada acto en su tramo, a 150 palabras por minuto, y se actualiza mientras se escribe.
- Autoguardado con la notificación flotante del asistente (`_guardado.ejs`). Sin botón «Guardar».

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

  El pedido de like y suscripción no lo escribe la IA: es un **cierre fijo** igual en todos los episodios (D18).
- **Formato para ElevenLabs Multilingual v2 (D15):** sin etiquetas entre corchetes; el tono se marca con la puntuación (puntos suspensivos para las pausas, frases cortas para el remate).

**Outros de ejemplo (del canal, 2026-09-30):**

> «Me gusta pensar que Alejandro tuvo suerte. No por haber escapado de las criaturas, sino porque llegó al único lugar donde alguien sabía qué hacer. El hombre del almacén preguntó si tenían astas. Eso significa que probablemente ya había visto cosas mucho peores. Así que, si alguien les pregunta qué clase de criatura los persigue, sean precisos. Las diferencias pueden importar. Y si esa persona se tranquiliza al escuchar la respuesta… bueno, ustedes también pueden relajarse. Aunque, yo empezaría a buscar un lugar donde esconderme… solo por las dudas. Buenas noches.»

> «Hay que reconocer que el protagonista hizo bien en tapiar la ventana. Si algo lleva noches corriendo alrededor de tu casa, lo último que querés es tener una ventana abierta hacia el patio. Aunque conozco a algunos de ustedes: en lugar de tapiarla, estarían pegados al vidrio grabando al bicho para subirlo a TikTok. Y probablemente discutirían en los comentarios si es un skinwalker o un perro raro. Pero recuerden algo: si una criatura lleva varios días observándolos desde afuera, quizá también esté aprendiendo de ustedes. Y espero que no haya aprendido a abrir ventanas. Buenas noches.»

> «La próxima vez que algo sobrenatural intente arrastrarlos debajo de la cama, recuerden: no todas las criaturas quieren matarlos. Algunas solamente quieren llevarlos a otro lugar. Lo cual, admito, no es mucho más tranquilizador. Pero si alguna vez sienten que el piso desaparece debajo de ustedes, busquen ayuda. Una mascota puede ser su mejor aliada. Porque allá afuera, algunas cosas conocen caminos alternativos para atraparlos… caminos que solo los animales pueden ver. Buenas noches.»

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

- **Guion de lectura (PDF)** y **mapa de producción (PDF)**: los genera el sitio (D2). La librería se elige en PLAN; siguiendo el stack, las opciones son desde el Core en Python o desde el frontend. Diseñados para imprimir en blanco y negro (§3.7.3 y §3.7.4).
- **La calabaza (.txt):** intro y outro, separados y rotulados.
- **En el panel de la variante:** «Armar el guion para el video» (job) y, cuando está listo, «Para el video», que abre la pantalla del paquete (§3.7.2) con un botón de descarga en cada pestaña.
- **Todo se puede corregir en la web (D19):** el guion, la intro y el outro de la calabaza y cada momento del mapa. Los archivos se arman al descargar con lo último guardado; no son la versión que se edita.
- **Guardado:** tabla `video_script` (variante, JSON del paquete, versión del relato con la que se armó, semilla, fecha). Rearmar reemplaza el anterior.

### 3.6 Lo que no entra

- Generar las imágenes, los videos, el audio o el video final (se hacen afuera). Mandar los prompts directo a ComfyUI queda como evolutivo (§8).
- Reescribir, resumir o «mejorar» el relato para el video.
- Subtítulos con tiempos exactos (los tiempos son estimados).
- Mostrar personajes o criaturas en las imágenes (D14: «al menos por ahora»; si cambia, va en otra spec).
- Simplificar la carga de la historia.

### 3.7 La pantalla (D19–D23)

Se diseñó con maquetas interactivas sobre el relato real («No te detengas en el bosque», Spec-600), elegidas por el usuario el 2026-10-01. La implementación sigue las maquetas; si algo no se puede hacer igual, se pregunta.

**Reglas que valen para todo:**
- Tono coloquial y sin jerga (Spec-580). Los textos de la pantalla viven en `config/` (Spec-620).
- Gramática visual de la Spec-550 H9: botón, chip, nota, pista y opción. Paleta solo con los tokens de `theme.css`. En prod los tokens son bronce `#785e1c` como acento y mostaza `#665f00` para los avisos (PR #53).
- **Uno a la vez:** a la izquierda la lista (actos o momentos), en el centro lo que se edita, a la derecha los datos y la ayuda. Abajo, «anterior» y «siguiente» con el nombre de cada uno. En pantallas angostas queda todo en una columna y la lista se recorre de costado.
- **Autoguardado** con la notificación flotante del asistente (`_guardado.ejs`). No hay botón «Guardar».
- **La duración** siempre a la vista, calculada a 150 palabras por minuto y actualizada mientras se escribe.

#### 3.7.1 Corregir el relato (D20)

Es lo descrito en §3.1. Maqueta: https://claude.ai/artifact/UMfHAY9sZYoepnzTBoTgtk (opción B).

#### 3.7.2 El paquete en la web (D19, D22)

Se entra con «Para el video», desde el panel de la variante. Arriba van «Corregir el relato» y «Armar de nuevo». «Armar de nuevo» **pide confirmación**, porque pisa lo que se corrigió en el paquete. Maqueta: https://claude.ai/artifact/QxtwWBw1LakhGBDHkTZaZu

- **Resumen:**
  - quién lee: Yael, Lucas o Vale como opciones, propuesto según quién narra y cambiable;
  - la duración del episodio con la calabaza incluida;
  - cuántos momentos hay de cada tipo.
- **Tres pestañas**, una por persona, cada una con su botón de descarga:
  - **Guion de lectura** (para quien lee):
    - Los actos van a la izquierda y los bloques del acto en el centro.
    - Cada bloque tiene «Cómo se lee» editable y el texto en la letra del relato.
    - **Remarcar:** tocar una palabra la remarca o la desmarca. **Solo esa palabra**, no las iguales. Arrastrar sobre varias remarca la frase entera. Las marcas se guardan como **posiciones** (tramos de palabras dentro del bloque), no como texto que se busca.
    - Entre bloques: «Seguido», «Pausa corta» o «Pausa larga».
    - A la derecha, las frases remarcadas del acto; tocar una la saca.
    - Las palabras del relato no se editan acá, sino en «Corregir el relato».
  - **La calabaza** (para quien hace la voz):
    - Arriba, la ficha del personaje, chica y con su dibujo.
    - Debajo, **la intro y el outro apilados en vertical**, con scroll de página. Son cuadros que crecen con el texto y muestran palabras, segundos y «Copiar para ElevenLabs».
    - El cierre fijo (`cierre_fijo`) se muestra en gris debajo del outro y no se edita acá.
  - **Mapa de producción** (para quien edita):
    - Una **línea de tiempo** de todo el episodio. Cada momento ocupa lo que dura, va coloreado por tipo y la calabaza está en las puntas. Tocar un momento lo abre.
    - A un lado, lo que se lee en ese tramo con su minuto de inicio y fin.
    - Al otro, la ficha editable: tipo (opción imagen, animación o video), «Qué se ve», prompt de la imagen y del movimiento con «Copiar» (el del movimiento solo en animación y video), transición y sonido.
    - Los tipos tienen tokens propios (`--tipo-imagen`, `--tipo-animacion`, `--tipo-video`, `--tipo-calabaza`), distintos del acento y de los estados.

#### 3.7.3 PDF del guion de lectura (D21)

- A4 vertical, pensado para una impresora en blanco y negro: nada depende del color.
- **Portada:**
  - el título, quién lee, cuánto dura, los actos y los bloques;
  - los cinco actos con el minuto en que empieza cada uno;
  - el recuadro «Cómo leer este guion».
- **Hojas de lectura:**
  - Cada acto empieza en hoja nueva y un bloque nunca se parte entre dos hojas.
  - En el margen izquierdo, el número de bloque y el minuto del video.
  - «Cómo se lee» en gris, con ▸.
  - **Texto a 14 pt** en Literata, con interlineado amplio. Lo remarcado sale en negrita subrayada.
  - Pausas: `‖` «respirá» y `‖ ‖` «contá hasta tres».
  - **Margen derecho para anotar** a mano.
  - Al final de cada acto, «Fin del acto N. Sigue: …».
  - En el pie, el título, quién lee y «Hoja N de M».
- Las fuentes son libres y van embebidas en la imagen: Literata (lectura) y Atkinson Hyperlegible (indicaciones). Georgia, la del sitio, no está en Linux.
- Maqueta: https://claude.ai/artifact/Cg5Y1fBNs1nnMmw2bumghR

#### 3.7.4 PDF del mapa de producción (D23)

- A4 vertical, en blanco y negro. Los tipos se distinguen por **trama**: imagen en blanco, animación rayada, video en negro y la calabaza punteada.
- **Primera hoja:**
  - la duración y cuántos momentos hay de cada tipo;
  - la línea de tiempo con las tramas y los minutos;
  - la tabla de todos los momentos (número, desde, qué se ve, tipo, hoja de su ficha y **casilla para tachar**);
  - el recuadro «Cómo usarlo».
- **Una ficha por momento:**
  - número, qué se ve, tipo y con qué se genera;
  - desde y hasta, duración y acto;
  - **«Entra cuando dice…» y «Hasta…»**: las primeras y las últimas 7 palabras del tramo, para ubicarlo en el audio grabado;
  - los prompts (en IBM Plex Mono), la transición y el sonido;
  - el **nombre del archivo** (`NN-lugar.png`, más `.mp4` en animación y video), para que en la carpeta queden en orden;
  - casillas «Imagen» y «Movimiento».
- La intro y el outro van como fichas cortas, con su `.mp3`.
- Las fichas no se parten entre hojas.
- Maqueta: https://claude.ai/artifact/KvnSibYW3DwrZmSGU3JWU7

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
| D3 | ¿Qué IA arma el paquete? | ✅ (usuario, 2026-09-30) **Claude Sonnet 5.5** (≈ US$ 0,05 por paquete). Revisada el 2026-10-01: se evaluó Gemma (ahorro chico, no entra en `num_ctx` 8192 en una llamada, la calabaza es lo más difícil) y el usuario **confirmó Sonnet**. |
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
| D17 | Los ejemplos de outro cortaban algunas palabras con guion («conoz-co»). ¿Es a propósito para ElevenLabs? | ✅ (usuario, 2026-09-30) **No, era un error de escritura.** Los ejemplos de §3.3 quedan corregidos; el generador escribe las palabras enteras. |
| D18 | ¿El pedido de like y suscripción va en el outro generado? | ✅ (usuario, 2026-09-30) **No: es un pedido fijo al final de cada episodio**, igual en todos. El outro generado termina en «Buenas noches». Si se carga su texto en `presentador.yaml` (`cierre_fijo`), el .txt lo agrega al final, rotulado aparte; si no, no se incluye. |
| D19 | Después de armar el paquete, ¿dónde se cambia lo que haga falta (indicaciones, textos de la calabaza, prompts)? | ✅ (usuario, 2026-10-01) **En la web.** Todo el paquete es editable en el sitio y es la única versión; el PDF y el .txt se arman **al descargar** con lo último guardado. Sin .docx: lo que se cambiara afuera no volvería al sitio y se perdería al rearmar. |
| D20 | ¿Cómo es la pantalla para corregir el relato? | ✅ (usuario, 2026-10-01) **Un acto a la vez (maqueta B)**: «más simple visualmente y prolija». Descartadas: corregir sobre el texto corrido (A) y un botón «Editar» con dos modos (C). Detalle en §3.1. |
| D21 | ¿Cómo se ve el PDF del guion de lectura? | ✅ (usuario, 2026-10-01) A4 para impresora en blanco y negro (nada depende del color). Portada (título, quién lee, duración, actos con su minuto, «Cómo leer este guion»); cada acto en hoja nueva; un bloque nunca se parte; número de bloque y minuto del video en el margen izquierdo; «cómo se lee» en gris; lo remarcado en negrita subrayada (palabras o frases, por posición); pausas `‖` corta y `‖ ‖` larga. **Texto a leer en 14 pt** (un punto menos que la primera maqueta, para asegurar que entre) y **margen para anotar a mano** en las hojas de lectura. Fuentes libres embebidas: Literata (lectura) y Atkinson Hyperlegible (indicaciones). Maqueta: https://claude.ai/artifact/Cg5Y1fBNs1nnMmw2bumghR |
| D22 | ¿Cómo se ve y se corrige el paquete en la web? | ✅ (usuario, 2026-10-01) Pantalla «Para el video» con resumen y tres pestañas (guion, calabaza, mapa), en el estilo «uno a la vez» (§3.7.2). Ajustes pedidos sobre la maqueta: remarcar **solo la palabra tocada** y también **frases**; la calabaza con intro y outro **en vertical**; más aire entre bloques y botones. |
| D23 | ¿Cómo se ve el PDF del mapa de producción? | ✅ (usuario, 2026-10-01) Índice con línea de tiempo y checklist, y una ficha por momento con las frases de entrada y salida, los prompts y el nombre del archivo, en blanco y negro con tramas (§3.7.4). |

---

## 7. PLAN (borrador, se detalla en PLAN)

| Slice | Qué |
|---|---|
| S0 | (Spec-620 hecha.) Fragmentos de esta spec, `presentador.yaml`, biblia visual y mezcla de tipos en `config/` |
| S1 | Editar el relato en la web (§3.1, §3.7.1) |
| S2 | Job `video_script`: esquema, prompt (fragmentos), chequeos, reparto al azar de tipos, tabla `video_script` |
| S3 | La pantalla del paquete (§3.7.2) y los tres archivos: PDF del guion (§3.7.3), PDF del mapa (§3.7.4), .txt de la calabaza |
| S4 | Un paquete real de punta a punta (con un relato de prod); los chicos graban, quien edita arma el video; ajustes (ritmo de lectura, mezcla de tipos); docs |

---

## 8. EVOLUTIVOS (fuera de esta spec)

- **Mandar los prompts a ComfyUI desde la app** (imágenes y animaciones), vía su API, con los workflows de Flux / Z-Image / LTX / Wan. **Se decide cuando Lucas, que edita los videos, diga si le resulta más cómodo** que copiar los prompts a mano (usuario, 2026-10-01).
- **Mostrar personajes o criaturas** en las imágenes, cuando el canal lo quiera (D14).
- **Reforzar la escaleta** (§4): pasar el Planificador a Claude si la prosa muestra problemas que vienen de ahí.

# SPEC-610: Del relato al video: guion de lectura, imágenes en orden y mapa de edición

**Fecha:** 2026-09-30
**Tipo:** SDD, feature nueva (después del relato)
**Estado:** SPECIFY, borrador para iterar con el usuario (decisiones abiertas en §6)
**Rama:** a definir (propuesta: `feat/spec-610-guion-video`, desde `development`, **después de cerrar la Spec-600**)
**Depende de:** Spec-600 (la Voz en Claude: el guion arranca solo si la prosa convence), Spec-490 (export para el TTS), Spec-460 (jobs)

---

## PRINCIPIO

**El relato ya está escrito: el guion no lo reescribe.** Lo que se lee en el video es el texto final del relato, el que las usuarias editaron. La IA lo **reparte y lo anota** (quién lee, cómo, dónde se corta, qué imagen va) pero no cambia sus palabras. Se verifica sin IA: el texto del guion, unido, es igual al relato.

**Sirve para producir, no para leer.** El guion responde lo que preguntan quienes graban y editan: qué leo, cómo lo leo, qué imagen pongo, cuánto dura. Nada de teoría.

**La IA nunca corre sola** (máxima del proyecto): armar el guion es un comando explícito (job) con modal, como el resto.

---

## 1. OBJETIVO

El usuario sube relatos a un canal de YouTube. Los narran sus **hijos**, en la voz de un presentador, **«la calabaza de la cripta»**, que abre y cierra cada video. Hoy, entre el relato y el video, todo se hace a mano: repartir la lectura, marcar pausas, pensar qué imagen va en cada momento, escribir los prompts, armar el orden para el editor.

**Qué se construye:** desde el relato final, un **paquete de producción**:

1. **Guion de lectura imprimible (PDF):** intro de la calabaza, el relato en bloques cortos con quién lee, cómo (ritmo, pausa, tono, énfasis) y marcas de corte, y el outro. Letra grande, pensado para leer frente al micrófono.
2. **Prompts de imágenes en orden:** una imagen por momento del relato, numeradas, con un estilo visual común (la misma cara para el narrador, el mismo lugar, la misma paleta en todas).
3. **Mapa de edición:** tabla con cada bloque, su duración estimada, la imagen que va, la transición y la música o el sonido sugerido. Es lo que tiene a mano quien edita.

**Éxito:**
- Con el guion impreso, los chicos graban el relato sin tener que marcar nada a mano.
- Quien edita arma el video siguiendo el mapa: cada imagen tiene su lugar y su duración.
- El texto leído es **igual** al relato final (verificado sin IA).
- Las imágenes se ven como una misma historia: el narrador, el lugar y la amenaza no cambian de cara entre una y otra.

---

## 2. LO QUE YA HAY Y LO QUE FALTA

| Pieza | Hoy | Falta |
|---|---|---|
| Relato final | `generated_narrative.content`; «Descargar .md» para el TTS (Spec-490) | **Editarlo en la UI.** La Spec-570 sacó el `PUT` de los actos y las usuarias editan el `.md` afuera. El guion tiene que salir del texto editado. |
| Datos de la historia | Escaleta (escenario, en escena, hechos por acto), personajes con parentesco, la amenaza (`entities`, `reveal_level`), dirección | Nada: son la materia de la «biblia visual» (cómo se ven el narrador, el lugar y la amenaza). |
| Jobs y modal | `JobManager`, `EventBus`, modal que bloquea | Un tipo nuevo: `video_script`. |
| Salida estructurada | `generate_structured()` con Pydantic, en los dos proveedores | El esquema del guion. |
| PDF | No hay librería de PDF en el proyecto | Ver D2: página imprimible (el navegador la guarda como PDF), sin dependencias nuevas. |

---

## 3. PROPUESTA

### 3.1 Editar el relato antes del guion (prerrequisito)

En el panel de la variante: **«Editar el relato»**. Un área de texto por acto con el texto de la variante; se guarda la variante (`PATCH /generated-narratives/{id}`). Sin versiones ni historial: la edición es del texto final. El control de repetición se vuelve a calcular sobre lo editado. Si ya hay un guion, queda marcado **«armado con una versión anterior del relato»** (como `stale` en los actos).

### 3.2 El guion (job `video_script`)

Un comando en el panel de la variante: **«Armar el guion para el video»**. Una sola llamada con salida estructurada (o una por acto si el relato no entra, ver §5):

- **Entrada:** el relato final dividido en actos y párrafos (numerados), la biblia visual armada **sin IA** desde la historia (narrador y su parentesco, personajes, escenarios, la amenaza según `reveal_level`, época y lugar), el lector del episodio (D5) y la duración objetivo (12–17 min, D8).
- **Salida por bloque:** `parrafos` (rango de párrafos del relato, **no texto**: el texto se toma del relato, así la IA no puede cambiarlo), `indicacion` (una línea: «despacio, casi en susurro», «pausa larga antes de la última frase»), `enfasis` (palabras a remarcar, que tienen que existir en el texto), `corte` (`seguido` | `pausa` | `fundido` | `negro`), `imagen` (número).
- **Salida por imagen:** `prompt` (en inglés si el generador lo pide, D7), `que_se_ve` (una línea en castellano para quien edita), `camara` (plano general, detalle, primer plano), `sonido` (ambiente sugerido).
- **Intro y outro de la calabaza** (D6), como texto listo para su voz de ElevenLabs.
- **Chequeos sin IA:** que los rangos cubran todos los párrafos, en orden y sin saltos; que cada énfasis exista en su bloque; que cada imagen se use. Si falla, un reintento; si vuelve a fallar, el job falla con un mensaje claro.

**Duración estimada sin IA:** palabras del bloque / ritmo de lectura (≈ 130 palabras por minuto para una lectura pausada, ajustable). Un relato de ~3 200 palabras da **~25 minutos** de video: ver D8.

### 3.3 Lo que se entrega

- **Página del guion** (`/relatos/{id}/guion`), pensada para imprimir (CSS de impresión): portada con título, duración total y quién lee; intro; el relato en bloques con número, lector, indicación y énfasis en negrita; marcas de corte e imagen en el margen; outro. «Imprimir o guardar como PDF» usa el diálogo del navegador.
- **Prompts de imágenes:** en la misma página, sección aparte, y **«Descargar prompts (.txt)»**: uno por línea con su número, para pegarlos en orden en el generador.
- **Mapa de edición:** tabla (bloque, tiempo de inicio estimado, duración, imagen, transición, sonido) en la página y **«Descargar mapa (.csv)»** para abrirlo en una planilla.
- **Guardado:** tabla `video_script` (variante, JSON del guion, versión del relato con la que se armó, fecha). Regenerar el guion lo reemplaza.

### 3.4 Lo que no entra

- Generar las imágenes, el audio o el video (se hacen afuera, con las herramientas que el usuario ya usa).
- Reescribir, resumir o «mejorar» el relato para el video.
- Subtítulos con tiempos exactos (los tiempos son estimados; los exactos salen de la grabación).
- Cargar la historia de otra forma (la idea de «simplificar la carga» queda para otra spec, si la Spec-600 muestra que con Claude alcanzan menos preguntas).

---

## 4. SOBRE REFORZAR EL CONTEXTO PARA LA VOZ FRONTIER

Pregunta del usuario (2026-09-30): si Sonnet supera las expectativas, ¿conviene enriquecer los datos que arma el modelo local para que el frontier escriba todavía mejor?

**Respuesta: queda como evolutivo, y se decide con lo que muestre la Spec-600 S1.**
- Con la Voz en Claude, el techo pasa a ser la **escaleta**, que sigue armando gemma. Si en la lectura de S1 los problemas vienen de ahí (hechos flojos, frases entre comillas que terminan en diálogo, lo que no se cuenta mal ubicado), la palanca más barata no es sumar datos: es **pasar el Planificador a Claude** (1 llamada por relato, ~US$ 0,05) y dejar el resto local. La plataforma ya lo permite (`provider` por rol).
- Si los problemas no vienen de la escaleta, sumar datos no ayuda y alarga el formulario (máxima de la Spec-530: cada campo nuevo tiene que prevenir un error visto).
- El guion de esta spec **sí** usa esos datos (la biblia visual sale de la escaleta y la amenaza), así que mejora solo si mejora la escaleta.

---

## 5. RIESGOS

| Riesgo | Mitigación |
|---|---|
| La IA cambia el texto del relato | No lo devuelve: devuelve rangos de párrafos. El texto sale del relato. |
| Imágenes inconsistentes entre sí (el narrador cambia de cara) | Biblia visual fija al principio de cada prompt (estilo, personaje, lugar), armada sin IA desde la historia. |
| El relato de ~3 200 palabras no entra con su salida en una llamada del modelo local | El guion va con Claude (D3). Si fuera local, una llamada por acto. |
| Un video de ~25 min es largo para lectores chicos | D8: grabar por actos o partes; el mapa marca los cortes naturales entre actos. |
| La amenaza aparece en una imagen antes de lo que el relato la muestra | Cada imagen recibe el `reveal_level` y la exposición del acto (Spec-450), igual que la Voz. |

---

## 6. DECISIONES ABIERTAS (de a una)

| # | Decisión | Recomendación |
|---|---|---|
| D1 | ¿El texto que se lee es el relato tal cual o una versión adaptada para el video? | **Tal cual** (el relato editado). La IA solo reparte y anota. |
| D2 | ¿Cómo sale el PDF? | **Página imprimible** y «guardar como PDF» del navegador: cero dependencias, mismo tema. Alternativa: generar el PDF en el servidor (librería nueva). |
| D3 | ¿Qué modelo arma el guion? | **Claude Sonnet 5.5** (≈ US$ 0,05–0,10 por guion): un relato entero de entrada y prompts de imagen en inglés salen mejor. Depende de cómo cierre la Spec-600. |
| D4 | ¿La edición del relato en la UI entra en esta spec? | **Sí, como primer slice**: sin ella el guion sale de un texto que no es el final. |
| D5 | ¿Cuántos chicos leen y cómo se reparten? | ✅ (usuario, 2026-09-30) **Un solo lector por episodio**, según quién narra: **Yael** si el narrador es mujer, **Lucas** si es hombre; a veces **Vale**. La calabaza tiene **su propia voz en ElevenLabs**. → El guion propone el lector desde el narrador de la historia y se puede cambiar; los bloques no llevan lector. Intro y outro salen aparte, como texto para ElevenLabs. |
| D6 | Intro y outro de la calabaza: ¿texto fijo con el título, o lo escribe la IA en su personaje para cada relato? | ✅ (usuario, 2026-09-30) **La calabaza de la cripta** es un personaje 3D: calabaza tallada con auriculares, ojos violetas que brillan, micrófono de estudio, fondo oscuro. Presenta y despide cada episodio. Al final hace **un chiste sarcástico sobre la historia** y pide like y suscripción «para generar una comunidad más activa». → Ficha fija en `config/presentador.yaml` (quién es, cómo habla, qué pide al final); la IA escribe intro (~20–30 s, sin adelantar el final) y outro (~30 s, con el chiste) para cada relato. Su imagen no se genera: ya existe. |
| D7 | ¿Con qué generador se hacen las imágenes y en qué formato? | ✅ (usuario, 2026-09-30) Los chicos usan **Gemini o ChatGPT gratis**; además hay **ComfyUI** en esta PC (compartido por proxy reverso) con **Flux schnell** y **Z-Image Turbo fp8**. → Prompts en **inglés, en lenguaje natural** (una o dos oraciones descriptivas, sin listas de etiquetas ni pesos): sirven igual en los tres. 16:9. El tope gratis de Gemini/ChatGPT hace que convenga ComfyUI para la tanda completa (ver D9). Generar las imágenes desde la app vía ComfyUI queda como evolutivo. |
| D8 | ¿Videos largos (~25 min, el relato entero) o partidos? | ✅ (usuario, 2026-09-30) **Un episodio por historia, de 12 a 17 minutos.** → El guion muestra la duración estimada y avisa si pasa de 17 min, con cuántas palabras sobran por acto (las usuarias ya recortan al editar). Ver D10. |
| D9 | ¿Cuántas imágenes por relato? | **Una cada ~30–45 s de lectura** (≈ 20–30 en un episodio de 12–17 min), con los momentos fuertes de cada acto seguro. Se puede bajar si generar tantas es mucho trabajo. |
| D10 | ¿Los chicos leen el relato en voz alta o lo sintetiza `audiogen` (Spec-490)? | ✅ (usuario, 2026-09-30) **Lo leen en voz alta**: no hay un TTS gratis con la precisión, el acento y el tono que buscan. → El guion impreso es para leer frente al micrófono: letra grande, indicaciones de lectura, pausas y énfasis a la vista. La calabaza sí va por ElevenLabs. |
| D11 | Un relato de hoy (~3 200 palabras) dura **~25 min** leído a 130 palabras por minuto: pasa el tope de 17. ¿Qué se ajusta? | ✅ (usuario, 2026-09-30) **Que la Voz escriba menos, para un promedio de 15 minutos** (≈ 1 950 palabras a 130 por minuto). Se hace en la Spec-600 S1, así Sonnet se mide ya con la extensión final. El ritmo de 130 se calibra con el primer episodio grabado. |

---

## 7. PLAN (borrador, se detalla en PLAN)

| Slice | Qué |
|---|---|
| S1 | Editar el relato en la UI (§3.1) |
| S2 | Biblia visual sin IA + esquema del guion + job `video_script` + chequeos |
| S3 | Página imprimible, prompts `.txt`, mapa `.csv` |
| S4 | Un guion real de punta a punta con los chicos y quien edita; ajustes; docs |

---

## 8. EVOLUTIVOS (fuera de esta spec)

- **Video con IA en ComfyUI** (idea del usuario, 2026-09-30): buscar un modelo de video que corra en ComfyUI (RTX 3060, 12 GB) para animar tomas cortas desde las imágenes. El tono que usan los chicos: **horror y terror intercalando lo abstracto y lo liminal**, monstruos aberrantes al estilo skinwalker, brujas, apariciones, hombres lobo. Ese tono también es el de la biblia visual de esta spec: va como estilo fijo en los prompts de imagen.
- **Generar las imágenes desde la app** vía la API de ComfyUI (D7).


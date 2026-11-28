# SPEC-820: La miniatura con la luz de Yael (una sola foto)

**Fecha:** 2026-11-27
**Tipo:** SDD: spikes de imagen (ComfyUI, modelos locales), sin cambios en el sitio hasta decidir
**Estado:** HECHO (2026-11-28, «Lo dejamos así» del usuario con la tanda 19 de Peter en dev). Sin commit ni deploy todavía. Cambios futuros de Yael → spec nueva.
**Rama:** `feat/spec-820-miniatura-luz-de-yael` (desde `development`, se crea al pasar a PLAN)
**Usa:** Spec-790 (el flujo de miniaturas, `ComfyClient`, workflows, plantillas, el rol `miniatura` que escribe los textos, D9, D15, D21–D29).
**Caso de prueba:** «El halloween de Peter» (`598a3b1d-75ff-4e6b-bae4-4db465468fbf`), con los bocetos y las descripciones que ya cargó Yael en dev.

---

## ASSUMPTIONS

1. **Lo pidió el usuario el 2026-11-27.** Yael no usó las 4 que armamos para Peter (tandas 1–8, en dev). Hizo la suya con **ChatGPT** y es la que subió a YouTube («NO SON PERSONAS»). El usuario quiere que el flujo llegue a ese estilo y esa calidad.
2. Es un **spike**: el resultado es una decisión (qué camino, con qué parámetros, a qué costo y en cuánto tiempo), con imágenes que se pueden ver. **No se toca `src/` ni `config/` hasta el OK** que cierra los spikes. Después viene una PLAN/TASKS para cambiar el flujo de la 790.
3. **Los resultados se ven en la vista de miniaturas de dev** (`https://storymaker.test/miniaturas/598a3b1d-…`), cargados a mano como tandas nuevas, como la tanda 9 (§2). **Evalúa el usuario** (decisión del usuario, 2026-11-27: esta vez Yael no participa). La vista muestra solo la última tanda; si hace falta ver variantes lado a lado, se arma una hoja de comparación en el scratchpad o se carga una tanda por variante.
4. **Las imágenes las generan solo los modelos locales** (decisión del usuario, 2026-11-27): Z-Image, Qwen-Edit 2511 y BiRefNet en ComfyUI. **La IA de la nube solo escribe los prompts** (el rol `miniatura` de la 790, hoy GPT-5.6 Sol en `openai-sol`). D9 sigue vigente: todo lo local ya tiene licencia comercial.
5. La de Yael se hizo con ChatGPT (generación de imagen en la nube): sirve **solo como referencia** de luz, criatura y color, no como camino a copiar.
6. **La GPU es compartida** (Yael en prod, `audiogen`). S1 corre cuando no hay un job de miniatura en curso y libera la VRAM al terminar (como en la 790).
7. No se bajan modelos nuevos sin OK. S1 usa lo instalado: Z-Image con el ControlNet Union, Qwen-Edit 2511 y BiRefNet.

## OBJECTIVE

Que «Armar las 4» devuelva miniaturas que Yael use sin rehacerlas. La referencia es la de Peter que ella armó con ChatGPT y sus 36 miniaturas recientes (C1 de la 790).

**Éxito (lo juzga el usuario en la vista; los números son la alarma, no el juez):**
- Al verlas al lado de la de Yael, **parecen de la misma serie**: luz, niebla, criatura y color.
- **La luz de sus miniaturas** (medida en la parte sin título, §1.1):
  - negros de verdad: p5 ≤ 10;
  - blancos de verdad: p95 ≥ 180;
  - la figura más oscura que lo que tiene detrás: luminancia media de la figura ≤ 0,5 × la de un anillo alrededor.
- **La criatura se ve fotografiada, no renderizada:** mate, de bordes irregulares (pelo, plumas, jirones), en silueta, con los ojos como único punto brillante.
- **La criatura toca el lugar:** si Yael dice que está escondida, la mano agarra el tronco o algo la tapa, con la misma luz y la misma niebla por delante y por detrás.
- Siguen siendo **4 opciones, una por plantilla** (D21) y **sin título** (D22), en 1280 × 720.
- **Tiempo:** como mucho el de hoy (~11 min las 4).

## 1. El diagnóstico (2026-11-27)

### 1.1 Lo que se midió

Luminancia (0–255) de la imagen entera:

| | Media | p5 | p50 | p95 | Píxeles > 150 |
|---|---|---|---|---|---|
| La de Peter de Yael (ChatGPT) | 97 | 20 | 75 | 214 | mucho |
| Sus 36 recientes (mediana) | 49 | **0** | 18 | **211** | 9 % |
| Las nuestras, tanda 8 | 23 | 4–8 | 16 | **63–68** | **0–1 %** |

Las de Yael también son oscuras en el medio, pero van **del negro puro al blanco**. Las nuestras quedan apretadas entre 4 y 68: no hay luz ni negro de verdad. En las 36 de ella el blanco incluye el título. Por eso los criterios se miden en la mitad sin título; en la de Peter, la niebla sola ya pasa 200.

### 1.2 Las diferencias, de mayor a menor peso

1. **La luz está invertida.** Yael pone la figura oscura contra un fondo claro: niebla iluminada, contraluz o un farol. Nuestros prompts piden lo contrario («very dark night», «underexposed», «most of the image in deep darkness») y la curva del escenario (`gamma 1.6`, `techo 0.75`) lo oscurece más. Figura y fondo quedan del mismo valor. Ya lo había visto C5 (790) como «falta la luz (E6)», y E6 quedó para después (D26).
2. **La criatura está iluminada de frente.** `fotografiar_personaje.md` pide flash directo, «wet patches, veins». Sale brillosa, de goma o de render. La de Yael es casi negra y mate, de bordes desflecados, y se lee por la silueta.
3. **Una foto contra un recorte pegado.** En la de Yael la mano agarra el tronco y la niebla pasa delante y detrás. La nuestra son piezas generadas por separado y fundidas; el tronco que agrega Qwen en A_der se ve hecho por computadora.
4. **La fidelidad al boceto.** Su criatura se aleja del boceto (más búho, más flaca, de pelo). Nuestro flujo obliga a copiar el trazo (img2img 0,50, ControlNet 0,6, «keeping exactly»), y por eso sale rígida.
5. **El color.** La suya es gris azulado frío (R88 G100 B104). El tono «verde» para bosque da un verde barroso.
6. **Detalles.** Manchas naranjas como de lava en la piel en las cuatro (probablemente la regla que respeta los acentos cálidos conserva grietas que inventó Z-Image; se verifica en S1). Grano «heavy, dirty, scratched» que ensucia. No queda una zona tranquila para el título.

## 2. S0: la luz sola, con Python (HECHO, 2026-11-27)

Sobre las piezas sin color de la tanda 8:
- lo que ya era claro en el fondo (la niebla lejana) se lleva a blanco, sobre todo arriba y al medio;
- lo oscuro (troncos cercanos, la figura) queda en silueta;
- los ojos quedan como estaban y todo pasa a gris azulado frío.

Script: `scripts/research/820/s0_luz_python.py` (se pasa del scratchpad al abrir la rama). Cargado en dev como **tanda 9** (registro anterior respaldado).

**Resultado:** se acerca mucho en clima (media 93 contra 97), lo que confirma que **la luz es la mitad del problema**. Lo que no arregla: la figura recortada con halo, el diseño de muñeco, la niebla sin profundidad y el tronco de A_der sin textura donde pasa delante. Por eso la luz tiene que salir de la generación.

## 3. S1: componer primero, fotografiar una vez (Z-Image, local)

**Pregunta:** ¿una sola pasada de Z-Image sobre una composición que arma Python da una foto coherente (luz, niebla, contacto) con la luz de Yael?

**El camino, por plantilla (una tarea por llamada, D15):**
1. **Python compone** el borrador del cuadro en la posición de la plantilla (`arte.yaml`), sobre el escenario: el personaje de Qwen (la pieza de hoy, reusada por hash) recortado. Si va escondido (`a_medio_ver: mucho`), Python pone delante el tronco del propio escenario espejado o corrido, o una franja de corteza del escenario, para que el modelo lo tome.
2. **Z-Image genera el cuadro entero** con `foto_controlnet`: el borrador como imagen de partida y su contorno como guía. Va más suelto que hoy para que pueda reinterpretar la criatura y la luz.
3. **Python controla:** mide p5, p95 y el contraste figura/anillo (§OBJECTIVE). Si no da, corrige con una curva (como S0, pero sobre una foto coherente). Sin pintar.

**Los prompts nuevos** (en `scripts/research/820/prompts/`, en positivo, D27):
- **Escena:** contraluz de niebla blanca densa, cielo nublado, los troncos cercanos en silueta, la profundidad lavada por la niebla.
- **Criatura:** silueta casi negra, piel o pelo mate y desflecado, borde de luz, los ojos como única luz.
- **Sin** flash, «underexposed» ni grano pesado.

**Se varía:**
- el cambio (0,70 / 0,82 / 0,92) × la fuerza de la guía (0,30 / 0,45);
- dos semillas;
- la guía: el contorno de la composición o los dos bocetos compuestos.

Primero en A_der (la de Yael) y, con lo mejor, las 4.

**Variante S1b (solo si S1 pierde la criatura):** Qwen-Edit 2511 multirreferencia (E10 de la 790): imagen 1 = la composición, imagen 2 = el personaje, imagen 3 = la miniatura de Peter de Yael como referencia de luz y estilo.

**Se anota:** tiempo por imagen, pico de VRAM, los tres números de luz y si pasa a ojo.

## 4. S2: prompts bien pensados por la IA de la nube

**Pregunta:** ¿cuánto mejora S1 si los prompts no son plantillas fijas sino que los escribe la IA de la nube pensando en la luz, mirando los bocetos y la referencia?

Hoy el rol `miniatura` (T3.3, T6.5 de la 790) solo **separa** lo que escribió Yael en personaje, lugar y relación, y mira los bocetos para nombrar lo que hay. La luz, la cámara y el material de la criatura salen de plantillas fijas (`fotografiar_*.md`) que piden noche cerrada y flash. En S2 la IA escribe, por plantilla, los prompts de la pasada única de S1, con:
- **las entradas:** los dos bocetos, las descripciones de Yael, la plantilla (dónde va la figura y dónde el título) y **2–3 miniaturas de referencia** (la de Peter de Yael y algunas de sus 36 recientes con contraluz, solo como imagen para leer la luz);
- **una guía de fotografía en `prompts/`**:
  - de dónde viene la luz (contraluz, niebla iluminada, farol);
  - qué queda en silueta y qué brilla (los ojos);
  - el material mate de la criatura;
  - la niebla por capas según la distancia;
  - una zona tranquila del lado del título;
  - todo en positivo y en el vocabulario que entiende Z-Image (frases concretas de foto, D27).
- **la salida:** un prompt por plantilla (en inglés) y una línea en castellano de qué luz eligió y por qué, para el informe.

**Se compara:** S1 con los prompts fijos de §3 contra S1 con los prompts de S2, con la misma composición, semilla y parámetros. Así se ve solo el efecto del prompt.

**Se anota:** el costo de la llamada (en `llm_call`, Spec-740) y si la IA describe la luz de las referencias o copia su contenido (no debe meter elementos de otras miniaturas).

## 5. Cómo se mira y cómo se decide

- Cada spike que dé algo se carga como **tanda nueva en dev** (la vista de Peter), y se le dice al usuario qué tanda es y qué mirar.
- **Informe** en `scripts/research/820/informe.md`: los números de luz por imagen, tiempos, VRAM, costo de los prompts y las imágenes de cada variante (las salidas fuera de git, como en la 790).
- **Decide el usuario:** qué parámetros y qué prompts quedan (fijos, de la IA o una mezcla), o seguir probando. Después se escribe PLAN/TASKS para cambiar el flujo de la 790:
  - los prompts y el pedido al rol `miniatura`;
  - `arte.yaml`: la luz y los tonos;
  - `imagen.py`: componer antes y controlar después;
  - los workflows que hagan falta.

## 6. Commands

```bash
# ComfyUI en el host; los spikes corren en el host con el .env (si no, el perfil es el local)
curl -s localhost:8188/system_stats
set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 uv run python scripts/research/820/s1_una_foto.py --plantilla A_der
set -a; . ./.env; set +a; uv run python scripts/research/820/s2_prompts.py --plantilla A_der   # la IA escribe los prompts
set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 uv run python scripts/research/820/s1_una_foto.py --plantilla A_der --prompts s2
uv run python scripts/research/820/luz.py <carpeta>           # p5, p95, figura/anillo de cada imagen
uv run python scripts/research/820/cargar_tanda.py <carpeta>  # carga una tanda en dev (respalda el registro)
```

## 7. Project Structure

```
scripts/research/820/            → spikes (s0_luz_python.py, s1_una_foto.py, s2_prompts.py, luz.py, cargar_tanda.py)
scripts/research/820/prompts/    → los prompts de prueba (después pasan a config/miniatura/prompts/)
scripts/research/820/salidas/    → imágenes (fuera de git)
scripts/research/820/informe.md  → resultados y decisión
data/dev/miniaturas/<id>/tanda_N → las tandas de prueba, para verlas en la vista
```

Reusa `scripts/research/790/comun.py` y el `ComfyClient` de la 790; no copia workflows: si S1 necesita uno nuevo, se exporta a `config/miniatura/workflows/` siguiendo su README, pero solo al pasar a PLAN.

## 8. Testing

Es un spike: no suma tests al sitio. `luz.py` trae un test chico con imágenes sintéticas (negro / blanco / figura oscura sobre fondo claro) para que los números sean confiables. Al pasar a PLAN, el cambio del flujo trae sus tests:
- `test_thumbnail_api.py` con `fake_comfy.py` y la IA de mentira;
- el snapshot `thumbnail_prompts.json` actualizado a propósito;
- un chequeo de luz sobre la salida.

## 9. Boundaries

- **Siempre:**
  - respaldar el registro de `thumbnail` antes de cargar una tanda a mano en dev;
  - liberar la VRAM al terminar;
  - anotar costo y tiempo de cada llamada;
  - prompts en positivo (D27).
- **Preguntar antes:**
  - bajar un modelo;
  - tocar `src/`, `config/` o prod.
- **Nunca:**
  - correr S1 con un job de miniatura de Yael en curso;
  - generar imágenes con una IA de la nube: solo escribe prompts;
  - mandarle a la IA de la nube algo que no sean los bocetos, las descripciones, la plantilla y las miniaturas de referencia;
  - tocar las tandas 1–8 ni la base de prod.

## 10. Success Criteria del spike

- [ ] S1 corrida en A_der con la grilla de §3 y, con lo mejor, en las 4. Números de luz y tiempos en el informe.
- [ ] S2 corrida: prompts de la IA contra prompts fijos, en A_der y, si mejora, en las 4. Costo de los prompts en el informe.
- [ ] Las mejores, cargadas como tandas en la vista de dev.
- [ ] Decisión del usuario anotada en el informe y en esta spec.

## 11. Decisiones

| # | Decisión | Quién |
|---|---|---|
| D1 | Las imágenes las generan solo los modelos locales; la IA de la nube solo escribe prompts | Usuario, 2026-11-27 |
| D2 | Evalúa el usuario (esta vez Yael no) | Usuario, 2026-11-27 |
| D3 | **Respeta** el boceto en dos plantillas (A_der, A_izq) y **reinterpreta** en las otras dos (C_primer_plano, B_lugar) | Usuario, 2026-11-27 |
| D4 | El tono es **gris frío azulado** | Usuario, 2026-11-27 |
| D5 | La criatura se **despega** del fondo: halo de niebla clara detrás, luz de borde, ojos que brillan | Usuario, tanda 10 |
| D6 | Escala: los árboles la superan mucho; «Manda el lugar» chica y a un costado (lugar para el texto) | Usuario, tanda 10 |
| D7 | Materiales **orgánicos y mate** (pelo, pelo apelmazado, piel aterciopelada con vello, plumón casi imperceptible), una cobertura distinta por plantilla; nada que parezca render 3D | Usuario, tanda 13 |
| D8 | El prompt nunca nombra la cámara, el trípode, el fotógrafo ni luces que no están en el lugar (el modelo los dibuja) | Tanda 14 |

## 12. Resultados de los spikes (2026-11-27/28)

Todo sobre Peter, cargado como tandas en dev. Las salidas están en `scripts/research/820/salidas/` (fuera de git).

| Tanda | Qué | Lo que salió |
|---|---|---|
| 9 | S0: la luz solo con Python | El clima se acerca (media 93); se nota que la figura está pegada |
| 10 | S1: una pasada de Z-Image, con guía de profundidad | Foto real, con pelo; la figura pegada al fondo; C y B reinterpretados de más |
| 11 | S1b: halo + profundidad con el halo «lejos» + ojos + escala | Despegada; media 96–101 (Yael 97); A_der perdió el tronco |
| 12 | S1c: el tronco por delante en A_der | La más parecida a la de Yael |
| 13 | S2: los mismos pasos que la 12, con los prompts de la IA | Cada encuadre con su carácter; piel lisa en C, luna inventada en B |
| 14 | S2b: los prompts con coberturas mate + Python aplasta los reflejos | Pelo o vello mate en las cuatro; ya no sale la cámara |

- **Lo que hizo la diferencia:** componer antes con la luz ya puesta y guiar con una **profundidad falsa** armada por Python (figura y tronco cerca, halo lejos). Los bordes como guía fallaron: la corteza mete ruido y corre la figura.
- **Lo que suma la IA:** carácter por encuadre (lente, plano, cobertura) y prompts más ricos. Los desvíos se corrigen en la guía.
- **Tiempo:** ~80 s por imagen en Z-Image (una pasada) contra ~150 s de antes (fundido con Qwen).

---

## PLAN

El flujo de la 790 cambia en el armado de las 4. **Las piezas (personaje y escenario) quedan igual** y se reusan por hash. Lo nuevo:

```
textos (IA, como hoy) ──┐
prompts de foto (IA, NUEVO: uno por plantilla, mirando bocetos + referencias) ──┐
personaje / escenario (igual) ──┐                                              │
                                ▼                                              ▼
por plantilla:  ubicar + espejo (igual)
                → iluminar el fondo (S0: la niebla clara, lo cercano oscuro)
                → silueta de la figura + ojos marcados
                → halo detrás de la figura
                → [escondida, en `detras_en`]: Qwen pone el tronco (`fundir_detras`, como hoy)
                   y Python saca la máscara del tronco por diferencia
                → guía de profundidad (figura cerca, tronco más cerca, halo lejos)
                → `foto_controlnet` una pasada (cambio/fuerza según el modo de la plantilla)
                → control: lienzo + niveles + niebla
                → `recortar` la figura en la foto → despegar (anillo) + mate (reflejos)
                → color (gris frío azulado) → JPG; sin color + alfa para recolorear
```

**Sale del flujo:**
- el fundido con Qwen en las plantillas sin tronco (`fundir.md`);
- `oscurecer_figura`, `restaurar_luces` y `a_medio_ver` (la sombra de las piernas): lo resuelve la pasada única.

Las funciones quedan en `imagen.py` mientras las usen los tests o la 790; se borran las que queden sin uso.

### Archivos

| Archivo | Cambio |
|---|---|
| `config/miniatura/arte.yaml` | `plantillas.*.modo: respeta|reinterpreta`; `modos: {respeta: {cambio: 0.62, fuerza: 0.60}, reinterpreta: {cambio: 0.80, fuerza: 0.50}}` (B: fuerza 0,55 por plantilla); `B_lugar: cx 0.70, alto 0.40`; bloque `luz` (niebla: gris, umbral, fuerza; silueta: techo; halo: radio, fuerza, color; despegar: anillo, fuerza; mate: umbral, compresión); tono nuevo `gris_azul` [[3,5,8],[86,98,108],[222,230,237]] con las palabras de bosque y niebla, y `tono_por_defecto: gris_azul` |
| `src/application/services/miniatura/arte.py` | valida lo nuevo (modos existentes, rangos) |
| `src/application/services/miniatura/imagen.py` | nuevas: `iluminar_fondo`, `silueta`, `ojos`, `con_halo`, `mascara_tronco` (diferencia antes/después de Qwen dentro de la zona), `profundidad`, `controlar_luz`, `despegar`, `mate`, `medir_luz` (p5/p95/media) |
| `src/application/services/miniatura/textos.py` | `prompts_de_foto(llm, input, texts, bocetos, referencias)` → `{plantilla: prompt}` (salida estructurada); sin IA: el prompt fijo |
| `src/domain/thumbnail.py` | `ImageTexts.fotos: dict[str, str]` y `fotos_hash` (se reusan mientras no cambien bocetos, descripciones, guía ni referencias) |
| `src/application/services/miniatura/arnes.py` | `armar()` con el flujo nuevo; el registro de luz de cada imagen en la tanda (`Batch.luz`, para el informe y para ver si se desvía) |
| `config/miniatura/prompts/` | `ia_foto_sistema.md` (la guía de S2: luz, materiales, escala, toma, encuadres, D7/D8), `ia_foto_pedido.md`, `una_foto.md` (el fijo, fallback) con `detras.md`; se retiran `fundir.md` y `fotografiar_personaje.md` si quedan sin uso (el personaje sigue con la foto: se decide en T4) |
| `config/miniatura/referencias/` | 4 miniaturas de Yael (la de Peter y 3 recientes con contraluz) que la IA mira solo para la luz; README con de dónde salen |
| `frontend/src/views/miniaturas/historia.ejs` | la nota de «escondido»: en la de la derecha queda detrás de lo que lo tapa; el resto, sin la frase de la sombra |
| `config/miniatura/README.md`, `CLAUDE.md` (Spec-790) | el flujo nuevo en dos líneas |

### Riesgos

- **El tronco por diferencia** es lo único que en el spike se hizo a mano. Si la diferencia antes/después de Qwen no da una máscara limpia, el plan B es el polígono de la caja `zona_detras` con la parte que Qwen oscureció. T3 lo prueba primero, sobre la tanda 8 y la 7 de Peter.
- **La IA puede volver a nombrar cosas que se dibujan.** Se cuida con la guía (D8) y con un chequeo sin IA: si el prompt trae palabras de una lista (`camera`, `tripod`, `photographer`, `moon` si el lugar no la nombra), se reintenta una vez con el aviso y, si no, va el fijo.
- **VRAM:** Z-Image + ControlNet ya corría en el flujo (escenario). Sin cambios en `VRAM_NECESARIA_MB`.

## TASKS

Cada una con sus tests; al final, `make test`, `make lint` y una tanda real de Peter en dev.

- [x] **T1 — `arte.yaml` y su validación:** modos, `luz`, B_lugar, tono `gris_azul`. Tests: carga, modo inexistente → error, el tono por lugar («bosque» → `gris_azul`).
- [x] **T2 — Funciones de imagen** (`imagen.py`), portadas de los spikes y con parámetros de `arte.yaml`. Tests con imágenes sintéticas:
  - `iluminar_fondo`: lo claro difuso sube y lo oscuro no;
  - `profundidad`: la figura en 255, el halo cerca de 0, el tronco por encima de la figura;
  - `despegar`: aclara el anillo y no la figura;
  - `mate`: baja los reflejos de la figura y no los ojos;
  - `medir_luz`.
- [x] **T3 — El tronco** (por diferencia daba una máscara llena de ruido en las tandas 7 y 8: se fue al plan B, **Python dibuja el tronco** con vetas y la guía lo marca como lo más cercano; sin la llamada a Qwen). ~~La máscara del tronco por diferencia~~, probada primero en las tandas 7 y 8 de Peter (las que tienen `A_der_zona/fundido`), con el plan B de Riesgos si no da. Test con un par sintético antes/después.
- [x] **T4 — Los prompts de foto** (`textos.prompts_de_foto`, `ImageTexts.fotos`, `prompts/ia_foto_*.md`, `referencias/`):
  - la salida estructurada, el reuso por hash y el chequeo de palabras que se dibujan (reintento y si no, el fijo);
  - el snapshot `thumbnail_prompts.json` actualizado a propósito, con un test que falle si falta la sección de materiales o de la toma;
  - `test_prompts_fuera_del_codigo` en verde.
- [x] **T5 — `armar()` con el flujo nuevo**:
  - `fake_comfy` cubre `foto_controlnet` y `recortar` sobre la composición;
  - `test_thumbnail_api.py`: 4 imágenes, una llamada a `fundir_detras` solo si está escondida, `foto_controlnet` 4 veces, la luz registrada y recolorear sigue andando sin GPU.
- [x] **T6 — La vista y la documentación:** la nota de «escondido», `config/miniatura/README.md` y la sección de la 790 en `CLAUDE.md`; `estimated_seconds.thumbnail_build` revisado con lo medido.
- [x] **T7 — Tanda real en dev (Peter)** con el flujo completo (personaje y escenario reusados), cargada sola por «Armar otras 4». Checkpoint con el usuario: la URL y qué mirar.
- [ ] **T8 — Limpieza:** borrar las tandas de prueba 9–14 de Peter en dev (con OK) y las funciones que quedaron sin uso. El deploy a prod va aparte, con `make deploy` y OK del usuario.

### Notas de la implementación (2026-11-28)

- **Los ojos:** detectarlos solo por brillo marcaba en amarillo lo que el flash aclara en la pieza del personaje; ahora son lo cálido, saturado y claro (`acentos`). Si la foto los apaga del todo (tanda 15, A_der), `devolver_ojos` trae el brillo de la composición, solo donde la cabeza sigue estando.
- **El tronco:** con un ruido fino Z-Image lo pintó como un poste liso (tanda 15); con vetas gruesas y grietas sale corteza (tanda 16).
- **Medido en dev (Peter, piezas reusadas):** 358–366 s las 4 (antes ~11 min). Luz de la tanda 16: media 55–98, p5 3–4, p95 191–217.

- **Tandas 17–19 (pedido del usuario: el halo más chico, ceñido y transparente):** el halo de la composición a la mitad (`radio` 0,05, `fuerza` 0,45), el corte de la guía más angosto (`profundidad_anillo` 0,04) y el anillo final más fino. La guía de la IA pide un borde fino de niebla y no dice «halo»: en la 17 Z-Image dibujó un aro de ángel (`halo` va a `se_dibujan`). `devolver_ojos` solo en las plantillas que respetan (en la 17 pintó los ojos en el pecho de una figura que se movió). En la 18 el primer plano inventó una cabeza de más: `contar_ojos` (4 o más luces cálidas sueltas = dos pares) rehace esa foto una vez con otra semilla, y el primer plano va con la guía un poco más firme (`fuerza` 0,58). Tanda 19: las 4 sin defectos grandes; queda una estela clara fina sobre el tronco de A_der.

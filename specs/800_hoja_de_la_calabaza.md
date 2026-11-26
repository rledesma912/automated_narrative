# SPEC-800: Las hojas de personaje de la calabaza de la cripta (cuerpo y expresiones)

**Fecha:** 2026-11-26
**Tipo:** SDD: arnés de imágenes (ComfyUI + Python), spikes primero; sin IA de texto
**Estado:** PLAN (OK a la spec el 2026-11-26; esperando OK al plan)
**Rama:** `feat/spec-800-hoja-calabaza` (desde `development`)
**Usa:** Spec-790 (el arnés de las miniaturas: `ComfyClient`, workflows, BiRefNet, igualar y pegar), Spec-795 (el tablero, para mostrar y elegir).
**Después (specs aparte):** la voz de Lucas (`audiogen`), la calabaza hablando y actuando, los reels.

---

## ASSUMPTIONS

1. Lo pidió el usuario el 2026-11-26: la hoja de personaje («character sheet») de **la calabaza de la cripta**, el presentador del canal, con **un arnés como el de las miniaturas**, porque con su setup, de una sola vez, no sale bien. Que quede **registrada**: es la referencia de todo lo que viene (la voz, la calabaza hablando, Lucas actuando, los reels).
2. **El último paso, como en las miniaturas** (pedido del usuario): Python arma la composición y ComfyUI la vuelve a generar para que todo se vea de una pieza. En las miniaturas ese paso es el **fundido** (`prompts/fundir.md`): Qwen-Edit recibe la composición de Python y la rehace, y Python **pega solo dentro de la máscara** de la figura, con la exposición igualada (Spec-790 E4b). Acá es lo mismo con la hoja: cada vista se genera aparte, Python las ubica en la hoja y ComfyUI la unifica (la luz, el material, el estilo); Python pega por panel y pone los rótulos al final (el texto nunca lo dibuja un modelo).
3. **D15 de la 790, divide y triunfarás:** cada llamada a ComfyUI hace una sola tarea. Nada de «hacé la hoja entera» de una vez, que es lo que falló.
4. **Todo local**, con licencia comercial: Qwen-Image-Edit 2511 (Apache 2.0) con Lightning, Z-Image Turbo (Apache 2.0), BiRefNet (MIT). Sin modelos nuevos salvo que un spike lo pida (y se pregunta antes de bajar).
5. **Elegir es en el tablero** (Spec-795): de cada paso salen 3 opciones, se publican como una entrega y el usuario, Yael o Lucas marcan 👍 / 👎 / nota. Claude lee las opiniones y sigue. **No hay sección nueva en el sitio** (ver §7, abierto).
6. **Las referencias de hoy** (en `scripts/research/790/insumos/calabaza/`, fuera de git):
   - `calabaza_de_la_cripta.png`: el avatar del canal, **130 × 131 px**, de busto, con auriculares, ojos violetas que brillan, micrófono en la mano y buzo oscuro con capucha, sobre negro.
   - `captura_video_sitio.png`: un cuadro de un video del canal (captura de pantalla del usuario, 924 × 518): la calabaza **más fotográfica**, con el tallo, la textura de la cáscara, los dientes tallados en punta, auriculares, ojos violetas, en su estudio oscuro con el micrófono en un brazo articulado. La descarga en 1080p desde YouTube dio 403; si está el archivo del video, un cuadro de ahí es mejor.
7. Lo fijo del personaje (lo que nunca cambia) sale de la imagen y de `config/video/presentador.yaml`: calabaza tallada naranja, sonrisa de dientes afilados, **ojos violetas que brillan**, **auriculares**, **micrófono de estudio**, buzo negro. El sótano es su lugar, pero la hoja va sobre fondo liso.

## OBJECTIVE

**Dos hojas de personaje** de la calabaza que el usuario y Yael aprueben (D5), armada por un arnés que se pueda volver a correr, y **registrada en el repo** con sus piezas sueltas y una ficha.

**Éxito:**
- **La hoja del cuerpo** tiene las vistas de cuerpo entero (frente, ¾, perfil, espalda), los materiales y la paleta; **la hoja de expresiones**, las expresiones y las bocas de busto. En todas es **la misma calabaza**: mismos ojos, mismo tallado, mismos auriculares y micrófono, misma luz.
- Se ve de una pieza (no un collage de recortes) y los rótulos se leen.
- Queda en `assets/personajes/calabaza/`: las dos hojas, cada pieza en PNG con transparencia (las van a usar los modelos de video, que piden una imagen, no una hoja) y `ficha.yaml`.
- Correr el arnés de nuevo con las mismas elecciones da las mismas hojas (semillas guardadas).

---

## 1. El flujo

```
referencias ─► [1] maestra de cuerpo entero ─┬─► [2] vistas: ¾ · perfil · espalda (pose neutra)
                   (fiel → agrandar, D3)       │
                                               └─► [1b] maestra de busto ─┬─► [3] expresiones
                                                                          └─► [4] bocas
                            (cada pieza: 3 opciones → tablero → se elige 1)

        HOJA DEL CUERPO                                   HOJA DE EXPRESIONES
  [5] recorte → [6] Python compone (vistas,         [5] recorte → [6] Python compone (expresiones
      materiales, paleta; sin texto)                    y bocas; sin texto)
  [7] ComfyUI la regenera para unificarla           [7] ComfyUI la regenera para unificarla
  [8] Python: pegar por panel + rótulos             [8] Python: pegar por panel + rótulos
        ▼                                                 ▼
  hoja_cuerpo.png                                   hoja_expresiones.png
                  └──────── + piezas/*.png + ficha.yaml ────────┘
```

### 1.1 Los pasos
- **[1] La maestra:** Qwen-Edit con la referencia → la calabaza de frente, en alta, sobre fondo liso, con lo que no se ve en el original resuelto (¿cuerpo entero o busto? §7). Es **la referencia de todos los pasos siguientes**. 3 opciones → tablero → se elige.
- **[2] Las vistas:** una llamada por vista, con la maestra de entrada («la misma calabaza, girada a perfil»). Qwen-Edit 2511 acepta varias imágenes: el spike prueba sumar la vista anterior como segunda referencia para que no se aleje.
- **[1b] La maestra de busto:** desde la maestra de cuerpo entero, la misma calabaza encuadrada de la cintura para arriba y en alta (para que la cara tenga detalle). Se elige y se aprueba como la otra.
- **[3] Las expresiones:** primer plano de la cara, una por llamada, desde la maestra de busto. Una calabaza tallada no mueve la cara como una persona: el spike define qué cambia (la forma del tallado, la luz de adentro, los ojos).
- **[4] Las bocas** (visemas): cerrada, A, O, E. Sirven después para que hable; si el modelo de video no las usa, igual quedan en la hoja.
- **[5] Recorte:** BiRefNet (el workflow `recortar` de la 790), fondo liso del color de `hoja.yaml`.
- **[6] Componer:** Python ubica las piezas elegidas en la grilla de **cada hoja** (`config/personajes/hoja.yaml` → `cuerpo` y `expresiones`), **sin texto**. Cuerpo: las 4 vistas a la misma escala y alineadas al piso, el panel de materiales y la paleta. Expresiones: las 5 expresiones arriba y las 4 bocas abajo.
- **[7] Regenerar (unificar):** una vez por hoja, ComfyUI recibe la hoja compuesta y la rehace con `prompts/unificar.md` («la misma hoja, el mismo personaje en cada panel, la misma luz y el mismo material; no muevas nada»). Como en el fundido: **en positivo**, sin negaciones (D27 de la 790: con cfg 1 el «no» trae lo negado).
- **[8] Pegar y rotular:** por cada panel, igualar la exposición y pegar lo regenerado **solo dentro de la máscara** de la pieza (lo de la 790: `igualar`, `pegar_fundido`), para que lo que no cambió no se pierda. Después Python escribe los rótulos («Frente», «¾», «Perfil», «Espalda», «Neutra»…) y la **paleta** (los colores de la pieza, sacados por Python) con la fuente de `assets/fonts/`.

### 1.2 Qué se reusa de la 790
- `ComfyClient.correr(receta, valores, entradas, destino)` y los workflows `boceto_a_imagen` (Qwen-Edit), `foto_img2img` (Z-Image) y `recortar` (BiRefNet), sin cambios.
- `imagen.py`: `igualar`, `pegar_fundido`, `dilatar`, `anillo`. Se mueven a un módulo común si hace falta (sin cambiar lo que hacen: los tests de la 790 lo cuidan).
- La espera de GPU (`esperando_gpu`) y liberar la VRAM antes de usar ComfyUI.

## 2. Los datos

### 2.1 Lo que queda registrado (en git)
```
assets/personajes/calabaza/
  hoja_cuerpo.png        # las dos hojas aprobadas, en alta
  hoja_expresiones.png
  piezas/maestra.png     # cada pieza elegida, con transparencia
  piezas/vista_tres_cuartos.png …  piezas/boca_o.png
  ficha.yaml
```
`ficha.yaml`:
```yaml
nombre: La calabaza de la cripta
version: 1                       # sube cuando se aprueba una hoja nueva
aprobada: 2026-12-…              # y por quién lo dijo (en el tablero)
quien_es: …                      # lo mismo que presentador.yaml (de ahí lo lee)
fijo:                            # lo que nunca cambia, en positivo (lo leen los prompts)
  - carved orange pumpkin head with sharp jagged teeth
  - glowing violet eyes
  - black over-ear headphones
  - studio microphone in a black-gloved hand
  - black hooded sweatshirt
paleta: ["#e0701c", "#8a3cf0", "#111111", …]   # la saca Python de la maestra
piezas:                          # de dónde salió cada una (para rehacerla)
  maestra: {receta: boceto_a_imagen, semilla: 1234, prompt: maestra}
  maestra_busto: {…}
  …
```
- `config/video/presentador.yaml` pasa a leer `quien_es` de la ficha (un solo lugar).
- Las imágenes van a git porque son **la referencia** del canal y pesan poco (unos MB). Si pesan de más, se evalúa Git LFS (se pregunta antes).

### 2.2 Lo de trabajo (fuera de git)
`data/dev/personajes/calabaza/corrida_N/` con todas las opciones de cada paso; lo que se elige se copia a `assets/`. Las entregas al tablero salen de acá.

### 2.3 Config
- `config/personajes/hoja.yaml`: dos bloques, `cuerpo` y `expresiones`, cada uno con su tamaño, la grilla (qué panel va dónde y de qué tamaño), el color del fondo, la fuente y el tamaño de los rótulos, cuántas opciones por paso (3).
- `config/personajes/prompts/<paso>.md`: un prompt por paso (D17 de la 790): `maestra`, `maestra_busto`, `agrandar`, `vista`, `expresion`, `boca`, `unificar`. Con `{fijo}` y `{vista}` / `{expresion}` de la ficha y la hoja.

## 3. Cómo se corre (Claude, CLI)
```bash
set -a; . ./.env; set +a; COMFY_URL=http://localhost:8188 \
uv run python -m src personaje calabaza maestra            # 3 opciones → publica en el tablero (prod)
uv run python -m src personaje calabaza elegir maestra 2   # o lo que dijeron en el tablero
uv run python -m src personaje calabaza vistas | expresiones | bocas
uv run python -m src personaje calabaza maestra-busto
uv run python -m src personaje calabaza hoja cuerpo|expresiones   # [5]–[8]
uv run python -m src personaje calabaza registrar          # copia a assets/ y escribe ficha.yaml
```
Cada comando que genera publica su entrega en el tablero (`proyecto: calabaza`) con «Qué mirar» y las opciones en una fila, y Claude lee las opiniones antes del paso siguiente.

## 4. Spikes (antes de construir)
Como en la 790, un spike por parte del flujo, cada uno con su checkpoint **en el tablero**. Scripts en `scripts/research/800/`, salidas fuera de git.

| Spike | Pregunta | Pasa si |
|---|---|---|
| **H1 maestra** | ¿Qwen-Edit saca una calabaza en alta y fiel desde 130 px? ¿Hace falta un paso de agrandar antes (Z-Image img2img, o un upscaler local)? | El usuario y Yael reconocen a su calabaza en una de las 3 |
| **H2 vistas** | ¿Se sostiene el personaje girado (ojos, tallado, auriculares)? ¿Ayuda pasar la maestra + la vista anterior? | Las 4 vistas son la misma calabaza |
| **H3 expresiones y bocas** | ¿Qué cambia en una calabaza tallada cuando ríe o se asusta? ¿Salen bocas distinguibles? | Se distinguen y siguen siendo ella |
| **H4 unificar** | El paso [7]: ¿regenerar la hoja entera (~1,3 MP, pierde resolución por panel) o **panel por panel** con la hoja de contexto? ¿Qwen-Edit o Z-Image img2img bajo? | La hoja se ve de una pieza y ningún panel cambió de personaje |

## 5. Testing (cuando se construya)
- Unit: componer la hoja con piezas de prueba (grilla de `hoja.yaml`, sin texto), pegar por panel (fuera de las máscaras no cambia nada), rótulos y paleta, `ficha.yaml` válida, semillas que se guardan.
- Integración: el arnés completo con `tests/support/fake_comfy.py` (sin GPU), que publica en un tablero temporal.
- Snapshot de los prompts (`personaje_prompts.json`), como el de las miniaturas.

## 6. Boundaries
- **Siempre:** una tarea por llamada a ComfyUI; prompts en positivo; texto de la hoja por Python; elegir en el tablero.
- **Preguntar antes:** bajar un modelo nuevo; Git LFS; publicar en el tablero algo que no sea del proyecto.
- **Nunca:** modelos sin licencia comercial; subir la calabaza a un servicio externo sin OK.

## 7. Decisiones (OK a la spec, 2026-11-26)
- **D1 Cuerpo entero.** La maestra y las vistas, de cuerpo entero: para que Lucas actúe y, si el canal anda, para construir **el cosplay**. Por eso las vistas van en **pose neutra** (de pie, brazos un poco separados del cuerpo), de frente, perfil y espalda bien ortogonales, y la hoja suma un panel con **los materiales** (cáscara, tallado, auriculares, buzo, guantes). Las expresiones y las bocas, de busto.
- **D2 Sin sección en el sitio.** La CLI + el tablero.
- **D3 Primero una imagen fiel, aprobada por el usuario; después escalar y regenerar.** H1 en dos partes: (a) Qwen-Edit con las dos referencias saca candidatas hasta que el usuario apruebe una que **es** su calabaza (aunque sea chica); (b) ComfyUI la agranda y la regenera por pasos (agrandar ×2 en Python → Z-Image img2img con poco cambio, que redibuja el detalle), repitiendo hasta la resolución de la maestra, y el usuario aprueba el resultado. Esa es la maestra.
- **D5 Dos hojas** (usuario, 2026-11-26): una **del cuerpo** (vistas de cuerpo entero, materiales, paleta: para actuar y el cosplay) y otra **de expresiones** (expresiones y bocas de busto). Cada una con su lienzo y su unificación: con menos paneles por hoja, cada uno conserva más resolución, y la del cuerpo queda limpia para el cosplay.
- **D4 Expresiones:** neutra, risa (humor negro), susto fingido, burla y «contando un secreto» (se acerca al micrófono).

---

## 10. PLAN

### 10.1 Dónde vive el código
Como la 790: el arnés en `application`, la CLI fina. Nada de UI.
```
config/personajes/hoja.yaml                 → la grilla, el fondo, la fuente, opciones por paso (3), resoluciones
config/personajes/prompts/{maestra,agrandar,vista,expresion,boca,unificar}.md
config/personajes/calabaza.yaml             → el personaje: referencias, lo fijo (en inglés, positivo), vistas y expresiones
src/application/services/personaje/
  hoja.py        → componer cada hoja (grilla, sin texto), pegar por panel, rótulos, paleta (Python puro, testeable)
  arnes.py       → los pasos: maestra, agrandar, vistas, maestra-busto, expresiones, bocas, hoja (cuerpo | expresiones), registrar (usa ComfyClient)
  corrida.py     → la carpeta de trabajo, qué se eligió, semillas (corrida.json)
  tablero.py     → arma y publica la entrega de cada paso (usa la Spec-795)
src/cli/personaje.py                        → `python -m src personaje <nombre> <paso> [...]`
assets/personajes/calabaza/                 → lo aprobado (git): hoja_cuerpo.png, hoja_expresiones.png, piezas/*.png, ficha.yaml
data/dev/personajes/calabaza/corrida_N/     → todo lo generado (fuera de git)
scripts/research/800/                       → los spikes H1–H4
```
- `igualar`, `pegar_fundido`, `dilatar`, `anillo` se importan de `miniatura/imagen.py` (sin moverlos: la 790 no cambia).
- Los workflows son los de la 790: `boceto_a_imagen` (Qwen-Edit; H2 ve si hace falta uno con **dos imágenes** de entrada, `qwen_dos_referencias`, exportado como los demás), `foto_img2img` (Z-Image, para agrandar y regenerar) y `recortar`.

### 10.2 Los pasos y lo que guardan
`corrida.json` (por corrida): para cada paso, las opciones (archivo, receta, semilla, prompt) y cuál se eligió. `registrar` copia lo elegido a `assets/` y escribe `ficha.yaml` con las semillas: con eso se rehace igual.

| Paso | ComfyUI | Python | Al tablero |
|---|---|---|---|
| `maestra` | Qwen-Edit × 3 semillas, con las referencias | fondo liso | fila «Maestra» con las 3 + las referencias |
| `agrandar` | por vuelta: Z-Image img2img (cambio bajo, ~0,25–0,35 según H1) | agrandar ×2 (Lanczos) antes de cada vuelta | antes / después de cada vuelta |
| `vistas` | Qwen-Edit × 3 por vista (frente, perfil, espalda en pose neutra; ¾) | — | una fila por vista |
| `maestra-busto` | Qwen-Edit × 3 desde la maestra (+ `agrandar` si hace falta) | — | fila «Maestra de busto» |
| `expresiones`, `bocas` | Qwen-Edit × 3 por cada una, desde la maestra de busto | — | una fila por expresión / boca |
| `hoja cuerpo` / `hoja expresiones` | `recortar` por pieza; `unificar`: Qwen-Edit o Z-Image según H4 | componer, pegar por panel, rótulos, paleta | la hoja antes y después de unificar |
| `registrar` | — | copiar a `assets/`, `ficha.yaml` | las dos hojas finales |

Elegir: `personaje calabaza elegir <paso> <n>`. Antes, Claude lee `tablero opiniones --env prod --entrega <id>` y propone la más votada; la elección la confirma el usuario.

### 10.3 La hoja (Python)
- **Hoja del cuerpo** (propuesta: 4096 × 2304, fondo gris cálido liso): las 4 vistas de cuerpo entero en fila, y a la derecha el panel de materiales (recortes en primer plano de la maestra: cáscara y tallado, auriculares, guante con micrófono, tela del buzo) y la paleta (5 colores por k-means sobre la maestra sin el fondo).
- **Hoja de expresiones** (propuesta: 4096 × 2304): las 5 expresiones de busto arriba, las 4 bocas abajo (más chicas, solo la cara).
- En la del cuerpo, cada vista se escala **con la misma escala para todas** (para el cosplay, las proporciones tienen que coincidir entre frente, perfil y espalda) y se alinea al piso.
- `unificar` recibe cada hoja **sin texto**; Python pega lo regenerado panel por panel dentro de la máscara (dilatada 1 %, borde suave) con la exposición igualada en el anillo, y después dibuja los rótulos con la fuente de `assets/fonts/`.

### 10.4 Spikes (orden y checkpoints)
1. **H1a maestra fiel** (`h1a_maestra.py`): Qwen-Edit con el avatar, con la captura y con las dos; prompts de cuerpo entero en pose neutra. → tablero. **Checkpoint: el usuario aprueba una.**
2. **H1b agrandar y regenerar** (`h1b_agrandar.py`): desde la aprobada, vueltas ×2 + Z-Image con 3 niveles de cambio (0,2 / 0,3 / 0,4). → tablero. **Checkpoint: el usuario aprueba la maestra.**
3. **H2 vistas** (`h2_vistas.py`): una o dos referencias; pose neutra. → tablero. Checkpoint.
4. **H3 maestra de busto, expresiones y bocas** (`h3_caras.py`). → tablero. Checkpoint.
5. **H4 unificar** (`h4_unificar.py`), con las dos hojas: hoja entera vs panel por panel; Qwen-Edit vs Z-Image. → tablero. Checkpoint.
Después de H4 se construye el arnés (10.1–10.3) con lo que pasó, y se corre de punta a punta.

### 10.5 Tests (al construir)
- `tests/unit/test_personaje_hoja.py`: las dos grillas (posiciones; en la del cuerpo, escala común de las vistas y alineado al piso), pegar por panel (fuera de las máscaras, idéntico), rótulos dentro de su panel, paleta de 5.
- `tests/unit/test_personaje_corrida.py`: elegir, semillas guardadas, `registrar` escribe la ficha y copia lo elegido.
- `tests/integration/test_personaje_arnes.py`: punta a punta con `FakeComfy` y un tablero temporal.
- Snapshot `tests/fixtures/snapshots/personaje_prompts.json` (+ que estén `{fijo}` y la vista en cada prompt).
- `config/personajes/*.yaml` validados con Pydantic al cargar (como `arte.py`).

### 10.6 Riesgos
- **La captura es de un video comprimido y oscuro:** la cáscara y los auriculares pueden salir inventados. Por eso D3: primero la aprueba el usuario, después se agranda.
- **Qwen-Edit gira mal a la espalda** (inventa la nuca): la espalda puede necesitar la vista de perfil como segunda referencia (H2).
- **VRAM:** Qwen-Edit 2511 int8 + Lightning entra hoy (miniaturas); agrandar con Z-Image a más de ~2 MP puede no entrar → H1b mide hasta dónde, y si hace falta se regenera por mosaicos.
- **GPU compartida** con prod (miniaturas de Yael) y audiogen: los spikes corren cuando no hay un job de miniatura en prod.

### 10.7 Tareas
- [ ] T1 `config/personajes/calabaza.yaml` + prompts de H1 (`maestra.md`, `agrandar.md`)
- [ ] T2 spike H1a → tablero → checkpoint
- [ ] T3 spike H1b → tablero → checkpoint (maestra aprobada)
- [ ] T4 spike H2 vistas → checkpoint
- [ ] T5 spike H3 maestra de busto, expresiones y bocas → checkpoint
- [ ] T6 spike H4 unificar (las dos hojas) → checkpoint
- [ ] T7 arnés (`hoja.py`, `corrida.py`, `arnes.py`, `tablero.py`) + CLI + tests
- [ ] T8 corrida de punta a punta (las dos hojas) → `registrar` → `assets/personajes/calabaza/` + ficha; `presentador.yaml` lee de la ficha
- [ ] T9 CLAUDE.md, commit, PR (sin deploy: no cambia nada de prod salvo `presentador.yaml`, que viaja en la imagen → deploy con OK)

## 11. Avance de H1a (2026-11-26)
- **H1a, primera vuelta** (`h1a_maestra.py`): 8 de cuerpo entero (avatar y video, lienzo vertical y referencia sola). El usuario descartó las del avatar en el tablero; **Yael eligió la cabeza de `avatar_sola_s11`** (la inclinada, con la boca oscura).
- **El cuerpo** (usuario): el buzo, los jeans y las botas no van con un anfitrión de cripta. Tres ideas (anfitrión con levita y enredadera, sepulturero, planta), presentadas en una lámina (`h1a2_presentacion.py`) en el tablero.
- **Los ojos** (Yael): menos brillo, la cuenca negra, el brillo que se escapa por el cuello. Qwen-Edit cambiaba el tallado y la inclinación de la cabeza → **los ojos se arreglan en Python** (`h1a3_ojos_python.py`: la cuenca a negro y la pupila violeta tenue, solo dentro de la caja de los ojos) y **la cabeza se protege**: después de cambiar la ropa con Qwen-Edit, Python vuelve a pegar la cabeza original (la calabaza y los auriculares, sin el fondo; `h1a3_cabeza.py`). Es el fundido de las miniaturas al revés; con `igualar` dejaba un halo en el fondo, sin él no.
- Hallazgo para el arnés: **lo que ya está aprobado (la cabeza) no pasa de nuevo por un modelo**; cada paso nuevo se pega por máscara sobre lo aprobado.

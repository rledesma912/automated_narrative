# SPEC-795: Tablero — la bitácora visual del proyecto

**Fecha:** 2026-11-26
**Tipo:** SDD: sección nueva (UI + API + datos), sin IA
**Estado:** IMPLEMENT (OK al plan el 2026-11-26). S1–S3 hechos; checkpoint en dev (`https://storymaker.test/tablero`).
**Rama:** `feat/spec-795-tablero` (desde `development`)
**Sirve a:** Spec-790 (miniaturas), Spec-800 (la calabaza de la cripta: hoja de personaje, voz, reels; por escribir).

---

## ASSUMPTIONS

1. Lo pidió el usuario el 2026-11-26: una página **dentro del sitio** donde Claude comparte imágenes de prueba, bocetos, conceptos y diagramas, para que el usuario, Yael y Lucas acompañen el proyecto. Que sirva de **bitácora**.
2. **Vive en prod** (http://192.168.0.65/tablero, `storymaker.prd/tablero`). Ellos también ven dev, pero la bitácora tiene que ser una sola y no cambiar con la rama activa. En dev la página existe igual (para desarrollarla), con sus propios datos.
3. **Publicar no es desplegar.** Una entrega es una carpeta en `data/prod/tablero/` (montado en el contenedor): Claude la copia y la página la muestra, sin `make deploy`. El código del tablero sí entra con `make deploy`, como siempre. OK del usuario (2026-11-26).
4. **Sin identificar a nadie** (usuario, 2026-11-26: «no hace falta identificar quién valida»). Las opiniones son anónimas: sin cuentas, sin nombres, sin «¿Quién sos?». Es una red de casa.
5. **Sin IA.** El tablero no genera nada: muestra lo que Claude publica y guarda lo que opinan.
6. Las muestras de voz de Lucas **no** van al tablero (datos personales). Sí puede ir un audio de prueba ya generado, si el usuario lo pide (ver §6, abierto).

## OBJECTIVE

Que todo lo visual del proyecto (pruebas, comparaciones, conceptos, diagramas) tenga **un solo lugar** donde verlo y opinar, y que lo que opinan **le vuelva a Claude** sin pasar por el chat.

**Éxito:**
- Claude publica una entrega con un comando y aparece en `/tablero` sin reiniciar nada.
- Desde cualquier PC de la casa se marca «Me gusta» / «No va» y se deja una nota en una imagen; Claude la lee con un comando y la cita en el checkpoint.
- El historial queda: las entregas viejas siguen ahí, ordenadas por proyecto y fecha.

---

## 1. Qué se ve

### 1.1 `/tablero`
- «Tablero» en el menú lateral (ícono de tablero), después de «Miniaturas».
- Filtro por **proyecto** (pestañas o chips: «Todos», «Calabaza», «Miniaturas»…, sacados de las entregas que hay).
- Lista de **entregas**, la más nueva arriba. Cada tarjeta: título, proyecto (chip), fecha, el texto corto y una tira de miniaturas de sus imágenes, con cuántas opiniones tiene.

### 1.2 `/tablero/{entrega}`
- Título, fecha, proyecto y **«Qué mirar»**: el texto que escribe Claude (Markdown simple: párrafos, listas, negritas).
- Las imágenes en grilla, cada una con su **leyenda**. Tocarla la abre grande (un `<dialog>`, con flechas para pasar a la siguiente).
- Una entrega puede agrupar imágenes en **filas para comparar** («Opción A · B · C», «Antes / Después»): la fila se ve lado a lado.
- Debajo de cada imagen: **«Me gusta»**, **«No va»** y **«Dejar una nota»**. Cada toque suma una opinión; se ven como cuentas («Me gusta · 2», «No va · 1») y las notas con su fecha.
- Cada opinión tiene su «×» para sacarla (con confirmación, `ForgeConfirm`): sin nombres, cualquiera puede corregir un toque de más.

### 1.3 Gramática visual (Spec-550 H9)
- Opinar es **botón**; las cuentas de «Me gusta» / «No va» son **chips** (`--cumple` / `--falta`); la nota es texto con su fecha; «Qué mirar» es una **nota** `--info`.
- Tono coloquial (Spec-580), sin jerga técnica en pantalla.

## 2. Los datos

### 2.1 Una entrega = una carpeta
```
data/<env>/tablero/
  2026-11-26-calabaza-hoja-v1/
    entrega.yaml
    maestra_a.png
    maestra_b.png
    vistas.svg
```
`entrega.yaml`:
```yaml
titulo: La calabaza, primera hoja
proyecto: calabaza            # slug; el nombre visible sale de config/tablero.yaml
fecha: 2026-11-26             # si falta, la del nombre de la carpeta
que_mirar: |
  Tres maestras de frente. Elegí la que más se parece a la de Yael.
filas:                        # opcional; sin filas, todas las imágenes en grilla
  - titulo: Maestra de frente
    imagenes:
      - archivo: maestra_a.png
        leyenda: A · Qwen, más contraste
      - archivo: maestra_b.png
        leyenda: B · Qwen, más parecida al original
imagenes:                     # sueltas (fuera de filas)
  - archivo: vistas.svg
    leyenda: Cómo se arma la hoja
```
- Formatos: PNG, JPG, WebP, SVG (los diagramas van como SVG o PNG). GIF y MP4 cortos para cuando haya video (Spec-800), si no pesa: tope por archivo en `config/tablero.yaml`.
- El id de la entrega es el nombre de la carpeta (`AAAA-MM-DD-slug`). Las carpetas que no validan **no rompen la página**: se saltean y se listan en `/debug` con el motivo.

### 2.2 Las opiniones, en la base
Tabla nueva `tablero_opinion` (en `init_db()`, sin migración): `id`, `entrega`, `archivo`, `tipo` (`me_gusta` | `no_va` | `nota`), `texto`, `created_at`.
- Cada opinión es una fila; no hay excluyencia ni dueño.
- Borrar la carpeta de una entrega no borra sus opiniones (quedan huérfanas, no se muestran).

### 2.3 `config/tablero.yaml`
```yaml
proyectos:
  calabaza: La calabaza de la cripta
  miniaturas: Miniaturas
  reels: Reels
tope_mb_por_archivo: 20
```
Viaja en la imagen: sumar un proyecto es un deploy. (Un proyecto desconocido se muestra con su slug, no falla.)

## 3. API (prefijo `/api/v1`)
- `GET /tablero/entregas?proyecto=` → lista (sin las opiniones, con su cuenta).
- `GET /tablero/entregas/{id}` → la entrega con sus filas, imágenes y opiniones.
- `GET /tablero/entregas/{id}/archivos/{archivo}` → el archivo (`FileResponse`; nombre validado contra el `entrega.yaml`, nada de rutas con `..`).
- `POST /tablero/entregas/{id}/opiniones` `{archivo, tipo, texto?}` → 201; `archivo` tiene que estar en la entrega; `texto` obligatorio solo en `nota`.
- `DELETE /tablero/opiniones/{id}` → saca esa opinión.
- Lectura de disco en cada request (son pocas carpetas): publicar no necesita reiniciar.

## 4. Lo que usa Claude (CLI)
```bash
uv run python -m src tablero publicar <carpeta> [--env prod|dev]   # valida entrega.yaml y la copia a data/<env>/tablero/
uv run python -m src tablero opiniones [--entrega <id>] [--desde AAAA-MM-DD] [--env prod]  # lo que dijeron, en texto
uv run python -m src tablero lista [--env prod]
```
- `publicar` valida antes de copiar (YAML, archivos que existen, tope) y no pisa una entrega que ya existe salvo `--reemplazar`.
- En prod, la base es `data/prod/stories.db`; la CLI escribe solo en `data/prod/tablero/` y solo **lee** opiniones.

## 5. Estructura
```
config/tablero.yaml
src/application/services/tablero/      → Entrega (Pydantic), leer/validar carpetas, opiniones
src/infrastructure/database/repositories/tablero_repository.py
src/presentation/routers/tablero_router.py
src/cli/commands/tablero.py
frontend/src/routes/tablero.ts
frontend/src/views/tablero/{index,entrega}.ejs  (+ partials)
frontend/public/js/tablero.js          → visor y opinar (UMD testeable)
```

## 6. Decisiones (OK a la spec, 2026-11-26)
- **D1 Sin identificar a nadie:** opiniones anónimas, cualquiera saca cualquiera (§1.2).
- **D2 Audio:** sí, MP3/WAV con `<audio>` (la voz de la calabaza ya generada); nunca las muestras crudas de Lucas.
- **D3 Sin avisos:** nada automático; Claude corre `tablero opiniones` al retomar cada checkpoint.
- **D4 «Qué mirar» sin dependencias nuevas:** párrafos, listas con `- ` y `**negrita**`, renderizados por una función chica con todo el texto escapado (no hace falta un motor de Markdown).

## 7. Testing
- Unit: validar `entrega.yaml` (completo, sin filas, archivo faltante, formato no permitido, slug raro), cuentas por tipo, rutas con `..` rechazadas.
- Integración API: listar, ver, servir un archivo, opinar (201/422), borrar una opinión; carpeta inválida salteada.
- CLI: `publicar` a un `data` temporal; `opiniones` en texto.
- Vitest: `tablero.js` (visor, opinar y sacar), vistas sin jerga, gramática visual, sin colores fijos.
- E2E (Firefox): publicar una entrega de prueba → verla → «Me gusta» + nota → recargar y que estén → sacar la nota.

## 8. Boundaries
- **Siempre:** las opiniones de verdad solo en prod; las pruebas en dev o en la base descartable de los E2E.
- **Preguntar antes:** publicar algo que no sea del proyecto (fotos de personas, audios de Lucas); borrar entregas de prod.
- **Nunca:** subir el tablero a un servicio externo; poner en una entrega muestras de voz crudas.

## 9. Slices (para el PLAN)
- **S1** Datos y API: `Entrega`, leer carpetas, tabla `tablero_opinion`, router. Tests.
- **S2** CLI: `publicar`, `opiniones`, `lista`.
- **S3** Páginas: `/tablero` y `/tablero/{id}`, visor, opinar. Vitest + E2E.
- **S4** Deploy y primera entrega real: lo que ya hay de miniaturas (tandas de Peter) como prueba, y después la Spec-800.

---

## 10. PLAN

### 10.1 Backend

**Dominio** — `src/domain/tablero.py` (Pydantic):
```python
class Archivo(BaseModel):          # una imagen, un SVG o un audio
    archivo: str                   # nombre dentro de la carpeta, sin "/" ni ".."
    leyenda: str = ""

class Fila(BaseModel):
    titulo: str = ""
    imagenes: list[Archivo]

class Entrega(BaseModel):
    id: str                        # nombre de la carpeta: AAAA-MM-DD-slug
    titulo: str
    proyecto: str                  # slug
    fecha: date                    # si falta en el YAML, la del id
    que_mirar: str = ""
    filas: list[Fila] = []
    imagenes: list[Archivo] = []   # sueltas

    def archivos(self) -> list[Archivo]: ...   # filas + sueltas, en orden

class Opinion(BaseModel):
    id: int; entrega: str; archivo: str
    tipo: Literal["me_gusta", "no_va", "nota"]; texto: str = ""; created_at: datetime
```

**Servicio** — `src/application/services/tablero/entregas.py`, sin IA ni base:
- `carpeta_tablero() -> Path`: `settings.tablero_dir` o, vacío, `tablero/` al lado de la base (igual que `miniaturas.carpeta_de`).
- `leer(carpeta) -> Entrega` (valida: YAML, id con formato, archivos que existen, extensión permitida, tope de MB) y `leer_todas() -> tuple[list[Entrega], list[Invalida]]` (las inválidas con su motivo, para `/debug`).
- `ruta_de(entrega, archivo) -> Path`: solo si el archivo está declarado en el `entrega.yaml` (D: nada que no esté listado se sirve).
- `publicar(origen, destino_base, reemplazar=False) -> Entrega`: valida en el origen, copia a una carpeta temporal y la renombra (para que la página nunca vea una entrega a medio copiar).
- `config/tablero.yaml` con `proyectos`, `tope_mb_por_archivo`, `extensiones` (`png jpg jpeg webp svg gif mp4 mp3 wav`), leído por `src/application/services/tablero/config.py` (validado al arrancar, como `arte.py`).
- Mensajes en `config/core_messages.yaml` → área `tablero` (Spec-620).

**Base** — `init_db()`:
```sql
CREATE TABLE IF NOT EXISTS tablero_opinion (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entrega TEXT NOT NULL, archivo TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('me_gusta','no_va','nota')),
  texto TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_tablero_opinion_entrega ON tablero_opinion(entrega);
```
Sin FK (las entregas viven en disco). `CREATE IF NOT EXISTS`: prod la crea sola en el deploy, sin export/import. Repo `SQLTableroRepository` (`agregar`, `de_entrega`, `cuentas_por_entrega`, `borrar`, `desde(fecha)`).

**API** — `src/presentation/routers/tablero_router.py` (§3), registrado en `main.py`:
- Respuesta de la entrega: cada archivo con `url`, `tipo_medio` (`imagen` | `audio` | `video`, por extensión), `me_gusta`, `no_va`, `notas: [{id, texto, created_at}]`; y además `opiniones` para el `×` de los toques.
- Archivos con `FileResponse` y `Cache-Control: no-store` (como las miniaturas); SVG con `Content-Security-Policy: script-src 'none'` para que un SVG no corra JS.
- Lecturas de disco en `asyncio.to_thread`.
- `/debug` del front muestra `GET /tablero/invalidas`.

**CLI** — subcomando `tablero` en `src/cli/runner.py` (`publicar | opiniones | lista`), lógica en `src/cli/tablero.py`.
- `--env prod|dev` elige `data/<env>/` (base y carpeta) sin tocar `DATABASE_URL`; por defecto `dev`, así un error no publica en prod.
- `opiniones` imprime por entrega y archivo: `👍 2 · 👎 1` y las notas con fecha; con `--desde` solo lo nuevo. Abre la base de prod **solo lectura** (`file:…?mode=ro`).

### 10.2 Frontend
- `frontend/src/controllers/tablero.controller.ts` + rutas en `routes/index.ts`: `GET /tablero` (con `?proyecto=`) y `GET /tablero/:id`.
- Los archivos se piden por el proxy `/api/*` que ya existe: la vista usa las URLs de la API tal cual.
- Vistas `tablero/index.ejs` (chips de proyecto con `?proyecto=`, tarjetas con tira de hasta 4 miniaturas y la cuenta) y `tablero/entrega.ejs` (nota «Qué mirar», filas lado a lado con scroll horizontal en el celular, grilla de sueltas, `<audio controls>` / `<video controls>` según el tipo).
- `utils/que_mirar.ts`: D4 (escapa todo, después párrafos, `- ` y `**…**`). Testeado.
- `public/js/tablero.js` (UMD, como `eta.js`): visor en `<dialog>` con ← → y Esc; «Me gusta» / «No va» → `POST` y actualiza la cuenta sin recargar; «Dejar una nota» abre un `textarea` en línea; `×` → `ForgeConfirm.ask({ icon: 'borrar' })` → `DELETE`.
- Menú: `{ page: 'tablero', href: '/tablero', icon: 'layout-dashboard', label: 'Tablero' }`.
- Tono y gramática visual (§1.3): `sin-jerga`, `gramatica-visual`, `no-hardcoded-colors` lo cubren al sumar las vistas.

### 10.3 Tests
- `tests/unit/test_tablero_entregas.py`: leer válida / sin filas / sin fecha (sale del id) / archivo faltante / extensión no permitida / pasado de tope / id con formato raro / `..` y `/` en `archivo`; `publicar` (no pisa sin `--reemplazar`, atómico).
- `tests/integration/test_tablero_api.py` con `tablero_dir` en `tmp_path`: listar (inválida salteada, cuentas), ver, archivo declarado 200 / no declarado 404, SVG con CSP, opinar 201 / archivo ajeno 422 / nota vacía 422, borrar.
- `tests/unit/test_tablero_cli.py`: `publicar` y `opiniones` contra un `data/` temporal.
- Vitest: `que-mirar.test.ts`, `tablero.js` (visor, opinar, sacar con confirmación), `tablero.view.test.ts` (render de index y entrega con una fixture).
- E2E `frontend/tests/e2e/tablero.spec.ts`: el `global-setup` publica una entrega de prueba en la carpeta descartable; verla → «Me gusta» + nota → recargar → sacar la nota.

### 10.4 Deploy
- `make deploy` desde `main` como siempre. El backup ya copia `data/prod/stories.db` (opiniones incluidas); **suma** `tar` de `data/prod/tablero/` como el de miniaturas (`deploy_prod.sh` paso 5).
- Después del deploy, S4: primera entrega real (las tandas de Peter de la Spec-790) con `tablero publicar --env prod`.

### 10.5 Riesgos
- **Permisos:** la CLI corre en el host y escribe `data/prod/tablero/`; el contenedor solo lee. Verificar en S4 que el usuario del contenedor puede leer lo copiado.
- **Archivos grandes:** el tope por archivo (20 MB) evita que un video de prueba trabe la página; las tiras de la lista usan `loading="lazy"`.

### 10.6 Tareas
- [x] T1 `config/tablero.yaml`, dominio, servicio `entregas` + tests unitarios (S1)
- [x] T2 tabla `tablero_opinion` + repo (S1)
- [x] T3 router + tests de integración (S1)
- [x] T4 CLI `tablero publicar | opiniones | lista` + tests (S2)
- [x] T5 vistas, controlador, menú, `que_mirar.ts` (S3)
- [x] T6 `tablero.js` (visor, opinar, sacar) + Vitest (S3)
- [x] T7 E2E + `make dev-status` + entrega de prueba en dev (checkpoint con el usuario en `https://storymaker.test/tablero`) (S3)
- [ ] T8 backup del tablero en `deploy_prod.sh` y CLAUDE.md (hechos), merge y `make deploy` (con OK) (S4)
- [ ] T9 primera entrega real en prod (S4)

### 10.7 Notas de la implementación (2026-11-26)
- Los botones de opinar son **solo íconos** (👍 👎 💬, con `title` y `aria-label`): con 4 opciones lado a lado, el texto los apilaba.
- La «×» de «Me gusta · N» / «No va · N» saca **la última** de ese tipo.
- Después de opinar o sacar, `tablero.js` pide la página de nuevo y reemplaza solo el bloque `[data-opiniones]` de ese archivo (sin duplicar el HTML en JS).
- Filtro por proyecto: `.opcion-forge__caja--elegida` (la opción elegida que es un link, sin input).
- El E2E usa una entrega que publica `run_api_mock.py` en la carpeta descartable.
- En el celular, el menú lateral del sitio no se colapsa solo y aprieta el contenido: es de todo el sitio, no del tablero (queda anotado, fuera de esta spec).

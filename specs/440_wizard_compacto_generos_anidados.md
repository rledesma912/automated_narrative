# SPEC-440: Wizard compacto, géneros anidados y narrador dinámico

**Fecha:** 2026-09-22
**Tipo:** SDD (Spec-Driven Development)
**Estado:** IMPLEMENT — S0–S3 desplegados; S0–S4 desplegados; S5 implementado (pendiente commit + deploy)

---

## ASSUMPTIONS

1. "Bien visible en 1080p" = el **paso 1 completo** (título + card Atmósfera + navegación) entra sin scroll en un viewport de navegador de **1920×960** (1080p menos el chrome del browser). La captura de referencia es de 1366×768; ahí se acepta scroll, pero no debe romperse el layout.
2. "Achicar sólo un poco" = reducir tipografía, paddings y espaciados de los campos del wizard (~15-20 % de altura), **sin** cambiar el ancho del contenedor ni la estructura de pasos.
3. La compactación aplica a **todos los pasos** del wizard (comparten `fieldHtml()` en `wizard.ejs`), no solo al paso 1.
4. Se mantienen los **8 géneros** actuales (mismos IDs). Lo que cambia es el catálogo de subgéneros, que pasa a depender del género.
5. El catálogo de géneros es **dominio de datos**: vive en la DB (tablas `genre` / `subgenre`) y lo gestiona el backend. `story.genero` / `story.subgenero` siguen guardando **IDs**, ahora con FK al catálogo. Hay cambio de esquema → `init_db()` + recrear `stories.db` (sin migraciones; recarga por `export-yaml` → `import-yaml`, ver Decisiones del plan).
6. El subgénero sigue siendo **opcional**. `otro: Otro estilo` existe en todos los géneros.
7. Los prompts siguen recibiendo `story.atmosfera` tal cual hoy (IDs). Enriquecer prompts con labels/descripciones del catálogo queda fuera de alcance.

→ Corregime ahora cualquiera de estas.

---

## OBJECTIVE

Cambios en el wizard de autoría (Spec-220), un bug de contrato descubierto durante el análisis y una propuesta de dominio:

1. **Wizard compacto** — que el formulario se lea completo en 1080p.
2. **Género → Subgénero anidados** — catálogo canónico jerárquico en el dominio; el combo de subgénero se filtra según el género elegido.
3. **Rasgos nuevos** — `miedoso` (opuesto de `audaz`), `curioso`, `impulsivo`, `desconfiado`.
4. **(Hallazgo) Contrato frontend ↔ API roto** — ver §4.
5. **Combo de narrador dinámico** — solo lista los personajes ya creados.
6. ~~Feedback de generación~~ → movido a **Spec-460**.
7. ~~Entidad/amenaza~~ → movida a **Spec-450**.

Éxito = un usuario en 1080p completa el paso 1 sin scrollear, solo puede elegir subgéneros coherentes con el género y el par elegido llega persistido a `story.genero` / `story.subgenero`.

---

## 1. WIZARD COMPACTO

### Estado actual (`frontend/src/views/wizard.ejs`)

| Elemento | Hoy | Propuesto |
|---|---|---|
| `CLS_INPUT` (input/select/textarea) | `text-lg px-4 py-3` | `text-base px-3 py-2` |
| Label de campo | `text-lg mb-1` | `text-base mb-0.5` |
| Subtítulo de campo | `text-sm mb-2` | `text-xs mb-1.5` |
| Wrapper de campo | `mb-5` | `mb-4` |
| Opciones radio/checkbox | `text-base`, `space-y-2` | `text-sm`, `space-y-1.5` |
| Radio de 5 opciones (ej. tono) | 1 columna | `grid sm:grid-cols-2 gap-x-6 gap-y-1.5` |
| Card de grupo | `!p-6 space-y-5` | `!p-5 space-y-4` |
| Stepper | `mb-10` | `mb-6` |
| Título de paso (`heading-forge-lg`) | `text-2xl md:text-3xl` | se mantiene la clase; en wizard `!text-2xl` |
| Subtítulo de paso | `mb-8` | `mb-5` |
| `<form>` | `space-y-6` | `space-y-5` |
| Navegación | `pt-8` | `pt-6` |

No se toca `.card-forge` global (lo usan galería y relatos): los overrides van en el wizard.

### Correcciones de copy (mismo archivo `ui_definitions.yaml`)

- "Cómo **evolve** la tensión" → "Cómo **evoluciona** la tensión" (label y hint).
- hint de `attention_focus`: "se **fixa**" → "se **fija**", "**auditvas**" → "**auditivas**".

### Criterio de aceptación

- Playwright, viewport 1920×960, `/generar/paso/1`: el botón "Siguiente" es visible sin scroll (`scrollHeight <= innerHeight` del contenedor principal).
- Viewport 1366×768: sin scroll horizontal.

---

## 2. GÉNEROS Y SUBGÉNEROS ANIDADOS

### Problema

Hoy `atmosfera` y `atmosphere_subgenre` son dos `select` planos e independientes en `frontend/config/ui_definitions.yaml`. Los "subgéneros" actuales mezclan ambientación y época (`rural`, `historico`, `scifi`, `leyenda_urbana`…), permiten combinaciones sin sentido (`body_horror` + `rural`) y el backend los acepta como string libre.

### Taxonomía — v2 (ajustada)

Criterio de ajuste: un subgénero describe **qué tipo de miedo** propone la historia, no la época ni el lugar (eso va en escenarios). Por eso salen `victoriano` y `thriller_psicologico` (este último se superponía con Terror Psicológico).

| Género (ID) | Subgéneros (ID: label) |
|---|---|
| `terror_psicologico` Terror Psicológico | `paranoia`: Paranoia y persecución · `culpa_trauma`: Culpa y trauma · `locura`: Descenso a la locura · `doble`: El doble / identidad fracturada · `domestico`: Terror doméstico (familia, hogar) · `aislamiento`: Aislamiento y soledad **(nuevo)** |
| `horror_cosmico` Horror Cósmico | `lovecraftiano`: Lovecraftiano clásico · `culto_prohibido`: Cultos y saberes prohibidos · `dimensional`: Otras dimensiones · `abismal`: Horror oceánico / abismal · `ciencia_prohibida`: Ciencia prohibida / experimento **(renombrado)** |
| `terror_gotico` Terror Gótico | `gotico_clasico`: Gótico clásico (casonas, castillos) · `maldicion_familiar`: Maldición familiar / linaje · `vampirico`: Vampírico · `gotico_criollo`: Gótico criollo / sureño (decadencia rural) · `amor_maldito`: Romance oscuro / amor maldito **(reemplaza `victoriano`)** |
| `body_horror` Horror Corporal | `mutacion`: Mutación y transformación · `contagio`: Infección y contagio · `quirurgico`: Médico / quirúrgico · `parasitario`: Parásitos y simbiosis · `decadencia`: Enfermedad y decadencia del cuerpo |
| `paranormal` Fenómenos Paranormales | `casa_embrujada`: Casa embrujada · `posesion`: Posesión · `fantasmas`: Fantasmas y aparecidos · `poltergeist`: Poltergeist · `leyenda_urbana`: Leyenda urbana · `objeto_maldito`: Objetos y lugares malditos |
| `folk_horror` Terror Rural | `rural`: Leyendas del campo · `mitologia_regional`: Mitología regional (Luz Mala, Pombero…) · `culto_pagano`: Cultos paganos y rituales · `pueblo_aislado`: Pueblo aislado / comunidad cerrada · `brujeria`: Brujería y curanderismo |
| `suspenso` Suspenso / Thriller | `misterio`: Misterio / enigma **(reemplaza `thriller_psicologico`)** · `policial_noir`: Policial / noir · `acecho`: Acecho · `invasion_hogar`: Invasión del hogar · `conspiracion`: Conspiración |
| `terror_supervivencia` Terror de Supervivencia | `slasher`: Slasher · `criaturas`: Criaturas y monstruos · `apocalipsis`: Apocalipsis / infectados · `naturaleza_hostil`: Naturaleza hostil · `encierro`: Encierro / trampa |

Todos los géneros incluyen además `otro`: Otro estilo.

**Compatibilidad:** `folk_horror/rural` se conserva. `input_stories/barco_fantasma.yaml` (`terror_psicologico/historico`) queda inválido → se actualiza a `paranormal/fantasmas`. `frontend/config/story_template.yaml` usa `otro` → sigue válido.

### Modelo de datos — el catálogo vive en la DB

El catálogo es **dominio de datos**: vive en SQLite y lo gestiona el backend. Dos tablas nuevas en `init_db()` (sin migraciones: se recrea `stories.db`):

```sql
CREATE TABLE IF NOT EXISTS genre (
    id          TEXT PRIMARY KEY,          -- 'folk_horror'
    label       TEXT NOT NULL,
    order_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS subgenre (
    genre_id    TEXT NOT NULL,
    id          TEXT NOT NULL,             -- 'rural', 'otro'
    label       TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    PRIMARY KEY (genre_id, id),
    FOREIGN KEY (genre_id) REFERENCES genre(id) ON DELETE RESTRICT
);
```

`story` agrega las FK (mismas columnas `genero` / `subgenero`):

```sql
FOREIGN KEY (genero)            REFERENCES genre(id),
FOREIGN KEY (genero, subgenero) REFERENCES subgenre(genre_id, id)
```

La FK compuesta hace que **la base misma rechace un par que no corresponde** (`body_horror` + `rural`). `PRAGMA foreign_keys = ON` ya está activo en `get_connection()`. La PK compuesta permite repetir `otro` en cada género.

**Valores vacíos → `NULL`:** con la FK, `''` violaría la restricción. Los repos persisten `NULL` cuando no hay género o subgénero (hoy guardan `''`), y el dominio sigue exponiendo `""` hacia arriba. En SQLite, una FK compuesta con alguna columna `NULL` no se verifica, así que "género sin subgénero" es válido.

**Seed:** `init_db()` puebla `genre` y `subgenre` con `INSERT OR IGNORE` desde `src/infrastructure/database/seeds/genre_catalog.py` (constante Python con la tabla v2). Es idempotente y solo corre al crear la DB. Una vez creada, la DB manda.

Backend:

- `src/domain/models.py` — entidades `Genre` y `Subgenre`.
- `src/domain/interfaces.py` — `GenreRepository` (protocolo): `list_with_subgenres()`, `exists(genero, subgenero) -> bool`.
- `src/infrastructure/database/repositories/genre_repository.py` — `SQLGenreRepository`.
- `src/application/use_cases/list_genres.py` — `ListGenresUseCase`.
- Validación en `CreateStoryUseCase` y en el PATCH de `story_router.py`: se consulta `GenreRepository.exists()` antes de persistir → **422** con detalle legible. La FK es la última línea de defensa; si igual salta un `IntegrityError`, se traduce a 422 y no llega como 500.
- `YamlStoryLoader` / CLI `generate`: par inválido → error claro antes de crear la historia.
- `src/presentation/routers/catalog_router.py` — `GET /api/v1/catalog/genres` → `[{id, label, subgenres: [{id, label}]}]`, ordenado por `order_index`.
- La gestión del catálogo en esta spec es **solo lectura + seed**. Un CRUD de géneros queda fuera de alcance (ver Open Questions).

Frontend:

- `ui_definitions.yaml`: `atmosfera` y `atmosphere_subgenre` quedan `type: select` con `source: genre_catalog` (sin `options:` hardcodeadas); `atmosphere_subgenre` declara `depends_on: atmosfera`.
- `catalog.service.ts` — `GET /api/v1/catalog/genres` al Core, con caché en memoria (TTL corto, ej. 5 min).
- `wizard.ejs` — render server-side: el combo de subgénero muestra solo los del género guardado; sin género → `disabled` con "Elegí primero el tipo de horror". El catálogo se embebe como `<script type="application/json" id="genre-catalog">`.
- `wizard.js` — al cambiar género: repoblar subgénero; si el valor actual no pertenece al nuevo género → reset a vacío y auto-save de ambos campos (el auto-save de Spec-220 ya dispara en `change`).
- `wizard.service.ts::mapStoryToWizard` — rehidrata contra el catálogo; subgénero no reconocido → vacío.

### Criterios de aceptación

- DB recién creada → `genre` tiene 8 filas y `subgenre` 50 (42 + 8 `otro`).
- Seleccionar `body_horror` → el combo de subgénero lista solo sus 5 + `otro`.
- Cambiar de `folk_horror/rural` a `suspenso` → subgénero vuelve a "Seleccioná…".
- Editar una historia existente `folk_horror/rural` → ambos combos vienen precargados.
- `POST /stories` con `genero=body_horror, subgenero=rural` → 422 (no 500).
- `INSERT` directo en `story` con un par inválido → `IntegrityError` (FK).
- Core caído al abrir el paso 1 → el wizard renderiza; género y subgénero `disabled` con aviso (no 500).

---

## 3. RASGOS DE PERSONAJE NUEVOS

Se agregan a `protagonista_N_traits`:

```yaml
- "miedoso: Miedoso / Temeroso"     # opuesto de audaz
- "curioso: Curioso"
- "impulsivo: Impulsivo"
- "desconfiado: Desconfiado"
```

La lista está copiada 5 veces en `ui_definitions.yaml`. Se unifica con un ancla YAML (`&character_traits` / `*character_traits`; `js-yaml` las soporta), así el próximo rasgo se agrega en un solo lugar. Con 18 rasgos, la grilla del multi-select pasa a `sm:grid-cols-3 lg:grid-cols-4` para no alargar la card. El backend guarda `traits` como JSON libre: sin cambios.

---

## 4. HALLAZGO: CONTRATO FRONTEND ↔ API

Al rastrear el flujo de `genero`, encontré (por lectura de código, a confirmar con un POST real en el primer slice):

- `mapWizardToCore()` (`frontend/src/services/mapper.service.ts`) envía `atmosfera` (string) y `storyteller_config` (objeto).
- `StoryCreateRequest` (`src/presentation/schemas/request.py`) espera `genero`, `subgenero`, `tono` y `narrator_config`. Pydantic ignora campos extra por defecto.

**Consecuencia:** las historias creadas desde el wizard web quedarían con `genero/subgenero/tono` vacíos **y** con `narrator_config = None`, perdiendo escenarios con descripción, reglas tipadas y toda la config de voz (percepción, conocimiento, lenguaje, sesgos). Las historias de la DB actual vienen del CLI (YAML), que sí usa el camino correcto.

**Estado (2026-09-22): resuelto del lado de la API** (hotfix para no perder la sesión del wizard con "La pena del colectivo"):

- `StoryCreateRequest.narrator_config` acepta `storyteller_config` como alias (`AliasChoices`).
- `_request_to_dto()` deriva `genero`/`subgenero`/`tono` de `atmosphere` y los `actos` de `storyteller_config.actos` cuando no vienen explícitos (mismo criterio que `YamlStoryLoader`; helpers `extract_atmosphere`/`extract_actos` en `narrator_config_sanitizer.py`).
- Tests: `tests/unit/presentation/routers/test_story_router.py`.

**Pendiente en esta spec:** que `mapWizardToCore()` envíe directamente `genero`, `subgenero`, `tono` y `narrator_config`, y deje de mandar `atmosfera` (es derivado en `Story.atmosfera`). Con el alias ya no es bloqueante; se hace junto con el catálogo de géneros (§2).

**También pendiente (visto en "la pena del colectivo", 2026-09-22):** `mapWizardToCore()` no limpia a ID los valores de `perception`, `knowledge`, `language` y `bias` ni el `Registro` del `relator`: se guardan como `"poco_confiable: A veces ve bien, a veces no"` en vez de `"poco_confiable"`. No rompe la generación (el prompt los interpola como texto), pero difiere de las historias del CLI y ensucia el export YAML. Aplicar `parseOptionalLabel` a todos esos campos.

**Antes de recrear la DB por el esquema de §2:** exportar las historias existentes (`python -m src export-yaml`) y re-importarlas. "la pena del colectivo" tiene `horror_cosmico/rural`, par que la FK del catálogo v2 rechazaría: hay que elegirle un subgénero válido al re-importar.

---

## 5. COMBO "QUIÉN CUENTA LA HISTORIA" DINÁMICO

### Problema

`storyteller_id` tiene 5 opciones fijas en `ui_definitions.yaml`. `updateStoryteller()` (`frontend/public/js/wizard.js`) solo renombra las opciones ("Personaje 3 (sin nombre)") pero nunca las oculta: el usuario ve 5 personajes aunque haya creado 1.

### Comportamiento esperado

- El combo lista **solo los personajes cuyas cards están visibles y tienen nombre** (label = nombre escrito).
- Recalcula en: `input` sobre `protagonista_N_name`, `addPersonaje()` y la confirmación de `askDeletePersonaje()`.
- Si el narrador seleccionado se borra o queda sin nombre → reset a "Seleccioná…" y auto-save.
- Con 1 solo personaje con nombre y nada elegido → se preselecciona ese.
- Sin personajes con nombre → combo `disabled` con placeholder "Primero nombrá un personaje".
- **Render server-side** (`wizard.ejs`): mismo filtro sobre los datos guardados, para que al volver al paso no aparezca el combo con 5 opciones antes de que corra el JS.
- **Validación en el POST del paso** (`wizard.controller.ts`): `storyteller_id` debe apuntar a un personaje con nombre; si no, se re-renderiza el paso con error.

Las opciones de `storyteller_id` dejan de estar hardcodeadas en el YAML (`source: characters`).

### Criterios de aceptación

- Paso 2 con 1 personaje → el combo tiene 1 opción (su nombre), preseleccionada.
- Agregar el personaje 2 y escribir "Ricardo" → aparece "Ricardo" en el combo.
- Borrar el personaje que narra → combo en "Seleccioná…".

---

## 6. FEEDBACK DE GENERACIÓN — MOVIDO A SPEC-460

El diagnóstico (botón que sigue habilitado, "GENERANDO" poco visible y visible sin generación, "Ver progreso" con `href="#"`) y el diseño de UI (botón en estado ocupado + banda de generación) pasan a **Spec-460** (`specs/460_jobs_asincronos_y_bus_sse.md`), porque dependen de reemplazar el polling por eventos SSE empujados desde el servidor.

---

## 7. ENTIDAD / AMENAZA — FUERA DE ALCANCE

Se trata en **Spec-450** (`specs/450_entidad_narrativa.md`). Esta spec no crea el grupo "La Amenaza" en el wizard.

---

## 8. EDITAR HISTORIAS YA GENERADAS (decisión 2026-09-22)

Hoy `PATCH /stories/{id}` responde 422 si la historia no es `draft` ("Solo se pueden editar historias en estado draft"). Hasta Spec-460 el wizard tragaba ese error: editar una historia completada **nunca se guardaba**, sin aviso. Decisión del usuario: **permitir editar historias generadas**.

- `PATCH /stories/{id}` acepta `draft`, `completed` y `failed`. Con un **job activo** → 409 (no se editan datos mientras se generan).
- Editar **no borra** lo generado (actos, journal, relatos) ni cambia el `status`: los cambios se aplican en la próxima generación.
- Tras guardar una historia `completed`, la galería avisa: "Guardada. Regenerala para aplicar los cambios".

## 9. HALLAZGO: TIPOS DE REGLA DEL WIZARD ≠ DOMINIO (2026-09-22)

El wizard ofrece `entorno`, `psicologica`, `paranormal`, `evento`, `social`; el dominio (`RuleType`) acepta `psicologica`, `entorno`, `fenomeno`, `indicador`. Los tres que no coinciden se guardan **en silencio como `None`** (visto al recuperar "barco fantasma" y "el galpon": sus reglas `social` quedaron sin tipo). Se resuelve en S1 (contrato wizard → API). Mapeo propuesto en Open Questions.

---

## PLAN

### Estrategia

Slices verticales, cada uno desplegable. Primero lo que corrige pérdida de datos (editar, contrato), después el catálogo (backend → frontend) y al final lo visual. Al cerrar cada slice: lint + pytest + Vitest + Playwright en verde, commit y despliegue con tu OK.

### Mapa

```
S0 Editar historias generadas ──┐
S1 Contrato wizard → API ───────┼─▶ S2 Catálogo de géneros (backend) ─▶ S3 Combos dependientes (frontend)
                                │                                                   │
                                └─▶ S4 Rasgos + narrador dinámico ◀─────────────────┘
                                                   │
                                                   ▼
                                        S5 Wizard compacto (1080p) ─▶ S6 Docs + DONE
```

### S0 — Editar historias ya generadas (§8)

- **Qué:** relajar la regla de `PATCH /stories/{id}` (draft/completed/failed; 409 con job activo); aviso en la galería tras editar una historia generada.
- **Stack:** FastAPI (`story_router`), `SQLJobRepository.get_active_for_story`; controller Express + flash de la galería.
- **Verificación:** pytest (editar completada conserva beats/relatos/status; 409 con job activo); Vitest (mensaje); Playwright (editar → guardar → aviso; datos cambiados en la ficha).

### S1 — Contrato wizard → API (§4 pendiente + §9)

- **Qué:** `mapWizardToCore()` envía `genero`/`subgenero`/`tono` y `narrator_config` explícitos, y **solo IDs** en `perception`/`knowledge`/`language`/`bias`/`relator` (hoy van como "id: Etiqueta"). `mapStoryToWizard()` acepta ambos formatos (IDs y legado "id: Etiqueta") al rehidratar. Tipos de regla alineados con `RuleType` (§9) en `ui_definitions.yaml` + mapeo de los valores viejos.
- **Stack:** TypeScript (`mapper.service.ts`, `wizard.service.ts`), YAML de UI; backend sin cambios salvo el mapeo de tipos de regla viejos en `_request_to_dto` / `YamlStoryLoader` si se decide mapearlos.
- **Verificación:** Vitest del mapper (payload exacto; rehidratación de ambos formatos); pytest del mapeo de tipos; E2E: wizard completo → la historia guardada tiene IDs limpios y reglas tipadas.

### S2 — Catálogo de géneros en la DB (backend, §2)

- **Qué:** tablas `genre`/`subgenre` + seed v2 en `init_db()` (`INSERT OR IGNORE`, idempotente); `GenreRepository` (`list_with_subgenres`, `exists`); validación de `(genero, subgenero)` en create/update (API → 422 legible) y en `YamlStoryLoader`; `GET /api/v1/catalog/genres`.
- **Integridad (ver Open Questions §1):** propuesta = validación en la capa de aplicación + tablas nuevas **aditivas** (sin tocar `story`) → **sin recrear bases**.
- **Stack:** SQLite/aiosqlite, FastAPI, pydantic; seed como constante Python.
- **Verificación:** pytest (seed idempotente: 8 géneros / 50 subgéneros; par inválido → 422; género sin subgénero válido; `otro` en todos; endpoint ordenado).

### S3 — Combos Género → Subgénero (frontend, §2)

- **Qué:** `catalog.service.ts` (GET al Core con caché en memoria); `ui_definitions.yaml` con `source: genre_catalog` / `depends_on`; `wizard.ejs` renderiza subgéneros del género guardado (sin género → `disabled` con aviso); `wizard.js` repuebla y resetea al cambiar de género (auto-save de ambos); rehidratación: subgénero inválido → vacío (caso "la pena del colectivo": `horror_cosmico/rural`, y "barco fantasma": `terror_psicologico/historico`). Core caído → combos deshabilitados con aviso, sin 500.
- **Stack:** Express/TypeScript, EJS, JS vanilla, `<script type="application/json">` con el catálogo embebido.
- **Verificación:** Vitest (servicio con caché y Core caído); Playwright (filtrado, reset, rehidratación, subgénero inválido vacío).

### S4 — Rasgos nuevos + narrador dinámico (§3, §5)

- **Qué:** lista de rasgos única con ancla YAML + `miedoso`, `curioso`, `impulsivo`, `desconfiado`; combo "quién cuenta la historia" solo con personajes creados y con nombre (JS + render server-side + validación en el POST del paso).
- **Stack:** YAML (`js-yaml` soporta anclas), EJS, JS vanilla, controller Express.
- **Verificación:** Vitest (parser de YAML con anclas; validación del paso); Playwright (1 personaje → 1 opción preseleccionada; agregar/borrar actualiza el combo).

### S5 — Wizard compacto para 1080p (§1)

- **Qué:** tipografías/paddings/espaciados de la tabla §1, radios de 5 opciones en 2 columnas, correcciones de copy ("evoluciona", "fija", "auditivas").
- **Stack:** Tailwind (clases en `wizard.ejs`, sin tocar `.card-forge` global).
- **Verificación:** Playwright con viewport 1920×960 (paso 1 sin scroll) y 1366×768 (sin scroll horizontal) + captura para revisión visual.

### S6 — Documentación y cierre

- **Qué:** `CLAUDE.md` (tablas del catálogo, endpoint, reglas de edición), notas en Spec-220, Spec-440 → DONE.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Cambiar el wizard rompe el E2E de guardado de Spec-460 (usa `selectOption({ index: 1 })`) | Se actualiza en S3/S4 junto con el cambio. |
| Datos existentes con pares género/subgénero inválidos | No se bloquea la lectura: el wizard los muestra vacíos para elegir uno válido; solo se valida al guardar. |
| Valores legado "id: Etiqueta" en historias ya guardadas | La rehidratación acepta ambos formatos (S1). |
| El seed de E2E depende de `data/dev/stories.db` | Sin recrear bases (S2 aditivo) no cambia. |

---

## DECISIONES DEL PLAN (2026-09-23)

1. **Integridad del catálogo: FK compuesta y recrear las bases.** Se aceptan las consecuencias: en dev se pierden actos, journal y relatos de las historias existentes (se re-importan como borradores); en prod hay 3 borradores y se re-importan sin pérdida. Para no escribir scripts de migración, la recarga usa el round-trip de Spec-302: `export-yaml` → recrear DB → **`import-yaml`** (comando nuevo).
2. **Tipos de regla:** el wizard ofrece los 4 de `RuleType` (`entorno` "Del lugar", `psicologica` "De la mente", `fenomeno` "Sobrenatural", `indicador` "Señal o indicio"); valores viejos: `paranormal` → `fenomeno`, `social` → `entorno`, `evento` → sin tipo.
3. **Editar historias generadas:** no borra lo generado ni cambia el `status`; el aviso sugiere regenerar.

### Ajustes al PLAN por la decisión 1

- **S2** suma: FK en `story`; `NULL` en vez de `''` para género/subgénero vacíos; `import-yaml` y `export-yaml --all`; semilla propia del arnés E2E (ya no copia `data/dev/stories.db`, que se recrea); procedimiento de recarga de dev y prod.
- **Pares inválidos existentes** ("la pena del colectivo" `horror_cosmico/rural`, "barco fantasma" `terror_psicologico/historico`): la FK los rechazaría. `import-yaml --descartar-subgenero-invalido` los importa con el subgénero vacío (género válido, sin subgénero) y avisa; se elige uno válido después en el wizard.
- **Tipos de regla perdidos:** las reglas `social` de "barco fantasma" y "el galpon" quedaron sin tipo en prod al recuperarlas. En la recarga de prod (T2.9) esas dos se re-importan desde el backup original (`social` → `entorno` por el mapeo de S1).

---

## TASKS

Formato: **Acceptance** / **Verify** / **Files**. Checkpoint por slice: lint + pytest + tsc + Vitest + Playwright en verde → commit y despliegue con tu OK.

### S0 — Editar historias ya generadas (§8)

- [x] **T0.1:** Regla de edición en la API.
  - Acceptance: `PATCH /stories/{id}` acepta `draft`, `completed` y `failed`; con job activo → 409 `{detail, job_id}`; no toca `macro_beat`, `narrative_journal`, `narrative_anchors`, `generated_narrative` ni `status`.
  - Verify: `uv run pytest tests/integration/test_story_edit.py -q` (editar completada conserva beats/relatos/estado; 409 con job activo; historia inexistente 404).
  - Files: `src/presentation/routers/story_router.py`, `tests/integration/test_story_edit.py` (nuevo)
- [x] **T0.2:** Aviso tras editar una historia generada.
  - Acceptance: `saveWizardStory` con historia `completed`/`failed` redirige con `success=saved_regenerar` → toast "Guardada. Regenerala para aplicar los cambios"; con borrador, el aviso actual. Error 409 → mensaje "Hay una generación en curso; esperá a que termine" en la confirmación.
  - Verify: Vitest `wizard.controller.test.ts` (3 casos nuevos).
  - Files: `frontend/src/controllers/wizard.controller.ts`, `frontend/src/controllers/gallery.controller.ts`
- [x] **T0.3:** E2E de edición.
  - Acceptance: galería → Editar historia completada → cambiar título → Guardar → aviso de regenerar; la ficha muestra el título nuevo y los relatos siguen.
  - Verify: `npx playwright test story-edit.spec.ts`
  - Files: `frontend/tests/e2e/story-edit.spec.ts` (nuevo)
- [x] **T0.4 (hallazgos de S0):** editar de verdad requería tres arreglos que no estaban en el plan.
  - **Pérdida de datos:** `SQLStoryRepository.save()` hace `INSERT OR REPLACE INTO story` (con FKs en cascada borra actos narrados, journal, anclas, relatos y jobs) y reescribe `macro_beat` sin `generated_act`. Con la regla relajada, editar una historia generada la dejaba sin nada (reproducido en test). Nuevo `update_inputs()`: `UPDATE` de la fila + personajes/reglas/escenarios; no toca lo generado ni el `status`. `PATCH` lo usa.
  - **Wizard vacío al editar:** `GET /stories/{id}` no devolvía `storyteller_config` (solo el `narrator_config` sanitizado: sin escenarios, reglas, actos ni atmósfera), y `mapStoryToWizard` lee `storyteller_config`. Ahora devuelve la vista de autoría completa (`YamlStoryExporter.authoring_config`).
  - **Actos perdidos en el export:** `_build_actos` leía `narrator_config.actos`, que se sanitiza al guardar. Ahora: `narrator_config.actos` → `macro_beat.synopsis_beat` → `sinopsis` en 5 párrafos (tras una generación web es la única copia). Impacta también la recarga de S2 (`export-yaml`).
  - Verify: `tests/integration/test_story_edit.py` (7 tests) + E2E.
- [x] **T0.5 (pedido 2026-09-23):** en la galería el título deja de ser link; la vista de la historia se abre con un botón «Vista» (primero de las acciones, en todos los estados). Verify: Vitest `gallery.view.test.ts`.
- [x] **Checkpoint S0:** lint + pytest 617 + tsc + Vitest 61 + Playwright 18 (×2).

### S1 — Contrato wizard → API (§4 pendiente + §9)

- [x] **T1.1:** `mapWizardToCore()` con IDs y campos explícitos.
  - Acceptance: envía `genero`, `subgenero`, `tono` y `narrator_config` (ya no `storyteller_config` ni `atmosfera`); `perception`/`knowledge`/`language`/`bias` y el `Registro` del `relator` solo con IDs (`poco_confiable`, no "poco_confiable: A veces…").
  - Verify: Vitest `mapper.service.test.ts` (nuevo): payload exacto para un wizard completo.
  - Files: `frontend/src/services/mapper.service.ts`
- [x] **T1.2:** Rehidratación con ambos formatos.
  - Acceptance: `mapStoryToWizard()` reconoce valores guardados como ID o como legado "id: Etiqueta" y los lleva a la opción correcta del combo.
  - Verify: Vitest (historia legado y nueva → mismo wizard).
  - Files: `frontend/src/services/wizard.service.ts`
- [x] **T1.3:** Tipos de regla alineados con `RuleType`.
  - Acceptance: `ui_definitions.yaml` ofrece los 4 tipos del dominio (lista única con ancla YAML); `RuleType.from_raw()` en el dominio mapea `paranormal`→`fenomeno`, `social`→`entorno`, `evento`/desconocido→`None`, y lo usan `_request_to_dto`, `CreateStoryUseCase`, `YamlStoryLoader` y el repo al leer.
  - Verify: pytest `tests/unit/domain/test_models.py` (mapeo) + integración (POST con `social` → guardado `entorno`).
  - Files: `src/domain/models.py`, `src/presentation/routers/story_router.py`, `src/application/use_cases/create_story.py`, `src/infrastructure/loaders/yaml_loader.py`, `src/infrastructure/database/repositories/story_repository.py`, `frontend/config/ui_definitions.yaml`
- [x] **T1.4:** E2E del contrato.
  - Acceptance: wizard completo → la historia guardada tiene `narrator_config` con IDs limpios y la regla con su tipo.
  - Files: `frontend/tests/e2e/generation-guard.spec.ts` (extender el test de guardado)
- [x] **Notas de S1:** `YamlStoryLoader` no cambia: pasa el tipo crudo y `CreateStoryUseCase` lo resuelve con `RuleType.from_raw()` (también acepta "id: Etiqueta" y mayúsculas). La rehidratación además mapea `paranormal`/`social` al combo nuevo; `evento` queda sin selección. Se deja de enviar `actos` suelto (el API lo toma de `narrator_config.actos`).
- [x] **Checkpoint S1:** lint + pytest 630 + tsc + Vitest 69 + Playwright 18.

### S2 — Catálogo de géneros en la DB + recarga (§2)

- [x] **T2.1:** Esquema.
  - Acceptance: tablas `genre` y `subgenre` (PK `(genre_id, id)`) en `init_db()`; seed v2 idempotente (`INSERT OR IGNORE`) desde `src/infrastructure/database/seeds/genre_catalog.py`; `story` con `FOREIGN KEY (genero) → genre(id)` y `FOREIGN KEY (genero, subgenero) → subgenre(genre_id, id)`; los repos escriben `NULL` (no `''`) cuando no hay género/subgénero y el dominio sigue exponiendo `""`.
  - Verify: pytest `test_db_connection.py` (8 géneros, 50 subgéneros, seed idempotente, FK rechaza par inválido, `NULL` pasa).
  - Files: `src/infrastructure/database/connection.py`, `src/infrastructure/database/seeds/genre_catalog.py` (nuevo), `src/infrastructure/database/repositories/story_repository.py`
- [x] **T2.2:** `GenreRepository` y validación.
  - Acceptance: entidades `Genre`/`Subgenre`, protocolo `GenreRepository` (`list_with_subgenres`, `exists`), `SQLGenreRepository`; par inválido → 422 legible en `POST`/`PATCH /stories` y error claro en `YamlStoryLoader`; `IntegrityError` residual → 422 (nunca 500).
  - Verify: pytest (válido, inválido, género sin subgénero, `otro`, 422 del API).
  - Files: `src/domain/models.py`, `src/domain/interfaces.py`, `src/infrastructure/database/repositories/genre_repository.py` (nuevo), `src/application/use_cases/create_story.py`, `src/presentation/routers/story_router.py`, `src/infrastructure/loaders/yaml_loader.py`
- [x] **T2.3:** `GET /api/v1/catalog/genres`.
  - Acceptance: `[{id, label, subgenres: [{id, label}]}]` ordenado por `order_index`.
  - Files: `src/presentation/routers/catalog_router.py` (nuevo), `src/main.py`, `src/application/use_cases/list_genres.py` (nuevo)
- [x] **T2.4:** CLI `import-yaml` y `export-yaml --all`.
  - Acceptance: `python -m src import-yaml <archivos...> [--descartar-subgenero-invalido]` crea cada historia como borrador **sin llamar al LLM**; `export-yaml --all --output-dir DIR` exporta todas. Round-trip export → import conserva personajes, escenarios, reglas tipadas, actos, narrador y atmósfera.
  - Verify: pytest (round-trip; par inválido sin flag → error; con flag → subgénero vacío + aviso).
  - Files: `src/cli/runner.py`, `src/cli/commands.py`
- [x] **T2.5:** `input_stories/barco_fantasma.yaml` con par válido (`paranormal/fantasmas`, según §2).
- [x] **T2.6:** Semilla propia del arnés E2E.
  - Acceptance: `run_api_mock.py` arranca con DB vacía, importa `input_stories/*.yaml` y genera cada una con el LLM mock (historias `completed` con relato); ya no copia `data/dev/stories.db`. Los E2E buscan las historias por título vía API (sin IDs fijos).
  - Verify: `npx playwright test` completo en verde.
  - Files: `tests/e2e_support/run_api_mock.py`, `frontend/playwright.config.ts`, `frontend/tests/e2e/*.spec.ts`
- [x] **T2.7:** Recarga de dev.
  - Acceptance: backup de `data/dev/stories.db` → `export-yaml --all` → `make db` → `import-yaml`; las 2 historias quedan como borradores con sus datos.
- [x] **T2.8:** Tests de catálogo en integración.
  - Acceptance: `test_job_api.py` / `test_story_router.py` usan pares válidos; nuevo `test_catalog_api.py`.
- [x] **T2.9:** Recarga de prod (**hecha en el despliegue de S3**, ver notas).
  - Acceptance: sin jobs activos → backup → `export-yaml --all` dentro de `narrative-api` → recrear `data/prod/stories.db` → `import-yaml --descartar-subgenero-invalido` ("la pena del colectivo"); "barco fantasma" y "el galpon" desde el backup original (recupera los tipos `social` → `entorno`). Verificación de las 3 historias como en la recuperación del 2026-09-22.
- [x] **Notas de S2 (2026-09-23):**
  - **Despliegue diferido a S3:** el wizard todavía ofrece los subgéneros planos viejos; de ellos solo `otro` (con cualquier género), `rural` (Terror Rural) y `leyenda_urbana` (Paranormal) existen en el catálogo v2. Desplegar S2 solo haría que guardar desde el wizard diera 422 en casi todos los casos. S2 y S3 salen juntos, con la recarga de prod (T2.9).
  - **Validación del YAML:** `YamlStoryLoader` no tiene acceso a la DB; la validación ocurre en `CreateStoryUseCase` (vía `ensure_valid_genre`) antes de persistir, y el CLI la muestra como "Error de validación" (exit 2).
  - **Fuga de conexión:** `SQLStoryRepository.save()` no cerraba la conexión si el `INSERT` fallaba (p. ej. por la FK) y el hilo de aiosqlite colgaba el proceso. Ahora `try/finally`.
  - **Semilla E2E:** `seed_e2e_db.py` corre en un subproceso (el `JobManager` guarda un `asyncio.Lock` y no debe cruzar loops) y usa un texto de mock distinto del servidor para que regenerar un acto produzca un cambio visible.
  - **Recarga de dev (T2.7):** backup en `data/dev/backups/stories-20260923-0739-pre-spec440-s2.db` y YAML en `data/dev/backups/export-20260923-0739/`. "La ofrenda" no tenía actos en ningún lado (JSON sanitizado, `synopsis_beat` vacío, sinopsis de 15 párrafos) → se importó desde `input_stories/la_ofrenda.yaml` (idéntica salvo los actos). Antes de T2.9, verificar que el export de prod traiga los 5 actos con texto.
- [x] **Checkpoint S2:** lint + pytest 652 + tsc + Vitest 73 + Playwright 18 (×2).

### S3 — Combos Género → Subgénero (frontend, §2)

- [x] **T3.1:** `catalog.service.ts` con caché en memoria (TTL 5 min) y manejo de Core caído.
- [x] **T3.2:** `ui_definitions.yaml`: `atmosfera` y `atmosphere_subgenre` con `source: genre_catalog` y `depends_on: atmosfera`; `form_renderer.service.ts` lo soporta.
- [x] **T3.3:** `wizard.ejs`: catálogo embebido (`<script type="application/json" id="genre-catalog">`), subgéneros del género guardado, sin género → `disabled` con "Elegí primero el tipo de horror"; Core caído → ambos `disabled` con aviso.
- [x] **T3.4:** `wizard.js`: al cambiar de género repuebla el subgénero; si el valor actual no pertenece, lo resetea y guarda ambos (auto-save).
- [x] **T3.5:** `mapStoryToWizard()`: subgénero que no pertenece al género → vacío.
- [x] **T3.6:** Tests: Vitest (servicio: caché, Core caído) + Playwright (filtrado de `body_horror`, reset al cambiar, rehidratación de `folk_horror/rural`).
- [x] **Notas de S3:**
  - Los combos del catálogo usan el **ID** como `value` (no "id: Etiqueta"); el mapper, la rehidratación y el render aceptan también el formato legado de sesiones viejas. La confirmación muestra la etiqueta del catálogo.
  - `submitStep` descarta el subgénero si quedó vacío (combo reseteado o deshabilitado) o si no pertenece al género; con el Core caído no toca nada.
  - Si el Core cae con el catálogo ya cacheado, se sigue usando la última copia.
- [x] **Despliegue S2+S3 y recarga de prod (2026-09-23):** prod detenido → backup en `data/prod/backup_2026-09-23/` (DB + YAML) → `export-yaml --all` con el código nuevo sobre una copia (los 3 con sus 5 actos) → las reglas `social` de "barco fantasma" y "el galpon" (sin tipo desde la recuperación; el backup `original/` tampoco lo tenía, salió de `historia_*.md`) → `entorno` → DB recreada + `import-yaml --descartar-subgenero-invalido` ("barco fantasma" queda `terror_psicologico` y "la pena del colectivo" `horror_cosmico`, ambas sin subgénero: elegirlo en el wizard) → `docker compose up -d --build`. Verificado: catálogo 8/50, 3 borradores con personajes, escenarios, reglas tipadas y actos; `POST` con par inválido → 422; editar "el galpon" precarga `folk_horror`/`rural`.
  - Hallazgo: `export-yaml` contra el backup `original/` (esquema pre-Spec-190, sin `rule.applies_to_beat`) falla, y la primera vez el proceso quedó colgado: otra conexión que no se cierra ante una excepción en un camino de lectura del repo. Anotado, fuera de S3.
- [x] **Checkpoint S3:** lint + pytest 652 + tsc + Vitest 90 + Playwright 21 (×2).

### S4 — Rasgos nuevos + narrador dinámico (§3, §5)

- [x] **T4.1:** Lista de rasgos única con ancla YAML + `miedoso`, `curioso`, `impulsivo`, `desconfiado`; grilla `sm:grid-cols-3 lg:grid-cols-4`.
- [x] **T4.2:** `storyteller_id` con `source: characters`: el combo lista solo personajes con nombre (JS en `input`/agregar/borrar); 1 solo → preseleccionado; ninguno → `disabled` "Primero nombrá un personaje"; el narrador borrado → reset + auto-save.
- [x] **T4.3:** Mismo filtro en el render server-side del paso 2.
- [x] **T4.4:** Validación en `submitStep`: `storyteller_id` debe apuntar a un personaje con nombre; si no, re-render con error.
- [x] **T4.5:** Tests: Vitest (anclas YAML, validación del paso) + Playwright (1 personaje → 1 opción preseleccionada; agregar/borrar actualiza).

### S5 — Wizard compacto para 1080p (§1)

- [x] **T5.1:** Clases de la tabla §1 en `wizard.ejs` (sin tocar `.card-forge` global); radios de 5 opciones en 2 columnas.
- [x] **T5.2:** Copy: "evoluciona", "fija", "auditivas".
- [x] **T5.3:** Playwright: viewport 1920×960 → botón "Siguiente" del paso 1 visible sin scroll; 1366×768 sin scroll horizontal; captura para revisión visual.
- **Nota de implementación (2026-09-23):** con solo la tabla de §1 el paso 1 seguía scrolleando 83px en 1920×960 (el scroll es del `<main>`, `p-12 pb-24`) y el pie fijo tapaba «Siguiente». Se agregó `width: half` en `ui_definitions.yaml`: campos `half` contiguos comparten fila desde `lg` (Género + Subgénero). Además los radios muestran solo la etiqueta (antes «id: Etiqueta»). El E2E mide `scrollHeight <= clientHeight` del `<main>` y que el botón termine por encima del pie.

### S6 — Documentación y cierre

- [ ] **T6.1:** `CLAUDE.md` (tablas `genre`/`subgenre`, FK, `/catalog/genres`, `import-yaml`, regla de edición, tipos de regla), nota en Spec-220, Spec-440 → DONE.

---

## COMMANDS

```bash
make lint
make test                                   # pytest backend
cd frontend && npx vitest run               # unit frontend
cd frontend && npx playwright test          # e2e (viewport 1080p + combos)
```

---

## PROJECT STRUCTURE (archivos afectados)

```
src/infrastructure/database/connection.py              # tablas genre/subgenre, FKs en story, seed
src/infrastructure/database/seeds/genre_catalog.py     # NUEVO — datos semilla (taxonomía v2)
src/domain/models.py                                   # Genre, Subgenre
src/domain/interfaces.py                               # GenreRepository (protocolo)
src/infrastructure/database/repositories/genre_repository.py  # NUEVO
src/infrastructure/database/repositories/story_repository.py  # '' → NULL en genero/subgenero
src/application/use_cases/list_genres.py               # NUEVO
src/application/use_cases/create_story.py              # validar par
src/infrastructure/loaders/yaml_loader.py              # validar par (CLI)
src/presentation/routers/story_router.py               # PATCH valida; IntegrityError → 422
src/presentation/routers/catalog_router.py             # NUEVO — GET /catalog/genres
src/main.py                                            # registrar catalog_router
input_stories/barco_fantasma.yaml                      # par válido
frontend/config/ui_definitions.yaml                    # source/depends_on, rasgos, anclas, typos
frontend/src/services/catalog.service.ts               # NUEVO
frontend/src/services/form_renderer.service.ts         # soportar source/depends_on
frontend/src/services/mapper.service.ts                # contrato §4
frontend/src/services/wizard.service.ts                # rehidratación
frontend/src/controllers/wizard.controller.ts          # validar storyteller_id (§5)
frontend/src/views/wizard.ejs                          # compactación + combos dependientes
frontend/public/js/wizard.js                           # repoblar subgénero y narrador
tests/unit/infrastructure/test_genre_repository.py     # NUEVO
tests/unit/infrastructure/test_db_connection.py        # tablas + seed + FK
frontend/tests/unit/services/mapper.service.test.ts    # NUEVO — contrato
frontend/tests/e2e/wizard.spec.ts                      # NUEVO
```

---

## TESTING STRATEGY

- **Backend unit:** `init_db()` crea y siembra el catálogo (idempotente al correr 2 veces); FK compuesta rechaza par inválido; `SQLGenreRepository.exists()` (par válido, inválido, género sin subgénero, `otro`); `POST`/`PATCH /stories` con par inválido → 422; `GET /catalog/genres` ordenado.
- **Frontend unit:** `mapWizardToCore` emite `genero/subgenero/tono/narrator_config`; `mapStoryToWizard` rehidrata par válido y descarta legacy.
- **E2E Playwright:** viewport 1920×960 sin scroll en paso 1; combo dependiente (filtrado + reset); rasgos nuevos seleccionables; combo de narrador solo con personajes creados.
- Lint y tests los corro yo en cada checkpoint (output filtrado) y reporto el resultado.

---

## BOUNDARIES

- **Siempre:** IDs sin tildes en valores nuevos; mantener IDs de género existentes.
- **Consultar antes:** tocar `.card-forge` global o cualquier estilo fuera del wizard; cambiar cómo `atmosfera` entra a los prompts.
- **Nunca:** scripts de migración. Esquema en `init_db()` + recrear `stories.db` (se pierden las 2 historias de dev; se recargan desde `input_stories/` con el CLI).

---

## DECISIONES (2026-09-22)

- Catálogo de géneros: **en la DB, gestionado por el backend** (tablas `genre`/`subgenre` + FK compuesta).
- Taxonomía: **ajustada a v2** (§2).
- Rasgos: `miedoso`, `curioso`, `impulsivo`, `desconfiado`.
- Entidad: **spec propia → Spec-450**.
- Feedback de generación: **movido a Spec-460** (jobs asíncronos + bus SSE).

- Hallazgo §4 (contrato frontend ↔ API): **incluido en esta spec**.
- Taxonomía v2: **aprobada**.
- Gestión del catálogo: **seed + lectura** (sin CRUD por ahora).
- Orden: se implementa **después de Spec-460** (460 DONE el 2026-09-22).
- Editar historias generadas: **sí** (§8, 2026-09-22).

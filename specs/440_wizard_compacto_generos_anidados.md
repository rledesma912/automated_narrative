# SPEC-440: Wizard compacto, géneros anidados y narrador dinámico

**Fecha:** 2026-09-22
**Tipo:** SDD (Spec-Driven Development)
**Estado:** SPECIFY — decisiones tomadas; se implementa después de Spec-460

---

## ASSUMPTIONS

1. "Bien visible en 1080p" = el **paso 1 completo** (título + card Atmósfera + navegación) entra sin scroll en un viewport de navegador de **1920×960** (1080p menos el chrome del browser). La captura de referencia es de 1366×768; ahí se acepta scroll, pero no debe romperse el layout.
2. "Achicar sólo un poco" = reducir tipografía, paddings y espaciados de los campos del wizard (~15-20 % de altura), **sin** cambiar el ancho del contenedor ni la estructura de pasos.
3. La compactación aplica a **todos los pasos** del wizard (comparten `fieldHtml()` en `wizard.ejs`), no solo al paso 1.
4. Se mantienen los **8 géneros** actuales (mismos IDs). Lo que cambia es el catálogo de subgéneros, que pasa a depender del género.
5. El catálogo de géneros es **dominio de datos**: vive en la DB (tablas `genre` / `subgenre`) y lo gestiona el backend. `story.genero` / `story.subgenero` siguen guardando **IDs**, ahora con FK al catálogo. Hay cambio de esquema → `init_db()` + recrear `stories.db` (sin migraciones).
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
- Orden: se implementa **después de Spec-460**.

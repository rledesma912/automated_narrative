# SPEC-540: Entorno dev siempre publicado detrás del proxy

**Fecha:** 2026-09-27
**Tipo:** SDD (Spec-Driven Development) — mantenimiento / infraestructura local
**Estado:** TASKS — SPECIFY y PLAN aprobados (2026-09-27); tareas pendientes de OK
**Extiende:** Spec-325 (separación dev/prod en host único), Spec-520 (prod solo cambia con `make deploy`) y Spec-531 (tema y favicon).

---

## ASSUMPTIONS

1. Todo corre en la misma máquina (192.168.0.65) y el usuario prueba con un navegador de esa máquina (`/etc/hosts` resuelve los `.test` a `127.0.0.1`).
2. El proxy es el contenedor `mi_reverse_proxy` (nginx 1.26). Su configuración vive **fuera del repo**, en `/mnt/LLM/apps/reverse_proxy/nginx_config/default.conf`. Los certificados son autofirmados (`generate_certs.sh`, openssl) y están en `/home/rick/Cosas/certificados_locales`.
3. Prod sigue cambiando solo con `make deploy` (Spec-520). La familia entra por `http://192.168.0.65` (`default_server`), y eso no cambia.
4. Dev refleja siempre **el directorio de trabajo**: la rama activa, con sus cambios sin commitear.
5. Dev y prod comparten Ollama (una GPU): una generación en dev compite con una de prod. El usuario lo tiene en cuenta (D4).

---

## OBJECTIVE

Que el usuario abra **`storymaker.test`** en cualquier momento y vea ahí el último cambio que hizo Claude, **sin levantar nada a mano**. Prod pasa a llamarse **`storymaker.prd`**.

**Éxito:**
- `storymaker.test` responde siempre con dev, también después de reiniciar la máquina.
- Un cambio de código, vista, estilo o prompt se ve con solo recargar la página.
- Si el cambio necesita más que eso (dependencias, esquema de la DB), Claude lo resuelve como parte del checkpoint y lo avisa.
- La página de dev dice que es dev, en qué rama y en qué commit está, y se ve distinta: título de pestaña, favicon y tema propios.

---

## 1. HALLAZGOS

| Hallazgo | Consecuencia |
|---|---|
| `http://192.168.0.65:3011` no respondía: dev **no estaba levantado**, y además 3010, 3011 y 3012 los usa el `browser-sync` de `cellwarstory`. | Dev necesita puertos propios y un proceso que viva solo. |
| Dev hoy es `make dev` en una terminal (uvicorn `--reload` + nodemon + `tailwind --watch`). Muere con la terminal, y un proceso lanzado desde una sesión de Claude muere con la sesión. | La recarga automática ya existe. Lo que falta es que el proceso **viva solo**: contenedores con `restart: unless-stopped`. |
| Las imágenes de prod (`Dockerfile`, `frontend/Dockerfile`) se construyen sin dependencias de dev y con el código copiado. | Dev necesita sus propios Dockerfiles: con dependencias de dev y el código montado. |
| `storymaker.test` apunta hoy a prod (:3000). Los certificados de `storymaker.test` ya existen. | El certificado se reutiliza para dev; prod necesita uno nuevo para `storymaker.prd`. |
| `make db` ya recrea `data/dev/stories.db` con `init_db()`, que siembra los catálogos (`genre`, `subgenre`, `entity_nature`, `genre_entity_nature`). Todo lo demás que es referencia (opciones del asistente, criterios del taller, actos, perfiles) se lee de `config/`. | La DB de dev «vacía de historias con los datos de referencia» ya sale de `make db`. Solo falta verificarla (§2.4). |
| Puertos declarados en `/mnt/LLM/apps` o en uso: 3000, 3001, 3009–3012, 3021, 8000–8002, 8010, 8020, 8021, 8080, 8081, 9000. | Para dev: **UI 3040, API 8040**, libres y sin declarar en ningún proyecto. |
| El pie de la barra lateral muestra `v0.3.0 — Slice 3`, fijo; dev y prod tienen el mismo tema, título y favicon. | No hay forma de saber qué ambiente ni qué versión se está mirando. |
| La paleta vive solo en `theme.css` como variables `--forge-*` (Spec-531). | Un tema por ambiente es un bloque más de variables; no se toca ninguna vista. |

---

## 2. CAMBIOS PROPUESTOS

### 2.1 Dominios en el proxy

| Dominio | Apunta a | Certificado |
|---|---|---|
| `storymaker.prd` | prod, `host.docker.internal:3000` (lo que hoy es `storymaker.test`) | nuevo (`generate_certs.sh`) |
| `storymaker.test` | **dev**, `host.docker.internal:3040` | el existente |
| `http://192.168.0.65` | prod (`default_server`, sin cambios) | — |

- Los dos bloques de dev (`:80` y `:443`) son copia del actual, con la misma preparación para SSE.
- Antes de editar se hace backup de `default.conf`, y se recarga solo si `nginx -t` pasa.
- El usuario agrega `storymaker.prd` a `/etc/hosts` (pide `sudo`).
- Se actualizan las referencias a `storymaker.test` como prod: `CLAUDE.md` y las notas de las specs vigentes (el script de deploy no nombra el dominio). Las specs cerradas se dejan como registro histórico.

### 2.2 Dev en contenedores propios, con el código montado

Nuevo `docker-compose.dev.yml` con `name: narrative-dev`: un proyecto de Compose aparte del de prod, que `make deploy` no ve ni toca.

| Servicio | Contenedor | Puerto | Imagen |
|---|---|---|---|
| `api` | `narrative-api-dev` | 8040 | `Dockerfile.dev` (Python 3.12 + `uv sync` **con** dependencias de dev) |
| `ui` | `narrative-ui-dev` | 3040 | `frontend/Dockerfile.dev` (Node 22 + `npm ci` **con** devDependencies) |

- **Código montado, no copiado:** `src/`, `config/`, `frontend/src/`, `frontend/public/`, `frontend/tailwind.config.js` y `.git/` en solo lectura (para la marca de §2.3). Los cambios se ven al instante; los bind mounts en Linux no agregan latencia y los watchers (inotify) funcionan igual que en el host.
- **Dependencias dentro de la imagen:** el `.venv` y los `node_modules` de los contenedores son de la imagen, no los del host. Dev no depende de lo que esté instalado afuera, y viceversa.
- **Recarga:** la API corre `uvicorn --reload --reload-dir src --reload-dir config --reload-include '*.yaml'`; la UI corre `npm run dev` (nodemon + `tailwind --watch`). Los prompts `.md` no necesitan recarga: se leen en cada generación.
- **Vive solo:** `restart: unless-stopped`. Arranca con Docker al prender la máquina, sin iniciar sesión, y aparece en Portainer junto a los demás.
- **Datos y secretos:** monta `data/dev/` y `frontend/public/output_stories/dev/`, y usa `.env` (el de dev) con `DATABASE_URL` a `data/dev/stories.db`. Nunca `data/prod/` ni `.env.prod`. Ollama por `host.docker.internal:11434`, como prod.
- **Dueño de los archivos:** los contenedores corren con el UID/GID del usuario (`user: "${UID}:${GID}"`), para que la DB y los relatos de dev no queden a nombre de root.
- **Efecto de la recarga:** si Claude edita Python mientras hay un job corriendo en dev, uvicorn reinicia y el job queda `failed` («interrumpida por reinicio»). Es lo mismo que pasa hoy con `make dev`, y solo afecta a dev.

Script `scripts/bash/dev_env.sh`, con atajos en el `Makefile`:

```bash
make dev-up        # construye si hace falta y levanta api + ui de dev
make dev-down      # las baja
make dev-rebuild   # reconstruye las imágenes de dev (dependencias nuevas) y las levanta
make dev-status    # rama, commit, /health de dev, estado de los contenedores
make dev-logs      # últimas líneas de los logs de api y ui
make dev-db        # recrea data/dev/stories.db vacía con los catálogos (§2.4)
```

`make dev` / `make api` / `make ui` en terminal siguen existiendo para depurar a mano, pero comparten puertos con los contenedores: se usan con `make dev-down` antes.

Qué pasa con cada tipo de cambio:

| Cambio | Cómo llega a dev | Quién |
|---|---|---|
| Python (`src/`), YAML de `config/` | uvicorn recarga solo | automático |
| Prompts `.md` | se leen en cada generación | automático |
| Vistas `.ejs`, JS de `public/` | se leen en cada request | automático (recargar la página) |
| TypeScript del server, clases Tailwind nuevas | nodemon / `tailwind --watch` | automático |
| `pyproject.toml`, `package.json`, `Dockerfile.dev` | `make dev-rebuild` | Claude, en el checkpoint |
| Esquema de la DB (`init_db()`) | `make dev-db` | Claude, avisando antes |
| Cambio de rama | uvicorn y nodemon recargan solos | automático |

### 2.3 Diferenciar dev de prod a simple vista: título, marca y tema

El dominio no alcanza: la pestaña y la página tienen que decir de qué ambiente son, sin leer la URL. Todo depende de `ENV` (`dev` | `prod`), que el layout expone como `data-env` en `<html>`. En prod no cambia nada de lo que se ve hoy.

**Título y marca**

| Dónde | Prod | Dev |
|---|---|---|
| `<title>` de la pestaña | `NarrativeForge — …` | `[DEV] NarrativeForge — …` |
| Marca de la barra lateral | `NARRATIVE Forge` | `NARRATIVE Forge` + etiqueta **DEV** |
| Pie de la barra lateral | `v0.3.0 — Slice 3` | **`DEV · <rama> · <commit>`** |
| Favicon | vela (`favicon.svg`) | la misma vela con los colores del tema de dev (`favicon-dev.svg`) |

La rama y el commit se leen de `.git/` (montado en solo lectura) en cada request: siempre muestran lo último.

**Tema de dev: «Latte», basado en Catppuccin Latte**

Catppuccin es un esquema abierto y muy usado en editores y terminales. Su variante clara, **Latte**, es fría: fondo gris lavanda y acento violeta. Es el opuesto visual de «Papel», que es cálido (papel y rojo óxido), así que no hay forma de confundir los ambientes. Se descartaron: Solarized Light y Rosé Pine Dawn (cálidos, demasiado parecidos a Papel), GitHub Light (neutro, poco distintivo) y Nord Snow Storm (contraste bajo para texto).

Los tonos saturados de Latte no llegan a AA como texto sobre fondo claro (verde 3,0:1, amarillo 2,3:1). Para los textos de estado se usan versiones oscurecidas del mismo tono, y los tonos originales quedan para los fondos pálidos y los bordes.

| Token | Papel (prod) | Latte (dev) | Contraste en Latte |
|---|---|---|---|
| `--forge-bg` | `#f7f3ec` | `#eff1f5` (base) | — |
| `--forge-surface` | `#fffdf8` | `#ffffff` | — |
| `--forge-border` | `#e2d9c8` | `#ccd0da` (surface0) | — |
| `--forge-text` | `#2b2620` | `#4c4f69` (text) | 7,1:1 sobre bg |
| `--forge-muted` | `#6f6454` | `#5c5f77` (subtext1) | 5,5:1 |
| `--forge-accent` | `#8a2b1f` | `#8839ef` (mauve) | 4,8:1; blanco encima 5,4:1 |
| `--forge-error` | `#a3261a` | `#b30d30` (red oscurecido) | 6,2:1 |
| `--forge-warning` | `#8a5d0f` | `#8a5a0c` (yellow oscurecido) | 5,2:1 |
| `--forge-success` | `#3f6b3a` | `#2d7a1e` (green oscurecido) | 4,7:1 |
| `--forge-info` | `#2f5d8a` | `#1650c8` (blue oscurecido) | 6,2:1 |

Los `-bg` y `-border` de cada estado y el `--forge-overlay` salen de los mismos tonos (se ajustan en la implementación).

- **Dónde vive:** en `theme.css`, como bloque `:root[data-env="dev"] { … }` que redefine los mismos `--forge-*`. Sigue siendo el único archivo con colores literales: las vistas y los scripts no cambian.
- **Tests:** `palette-contrast` pasa a verificar **las dos paletas** (AA ≥ 4,5:1 en cada par texto/fondo); `no-hardcoded-colors` sin cambios. Capturas de las dos con `visual-snapshots`.
- **E2E:** los Playwright corren con `ENV` de test, que usa el tema de prod: las capturas y aserciones de hoy no cambian.

### 2.4 DB de dev: vacía de historias, con los datos de referencia

- `make dev-db`: baja la API de dev, borra `data/dev/stories.db` (y `-wal`/`-shm`), corre `init_db()` dentro del contenedor y la vuelve a levantar. `make db` queda como alias.
- **Verificación nueva** al final del script: cuenta las filas de los cuatro catálogos y de `story`, y falla si algún catálogo queda vacío o si hay historias. Así, si mañana se agrega un catálogo sin seed, se nota.
- Si al implementar aparece alguna tabla de referencia sin seed, se agrega su seed a `seeds/`, siguiendo el patrón de `genre_catalog.py`.

### 2.5 Dinámica de trabajo (la parte «implícita»)

Regla para Claude, que se agrega a `CLAUDE.md` y a la memoria:

1. Cada checkpoint termina con **dev reflejando el cambio**: `make dev-status` en verde (health OK, rama y commit correctos). Si el cambio lo pide, antes `make dev-rebuild` (dependencias) o `make dev-db` (esquema).
2. El cierre del checkpoint le dice al usuario **qué mirar**: la URL exacta en `storymaker.test` y los pasos para validar.
3. Tests en verde y dev actualizado son condiciones para cerrar el checkpoint (se suma a la política de tests vigente).
4. Prod no se toca: `make deploy` desde `main`, solo cuando el usuario lo pide.

---

## 3. DECISIONES TOMADAS

- **D1 — Dominios:** dev = `storymaker.test`; prod = `storymaker.prd`. Puertos de dev libres: UI **3040**, API **8040**.
- **D2 — Dev en contenedores propios** (proyecto de Compose `narrative-dev`, separado del de prod) con el código montado. Se eligió sobre `systemd --user` por aislamiento: dependencias propias, sin tocar el host, visibles en Portainer. En Linux, montar el código no agrega latencia.
- **D3 — DB de dev:** vacía de historias, con los catálogos sembrados por `init_db()`. Sin copia de prod.
- **D4 — Modelo:** dev usa el modelo real y comparte la GPU con prod; el usuario lo tiene en cuenta.
- **D5 — Diferenciar ambientes:** además del dominio, título `[DEV]`, marca y favicon de dev, y un tema claro propio para dev, «Latte» (Catppuccin Latte).

---

## 4. BOUNDARIES

- **Siempre:** dev lee y escribe solo `data/dev/` y `.env`; backup de `default.conf` y `nginx -t` antes de recargar el proxy.
- **Preguntar antes:** editar la configuración del proxy (está fuera del repo y sirve a otros proyectos); `make dev-db` si dev tiene historias que el usuario cargó a mano; `/etc/hosts` lo edita el usuario.
- **Nunca:** tocar `docker-compose.yml`, los Dockerfiles ni los contenedores de prod, `data/prod/` ni `.env.prod`; hacer que dev sea el `default_server`.

---

## 5. CRITERIOS DE ÉXITO

1. `https://storymaker.test` (y `http://`) muestra dev con el tema Latte, `[DEV]` en el título de la pestaña, el favicon de dev y la marca «DEV · rama · commit».
2. `https://storymaker.prd` y `http://192.168.0.65` muestran prod con el tema Papel, sin marca de dev, y con el mismo commit y perfil que antes del cambio.
3. Después de reiniciar la máquina, `storymaker.test` responde sin intervención.
4. Editar un `.ejs`, un `.py` o un prompt se ve en dev recargando la página, sin comandos.
5. El SSE funciona por el proxy de dev: la banda de generación y el modal del asistente reciben eventos y heartbeat.
6. `make dev-db` deja 0 historias y los cuatro catálogos con datos, y lo verifica.
7. `make dev-status` informa rama, commit, salud y estado de los contenedores.
8. `make deploy` y `make deploy-check` siguen funcionando igual y no ven los contenedores de dev.
10. Las dos paletas pasan `palette-contrast` (AA ≥ 4,5:1).
11. `make test`, `npm test` y Playwright siguen en verde (los E2E usan sus propios puertos, 8021/3021).

---

## 6. PLAN

Cuatro slices, en orden de riesgo creciente para prod: primero lo que solo toca el repo y se prueba con tests, al final lo que toca el proxy compartido. Cada slice cierra con un checkpoint verificable.

### S1 — Diferenciación visual (solo frontend, sin infraestructura)

- **Ambiente:** `frontend/src/utils/environment.ts` lee `process.env.ENV` (`dev` | `prod`; **sin valor = prod**, así prod y los E2E no cambian) y la rama y el commit leyendo `.git/HEAD` y los refs (incluido `packed-refs`), sin necesitar el binario de `git` en el contenedor. Si no hay `.git` legible, muestra «DEV · sin git». Se publica en `app.locals.environment`.
- **Layout:** `data-env` en `<html>`; `[DEV]` en `<title>`; en dev, favicon `favicon-dev.svg` y `theme-color` de Latte.
- **Barra lateral:** etiqueta DEV junto a la marca y pie `DEV · <rama> · <commit>`; en prod, igual que hoy.
- **Tema:** bloque `:root[data-env="dev"]` en `theme.css` con la paleta Latte completa (incluidos los `-bg`, `-border` y `overlay`).
- **Tests:** `palette-contrast` recorre las dos paletas; unit de `environment.ts` (ENV ausente/dev/prod, HEAD con rama, HEAD suelto, `packed-refs`, sin `.git`); vista del layout y de la barra en los dos ambientes.
- **Checkpoint:** Vitest + Playwright en verde; capturas de los dos temas (`CAPTURAS=540`, corriendo la UI con `ENV=dev`).

### S2 — Contenedores de dev

- `Dockerfile.dev` (raíz): Python 3.12 + `uv sync --frozen` con dependencias de dev; `CMD` uvicorn `--reload` en 8040 vigilando `src/` y `config/`.
- `frontend/Dockerfile.dev`: Node 22 + `npm ci` con devDependencies; `CMD npm run dev`.
- `docker-compose.dev.yml` (`name: narrative-dev`): servicios `api` y `ui`, puertos 8040/3040, montajes de §2.2, `.git` en solo lectura, `user: ${DEV_UID}:${DEV_GID}`, `HOME=/tmp`, `ENV=dev`, `CORE_API_URL=http://api:8040`, `OLLAMA_HOST=http://host.docker.internal:11434`, `restart: unless-stopped`.
- `scripts/bash/dev_env.sh` (`up | down | rebuild | status | logs | db`) y los atajos `make dev-*`. `db`: baja la API, recrea la base con `init_db()` dentro del contenedor, **verifica** catálogos > 0 y `story` = 0, y la vuelve a levantar. `make db` queda como alias.
- Puertos de dev en todos lados (8020→8040, 3010→3040): `.env`, `frontend/.env`, `Makefile`, `scripts/bash/run_dev.sh`, `pyproject.toml` (`base_url`), `config/.env.sample`, README, `docs/frontend_architecture_map.md` y los comentarios de los tests que los nombran.
- **Checkpoint:** `make dev-up` → `make dev-status` en verde; `curl` a :8040/health y :3040 con el tema Latte; editar un `.ejs` y un `.py` y ver el cambio sin comandos; `docker restart narrative-ui-dev` recupera; `make dev-db` verifica; `make deploy-check` sigue pasando y `docker ps` de prod sin cambios; `make test` + Vitest + Playwright en verde.

### S3 — Proxy y dominios (fuera del repo; se confirma con el usuario antes de tocar)

- Backup de `/mnt/LLM/apps/reverse_proxy/nginx_config/default.conf` con fecha.
- Los dos bloques actuales de `storymaker.test` pasan a `storymaker.prd` (siguen apuntando a :3000; el de `:80` conserva `default_server`, así la familia sigue entrando por la IP).
- Bloques nuevos `storymaker.test` (`:80` y `:443`) → `host.docker.internal:3040`, con la misma preparación para SSE, sin `default_server`.
- Certificado de `storymaker.prd` con `generate_certs.sh` (solo crea los que faltan).
- `nginx -t`; si pasa, `nginx -s reload` (recarga sin cortar conexiones).
- El usuario agrega `storymaker.prd` a `/etc/hosts`.
- **Checkpoint:** `curl -k --resolve` a los dos dominios (dev con `data-env="dev"`, prod sin él y con el commit desplegado); `http://192.168.0.65` sigue en prod; SSE de dev por el proxy (`/api/v1/events` recibe `snapshot` y heartbeat). El usuario valida en su navegador.

### S4 — Documentación y dinámica de trabajo

- `CLAUDE.md`: dominios, puertos, `make dev-*`, tema por ambiente y la regla de cierre de checkpoint (§2.5).
- Memoria: la regla de checkpoint con dev actualizado; el mapa de dominios.
- Notas en las specs vigentes que nombran `storymaker.test` como prod (Spec-520, Spec-531); esta spec pasa a DONE.
- **Checkpoint:** tests en verde; el usuario reinicia la máquina (cuando le quede cómodo) y confirma el criterio 3.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| Un error en `default.conf` tira el proxy de **todos** los proyectos. | Backup previo, `nginx -t` antes de recargar y `reload` (no `restart`): si la validación falla, nginx sigue con la configuración anterior. |
| Marcadores o costumbre: `storymaker.test` deja de ser prod. | Lo avisamos al cerrar S3; la familia no se ve afectada (entra por IP). |
| Watchers dentro del contenedor que no detectan cambios. | En Linux, inotify atraviesa los bind mounts; se verifica en el checkpoint de S2 editando un `.ejs`, un `.ts` y un `.py`. |
| Una recarga de uvicorn interrumpe un job de dev. | Esperado y documentado (§2.2); solo afecta a dev. |
| Archivos de `data/dev/` a nombre de root. | `user: ${DEV_UID}:${DEV_GID}`; se verifica con `ls -l` en S2. |
| El commit de la marca queda viejo tras un `git commit` sin cambios en `src/`. | Se lee en cada request, no solo al arrancar: leer dos archivos chicos de `.git/` es despreciable. |

---

## 7. TASKS

Cada tarea cierra con su verificación. Al final de cada slice: lint + pytest + Vitest + Playwright en verde (política vigente) y resumen al usuario de qué mirar.

### S1 — Diferenciación visual

- [ ] **T1.1 — Ambiente y versión de git**
  - Acceptance: `getEnvironment()` devuelve `{ env, isDev, branch, commit }`; `ENV` ausente o distinto de `dev` → prod; lee `.git/HEAD` → ref suelto o por rama → `refs/heads/…` o `packed-refs`; sin `.git` → `branch: null`, sin excepción. Middleware que lo deja en `res.locals.environment` en cada request.
  - Verify: `tests/unit/utils/environment.test.ts` (repo git falso en un directorio temporal: rama, HEAD suelto, packed-refs, sin `.git`, ENV ausente/dev/prod).
  - Files: `frontend/src/utils/environment.ts`, `frontend/src/app.ts`, test nuevo.
- [ ] **T1.2 — Paleta Latte**
  - Acceptance: bloque `:root[data-env="dev"]` en `theme.css` con los 20 tokens `--forge-*` (valores de §2.3; `-bg`/`-border`/`overlay` derivados); `palette-contrast` verifica **Papel y Latte** con los mismos pares.
  - Verify: `npx vitest run tests/unit/css-architecture`.
  - Files: `frontend/src/styles/theme.css`, `palette-contrast.test.ts`.
- [ ] **T1.3 — Layout, barra lateral y favicon**
  - Acceptance: en dev, `<html data-env="dev">`, `<title>[DEV] NarrativeForge — …`, favicon `favicon-dev.svg` (la vela con colores de Latte), `theme-color` `#eff1f5`, etiqueta DEV en la marca y pie `DEV · <rama> · <commit>`; en prod, HTML idéntico al de hoy (sin `data-env="dev"`, sin `[DEV]`, pie `v0.3.0 — Slice 3`).
  - Verify: `layout.view.test.ts` ampliado con los dos ambientes; `no-hardcoded-colors` con la excepción del `theme-color` de dev.
  - Files: `partials/layout.ejs`, `partials/sidebar.ejs`, `public/favicon-dev.svg`, `layout.view.test.ts`, `no-hardcoded-colors.test.ts`.
- [ ] **T1.4 — Capturas de los dos temas**
  - Acceptance: `visual-snapshots` acepta `ENV=dev` para el frontend del harness y guarda en `capturas/540/<tema>/`.
  - Verify: `CAPTURAS=papel npx playwright test visual-snapshots` y lo mismo con Latte; revisión visual de las capturas.
  - Files: `playwright.config.ts`, `tests/e2e/visual-snapshots.spec.ts`.
- **Checkpoint S1:** suite completa en verde; capturas Papel vs. Latte para el usuario.

### S2 — Contenedores de dev

- [ ] **T2.1 — Imágenes de dev**
  - Acceptance: `Dockerfile.dev` y `frontend/Dockerfile.dev` construyen con dependencias de dev; la API arranca uvicorn `--reload` en 8040 vigilando `src/` y `config/` (`*.yaml`); la UI corre `npm run dev`.
  - Verify: `docker build -f Dockerfile.dev .` y `docker build -f frontend/Dockerfile.dev frontend` sin errores.
  - Files: `Dockerfile.dev`, `frontend/Dockerfile.dev`, `.dockerignore` si hace falta.
- [ ] **T2.2 — Compose de dev**
  - Acceptance: `docker-compose.dev.yml` con `name: narrative-dev`, servicios `api` (`narrative-api-dev`, 8040) y `ui` (`narrative-ui-dev`, 3040), montajes de §2.2, `.git` en solo lectura, `user: ${DEV_UID}:${DEV_GID}`, `HOME=/tmp`, `ENV=dev`, `CORE_API_URL=http://api:8040`, `OLLAMA_HOST`, `restart: unless-stopped`; `api` con healthcheck y `ui` que depende de él.
  - Verify: `docker compose -f docker-compose.dev.yml config` válido; `docker compose ls` muestra `narrative-dev` separado del proyecto de prod.
  - Files: `docker-compose.dev.yml`.
- [ ] **T2.3 — Script y atajos**
  - Acceptance: `scripts/bash/dev_env.sh up|down|rebuild|status|logs|db`; `status` muestra rama, commit, estado de los contenedores, `/health` de la API y respuesta de la UI, y sale ≠ 0 si algo falla; `db` baja la API, recrea la base con `init_db()` en el contenedor, verifica catálogos > 0 y `story` = 0, y la levanta; `make dev-up|dev-down|dev-rebuild|dev-status|dev-logs|dev-db`, y `make db` como alias de `dev-db`.
  - Verify: `make dev-up && make dev-status`; `make dev-db` (imprime los conteos); `ls -l data/dev` a nombre del usuario.
  - Files: `scripts/bash/dev_env.sh`, `Makefile`.
- [ ] **T2.4 — Puertos de dev 8040/3040 en todo el repo**
  - Acceptance: ningún `8020`/`3010` de dev queda en `.env`, `frontend/.env`, `Makefile`, `scripts/bash/run_dev.sh`, `pyproject.toml`, `config/.env.sample`, README, `docs/frontend_architecture_map.md` ni en los comentarios de tests (los E2E siguen en 8021/3021).
  - Verify: `grep -rn "8020\|3010"` fuera de `specs/` sin resultados de dev.
  - Files: los listados (cambios de una línea).
- [ ] **T2.5 — Recarga en vivo**
  - Acceptance: con dev levantado, un cambio en un `.ejs`, un `.ts` del server, un `.py` y un `.yaml` de `config/` se ve en :3040/:8040 sin comandos; `docker restart narrative-ui-dev` recupera sola.
  - Verify: prueba manual con un cambio temporal en cada tipo, que se revierte al terminar.
  - Files: ninguno (verificación).
- **Checkpoint S2:** suite completa en verde; `make deploy-check` pasa; contenedores de prod sin cambios (`docker ps`, misma imagen y uptime); el usuario puede entrar a `http://localhost:3040`.

### S3 — Proxy y dominios (se confirma antes de empezar)

- [ ] **T3.1 — Backup y edición de `default.conf`**
  - Acceptance: copia `default.conf.bak-2026-09-27-<HHMM>`; los bloques de prod pasan a `server_name storymaker.prd` (el de `:80` sigue siendo `default_server`); bloques nuevos `storymaker.test` `:80`/`:443` → `host.docker.internal:3040` con la misma preparación para SSE.
  - Verify: `diff` contra el backup revisado con el usuario.
  - Files: `/mnt/LLM/apps/reverse_proxy/nginx_config/default.conf` (fuera del repo).
- [ ] **T3.2 — Certificado y recarga**
  - Acceptance: `storymaker.prd.pem` y su clave en `certificados_locales`; `nginx -t` OK; `nginx -s reload`.
  - Verify: `docker exec mi_reverse_proxy nginx -t`; los otros dominios (`portainer.test`, `n8n.test`, `cellwar.test`) siguen respondiendo.
  - Files: fuera del repo.
- [ ] **T3.3 — `/etc/hosts` y verificación**
  - Acceptance: el usuario agrega `storymaker.prd`; `storymaker.test` → dev (`data-env="dev"`), `storymaker.prd` y `http://192.168.0.65` → prod; el SSE de dev por el proxy entrega `snapshot` y heartbeat.
  - Verify: `curl -k` a los tres; `curl -N` a `https://storymaker.test/api/v1/events` durante ≥ 16 s; el usuario valida en el navegador.
  - Files: ninguno del repo.
- **Checkpoint S3:** criterios 1, 2 y 5.

### S4 — Documentación y dinámica

- [ ] **T4.1 — `CLAUDE.md`**: dominios, puertos, `make dev-*`, tema por ambiente, regla de cierre de checkpoint (§2.5).
- [ ] **T4.2 — Specs vigentes**: nota en Spec-520 y Spec-531 sobre el cambio de dominio; esta spec a DONE con fecha y commit.
- [ ] **T4.3 — Memoria**: regla de checkpoint con dev actualizado; mapa de dominios y puertos; actualizar el punto de retomo.
- **Checkpoint S4:** suite completa en verde; PR a `development`; el usuario confirma el criterio 3 tras un reinicio.

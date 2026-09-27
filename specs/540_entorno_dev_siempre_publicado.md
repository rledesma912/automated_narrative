# SPEC-540: Entorno dev siempre publicado detrás del proxy

**Fecha:** 2026-09-27
**Tipo:** SDD (Spec-Driven Development) — mantenimiento / infraestructura local
**Estado:** SPECIFY — decisiones D1–D5 tomadas, pendiente OK para pasar a PLAN
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

La rama y el commit se leen de `.git/` (montado en solo lectura) al arrancar, y nodemon reinicia la UI con cada cambio.

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

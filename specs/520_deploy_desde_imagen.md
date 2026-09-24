# SPEC-520: Producción solo cambia al construir la imagen

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development) — mantenimiento
**Estado:** TASKS — pendiente de revisión (SPECIFY aprobado 2026-09-24)
**Extiende:** Spec-325 (separación dev/prod en host único).

---

## ASSUMPTIONS

1. La app corre solo en la máquina local (sin publicación a internet). «Producción» son los contenedores de `docker-compose.yml` (`narrative-api` :8010, `narrative-ui` :3000, detrás de nginx `storymaker.test`), que usan la esposa y la hija del usuario.
2. Producción tiene que cambiar **solo cuando el usuario lo decide**: al construir las imágenes desde `main`. Nada de lo que se haga en el directorio de trabajo (cambiar de rama, editar prompts) puede afectarla mientras tanto.
3. Datos y secretos siguen afuera de la imagen: `data/prod/` (SQLite), `frontend/public/output_stories/prod/` y `.env.prod`.
4. Un solo directorio de trabajo (sin `git worktree`): el build se protege con validaciones previas, no con una copia aparte.

---

## OBJECTIVE

Que producción use siempre el código y la configuración de `main` que había al momento del último deploy, y que el deploy sea **un comando** que se niegue a correr si algo no está en orden.

**Éxito:** cambiar de rama o editar `config/prompts_generation/*.md` en el directorio de trabajo no cambia lo que genera prod; `make deploy` despliega `main` con backup y verificación, y aborta (sin tocar prod) si la rama no es `main`, hay cambios sin commitear, `main` no está al día con GitHub o hay una generación en curso.

---

## 1. HALLAZGOS

| Hallazgo | Consecuencia |
|---|---|
| `Dockerfile` del backend ya hace `COPY config/ ./config/`; el del frontend también. | La imagen ya trae la configuración: no hay que tocar los Dockerfiles. |
| `docker-compose.yml` monta `./config:/app/config:ro` en el backend. | El volumen **tapa** el `config/` de la imagen con la carpeta viva del directorio de trabajo. |
| `TemplateLoader` cachea por instancia: los prompts y `llm_beats_definition.yaml` se releen del disco en cada generación. | Hoy prod genera con los prompts de **la rama que esté activa** en el directorio de trabajo, sin rebuild ni aviso. |
| El build usa como contexto el directorio de trabajo. | Construir parado en una rama a medio hacer la convierte en «producción». |
| El deploy se viene haciendo a mano (Spec-460 en adelante): jobs activos → backup → `docker compose up -d --build` → `/health` y `/config/active-profile`. | Esos pasos pasan a un script que no se olvida ninguno. |

---

## 2. CAMBIOS PROPUESTOS

### 2.1 Configuración dentro de la imagen

- Quitar el volumen `./config:/app/config:ro` del servicio `backend`. Prod usa el `config/` copiado al construir.
- Consecuencia buscada: un cambio de prompt o de perfil LLM llega a prod **solo** con un `make deploy`.

### 2.2 `make deploy` (y `make deploy-check`)

Script `scripts/bash/deploy_prod.sh`, invocado por `make deploy`. En orden, abortando ante el primer fallo con un mensaje claro:

1. **Rama:** la rama actual es `main`.
2. **Árbol limpio:** `git status --porcelain` vacío (sin cambios ni archivos sin trackear que entrarían al build).
3. **Al día con GitHub:** `git fetch` y `HEAD` == `origin/main`.
4. **Sin generaciones en curso:** ningún job `queued`/`running` en `data/prod/stories.db` (consulta de solo lectura; funciona aunque el backend esté caído).
5. **Backup:** copia consistente de `data/prod/stories.db` (API de backup de SQLite) en `data/prod/backup_<AAAA-MM-DD>/stories-pre-deploy-<HHMM>-<commit>.db`, con `integrity_check`.
6. **Build y arranque:** `docker compose up -d --build backend frontend`.
7. **Verificación:** espera a que el backend esté sano y muestra `/health`, el perfil activo (`/config/active-profile`) y el commit desplegado. Si la verificación falla, lo dice y deja el backup a mano para volver atrás.

`make deploy-check` corre solo los pasos 1–4 (no toca nada).

### 2.3 Documentación y limpieza

- Spec-325 §3.4 y `CLAUDE.md`: el deploy es `make deploy`; la configuración viaja en la imagen.
- `CLAUDE.md` y `README.md` citan `500_clean_code_responsability.md`, borrada en `21f5c60`: se quita la referencia.
- Estados desactualizados, con la funcionalidad verificada en el código (2026-09-24):
  - Spec-160 (`IMPLEMENTANDO`) y Spec-170 (`APROBADO`) → `IMPLEMENTADO`, con nota: el checklist no se actualizó en su momento; lo implementado está en `narrative_anchors.resonance_*`, `llm_narrative_definition.yaml`, `NarrativeAuditor`, `INarrativeValidator` y `story_analyst_system_assertive.md`.
  - Spec-420 y Spec-430 (`APPROVED`, todas sus tareas marcadas) → `DONE`.

---

## BOUNDARIES

- **Siempre:** el script aborta antes de tocar prod ante cualquier validación fallida; backup antes del build.
- **Preguntar antes:** cambiar los Dockerfiles, los puertos o los volúmenes de datos.
- **Nunca:** `git checkout`/`pull` automáticos dentro del script (el usuario o Claude se paran en `main` a propósito); borrar backups; desplegar con jobs en curso.

---

## TESTING

- **Script:** `make deploy-check` en cada caso de falla (otra rama, árbol sucio, `main` atrasado, job activo simulado en una copia de la DB) → aborta con el mensaje esperado y sin efectos.
- **Aislamiento:** con prod desplegado, cambiar de rama y editar un prompt en el directorio de trabajo → `docker exec narrative-api` muestra el prompt de la imagen, no el editado.
- **Deploy real:** un `make deploy` de punta a punta desde `main`.
- Suites de siempre en verde (el cambio no toca código de la app).

---

## SUCCESS CRITERIA

1. `docker-compose.yml` sin el volumen de `config/`; prod lee la configuración de la imagen.
2. `make deploy` despliega con backup y verificación; `make deploy-check` valida sin tocar nada.
3. Cada validación fallida aborta sin efectos y explica qué hacer.
4. Documentación al día (325, `CLAUDE.md`, `README.md`) y specs 160/170/420/430 con su estado real.

---

## PLAN

### Estrategia

Primero el script con sus piezas testeables (consultas a la DB de prod en Python, orquestación en bash), después el compose y el `Makefile`, después la documentación. La prueba de punta a punta es el propio pase a producción de esta spec: `development` → `main` y `make deploy`.

### Decisiones técnicas

| Tema | Decisión |
|---|---|
| Lógica de DB | `scripts/prod_db.py` (stdlib, sin importar `src`): `active-jobs <db>` imprime la cantidad de jobs `queued`/`running` y sale con 1 si hay alguno; `backup <db> <dir> <sufijo>` copia con `sqlite3.Connection.backup`, corre `integrity_check` y aborta si no da `ok`. Solo lectura sobre la DB de prod (`mode=ro`). |
| Orquestación | `scripts/bash/deploy_prod.sh [--check]`: `set -euo pipefail`, cada paso con su mensaje y, si falla, qué hacer. Rutas y URL por variables con default (`PROD_DB=data/prod/stories.db`, `API_URL=http://localhost:8010`), así se prueba contra una copia. |
| Git | `git rev-parse --abbrev-ref HEAD` = `main`; `git status --porcelain` vacío; `git fetch origin main` y `git rev-parse HEAD` = `git rev-parse origin/main`. |
| Espera del backend | `docker compose up -d --build` ya espera `service_healthy` para el frontend; después, hasta 60 s de reintentos contra `/api/v1/health`. |
| Makefile | `deploy` → `scripts/bash/deploy_prod.sh`; `deploy-check` → con `--check`. En `help`. |
| Compose | Se quita `- ./config:/app/config:ro` del backend, con un comentario de por qué (Spec-520). |

### S0 — Script y compose

`prod_db.py` con tests, `deploy_prod.sh`, targets del `Makefile` y compose sin el volumen de `config/`. Verificación con `deploy-check` en los casos de falla (esta misma rama sirve para «no es main»).

### S1 — Documentación y limpieza

Spec-325 §3.4, `CLAUDE.md` (deploy), referencia a la spec 500 en `CLAUDE.md` y `README.md`, estados de las specs 160, 170, 420 y 430.

### S2 — Pase a producción y verificación del aislamiento

PR a `development`, PR `development` → `main` y `make deploy` real (con OK del usuario). Después, prueba de aislamiento: cambiar de rama y editar un prompt en el directorio de trabajo, y ver que el contenedor sigue con el de la imagen.

### Riesgos

| Riesgo | Mitigación |
|---|---|
| El primer deploy sin el volumen rompe algo que dependía de leer `config/` del host. | La imagen ya trae `config/` (mismo contenido de `main`); el deploy verifica `/health` y el perfil activo, y el backup queda para volver atrás. |
| Archivos ignorados por git (p. ej. `.env.prod`) no se validan. | `.env.prod` no entra a la imagen (`.dockerignore`) y va por `env_file`; es lo esperado. |
| Un deploy con el backend caído no puede verificar jobs por la API. | La consulta de jobs va directo a la DB, no a la API. |

---

## TASKS

Formato: **Acceptance** / **Verify** / **Files**. Checkpoint por slice: `make lint` + `make test` en verde → commit con tu OK.

### S0 — Script y compose

- [ ] **T0.1:** `scripts/prod_db.py`.
  - Acceptance: `active-jobs` cuenta `queued`/`running` (exit 0 sin activos, 1 con activos, 2 si la DB no existe); `backup` escribe `<dir>/stories-pre-deploy-<sufijo>.db`, verifica `integrity_check = ok` e imprime la ruta; nunca escribe en la DB de origen.
  - Verify: pytest sobre DBs temporales (sin jobs, con uno `running`, sin archivo; backup legible e íntegro).
  - Files: `scripts/prod_db.py`, `tests/unit/scripts/test_prod_db.py`
- [ ] **T0.2:** `scripts/bash/deploy_prod.sh`.
  - Acceptance: pasos 1–7 de §2.2; `--check` corre 1–4 y termina; cada falla sale con código ≠ 0, un mensaje que dice qué hacer y sin efectos.
  - Verify: `make deploy-check` en esta rama → «no estás en main»; con `PROD_DB` apuntando a una copia con un job `running` (y los chequeos de git salteados solo en esa prueba) → «hay una generación en curso».
  - Files: `scripts/bash/deploy_prod.sh`
- [ ] **T0.3:** `Makefile` y compose.
  - Acceptance: `make deploy` / `make deploy-check` (en `help`); `docker-compose.yml` sin `./config:/app/config:ro` y con el comentario.
  - Verify: `docker compose config` válido y sin el volumen; `make help` los lista.
  - Files: `Makefile`, `docker-compose.yml`
- [ ] **Checkpoint S0:** lint + pytest → commit.

### S1 — Documentación y limpieza

- [ ] **T1.1:** Deploy documentado.
  - Acceptance: Spec-325 §3.4 remite a Spec-520 (config en la imagen, `make deploy`); `CLAUDE.md` en Commands (`make deploy`, `make deploy-check`) y la regla «prod cambia solo con `make deploy` desde `main`».
  - Verify: lectura.
  - Files: `specs/325_separacion_dev_prod.md`, `CLAUDE.md`
- [ ] **T1.2:** Referencias y estados.
  - Acceptance: sin referencias a `500_clean_code_responsability.md` en `CLAUDE.md` ni `README.md`; specs 160/170 → `IMPLEMENTADO` con la nota de §2.3; 420/430 → `DONE`.
  - Verify: `grep -rn "500_clean"` sin resultados fuera de git; lectura de los encabezados.
  - Files: `CLAUDE.md`, `README.md`, `specs/160_*.md`, `specs/170_*.md`, `specs/420_*.md`, `specs/430_*.md`
- [ ] **Checkpoint S1:** lint + pytest → commit → push → PR a `development`.

### S2 — Pase a producción y aislamiento

- [ ] **T2.1:** Deploy real (con OK del usuario).
  - Acceptance: merge a `development` y a `main`; `make deploy` desde `main` termina con `/health` sano, perfil `ollama-gemma3-12b` y el commit de `main`.
  - Verify: salida del script + `docker inspect narrative-api` sin montaje de `config/`.
- [ ] **T2.2:** Aislamiento.
  - Acceptance: en otra rama, un cambio en `config/prompts_generation/voice_craft.md` no aparece en `docker exec narrative-api cat /app/config/prompts_generation/voice_craft.md`; se descarta el cambio.
  - Verify: diff entre el archivo del host y el del contenedor.
- [ ] **T2.3:** Cierre.
  - Acceptance: spec en DONE con resultados; memoria del procedimiento de deploy actualizada.
  - Verify: lectura.

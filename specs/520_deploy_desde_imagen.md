# SPEC-520: Producción solo cambia al construir la imagen

**Fecha:** 2026-09-24
**Tipo:** SDD (Spec-Driven Development) — mantenimiento
**Estado:** SPECIFY — pendiente de revisión
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

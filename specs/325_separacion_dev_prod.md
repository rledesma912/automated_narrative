# Spec 325: Separación de Entornos (Dev/Prod) en Host Único

## 1. Contexto y Objetivos
Para permitir el uso continuo de la aplicación por parte de usuarios finales (familia) mientras se realizan evolutivos técnicos (saneamiento de relatos), se requiere una segregación física y lógica de los recursos en la misma máquina.

**Objetivos:**
- **Disponibilidad:** Producción debe ser un servicio "always-on" vía Docker.
- **Aislamiento:** Las bases de datos y archivos generados no deben mezclarse.
- **Simultaneidad:** Poder ejecutar ambas versiones sin conflictos de puertos.

---

## 2. Arquitectura de Segregación

### 2.1. Puertos y Networking
| Servicio | Producción (Docker) | Desarrollo (Host/Native) |
| :--- | :--- | :--- |
| **Frontend (Express)** | `3000` | `3010` |
| **Backend (FastAPI)** | `8010` | `8020` |

### 2.2. Persistencia y FileSystem
| Recurso | Path Producción | Path Desarrollo |
| :--- | :--- | :--- |
| **SQLite DB** | `data/prod/stories.db` | `data/dev/stories.db` |
| **Output MD** | `frontend/public/output_stories/prod/` | `frontend/public/output_stories/dev/` |

---

## 3. Implementación Quirúrgica

### 3.1. Configuración de Entorno (.env)
Dos archivos de entorno, alineados con **cómo cada runtime carga su configuración**:
- `.env`: entorno de **desarrollo** nativo en el host. Es el archivo que `src/config.py`
  carga de forma fija (`SettingsConfigDict(env_file=".env")`). Por eso el dev **no** usa
  un `.env.dev` separado.
- `.env.prod`: entorno de **producción**, inyectado por `docker-compose.yml` vía
  `env_file:`. Contiene las rutas internas de los contenedores.

> **Decisión de validación (2026-05-16):** se descarta `.env.dev`. Crear ese archivo
> sería inerte porque `config.py` lee `.env` hardcodeado; alinear el spec al código
> evita un cambio de bootstrap sin valor. Como consecuencia, el `include .env.dev`
> muerto del `Makefile` se elimina.

### 3.2. Cambios en Backend (FastAPI)
- El archivo `src/config.py` ya soporta `pydantic-settings`. Se debe asegurar que `DATABASE_URL` y `OUTPUT_DIR` se inyecten correctamente.
- El comando de ejecución de `uvicorn` en desarrollo deberá especificar el puerto `8020`.

### 3.3. Cambios en Frontend (Express)
- Introducir `PORT` como variable de entorno (default 3000, usado solo por prod/Docker).
- Configurar `CORE_API_URL` dinámicamente según el entorno.
- El script `dev` en `package.json` debe permitir el paso de estas variables.
- **`frontend/.env` es el archivo de desarrollo**: debe fijar `PORT=3010` y
  `CORE_API_URL=http://localhost:8020`. Tener `PORT=3000` ahí provoca colisión con el
  contenedor de prod cuando se corre `npm run dev` sin pasar por `make ui`.

### 3.4. Docker Compose (Producción)
- Ajustar `docker-compose.yml` para usar el perfil de producción.
- Mapear volúmenes específicamente a la subcarpeta `prod`.
- **Importante:** El contenedor de frontend debe apuntar a la URL interna del contenedor backend en la misma red de Docker, no a `host.docker.internal` si ambos están dentro de Compose.

---

## 4. Plan de Acción

1.  **Infraestructura de Datos:** ✅ *hecho*
    - Crear carpetas `data/prod`, `data/dev`, `output_stories/prod`, `output_stories/dev`.
    - Mover la DB actual a `prod` para no perder datos existentes.
2.  **Configuración:** ✅ *hecho* (`.env` = dev, `.env.prod` = prod — ver §3.1).
3.  **Refactor de Código:** ✅ *hecho* (`frontend/src/server.ts` respeta `PORT`).
4.  **Orquestación:** ✅ *hecho* (`docker-compose.yml` con volúmenes a `prod`).

---

## 5. Verificación
- [x] Producción accesible en `localhost:3000` (contenedor `narrative-ui`).
- [ ] Desarrollo accesible en `localhost:3010`.
- [x] Una historia creada en Dev **no** aparece en Prod (DBs físicamente separadas).
- [ ] El hot-reload en Dev no afecta la ejecución de Prod.

---

## 6. Hallazgos de Validación y Saneamiento (2026-05-16)

Validación cruzada del código tras detectar que `localhost:3000/galeria` mostraba la
historia *barco fantasma* mientras `data/dev/stories.db` estaba vacía.

**Diagnóstico raíz:** *no era un bug.* `localhost:3000` es el contenedor de **producción**
(`narrative-ui` → `narrative-api:8010` → `data/prod/stories.db`, que contiene esa
historia). La separación de bases de datos funciona; lo que falla es la **coherencia de
la configuración**, que confunde y arriesga colisiones.

### 6.1. Correcciones acordadas (refacto quirúrgica, sin breaking changes)

| # | Sev. | Hallazgo | Corrección |
|---|------|----------|------------|
| 1 | 🔴 Bug | `make db` (`Makefile:88`) hace `rm -f data/stories.db && touch data/stories.db`: crea/toca la DB **vieja** en la raíz, mientras `init_db.sh` crea las tablas en `data/dev/stories.db`. | `make db` debe operar sobre `data/dev/stories.db` (crear `data/dev/` y `touch` ahí). |
| 2 | 🔴 Bug | `frontend/.env` tiene `PORT=3000` (puerto de prod). `make ui` lo enmascara, pero `npm run dev` directo colisiona con el contenedor de prod. | `frontend/.env`: `PORT=3010`. `CORE_API_URL=http://localhost:8020` ya es correcto. |
| 4 | 🟡 Doc | `CLAUDE.md` documenta `make api → 8010` y `make ui → 3000`; los puertos reales son `:8020` / `:3010`. | Corregir los puertos en `CLAUDE.md` (sección Commands). |
| 5 | 🟠 Default | `config.py:85` default `database_url = "sqlite+aiosqlite://stories.db"` está malformado (faltan slashes). | Default a `sqlite+aiosqlite:///data/dev/stories.db`. |
| 6 | 🟢 Limpieza | Archivo huérfano `data/stories.db` (0 bytes) en la raíz. `Makefile:11` tiene un `include .env.dev` muerto. | Eliminar `data/stories.db`; quitar `include .env.dev` del `Makefile`. |
| 7 | 🔴 Bug | `scripts/bash/run_dev.sh` (creado por §4) hace `source .env.dev` y aborta con `exit 1` porque ese archivo no existe. | Cargar `.env` en lugar de `.env.dev`. |

### 6.2. Estado correcto verificado (sin cambios)
- Puertos del §2.1 (Docker `3000`/`8010`, host `3010`/`8020`).
- Volúmenes de `docker-compose.yml` apuntando a `data/prod` y `output_stories/prod`.
- `.env.prod` con `DATABASE_URL` de 4 slashes (ruta absoluta de contenedor).
- `init_db()` invocado en el `lifespan` de `src/main.py`.

### 6.3. Documentación sincronizada
Tras el saneamiento se corrigieron las referencias a puertos/rutas obsoletas en:
`README.md`, `CLAUDE.md`, `frontend/.env.example`, `docs/frontend_architecture_map.md`.
`AGENTS.md` se reescribió por completo (referenciaba specs inexistentes `001`–`004` y
flags obsoletos como `--real`).

**Deuda fuera de alcance (no tocada — requiere su propia tarea):**
- `specs/060` y `specs/302` mencionan el path único `data/stories.db` (pre-Spec-325);
  son specs cerrados que describen su estado histórico.

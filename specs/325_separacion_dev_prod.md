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
Se crearán archivos de entorno específicos:
- `.env.prod`: Configurado para las rutas internas de los contenedores.
- `.env.dev`: Configurado para ejecución nativa en el host.

### 3.2. Cambios en Backend (FastAPI)
- El archivo `src/config.py` ya soporta `pydantic-settings`. Se debe asegurar que `DATABASE_URL` y `OUTPUT_DIR` se inyecten correctamente.
- El comando de ejecución de `uvicorn` en desarrollo deberá especificar el puerto `8020`.

### 3.3. Cambios en Frontend (Express)
- Introducir `PORT` como variable de entorno (default 3000).
- Configurar `CORE_API_URL` dinámicamente según el entorno.
- El script `dev` en `package.json` debe permitir el paso de estas variables.

### 3.4. Docker Compose (Producción)
- Ajustar `docker-compose.yml` para usar el perfil de producción.
- Mapear volúmenes específicamente a la subcarpeta `prod`.
- **Importante:** El contenedor de frontend debe apuntar a la URL interna del contenedor backend en la misma red de Docker, no a `host.docker.internal` si ambos están dentro de Compose.

---

## 4. Plan de Acción

1.  **Infraestructura de Datos:**
    - Crear carpetas `data/prod`, `data/dev`, `output_stories/prod`, `output_stories/dev`.
    - Mover la DB actual a `prod` para no perder datos existentes.
2.  **Configuración:**
    - Generar `.env.prod` y `.env.dev` basados en `.env.sample`.
3.  **Refactor de Código:**
    - Modificar `frontend/src/server.ts` para respetar la variable `PORT`.
4.  **Orquestación:**
    - Actualizar `docker-compose.yml` para producción estable.
    - Crear script `scripts/bash/run_dev.sh` para levantar el entorno de desarrollo localmente.

---

## 5. Verificación
- [ ] Producción accesible en `localhost:3000`.
- [ ] Desarrollo accesible en `localhost:3010`.
- [ ] Una historia creada en Dev **no** aparece en Prod.
- [ ] El hot-reload en Dev no afecta la ejecución de Prod.

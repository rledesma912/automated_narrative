# 🐳 Story Form - Guía Docker

Guía para ejecutar la aplicación Story Form en un contenedor Docker.

## 📋 Requisitos previos

- Docker (v20.10+)
- Docker Compose (v2.0+)

## 🚀 Inicio rápido

### 1. Clonar o descargar el proyecto

```bash
cd /mnt/LLM/apps/automated_narrative
```

### 2. Ejecutar con Docker Compose

```bash
# Construir y levantar el contenedor
docker-compose up -d

# Ver los logs
docker-compose logs -f story-form

# Detener el contenedor
docker-compose down
```

### 3. Acceder a la aplicación

- **URL**: http://localhost:3100
- **Contenedor**: story-form-app
- **Puerto expuesto**: 3100

## ⚙️ Configuración

### Variables de entorno

Editar en `.env` antes de ejecutar:

```env
PORT=3100                          # Puerto de la aplicación
SITE_TITLE=Narrative Builder       # Título del sitio
DEFAULT_TOTAL_ACTS=5               # Actos por defecto
```

### Comandos útiles

```bash
# Reconstruir la imagen
docker-compose build --no-cache

# Ejecutar en primer plano
docker-compose up

# Ver estado de contenedores
docker-compose ps

# Acceder a la terminal del contenedor
docker-compose exec story-form sh

# Ver logs en tiempo real
docker-compose logs -f

# Limpiar volúmenes (cuidado: borra datos)
docker-compose down -v
```

## 📁 Volúmenes

El contenedor monta los siguientes volúmenes:

| Local | Contenedor | Descripción |
|-------|-----------|-------------|
| `./story-form/output_stories` | `/app/output_stories` | Historias generadas |
| `./prompts_generacion` | `/app/prompts_generacion` | Prompts de generación (solo lectura) |
| `./prompts_historias` | `/app/prompts_historias` | Prompts de historias (solo lectura) |

## 🔍 Solución de problemas

### El contenedor no inicia

```bash
# Ver los logs detallados
docker-compose logs story-form

# Verificar que el puerto 3100 no esté en uso
lsof -i :3100
```

### Error: "Port 3100 is already allocated"

```bash
# Cambiar el puerto en .env
PORT=3101
```

### Los archivos generados no persisten

Verificar que los directorios locales existan:

```bash
mkdir -p ./story-form/output_stories
mkdir -p ./prompts_generacion
mkdir -p ./prompts_historias
```

## 🐳 Detalles técnicos

- **Base Image**: `node:18-alpine`
- **Node Version**: 18 (LTS)
- **Tamaño de imagen**: ~150 MB
- **Health Check**: Cada 30 segundos
- **Reinicio automático**: Sí (unless-stopped)

## 📝 Notas

- El contenedor se reinicia automáticamente si falla
- Los health checks verifican que la aplicación esté respondiendo
- Los logs están disponibles mediante `docker-compose logs`
- Los datos en `output_stories` persisten entre reinicios

---

Para más información sobre la aplicación, ver [README.md](./README.md)

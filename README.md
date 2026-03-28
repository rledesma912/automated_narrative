# 🧟 Ecosistema de Narrativa Automatizada con IA Local

Este proyecto es una plataforma integral para la generación, gestión y perfeccionamiento de relatos narrativos (especialmente de terror y suspense) utilizando modelos de lenguaje de gran tamaño (LLM) ejecutados localmente. Combina una interfaz web amigable, potentes flujos de automatización en n8n y un sistema de "saneamiento" para garantizar coherencia y calidad literaria.

---

## 🏗️ Arquitectura del Sistema

El ecosistema se divide en tres componentes principales que trabajan en conjunto:

### 1. 🖥️ Story Form (Interfaz Web)
Una aplicación **Node.js/Express** que sirve como centro de control. Permite:
- Gestionar y previsualizar los prompts de generación.
- Visualizar el listado de historias generadas en formato Markdown.
- Administrar la configuración de los capítulos y actos.
- **Tecnologías:** Node.js, EJS, SQLite (para metadatos locales), Docker.

### 2. 🔄 Motores de Generación (n8n)
Flujos de trabajo avanzados que orquestan la inteligencia artificial:
- **Generador de Relatos:** Divide la historia en actos, mantiene una "memoria narrativa" en PostgreSQL y utiliza **Ollama** con modelos como `qwen2.5:32b` para la prosa y `gemma2:9b` para la extracción de estados.
- **Saneador de Narrativa:** Un proceso de post-producción que detecta inconsistencias, corrige errores de estilo y valida la calidad del texto final.

### 3. 🧠 IA Local (Ollama)
Toda la inteligencia reside en tu propia máquina. No hay costes por API ni dependencia de la nube.
- **Modelos recomendados:** `qwen2.5:32b` (Escritura creativa), `gemma2:9b` (Análisis y Resumen).

---

## 📂 Estructura del Proyecto

```bash
/mnt/LLM/apps/automated_narrative/
├── 🌐 story-form/            # Aplicación web (Frontend/Gestión)
├── 🔗 flujos_n8n/             # Archivos JSON para importar en n8n
├── 📝 prompts_generacion/     # Plantillas de sistema y memoria
├── 🖋️ prompts_historias/      # Argumentos y estructuras de relatos específicos
├── 🧹 prompts_saneadores/     # Reglas para el refinamiento de textos
├── 📖 output_stories/         # Relatos terminados en Markdown
├── 🗄️ scripts_db/             # Scripts SQL para inicializar PostgreSQL (n8n)
└── 🐳 docker-compose.yml      # Orquestación de la interfaz web
```

---

## 🚀 Guía de Inicio Rápido

### 1. Requisitos Previos
- **Docker & Docker Compose**
- **Ollama** instalado y corriendo con los modelos: `ollama pull qwen2.5:32b` y `ollama pull gemma2:9b`.
- **n8n** (self-hosted) con acceso a una base de datos **PostgreSQL**.

### 2. Levantar la Interfaz Web (Story Form)
```bash
docker-compose up -d
```
Accede a la gestión de historias en `http://localhost:3100`.

### 3. Configurar la Generación (n8n)
1. Importa el flujo `flujos_n8n/short_distance_narrative.json` en n8n.
2. Ejecuta los scripts de `scripts_db/scripts_dbs.pgsql` en tu base de datos PostgreSQL para crear las tablas necesarias.
3. Configura las credenciales de Ollama y Postgres en n8n.

---

## 🔄 El Proceso de Creación

1. **Definición:** Creas o editas un archivo en `prompts_historias/` con la premisa y los actos.
2. **Lanzamiento:** Inicias el flujo en n8n (puedes dispararlo manualmente o vía webhook).
3. **Escritura Iterativa:** La IA escribe capítulo por capítulo, consultando la base de datos para no perder el hilo narrativo.
4. **Saneamiento:** El flujo de saneamiento revisa el texto generado buscando "alucinaciones" o inconsistencias.
5. **Lectura:** El resultado final se guarda en `output_stories/` y se puede leer desde la interfaz web.

---

## 🛠️ Detalles de los Componentes

### Saneador de Narrativa (`flujo_saneador.md`)
Este componente es crucial para la calidad. Utiliza un proceso de 4 pasos:
- **Detección:** Identifica problemas (nombres cambiados, objetos que desaparecen).
- **Resolución:** Propone correcciones basadas en el contexto previo.
- **Corrección:** Aplica los cambios al texto original.
- **Validación:** Asegura que el texto corregido sea superior al original.

### Base de Datos de Memoria
A diferencia de otros generadores, este sistema usa **PostgreSQL** para almacenar el "Estado Narrativo". Esto permite que la IA sepa exactamente qué ha ocurrido en capítulos anteriores, evitando contradicciones en historias largas.

---

## ⚠️ Consideraciones de Hardware
- **VRAM:** Se recomienda una GPU con al menos **12GB o 16GB de VRAM** para ejecutar `qwen2.5:32b` con fluidez.
- **Almacenamiento:** Los modelos de IA y la base de datos pueden ocupar bastante espacio (aprox. 30GB+ en total).

---
*Desarrollado con pasión por la narrativa y la soberanía tecnológica.*

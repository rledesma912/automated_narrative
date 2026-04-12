
# 🧟 Ecosistema de Narrativa Automatizada con IA Local

Este proyecto es una plataforma integral para la generación, gestión y perfeccionamiento de relatos narrativos de alto impacto (especialmente de terror, suspense y horror cosífico). Utiliza modelos de lenguaje de gran tamaño (LLM) ejecutados localmente, combinados con una técnica de prompting avanzada para evitar narraciones simplistas y lograr una inmersión adulta y sensorial.

El sistema combina una interfaz web amigable, potentes flujos de automatización en n8n y un sistema de "saneamiento" para garantizar coherencia y calidad literaria.

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
- **Generador de Relatos:** Divide la historia en actos, mantiene una "memoria narrativa" en PostgreSQL y utiliza **Ollama** con modelos como `qwen2.5:32b` para la prosa inmersiva y `gemma2:9b` para la extracción y análisis de estados.
- **Saneador de Narrativa:** Un proceso de post-producción que detecta inconsistencias, corrige errores de estilo y valida la calidad del texto final.

### 3. 🧠 IA Local (Ollama)
Toda la inteligencia reside en tu propia máquina. No hay costes por API ni dependencia de la nube.
- **Modelo Principal (Prosas):** `qwen2.5:32b` (Optimizado para escritura creativa compleja y estilo adulto).
- **Modelo Secundario (Análisis):** `gemma2:9b` (Ágil para resumen y extracción de datos).

---

## 🎨 Estrategia de Narrativa y Calidad Literaria

Para elevar la calidad de los relatos y solucionar problemas comunes como el tono infantil ("naif") o la falta de descripción, el sistema implementa una **arquitectura de prompting estricta**:

### Principios Rectores en el System Prompt
El `system_prompt.md` ha sido diseñado para forzar un estilo profesional e inmersivo:
1.  **Show, Don't Tell (Mostrar, no contar):** Se prohíben descripciones vagas de emociones (ej. "tenía miedo"). En su lugar, se obliga a la IA a describir reacciones fisiológicas y sensoriales (ej. "un frío ácido me recorrió la espalda", "mis manos temblaban").
2.  **Densidad Sensorial:** Cada párrafo debe contener al menos dos elementos sensoriales (olores, texturas, sonidos ambientales) para anclar la narración en la realidad.
3.  **Voz Adulta y Testimonial:** La narración se configura en primera persona desde una perspectiva madura y reflexiva, evitando vocabulario simplificado.
4.  **Atmósfera Opresiva:** Se prioriza la construcción de escenarios detallados y climatológicos sobre la acción pura.

### Uso de la Plantilla de Historia (`prompt_story.md`)
Al definir una nueva historia, es crucial alimentar bien el motor:
- **Relator:** Definir no solo quién narra, sino *cómo* lo hace (ej. "desde la adultez, con tono de remordimiento").
- **Input de Actos:** Escribir instrucciones densas para la IA en lugar de resúmenes simples. Incluir detalles del entorno (luces, olores) en la definición del acto.

---

## 📂 Estructura del Proyecto

```bash
/mnt/LLM/apps/automated_narrative/
├── 🌐 frontend/                # Aplicación web Node.js
├── 🔧 src/                     # Backend Python (FastAPI)
├── 📝 prompt_generacion/       # Prompts para generación de relatos
├── 🧹 prompts_saneadores/      # Prompts para refinamiento/saneado
├── 📖 output_stories/          # Relatos terminados
├── 📋 specs/                   # Documentación técnica
├── ⚙️ config/                  # Configuración YAML
└── 🐳 docker-compose.yml       # Orquestación de contenedores
```

---

## 🚀 Guía de Inicio Rápido

### 1. Requisitos Previos
- **Hardware Recomendado (Basado en perfil actual):**
  - **GPU:** NVIDIA GeForce RTX 3060 (12GB VRAM) o superior.
  - **CPU:** AMD Ryzen 5 5600G o equivalente.
  - **RAM:** 32GB+ (Sistema actual: 64GB).
- **Software:**
  - **Docker & Docker Compose**
  - **Ollama** instalado y corriendo.
- **Modelos IA:**
  - `ollama pull qwen2.5:32b` (Para escritura principal).
  - `ollama pull gemma2:9b` (Para tareas auxiliares).
- **n8n** (self-hosted) con acceso a una base de datos **PostgreSQL**.

### 2. Levantar la Interfaz Web (Story Form)
```bash
docker-compose up -d
```
Accede a la gestión de historias en `http://localhost:3100`.

### 3. Configurar la Generación (n8n)
1. Importa el flujo `flujos_n8n/short_distance_narrative.json` en n8n.
2. Ejecuta los scripts de `scripts_db/scripts_dbs.pgsql` en tu base de datos PostgreSQL para crear las tablas necesarias.
3. Configura las credenciales de Ollama y Postgres en n8n. Asegúrate de que el nodo de Ollama apunte a tu modelo `qwen2.5:32b`.

---

## 🔄 El Proceso de Creación

1.  **Definición:** Creas o editas un archivo en `prompts_historias/` aplicando las reglas de "Densidad Sensorial". Defines la premisa, los personajes con profundidad y los actos con detalles ambientales.
2.  **Lanzamiento:** Inicias el flujo en n8n (vía webhook o manualmente).
3.  **Escritura Iterativa:** La IA (`qwen2.5`) escribe capítulo por capítulo. El System Prompt asegura que use un tono adulto y descriptivo. Consulta la base de datos para mantener la coherencia (memoria narrativa).
4.  **Saneamiento:** El flujo de saneamiento revisa el texto generado buscando "alucinaciones" o inconsistencias lógicas.
5.  **Lectura:** El resultado final se guarda en `output_stories/` y se puede leer desde la interfaz web.

---

## 🛠️ Detalles de los Componentes

### Saneador de Narrativa (`flujo_saneador.md`)
Este componente es crucial para la calidad en relatos largos. Utiliza un proceso de 4 pasos:
- **Detección:** Identifica problemas (nombres cambiados, objetos que desaparecen, cambios bruscos de tono).
- **Resolución:** Propone correcciones basadas en el contexto previo almacenado en DB.
- **Corrección:** Aplica los cambios al texto original.
- **Validación:** Asegura que el texto corregido sea superior al original y mantenga el estilo literario.

### Base de Datos de Memoria
A diferencia de otros generadores simples, este sistema usa **PostgreSQL** para almacenar el "Estado Narrativo". Esto permite que la IA sepa exactamente qué ha ocurrido en capítulos anteriores, evitando contradicciones y permitiendo que el miedo o las heridas de los personajes evolucionen con el tiempo.

---

## ⚙️ Configuración de Hardware y Optimización

El sistema está optimizado para funcionar en el siguiente perfil de hardware detectado:
- **Host:** Ubuntu 24.04.4 LTS
- **GPU:** NVIDIA RTX 3060 (12GB VRAM). *Nota: Para modelos de 32B (Qwen), se recomienda ajustar el contexto o usar cuantización si la VRAM se llena.*
- **RAM:** 64GB DDR4.
- **Almacenamiento:** Se recomienda un disco SSD dedicado para los modelos de IA y la base de datos (aprox. 30GB+ en total).

---
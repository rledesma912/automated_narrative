# 🧟 Generador de Relatos con IA Local

Una automatización que escribe historias de terror por capítulos usando inteligencia artificial instalada localmente en tu computadora. No depende de servicios externos ni cobra por uso: todo corre en tu máquina.

---

## 🎯 ¿Qué hace esta automatización?

Esta automatización genera una historia completa dividida en capítulos (actos). Cada vez que la ejecutás, el sistema:

• Lee los archivos de configuración de la historia (personajes, contexto, misión de cada acto).
• Genera cada capítulo usando una IA de escritura creativa (Qwen 2.5).
• Guarda lo que pasó en cada capítulo para que el siguiente no repita ni olvide nada.
• Al terminar todos los actos, une todo y guarda el relato completo como un archivo Markdown.

El resultado es una historia coherente de múltiples capítulos, sin cortes ni contradicciones.

---

## 🔄 Cómo funciona, paso a paso

### 1. Configuración inicial
Se definen el nombre de la historia, la cantidad de capítulos y los archivos de instrucciones. Es el único lugar donde hay que tocar algo antes de ejecutar.

### 2. Lectura de instrucciones
El sistema lee tres archivos desde el disco: el estilo de escritura general, el argumento de la historia y las instrucciones para extraer memoria de cada capítulo.

### 3. Preparación de los actos
El flujo genera un "paquete" por cada capítulo a escribir, con toda la información necesaria: contexto, misión y el estado narrativo acumulado hasta ese momento.

### 4. Bucle de escritura (un capítulo a la vez)
Para cada capítulo, la IA recibe todo el contexto acumulado y escribe el texto del acto. Usa el modelo Qwen 2.5 (32B) para escritura narrativa y Gemma 2 (9B) para extraer y guardar los hechos importantes que deben recordarse.

### 5. Guardado en base de datos
Cada capítulo terminado se guarda en PostgreSQL junto con un resumen y la "memoria" de hechos relevantes. Así, el próximo capítulo siempre sabe qué pasó antes.

### 6. Exportación del relato completo
Cuando todos los capítulos están listos, el sistema los une en orden y guarda el relato completo como un archivo .md (Markdown) en la carpeta de historias generadas.

---

## ⚙️ Qué necesitás para usarlo

- 🤖 n8n (self-hosted, versión comunitaria)
- 🧠 Ollama con modelos `qwen2.5:32b` y `gemma2:9b`
- 🗄️ PostgreSQL para guardar el progreso
- 💻 GPU con al menos 12 GB VRAM (RTX 3060 o similar)
- 📁 Carpeta de prompts con los 3 archivos de instrucciones
- 🐳 Docker Compose para orquestar los servicios

Los modelos de IA se descargan automáticamente con Ollama la primera vez. El flujo n8n se importa desde el archivo .json incluido en este repositorio. Ver el README técnico para la configuración detallada de Docker.

---

## 📂 Archivos del proyecto

```
archivos/
├── prompts_generacion/
│   ├── system_prompt.md          → Estilo y voz del narrador
│   ├── el_nuevo_hogar.md         → Argumento y actos de la historia
│   └── extract_story_state.md    → Instrucciones para extraer memoria
└── historias_generadas/
    └── relato_*.md               → Los relatos terminados (se generan al correr el flujo)

short_distance_narrative.json     → El flujo de n8n, para importar directamente
```

---

## ▶️ Cómo ejecutar

1. Importá el archivo `short_distance_narrative.json` en tu instancia de n8n.
2. Abrí el nodo `valores_manuales` y configurá:
   - `story_name`: el nombre de tu historia
   - `total_acts`: cuántos capítulos querés generar (ej. 5)
   - `story_prompt_file`: el nombre del archivo .md con el argumento
3. Asegurate de que Ollama esté corriendo con los modelos descargados.
4. Hacé clic en "Execute workflow".
5. Esperá — cada capítulo tarda entre 2 y 5 minutos dependiendo del hardware.
6. El relato terminado aparecerá en `historias_generadas/` como un archivo Markdown.

---

## ⚠️ Limitaciones conocidas

• El flujo tarda bastante: en una RTX 3060 cada capítulo puede llevar de 2 a 8 minutos.
• No tiene interfaz visual de progreso — hay que mirar la ejecución en n8n.
• El modelo qwen2.5:32b requiere bastante VRAM; con menos de 12 GB puede no correr bien.
• Si se interrumpe a mitad, los capítulos ya guardados en la base de datos no se borran, pero el archivo final no se genera.

---

*Generado con n8n · Ollama · PostgreSQL · todo local, sin costos de API.*

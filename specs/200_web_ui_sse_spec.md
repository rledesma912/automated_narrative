# Spec-200: Web Experience & SSE Streaming

## 1. Objetivo
Transformar NarrativeForge en una aplicación web inmersiva para uso local/familiar, permitiendo la configuración detallada de historias y la visualización de su generación en tiempo real mediante Server-Sent Events (SSE).

## 2. Visión del Producto (Business Context)
- **Audiencia:** Uso doméstico y familiar.
- **Experiencia:** Un "Asistente de Autoría" que guía al usuario para eliminar "huecos" narrativos, seguido de una "Sala de Streaming" donde el relato cobra vida.
- **Estética:** Horror/Noir atmosférico, con temas visuales intercambiables.

## 3. Arquitectura Técnica (Frontend)
### 3.1 Stack
- **Servidor:** Node.js + Express + TypeScript.
- **Vistas:** EJS (Embedded JavaScript templates) + HTMX (para interactividad y SSE).
- **Estilos:** Tailwind CSS + Lucide Icons.
- **Patrón:** Clean MVC (Model-View-Controller) con Capa de Servicio.

### 3.2 El Adaptador Literario (The Bridge)
Para no modificar el Core (Python), el servidor Node.js realizará un mapeo:
- **Input:** Datos granulares del Wizard (WizardDTO: nombre, edad, miedo, etc.).
- **Output:** Strings descriptivos para el Core (CoreDTO: `protagonista`, `sinopsis`, etc.).
- **Persistencia:** El JSON granular original se enviará al campo `storyteller_config` de la base de datos para permitir ediciones futuras.

### 3.3 Estrategia de "Zero Gaps"
- **`ui_definitions.yaml`:** Fuente de verdad para los campos del formulario, tipos, validaciones y placeholders.
- **Stepper Navigation:** Navegación adelante/atrás gestionada por la sesión de Express para garantizar integridad de datos.

## 4. Roadmap de Slices (QA-Oriented)

Cada slice debe ser auditable y funcional de forma aislada.

### Slice 1: Latido de Infraestructura y Diagnóstico
- **Meta:** Servidor Node/TS vivo con comunicación básica y entorno de pruebas.
- **QA Check:** Ruta `/debug` con estado del Core API. Verificación de instalación de Playwright.
- **Entregable:** Base de servidor Express funcional + Configuración de Playwright local.

### Slice 2: Scaffolding y Navegación
- **Meta:** Layout maestro y sistema de rutas MPA.
- **QA Check:** Navegación funcional vía Sidebar entre Inicio, Generar y Galería.
- **Entregable:** Layout EJS + Menú lateral con Lucide Icons.

### Slice 3: Motor de Temas y UI Components
- **Meta:** Estética inmersiva y flexibilidad visual.
- **QA Check:** Selector de temas dinámico inyectando clases CSS desde `themes.json`.
- **Entregable:** Catálogo de componentes (botones, inputs) y sistema de temas.

### Slice 4: Framework del Wizard (Navegación de Estado)
- **Meta:** Motor de pasos con persistencia de datos.
- **QA Check:** Completar datos en Paso 1, avanzar al 3, volver al 1 y verificar persistencia.
- **Entregable:** Stepper dinámico con Express-Session.

### Slice 5: Generación Dinámica de Formularios (YAML)
- **Meta:** Formularios automáticos basados en el esquema de dominio.
- **QA Check:** Verificación de que los inputs coinciden con `ui_definitions.yaml`.
- **Entregable:** Renderizador de formularios dinámico.

### Slice 6: El Puente y Streaming (Final Integration)
- **Meta:** Conexión real con el Core y visualización SSE.
- **QA Check:** Previsualización del JSON enviado a Python y visualización del stream.
- **Dependencia:** **Requiere implementación de Spec-201 en el Core API.**
- **Entregable:** Mapper Service + Streaming Room.

## 5. Estándar de Documentación y Calidad (EDF)
- **Code:** Comentarios en TypeScript para lógica compleja.
- **Templates:** Documentar variables de entrada en cada partial EJS.
- **API:** Registro de endpoints internos de Node en este Spec.
- **Validación Automática:** Se utilizará **Playwright** (instalación local en `frontend/`) para pruebas E2E y regresión visual de cada Slice. Los tests residirán en `frontend/tests/e2e/`.

## 6. Apéndice Técnico para Implementación

### 6.1 Endpoints del Core API (FastAPI)
- `GET /health`: Chequeo de salud y proveedores (Ollama/API Keys).
- `GET /stories`: Lista todas las historias.
- `GET /stories/{id}/full`: (Spec-201) Historia + Beats + Anclajes en una sola petición.
- `POST /stories`: Crea una nueva historia. Recibe `StoryCreateRequest`.
- `POST /stories/{id}/stream`: (Spec-201) Endpoint SSE para generación.

### 6.2 Lógica del Wizard (Mapping)
1. **Configuración:** `title`, `atmosfera`, `relator`.
2. **Protagonista:** `nombre`, `rasgo`, `miedo`, `motivacion`.
    - `protagonista` = `"${nombre}, caracterizado por ${rasgo}, cuyo mayor miedo es ${miedo}. Su meta: ${motivacion}"`
3. **Mundo:** `ubicacion`, `clima`, `regla_paranormal`.
    - `escenarios` = `"${ubicacion} bajo un clima de ${clima}"`
4. **Trama:** `sinopsis` (textarea libre).

# Spec-210: Arquitectura Web, Streaming y Comunicación

## 1. Visión General
NarrativeForge es una aplicación web inmersiva que transforma el core de generación literaria en una experiencia de autoría asistida. Se basa en una arquitectura de doble servidor con un origen único para el cliente.

## 2. Stack Tecnológico
- **Frontend Server:** Node.js + Express + TypeScript.
- **Backend Core:** Python + FastAPI.
- **Interactividad:** HTMX para swaps asíncronos y diálogos.
- **Estilos:** Vanilla CSS con variables de escala global (tipografía y espaciado aumentados para legibilidad).
- **Comunicación:** Server-Sent Events (SSE) para streaming en tiempo real.

## 3. Estrategia de Origen Único (Proxy)
El navegador solo se comunica con el servidor Express. Todas las llamadas al Core API se realizan a través de un proxy interno:
- **Path:** `/api/*` en Express se redirige a `CORE_API_URL`.
- **URLs Relativas:** El frontend utiliza rutas relativas (ej: `/api/v1/stories/...`) eliminando dependencias de host/puerto en el cliente.
- **Configuración:** El proxy desactiva el buffering y la compresión para permitir el flujo SSE sin interrupciones.

## 4. Arquitectura de Streaming (Broadcaster)
Para garantizar la integridad y eficiencia, el sistema utiliza un **StreamSessionManager** (Singleton) en el backend:
- **Idempotencia:** Solo existe un pipeline de generación (productor LLM) por cada `story_id`.
- **Multi-consumidor:** Múltiples pestañas pueden observar la misma generación. El manager distribuye los eventos a todos los clientes conectados.
- **Replay Buffer:** Los nuevos clientes que se conectan a una generación en curso reciben los últimos 50 eventos (catch-up) para visualizar el progreso previo.
- **Modo Monitor:** Si una historia ya está en estado `processing`, la sala de streaming entra automáticamente en modo lectura activa, conectándose al flujo existente sin disparar una nueva generación.

## 5. Endpoints de Soporte y Diagnóstico
El Core expone endpoints específicos para facilitar la integración y observabilidad:
- `GET /health`: Verifica la salud de SQLite y los proveedores de LLM (Ollama/Anthropic/Gemini).
- `GET /stories/{id}/full`: Devuelve la historia con sus beats y anclajes anidados para carga rápida.
- `GET /config/active-profile`: Informa sobre el modelo y proveedor de IA activo.

## 6. Observabilidad y UI de Estado
- **Logs de Contexto:** El backend registra logs detallados de cada sesión de stream, incluyendo el estado de la base de datos y conflictos de concurrencia.
- **Footer Global:** La aplicación muestra un footer con el estado de la historia actualmente en proceso, permitiendo volver a la sala de streaming desde cualquier vista.
- **Feedback Visual:** Uso de spinners dinámicos y círculos de fase (Análisis, Exposición, Acción, Clímax, Resolución) para indicar el progreso del LLM.

---
*Este documento unifica las especificaciones 200, 201, 211, 220 y 221.*

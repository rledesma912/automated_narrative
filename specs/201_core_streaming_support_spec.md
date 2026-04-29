# Spec-201: Core Streaming & Support Implementation

## 1. Objetivo
Habilitar las capacidades técnicas en el Core API (Python) para soportar la visualización en tiempo real (streaming) y facilitar el consumo de datos por parte del frontend.

## 2. Hito 1: Tipado y Dominio del Stream
### 2.1 StreamEvent DTO
Crear un objeto estándar para la comunicación asíncrona:
```python
class StreamEventType(str, Enum):
    STATUS = "status"
    ANCHORS = "anchors"
    BEAT_START = "beat_start"
    BEAT_DONE = "beat_done"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    DONE = "done"

class StreamEvent(BaseModel):
    event: StreamEventType
    data: dict | str
    timestamp: datetime = Field(default_factory=datetime.now)
```

## 3. Hito 2: Refactor de Orquestación
### 3.1 DirectorUseCase.execute_full()
Transformar el método principal en un Generador Asíncrono:
- **Firma:** `async def execute_full(self, story: Story) -> AsyncGenerator[StreamEvent, None]`
- **Comportamiento:** Debe hacer `yield` de un `StreamEvent` en cada punto de control:
    - Inicio de extracción de anclajes.
    - Fin de anclajes (incluyendo el payload).
    - Inicio/Fin de cada beat.
    - Errores capturados durante el pipeline.

## 4. Hito 3: Streaming API (SSE)
### 4.1 Endpoint POST /stories/{id}/stream
- **Descripción:** Dispara el orquestador para una historia existente.
- **Implementación:** Usa `sse_starlette.EventSourceResponse`.
- **Heartbeat:** Inyectar un evento de tipo `heartbeat` cada 15 segundos de inactividad del LLM para evitar timeouts de Nginx/Browser.

## 5. Hito 4: Endpoints de Soporte y Diagnóstico
### 5.1 GET /health
- Verifica conectividad con:
    - SQLite (`aiosqlite`).
    - Ollama (si el perfil activo es local).
    - Anthropic/Gemini (si hay API Keys configuradas).
- Devuelve estado 200 si el sistema es capaz de generar, 503 si el proveedor principal está caído.

### 5.2 GET /stories/{id}/full
- Devuelve el objeto `Story` con sus `Beats` y `NarrativeAnchors` anidados.
- Propósito: Minimizar llamadas de red del Frontend al cargar el lector de historias.

### 5.3 GET /config/active-profile
- Devuelve el nombre del modelo y proveedor activo.
- Propósito: Mostrar logos o info técnica en la UI del usuario.

## 6. Documentación
- Actualizar el Swagger (`/docs`) con ejemplos de payloads para los nuevos endpoints.
- Documentar los códigos de error específicos para el streaming.

---
*Este documento es complementario al Spec-200 y define el contrato técnico del lado del servidor.*

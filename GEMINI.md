# Manifiesto de Ingeniería (NarrativeForge API)

> Este documento es una extensión de las instrucciones del sistema. Sus mandatos tienen **precedencia absoluta** durante el desarrollo de este proyecto.

## 1. Calidad del Código y Diseño
- **Clean Architecture:** Mantener una separación estricta entre Domain, Application, Infrastructure y Presentation.
- **Interfaces sobre Implementación:** Nunca inyectar clases concretas de infraestructura en la capa de Aplicación. Usar `src/domain/interfaces.py` (ABC o Protocol).
- **SOLID Mandatorio:** 
    - (S) Clases con una única responsabilidad.
    - (O) El `ResponseProcessor` debe estar abierto a nuevos sanitizadores sin cambiar su código.
    - (L) Los Adaptadores de LLM deben ser intercambiables sin romper el pipeline.
    - (I) Interfaces granulares, no genéricas.
    - (D) Depender de abstracciones, no de concreciones.
- **KISS & DRY:** Si una solución es "demasiado inteligente" pero difícil de leer, simplifícala. Centraliza la lógica de sanitización.

## 2. Estándares Técnicos (Python 3.12+)
- **Tipado Estricto:** Todas las funciones deben tener Type Hints completos.
- **Validación:** Usar Pydantic v2 para todos los modelos de datos y esquemas de API.
- **Asincronía:** Usar `async/await` para I/O (Ollama, DB, FastAPI).
- **Testing:** 
    - Escribir el test **antes o junto** con la funcionalidad.
    - El 100% de la lógica de sanitización debe estar cubierta por tests unitarios.
- **Logs:** Usar el logger estándar de Python, evitando `print()`.

## 3. Workflow de Desarrollo (SDD)
- No avanzar a un nuevo hito si los tests del anterior fallan.
- Mantener el Spec (`specs/003_evolutivo_refactor_to_api.md`) actualizado con cualquier decisión técnica importante.

---
*Firma: El Agente Gemini CLI en modo Senior Software Engineer.*

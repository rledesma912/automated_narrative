# Spec 007: Gemini Multi-Provider Integration

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Implementado (adapter existe, no usado en producción)  
> **Owner:** Arquitecto de Software  
> **Tags:** infrastructure, llm, gemini, ports-and-adapters

---

## 1. Objective

Habilitar la integración de **Google Gemini** como un proveedor de LLM alternativo a Ollama. Esto permitirá al sistema generar relatos con mayor coherencia narrativa y aprovechar la ventana de contexto extendida de Gemini cuando sea necesario, manteniendo la arquitectura de **Ports & Adapters**.

**¿Por qué?**
- Calidad narrativa superior en modelos grandes.
- Estabilidad de generación (evita caídas de Ollama local en equipos de bajos recursos).
- Transparencia para el resto del sistema gracias a la abstracción de la interfaz `LLMProvider`.

---

## 2. Project Structure

```
src/
├── domain/
│   └── interfaces.py       # LLMProvider (ya definido)
├── infrastructure/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── ollama_adapter.py
│   │   └── gemini_adapter.py   # NUEVO: Implementación Gemini
│   └── factories.py           # NUEVO: Inyección de dependencias (Factory Pattern)
├── config.py                 # Actualizar Settings para Gemini API Key
└── cli/
    └── commands.py           # Usar Factory para instanciar el LLM
```

---

## 3. Tech Stack

- **Librería:** `google-generativeai>=0.8.0`
- **Modelos recomendados:** `gemini-1.5-flash` (velocidad) o `gemini-1.5-pro` (calidad).
- **Seguridad:** Manejo de API Key mediante variables de entorno (.env).

---

## 4. Cambios en Configuración

Se añadirán las siguientes variables al archivo `.env` y a `src/config.py`:

| Variable | Tipo | Descripción | Default |
|----------|------|-------------|---------|
| `LLM_PROVIDER` | `str` | `ollama` o `gemini` | `ollama` |
| `GEMINI_API_KEY` | `str` | API Key de Google AI Studio | (vacío) |
| `GEMINI_MODEL` | `str` | Modelo a usar | `gemini-1.5-flash` |

---

## 5. Patrón de Diseño: LLM Factory

Para cumplir con **SOLID**, el orquestador y los comandos no deben instanciar adaptadores concretos. Usaremos una **Factory** en infraestructura:

```python
# src/infrastructure/factories.py
class LLMFactory:
    @staticmethod
    def get_provider() -> LLMProvider:
        if settings.llm_provider == "gemini":
            return GeminiAdapter(api_key=settings.gemini_api_key)
        return OllamaAdapter()
```

---

## 6. Success Criteria

- [ ] `GeminiAdapter` implementa satisfactoriamente `LLMProvider`.
- [ ] El sistema permite cambiar de proveedor solo modificando el `.env`.
- [ ] El manejo de errores de Gemini (quotalimits, invalid key) se traduce a `OllamaConnectionError` o una nueva `LLMProviderError` genérica en español.
- [ ] Tests unitarios del adaptador con mocks de la API de Google.

---

## 7. Boundaries (Límites)

### Always Do
- [ ] Usar el SDK oficial de Google.
- [ ] Traducir logs de Gemini a español siguiendo el hito **REF-1**.
- [ ] Cerrar sesiones/clientes asíncronos en el método `close()`.

### Ask First
- [ ] Cambiar la temperatura por defecto de Gemini si difiere mucho de la de Ollama.
- [ ] Usar modelos específicos de Gemini para diferentes roles (Director vs Voz).

### Never Do
- [ ] Hardcodear la API Key en el código.
- [ ] Committear el archivo `.env` con la llave real.

---

## 8. Hitos de Implementación

### Hito 1: Infraestructura Gemini
- [ ] T.1.1: Añadir `google-generativeai` a `pyproject.toml`.
- [ ] T.1.2: Implementar `GeminiAdapter` en `src/infrastructure/adapters/gemini_adapter.py`.
- [ ] T.1.3: Asegurar que `LLMResponse` maneje el output de Gemini.

### Hito 2: Configuración y Factory
- [ ] T.2.1: Actualizar `src/config.py` con las nuevas variables.
- [ ] T.2.2: Crear `src/infrastructure/factories.py`.
- [ ] T.2.3: Refactorizar `src/cli/commands.py` para usar la Factory.

### Hito 3: Validación y Pruebas
- [ ] T.3.1: Test de integración básico (con Mock o API Real).
- [ ] T.3.2: Documentar el uso en el README.

---

## 9. Nota de Estado Actual

El adapter `GeminiCLIAdapter` está implementado en `src/infrastructure/adapters/gemini_cli_adapter.py`. El sistema soporta `--provider gemini` desde CLI. Sin embargo, el provider default es Ollama.

---

## 10. Preguntas Abiertas

1. ¿Deseamos que el comando CLI acepte un flag `--provider gemini` para sobrescribir el `.env` en tiempo de ejecución?
2. ¿Cómo manejamos el `context` (memoria interna de Ollama) en Gemini? (Gemini usa historial de mensajes, no un vector de ints).

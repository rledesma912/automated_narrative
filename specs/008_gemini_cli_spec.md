# Spec 008: Gemini CLI Provider Integration

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Implementado (GeminiCLIAdapter funciona)  
> **Owner:** Arquitecto de Software  
> **Tags:** infrastructure, llm, gemini, cli, subprocess

---

## 1. Objetivo

Habilitar la integración de **Gemini CLI** (comando `gemini`) como un proveedor de LLM alternativo. En lugar de utilizar el SDK de Google AI Studio, el sistema interactuará con el binario instalado en el sistema operativo mediante subprocesos asíncronos.

**¿Por qué?**
- Aprovechar configuraciones de autenticación ya existentes en el entorno del usuario.
- Evitar dependencias pesadas de SDKs externos si el CLI ya está disponible.
- Consistencia con el flujo de trabajo de otros proyectos del usuario.

---

## 2. Project Structure

```
src/
├── infrastructure/
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── ollama_adapter.py
│   │   └── gemini_cli_adapter.py   # NUEVO: Implementación vía Subprocess
│   └── factories.py                # Actualizar para inyectar GeminiCLIAdapter
└── config.py                       # Variables para GEMINI_CLI_COMMAND y GEMINI_MODEL_NAME
```

---

## 3. Tech Stack

- **Python:** `asyncio.subprocess` para ejecución asíncrona no bloqueante.
- **CLI:** Comando `gemini` (debe estar en el PATH).
- **Mecanismo:** Pipe de `stdin` para el prompt y captura de `stdout` para la respuesta.

---

## 4. Cambios en Configuración

Se añadirán las siguientes variables al archivo `.env` y a `src/config.py`:

| Variable | Tipo | Descripción | Default |
|----------|------|-------------|---------|
| `GEMINI_CLI_COMMAND` | `str` | Nombre del binario/comando | `gemini` |
| `GEMINI_MODEL_NAME` | `str` | Modelo a pasar al flag `--model` | `gemini-1.5-pro-latest` |

---

## 5. Implementación Técnica (Lógica de Generación)

El adaptador debe realizar una llamada equivalente a:
`echo "prompt" | gemini --model <modelo>`

En Python:
```python
process = await asyncio.create_subprocess_exec(
    self.cli_command, "--model", self.model_name,
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
)
stdout, stderr = await process.communicate(input=prompt.encode())
```

---

## 6. Success Criteria

- [ ] `GeminiCLIAdapter` implementa satisfactoriamente `LLMProvider`.
- [ ] El sistema captura correctamente la salida de texto del CLI.
- [ ] Los errores de ejecución (comando no encontrado, error del modelo) se capturan en los logs de NarrativeForge.
- [ ] **Importante:** El método `generate` retorna siempre el objeto `LLMResponse` con el contenido de `stdout`.

---

## 7. Boundaries (Límites)

### Always Do
- [ ] Usar `asyncio` para evitar bloqueos del servidor FastAPI.
- [ ] Validar que el comando `gemini` existe al inicializar el adaptador.
- [ ] Concatenar `system_prompt` + `prompt` antes de enviarlo al CLI.

### Never Do
- [ ] Usar `os.system` o `subprocess.run` (sincrónicos).
- [ ] Dejar procesos "zombis" o huérfanos sin cerrar los pipes.

---

## 8. Hitos de Implementación

### Hito 1: Limpieza y Reorientación
- [ ] T.1.1: Eliminar `google-generativeai` de las dependencias.
- [ ] T.1.2: Eliminar `src/infrastructure/adapters/gemini_adapter.py`.

### Hito 2: Adaptador CLI
- [ ] T.2.1: Implementar `GeminiCLIAdapter` en `src/infrastructure/adapters/gemini_cli_adapter.py`.
- [ ] T.2.2: Actualizar `src/config.py` con `GEMINI_CLI_COMMAND` y `GEMINI_MODEL_NAME`.

### Hito 3: Integración Final
- [ ] T.3.1: Actualizar `LLMFactory` para usar el nuevo adaptador CLI.
- [ ] T.3.2: Realizar una prueba de generación usando el CLI.

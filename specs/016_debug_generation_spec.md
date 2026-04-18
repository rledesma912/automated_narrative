# SPEC 016: Debug de Generación - Verificar Flujo de Prompts

## Estado

> Draft - Pendiente de implementación

## Objetivo

Agregar logging/debug para verificar exactamente qué se envía al LLM y qué responde, para identificar por qué la historia no respeta el input.

## Problema

Al generar, el LLM recibe prompts incorrectos o incompletos, resultando en:
- Narrador incorrecto (Ricardo en vez de Irene)
- Repetición de "Me desperté..."
- Sin continuidad de beats

## Plan de Debug

### Nivel 1: Logging en PromptBuilder

Agregar logs en `prompt_builder.py` para verificar TODAS las variables que se pasan:

```python
def build_beat_prompt(self, ...):
    logger.debug(f"[BUILDER] build_beat_prompt llamado")
    logger.debug(f"[BUILDER] story.relator = {story.relator}")
    logger.debug(f"[BUILDER] beat.number = {beat.number}")
    logger.debug(f"[BUILDER] previous_beats count = {len(previous_beats) if previous_beats else 0}")
    logger.debug(f"[BUILDER] journal = {journal}")
    logger.debug(f"[BUILDER] total_beats = {total_beats}")
```

### Nivel 2: Logging en VozUseCase

Agregar logs en `voz_use_case.py`:

```python
async def execute(self, ...):
    logger.debug(f"[VOZ] execute llamado para beat #{beat.number}")
    logger.debug(f"[VOZ] previous_beats = {previous_beats}")
    logger.debug(f"[VOZ] journal = {journal}")
    logger.debug(f"[VOZ] prompt (primeros 500 chars) = {prompt[:500]}")
    logger.debug(f"[VOZ] system_prompt = {system_prompt}")
```

### Nivel 3: Logging en LLM Adapter

Agregar logs en `ollama_adapter.py`:

```python
async def generate(self, prompt, ...):
    logger.debug(f"[OLLAMA] generate llamado")
    logger.debug(f"[OLLAMA] prompt = {prompt[:200]}...")
    logger.debug(f"[OLLAMA] model = {model}")
    logger.debug(f"[OLLAMA] temperature = {temperature}")
    # ... después de generar
    logger.debug(f"[OLLAMA] response = {response.text[:200]}...")
```

## Puntos de Verificación

| # | Checkpoint | Qué verificar | Esperado |
|---|----------|-----------|--------|
| 1 | `_normalize_relator("Irene")` | Debe retornar "Irene" | "Irene" |
| 2 | `story.relator` en DB | Qué se guarda | "Irene" |
| 3 | `build_beat_prompt()` prompt | Incluye "Irene" |Sí |
| 4 | `persona_gramatical` | "primera persona (ella narra)" |Sí |
| 5 | `previous_beats` en ejecución | Lista con beats anteriores |Sí |
| 6 | Prompt enviado a Ollama | Contiene contexto anterior |Sí |
| 7 | Respuesta del LLM | Usa "Irene" o "ella" |Sí |

## Implementación

### 1. Agregar logger de debug en prompt_builder.py

```python
import logging
logger = logging.getLogger(__name__)

class PromptBuilder:
    # ... en build_beat_prompt:
    logger.debug(f"[PB] relator={story.relator}, beat={beat.number}, prev_beats={len(previous_beats) if previous_beats else 0}")
    ...
    logger.debug(f"[PB] prompt_preview=\n{prompt[:1000]}")
```

### 2. Agregar debug en voz_use_case.py

```python
logger.debug(f"[VOZ] beat={beat.number}, story.relator={story.relator}")
logger.debug(f"[VOZ] prompt=\n{prompt[:1500]}")
logger.debug(f"[VOZ] system_prompt=\n{system_prompt[:500]}")
```

### 3. Habilitar logging

En `.env` o temporalmente:

```bash
LOG_LEVEL=DEBUG
```

O en código:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Ejecución de Debug

```bash
# Con mock para ver rapidamente
uv run python -m src generate --input el_monte_prohibido.md --beats 3

# Con real
uv run python -m src generate --input el_monte_prohibido.md --beats 3 --real
```

## output esperado

Debería ver en los logs:

```
[PB] relator=Irene, beat=1, prev_beats=0
[PB] persona_gramatical=primera persona (ella narra)
[PB] prompt_preview=
# INSTRUCCIONES DE VOZ - NARRACIÓN DE BEAT
## HISTORIA BASE
- Título: El Monte Prohibido
- Relator: Irene
- Persona gramatical: primera persona (ella narra)
...

[VOZ] beat=1, story.relator=Irene
[VOZ] prompt=
# INSTRUCCIONES DE VOZ...
```

## Criterios de Validación

- [ ] Logs muestran relator correcto ("Irene")
- [ ] Logs muestran beat_number y total_beats
- [ ] Logs muestran previous_beats
- [ ] Prompt enviado contiene contexto anterior
- [ ] Response del LLM usa relator correcto
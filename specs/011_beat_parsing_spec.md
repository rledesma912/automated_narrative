# Spec 011: Fix Beat Parsing y Control de Cantidad

## Problema

Al generar beats, el sistema presenta varios problemas:

1. **Parsing incorrecto**: Los beats se numeran incorrectamente (1, 3, 5, 7, 9 en vez de 1, 2, 3, 4, 5)
2. **Modelo no respeta cantidad**: Al pedir 5 beats, el planner genera 30 beats (con el modelo Tohur/natsumura)
3. **Refusal del modelo**: Llama3.1 se niega a generar ciertos contenidos con "Lo siento, pero no puedo..."

## Análisis

### 1. Problema de Parsing

El código en `director_use_case.py:_parse_beats()` parsea beats así:
```python
for i, line in enumerate(lines, 1):
    if line and line[0].isdigit():
        summary = line.split(".", 1)[-1].strip()
        beats.append(Beat(number=i, ...))  # <-- usa i (índice del enumerate) no el número del beat
```

El problema: usa `i` (el índice del loop) en vez del número real que el modelo emitió. El modelo emitió líneas como "1. Apertura:", "3. Incidente:", etc, y el código debería extraer ese primer número.

### 2. Modelo no respeta cantidad

El prompt actual no tiene suficiente enforcement para respetar `num_beats`. Especialmente cuando usa el planner_prompt_narrative.md que siempre dice "Responde solo con 6 líneas".

### 3. Refusals

El modelo Llama3.1 tiene content policies que refusan ciertos prompts. Esto es un problema del modelo, no del código.

## Solución

### Fix 1: Corregir parsing de beats

En `director_use_case.py`, extraer el número real del beat desde la línea:

```python
def _parse_beats(self, text: str, story_id, num_beats: int) -> list[Beat]:
    beats = []
    lines = text.strip().split("\n")
    
    for line in lines:
        line = line.strip()
        # Extraer el número del beat (puede ser "1." o "1" al inicio)
        match = re.match(r'^(\d+)', line)
        if match:
            beat_number = int(match.group(1))
            # Extraer el contenido después del número
            summary = line[len(match.group(0)):].strip(".- ").strip()
            if summary:
                beats.append(Beat(
                    number=beat_number,  # Usar el número real extraído
                    summary=summary,
                    status="pending",
                ))
```

### Fix 2: Enforce cantidad de beats en prompt

Modificar el prompt para que sea más estricto con la cantidad de beats solicitados:

```python
def build_planner_prompt(self, story: Story, num_beats: int = 8) -> str:
    # Siempre usar el formato genérico, nunca el hardcodeado de 6
    return f"""Crea exactamente {num_beats} beats para esta historia de terror:

Título: {story.title}
Protagonistas: {story.protagonista}
Escenarios: {story.escenarios}
Sinopsis: {story.sinopsis}
Atmósfera: {story.atmosfera}

REGLAS OBLIGATORIAS:
- Genera EXACTAMENTE {num_beats} beats
- Cada beat debe ser una línea que starts con el número: "1.", "2.", etc
- No生成es más de {num_beats} beats
- Formato: "n. Título del beat" (una línea por beat)

Responde solo con {num_beats} líneas numeradas."""
```

### Fix 3: Manejar refusals

Agregar retry logic o fallback cuando el modelo refuses.

## Implementación

1. [ ] Fix parsing en `director_use_case.py:_parse_beats()`
2. [ ] Enforce `num_beats` en prompts (remover el branch de 6 beats)
3. [ ] Agregar manejo de refusals
4. [ ] Testear con generación real
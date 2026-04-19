# Spec 032 — Debug Prompt/Response Dump

**Estado:** DRAFT  
**Fecha:** 2026-04-19  
**Rama destino:** `fix_flow_ollama_local`  
**Motivación:** Los modelos locales (Ollama/Mistral, Llama, Natsumura) producen relatos que ignoran la sinopsis o rompen la estructura de beats, mientras que Gemini y Claude generan con calidad aceptable. El log actual registra mensajes de orquestación pero **no expone el payload completo** (prompt exacto → respuesta raw → respuesta normalizada → resultado del parser). Sin esa tripleta en crudo, diagnosticar la causa raíz es imposible.

---

## 1. Objetivo

Agregar un flag `--debug` al comando `generate` que, al activarse, genere un archivo  
`debug_prompts_responses_YYYYMMDDHHМM.md` en el directorio `output_stories/` (o en el directorio de output configurado).

El archivo debe permitir responder estas preguntas sin tocar el código:

| Pregunta diagnóstica | Sección del archivo |
|---|---|
| ¿El prompt que llega al modelo es coherente y completo? | `### Prompt Enviado` |
| ¿El modelo ignoró las instrucciones o alucinó formato? | `### Respuesta Raw` |
| ¿El normalizer eliminó contenido narrativo útil? | `### Respuesta Normalizada` + diff conceptual |
| ¿El parser pudo extraer los beats o falló silenciosamente? | `### Resultado del Parser` |
| ¿Qué parámetros de inferencia usó el modelo? | `### Parámetros de Inferencia` |
| ¿Cuánto tiempo tomó cada llamada? | `### Timing` |

---

## 2. Alcance

### 2.1 Incluido en este spec

- Flag `--debug` en `runner.py` (subparser `generate`).
- Servicio `DebugCollector` en `src/application/services/debug_collector.py`.
- Inyección de `DebugCollector` en `StoryRunner`, `SynopsisBeatMapper`, `VozUseCase` y `MemoryJournalist`.
- Renderer `DebugMarkdownRenderer` en `src/infrastructure/renderers/debug_renderer.py`.
- Tests unitarios en `tests/unit/application/test_debug_collector.py`.

### 2.2 Excluido

- UI / FastAPI endpoint (fuera de scope de diagnóstico CLI).
- Exportación en JSON o HTML (puede venir en spec posterior).
- Integración con `plan` y `narrate` como comandos separados (se puede agregar fácilmente después por reutilización del collector).

---

## 3. Project Structure

```
src/
  application/
    services/
      debug_collector.py        ← NUEVO
  infrastructure/
    renderers/
      debug_renderer.py         ← NUEVO
  core/
    orchestrator.py             ← MODIFICADO (inyección del collector)
  application/
    use_cases/
      synopsis_beat_mapper.py   ← MODIFICADO (emite eventos al collector)
      voz_use_case.py           ← MODIFICADO (emite eventos al collector)
  cli/
    runner.py                   ← MODIFICADO (flag --debug)
    commands.py                 ← MODIFICADO (pasa debug_mode al runner)
tests/
  unit/
    application/
      test_debug_collector.py   ← NUEVO
```

---

## 4. Modelo de datos del Collector

### 4.1 `LLMCallRecord` — registro de una llamada individual al LLM

```python
@dataclass
class LLMCallRecord:
    role: str                    # "mapper" | "voz" | "journal"
    beat_number: int | None      # None para mapper, 1-N para voz/journal
    source_component: str        # clase + archivo resueltos en runtime, ej: "SynopsisBeatMapper (synopsis_beat_mapper.py)"
    model: str
    temperature: float
    num_ctx: int | None
    num_predict: int | None
    system_prompt: str | None
    user_prompt: str
    raw_response: str
    normalized_response: str
    parser_result: str           # "ok:<N beats>" | "error:<mensaje>" | "n/a"
    elapsed_s: float
    timestamp: datetime
```

### 4.2 `DebugCollector` — acumulador de sesión

```python
class DebugCollector:
    records: list[LLMCallRecord]

    def record(self, **kwargs) -> None: ...   # agrega un LLMCallRecord
    def is_active(self) -> bool: ...          # True si está habilitado
    def write(self, output_dir: Path) -> Path: ...  # delega a DebugMarkdownRenderer

    @staticmethod
    def source_label(caller: object) -> str:
        """Resuelve 'ClassName (filename.py)' en runtime. Sin hardcoding."""
        import inspect
        from pathlib import Path
        return f"{type(caller).__name__} ({Path(inspect.getfile(type(caller))).name})"
```

Cada use-case llama `DebugCollector.source_label(self)` al construir el record — el nombre de clase y el archivo se resuelven desde el objeto en ejecución, no desde strings literales.

El collector tiene dos modos:
- **activo** (`debug=True`): almacena registros y escribe el archivo al final.
- **noop** (`debug=False`): todos los métodos son no-ops de costo cero (evita IFs en los use-cases).

La implementación noop se hace con una subclase `NullDebugCollector` que sobreescribe `record()` con `pass` e `is_active()` con `return False`. El `StoryRunner` instancia una u otra según el flag.

---

## 5. Flujo de inyección

```
CLI (--debug flag)
    │
    └─► commands.generate()
            │
            ├─► instancia DebugCollector(debug=True)  ← o NullDebugCollector
            │
            └─► StoryRunner(debug_collector=collector)
                    │
                    ├─► SynopsisBeatMapper(debug_collector=collector)
                    │       └─► collector.record(role="mapper", ...)
                    │
                    └─► VozUseCase(debug_collector=collector)  [por beat]
                            ├─► collector.record(role="voz", beat_number=N, ...)
                            └─► MemoryJournalist → collector.record(role="journal", beat_number=N, ...)
                    │
                    └─► collector.write(output_dir)  ← al finalizar run_full()
```

**Regla de inyección:** los use-cases reciben el collector como parámetro opcional con default `NullDebugCollector()`. Esto garantiza backwards compatibility y que los tests existentes no requieran cambios.

---

## 6. Estructura del archivo de salida

El archivo se llama `debug_prompts_responses_YYYYMMDDHHМM.md` y tiene las siguientes secciones:

```markdown
# Debug Session — NarrativeForge
**Generado:** 2026-04-19 14:32  
**Perfil activo:** ollama-mistral  
**Provider:** ollama  
**Duración total:** 127.4 s  
**Story ID:** nombre_20260419143200  

---

## Parámetros de la Historia

| Campo | Valor |
|---|---|
| Título | "El umbral" |
| Protagonista | "Marta Solano" |
| Sinopsis | "Una arqueóloga descubre..." |
| Atmósfera | "terror psicológico" |
| Relator | tercera_persona |

---

## Llamada 1 — MAPPER (Planificación)

### Componente
`SynopsisBeatMapper` — `synopsis_beat_mapper.py`

### Parámetros de Inferencia
| Param | Valor |
|---|---|
| model | mistral:latest |
| temperature | 0.3 |
| num_ctx | 4096 |
| num_predict | 800 |

### System Prompt
```
<contenido completo del system prompt>
```

### Prompt Enviado
```
<contenido completo del user prompt>
```

### Respuesta Raw
```
<respuesta literal del LLM sin ningún procesamiento>
```

### Respuesta Normalizada
```
<respuesta luego de ResponseNormalizer>
```

### Resultado del Parser
**Estado:** ok — 5 beats extraídos  
**Beats parseados:**
- Beat 1: "La llegada al yacimiento..."
- Beat 2: "El primer símbolo en la pared..."
- ...

### Timing
- Elapsed LLM: 8.23 s

---

## Llamada 2 — VOZ Beat #1

### Componente
`VozUseCase` — `voz_use_case.py`

### Parámetros de Inferencia
...

### Context Strategy aplicada
`beat_slice` — fragmento de sinopsis inyectado: "Una arqueóloga descubre..."

### Prompt Enviado
...

### Respuesta Raw
...

### Respuesta Normalizada
...

### Resultado del Parser
**Estado:** n/a (voz no usa parser)  
**Longitud:** 1243 chars

### Timing
- Elapsed LLM: 14.7 s

---

## Llamada 3 — JOURNAL Beat #1
...

---

## Resumen de Sesión

| Llamada | Rol | Componente | Beat | Modelo | Elapsed | Raw chars | Norm chars | Parser |
|---|---|---|---|---|---|---|---|---|
| 1 | mapper | SynopsisBeatMapper (synopsis_beat_mapper.py) | — | mistral:latest | 8.2s | 542 | 498 | ok: 5 beats |
| 2 | voz | VozUseCase (voz_use_case.py) | 1 | mistral:latest | 14.7s | 2341 | 1243 | n/a |
| 3 | journal | MemoryJournalist (memory_journalist.py) | 1 | mistral:latest | 6.1s | 387 | 312 | n/a |
...
| **TOTAL** | | | | **127.4s** | | | |
```

---

## 7. Implementación detallada por componente

### 7.1 `DebugCollector` (`src/application/services/debug_collector.py`)

```python
class DebugCollector:
    def __init__(self, active: bool = True):
        self._active = active
        self.records: list[LLMCallRecord] = []
        self._session_start = datetime.now()

    def record(self, *, role, beat_number, model, temperature, num_ctx,
               num_predict, system_prompt, user_prompt, raw_response,
               normalized_response, parser_result, elapsed_s): ...

    def is_active(self) -> bool:
        return self._active

    def write(self, output_dir: Path, story_meta: dict) -> Path:
        renderer = DebugMarkdownRenderer()
        return renderer.render(self.records, story_meta, output_dir, self._session_start)
```

`NullDebugCollector(DebugCollector)` — `__init__(active=False)`, `record()` es `pass`.

### 7.2 Modificaciones en `SynopsisBeatMapper.map()`

Después de `response = await self.llm.generate(...)` y después de `parse_beats(...)`:

```python
self.debug_collector.record(
    role="mapper",
    beat_number=None,
    source_component=DebugCollector.source_label(self),
    model=model,
    temperature=temperature,
    num_ctx=role_cfg.get("num_ctx"),
    num_predict=role_cfg.get("num_predict"),
    system_prompt=system_prompt,
    user_prompt=prompt,
    raw_response=response.text,
    normalized_response=clean_text,
    parser_result=f"ok: {len(beats)} beats" if beats else "error: 0 beats",
    elapsed_s=response.elapsed_s,
)
```

### 7.3 Modificaciones en `VozUseCase.execute()`

Después de la normalización:

```python
self.debug_collector.record(
    role="voz",
    beat_number=beat.number,
    source_component=DebugCollector.source_label(self),
    model=model,
    temperature=temp,
    num_ctx=role_cfg.get("num_ctx"),
    num_predict=role_cfg.get("num_predict"),
    system_prompt=system_prompt,
    user_prompt=prompt,
    raw_response=response.text,
    normalized_response=clean_text,
    parser_result="n/a",
    elapsed_s=response.elapsed_s,
)
```

### 7.4 Modificaciones en `MemoryJournalist.update_journal()`

Ídem, con `role="journal"` y `source_component=DebugCollector.source_label(self)`.

### 7.5 Modificaciones en `StoryRunner`

- Constructor recibe `debug_collector: DebugCollector | None = None`.
- Usa `self.debug_collector = debug_collector or NullDebugCollector()`.
- Pasa el collector a `SynopsisBeatMapper`, `VozUseCase`, y `MemoryJournalist`.
- Al final de `run_full()`, si `self.debug_collector.is_active()`, llama `self.debug_collector.write(self.output_dir, story_meta)`.

### 7.6 Modificaciones en `commands.generate()`

```python
def generate(..., debug: bool = False, ...):
    from src.application.services.debug_collector import DebugCollector, NullDebugCollector
    collector = DebugCollector() if debug else NullDebugCollector()
    runner = StoryRunner(..., debug_collector=collector)
    ...
```

### 7.7 Modificaciones en `runner.py`

```python
generate_parser.add_argument(
    "--debug",
    action="store_true",
    default=False,
    help="Genera debug_prompts_responses_YYYYMMDDHHМM.md con prompts y respuestas completas",
)
```

Y en el dispatch:

```python
commands.generate(..., debug=args.debug)
```

---

## 8. `DebugMarkdownRenderer` (`src/infrastructure/renderers/debug_renderer.py`)

Responsabilidades:
- Recibe `list[LLMCallRecord]`, `story_meta: dict`, `output_dir: Path`, `session_start: datetime`.
- Genera el nombre de archivo con `session_start.strftime("debug_prompts_responses_%Y%m%d%H%M.md")`.
- Escribe el archivo completo siguiendo la estructura de §6.
- Devuelve el `Path` del archivo escrito.

No tiene lógica de negocio — solo formateo. Usa f-strings o `str.join`. No depende de Jinja2 ni templates externos.

---

## 9. Tests

### `tests/unit/application/test_debug_collector.py`

| Test | Descripción |
|---|---|
| `test_null_collector_no_ops` | `NullDebugCollector.record()` no acumula nada, `is_active()` es False |
| `test_active_collector_accumulates` | 3 llamadas a `record()` → `len(records) == 3` |
| `test_record_fields_stored_correctly` | Un `LLMCallRecord` tiene todos los campos con valores correctos |
| `test_write_generates_file` | `collector.write(tmp_path, {})` crea el archivo con nombre correcto |
| `test_write_file_contains_raw_response` | El archivo incluye la respuesta raw exacta del record |
| `test_write_file_contains_parser_result` | El archivo incluye el resultado del parser |
| `test_summary_table_row_count` | La tabla resumen tiene tantas filas como records |

---

## 10. Success Criteria

| Criterio | Verificación |
|---|---|
| `--debug` genera archivo al final de `generate` | `ls output_stories/debug_prompts_responses_*.md` |
| Sin `--debug` no se genera archivo ni overhead apreciable | Ejecutar sin flag; `NullDebugCollector` es instanciado |
| El archivo contiene prompt raw completo para mapper | Buscar texto del sinopsis en el archivo de debug |
| El archivo contiene respuesta raw pre-normalizer para cada beat | Comparar con respuesta normalizada — deben diferir si hay thinking tags |
| El archivo contiene resultado del parser (cuántos beats) | `ok: 5 beats` en sección MAPPER |
| Tests pasan sin tocar tests existentes | `pytest tests/unit/ -v` sin fallos |
| Sin cambios en la signatura pública de VozUseCase/SynopsisBeatMapper para código que no pasa collector | Parámetro opcional con default `NullDebugCollector()` |

---

## 11. Boundaries

### Always Do
- `debug_collector` siempre es parámetro opcional con default `NullDebugCollector()` en todos los use-cases.
- Capturar `raw_response` **antes** de pasar por `ResponseNormalizer`.
- Capturar `normalized_response` **después** del normalizer y **antes** de persistir.
- Incluir `elapsed_s` de `response.elapsed_s` (ya disponible en `LLMResponse`).
- El `context_strategy` aplicado en VOZ debe registrarse en el record (campo `context_strategy: str`).

### Ask First
- Cambiar el nombre del archivo de salida o el directorio destino.
- Agregar campos nuevos a `LLMCallRecord` (puede impactar el renderer).

### Never Do
- Loggear el payload completo en `logger.debug` como sustituto — el log es texto plano no estructurado.
- Persistir los registros de debug en la DB (pertenecen a archivos de diagnóstico temporales).
- Interrumpir la generación si el collector falla al escribir (el write debe ser silencioso con `try/except`).

---

## 12. Diagrama de flujo (modificado)

```
CLI --debug
    │
    ▼
commands.generate(debug=True)
    │
    ├── DebugCollector()
    │
    └── StoryRunner(debug_collector=collector)
            │
            ├── SynopsisBeatMapper
            │       ├── llm.generate()        → raw_response
            │       ├── normalizer.normalize() → normalized_response
            │       ├── parse_beats()         → parser_result
            │       └── collector.record(role="mapper", ...)
            │
            └── [por cada beat]
                    ├── VozUseCase
                    │       ├── llm.generate()        → raw_response
                    │       ├── normalizer.normalize() → normalized_response
                    │       └── collector.record(role="voz", beat_number=N, ...)
                    │
                    └── MemoryJournalist
                            ├── llm.generate()        → raw_response
                            ├── normalizer.normalize() → normalized_response
                            └── collector.record(role="journal", beat_number=N, ...)

    └── collector.write(output_dir, story_meta)
            └── debug_prompts_responses_202604191432.md ✓
```

---

## 13. Notas de diagnóstico esperadas

Una vez generado el archivo con `ollama-mistral`, se espera poder confirmar o descartar estas hipótesis de falla:

1. **El prompt mapper no inyecta correctamente la sinopsis** → visible en `### Prompt Enviado` de la llamada 1.
2. **El modelo responde en formato libre ignorando la estructura de beats** → visible en `### Respuesta Raw` vs el formato esperado `## Beat N`.
3. **El normalizer elimina bloques completos de texto narrativo** → comparar `Raw chars` vs `Norm chars` en la tabla resumen; diferencias > 30% son sospechosas.
4. **El parser extrae 0 beats o beats mal formados** → `### Resultado del Parser` muestra `error:` o beats con summary vacío.
5. **El contexto de sinopsis en VOZ es demasiado completo** (`context_strategy: full`) forzando al modelo a anticipar el final → visible en `### Context Strategy aplicada`.
6. **El modelo local tiene num_ctx insuficiente** para el prompt completo → comparar longitud del prompt vs `num_ctx` en `### Parámetros de Inferencia`.

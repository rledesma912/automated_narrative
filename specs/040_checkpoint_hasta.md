# Spec 040 — Checkpoint `--hasta`: ejecución parcial del pipeline

**Estado:** ESPECIFICADO  
**Fecha:** 2026-04-21  
**Relacionado con:** Spec-038 (pipeline execute_full), Spec-035 (Director)

---

## Problema

El pipeline completo ejecuta 16 llamadas LLM sin posibilidad de detenerse antes. Para refinar
prompts durante integración, el flujo de trabajo actual fuerza a:

1. Copiar manualmente system_prompt + user_prompt del archivo debug.
2. Pegarlos en una herramienta externa (LM Studio, playground) con un modelo distinto.
3. Interpretar los resultados fuera de contexto.

Lo que se necesita: poder decir `--hasta analyst` o `--hasta voz:2` y que el pipeline se detenga
ahí, entregando el **archivo de debug con los prompts y respuestas de todo lo que sí se ejecutó**.
Ese archivo es la herramienta de inspección: contiene system_prompt, user_prompt, raw_response y
normalized_response de cada llamada LLM, ya en contexto real con el LLM activo.

---

## Los 16 checkpoints

| # | Nombre | Fase en pipeline |
|---|--------|-----------------|
| 1 | `analyst` | StoryAnalystService.extract_anchors() |
| 2 | `mapper:1` | SynopsisBeatMapper.map_one() — Beat 1 |
| 3 | `voz:1` | VozUseCase.narrate() — Beat 1 |
| 4 | `journal:1` | MemoryJournalist.extract() — Beat 1 |
| 5 | `mapper:2` | Beat 2 |
| 6 | `voz:2` | Beat 2 |
| 7 | `journal:2` | Beat 2 |
| 8 | `mapper:3` | Beat 3 |
| 9 | `voz:3` | Beat 3 |
| 10 | `journal:3` | Beat 3 |
| 11 | `mapper:4` | Beat 4 |
| 12 | `voz:4` | Beat 4 |
| 13 | `journal:4` | Beat 4 |
| 14 | `mapper:5` | Beat 5 |
| 15 | `voz:5` | Beat 5 |
| 16 | `journal:5` | Beat 5 (fin normal) |

---

## Interfaz de usuario

```bash
# Detener después del analyst (1 llamada LLM)
python -m src generate --input historia.md --debug --hasta analyst

# Detener después del mapper del beat 1 (2 llamadas LLM)
python -m src generate --input historia.md --debug --hasta mapper:1

# Detener después de narrar el beat 2 (6 llamadas LLM: analyst + 2×mapper + 2×voz)
python -m src generate --input historia.md --debug --hasta voz:2
```

**`--hasta` sin `--debug`:** válido — persiste el estado parcial en DB. Sin debug no hay archivo
de diagnóstico pero el pipeline se detiene igual. En la práctica el uso habitual será con `--debug`.

**Sin `--hasta`:** comportamiento idéntico al actual.

---

## Comportamiento al detenerse

1. El pipeline ejecuta todas las llamadas LLM hasta el checkpoint inclusive.
2. Los beats completados (mapper + voz + journal) se persisten en DB como `status='completed'`.
3. Los beats parciales (solo mapper, o mapper + voz) se persisten con los campos disponibles y
   `status='pending'` — el contenido parcial es visible para debug.
4. **El archivo de debug se escribe siempre**, incluso en parada anticipada. Esto es el
   comportamiento crítico del spec: la lógica de escritura del debug en `run_full()` ya está
   después del `async for`, por lo que se ejecuta naturalmente al terminar el generador.
5. El CLI imprime al terminar:
   ```
   [PAUSA] Pipeline detenido en 'mapper:1' (2/16 llamadas LLM).
   Story ID: <id>
   Debug: output_stories/debug_<titulo>_<ts>.md
   ```

---

## Validación del parámetro `--hasta`

Si el valor no es reconocible, el sistema debe fallar **antes de hacer cualquier llamada LLM**,
listando los valores válidos:

```
Error: checkpoint inválido 'foo'. Valores válidos:
  analyst
  mapper:1 .. mapper:5
  voz:1 .. voz:5
  journal:1 .. journal:5
```

---

## Diseño de implementación

### Archivo nuevo: `src/application/services/checkpoint.py`

Módulo pequeño y autocontenido. Sin dependencias del dominio.

```python
# Responsabilidades:
# 1. VALID_CHECKPOINTS: dict[str, int]  — nombre → ordinal (1..16)
# 2. validate(s) → None | raises ValueError con mensaje descriptivo
# 3. reached(name: str, ordinal: int, target: int) → bool
```

`VALID_CHECKPOINTS`:
```python
{
  "analyst": 1,
  "mapper:1": 2, "voz:1": 3,  "journal:1": 4,
  "mapper:2": 5, "voz:2": 6,  "journal:2": 7,
  "mapper:3": 8, "voz:3": 9,  "journal:3": 10,
  "mapper:4": 11,"voz:4": 12, "journal:4": 13,
  "mapper:5": 14,"voz:5": 15, "journal:5": 16,
}
```

### `DirectorUseCase.execute_full()` — `src/application/use_cases/director_use_case.py`

Agrega parámetro `stop_after: str | None = None`.

Lógica de corte con `stop_at: int | None = VALID_CHECKPOINTS.get(stop_after)`:

```
analyst call          → if stop_at == 1: return
for beat_id in 1..5:
  mapper call         → if stop_at == ordinal("mapper", beat_id): yield parcial; return
  build_nc (sin LLM)
  voz call            → if stop_at == ordinal("voz",    beat_id): yield parcial; return
  journal call
  yield completo
  if stop_at == ordinal("journal", beat_id): return  ← cierra el generator limpiamente
```

**Beat parcial**: cuando se corta después de mapper o voz, el beat tiene `summary` pero no
`content` (o tiene `content` pero no `memory_snapshot`). Se hace yield de ese beat parcial con
lo disponible para que `run_full()` lo persista — útil para inspección en DB.

### `StoryRunner.run_full()` — `src/core/orchestrator.py`

Agrega `stop_after: str | None = None`. Lo pasa a `director.execute_full()`.
Valida con `checkpoint.validate(stop_after)` al inicio (antes de crear la historia en DB).
Imprime el mensaje de pausa si `stop_after` está seteado.

### `commands.generate()` — `src/cli/commands.py`

Agrega `hasta: str | None = None` como parámetro. Lo pasa a `runner.run_full()`.

### Typer/Click entry point — `src/__main__.py`

Agrega `--hasta` como `Option` opcional al comando `generate`.

---

## Garantía del archivo de debug

El archivo de debug se escribe en `run_full()` después del `async for`:

```python
async for beat, journal, llm_elapsed in director.execute_full(..., stop_after=stop_after):
    ...  # persiste cada beat

# Aquí se escribe el debug — se ejecuta siempre, incluso si el generator terminó antes
if self.debug_collector.is_active():
    debug_path = self.debug_collector.write(self.output_dir, story_meta)
```

No se necesita ningún cambio en `DebugCollector` ni en `DebugMarkdownRenderer`: registran
cada llamada LLM al momento de ocurrir, y al final escriben todo lo acumulado.

---

## Labels de fase para el log de terminal

Cada llamada LLM tiene un label canónico para mostrar en consola. Se define en `checkpoint.py`
junto con el mapa de ordinals — misma fuente de verdad.

| Checkpoint | Label en terminal |
|---|---|
| `analyst` | `🔍  Analyst          — Extrayendo anclajes` |
| `mapper:N` | `🗺   Mapper  · Beat N — Mapeando acto N` |
| `voz:N` | `✍️   Voz     · Beat N — Narrando acto N` |
| `journal:N` | `📓  Journal · Beat N — Registrando memoria` |

`ProgressReporter` usará estos labels en el método `phase_start(checkpoint: str)` para imprimir
una línea de progreso al inicio de cada llamada LLM — independiente del checkpoint `--hasta`.
Este método se agrega en este spec pero los callers (DirectorUseCase) lo invocan en el
pipeline normal también, no solo en modo `--hasta`.

---

## Cambio: `config_summary` → muestra perfil activo

### Problema actual

```
📐  Modelo: qwen2.5:14b  |  Director: 0.4  |  Voz: 0.6  |  Journal: 0.3
```

Muestra datos de bajo nivel que requieren conocer el YAML para interpretar. El usuario necesita
saber **con qué perfil está corriendo**, no los hiperparámetros individuales.

### Solución

```
📐  Perfil: ollama-qwen25-14b
```

**`ProgressReporter.config_summary()`** — simplificar firma:
```python
# Antes:
def config_summary(self, model: str, director_t: float, voz_t: float, journal_t: float)

# Después:
def config_summary(self, profile: str)
```

**`SilentReporter.config_summary()`** — misma firma simplificada.

**`commands._generate_async()`** — el caller pasa `settings.active_profile_name`:
```python
# Antes:
reporter.config_summary(
    model=settings.llm_model,
    director_t=settings.director_temperature,
    voz_t=settings.voz_temperature,
    journal_t=settings.state_extractor_temperature,
)

# Después:
reporter.config_summary(profile=settings.active_profile_name)
```

---

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `src/application/services/checkpoint.py` | **nuevo** — validación, mapa ordinals y labels de fase |
| `src/application/use_cases/director_use_case.py` | `execute_full()` acepta `stop_after` |
| `src/core/orchestrator.py` | `run_full()` acepta y propaga `stop_after`, imprime mensaje de pausa |
| `src/cli/commands.py` | `generate()` acepta `hasta`; pasa `profile` a `config_summary` |
| `src/__main__.py` | opción `--hasta` en el comando Typer |
| `src/cli/progress.py` | `config_summary(profile)`, nuevo método `phase_start(checkpoint)` |

---

## Tests

`tests/unit/application/test_checkpoint.py` — módulo nuevo:
- `test_validate_valid_names()` — todos los 16 nombres pasan sin excepción.
- `test_validate_invalid_raises()` — `'foo'`, `'mapper:9'`, `''` lanzan `ValueError`.
- `test_analyst_stops_after_one_call()` — `execute_full` con `stop_after="analyst"` hace exactamente 1 llamada LLM (el analyst).
- `test_mapper1_stops_after_two_calls()` — `stop_after="mapper:1"` hace 2 llamadas.
- `test_voz2_stops_after_six_calls()` — `stop_after="voz:2"` hace 6 llamadas (1 analyst + 2 mapper + 2 voz + 1 = 6... espera, analyst=1, mapper:1=1, voz:1=1, journal:1=1, mapper:2=1, voz:2=1 → 6 llamadas).
- `test_no_hasta_runs_full_pipeline()` — sin `stop_after` hace 16 llamadas.
- `test_partial_beat_yielded_on_mapper_stop()` — el beat parcial (solo summary) se yieldea.

---

## Criterios de aceptación

- `--hasta analyst` → 1 llamada LLM, DB tiene la historia creada + `narrative_anchors`, debug contiene 1 entrada.
- `--hasta mapper:1` → 2 llamadas LLM, debug contiene 2 entradas (analyst + mapper).
- `--hasta voz:3` → 10 llamadas LLM, beats 1-2 `status=completed`, beat 3 `status=pending` con `content` populado.
- Sin `--hasta` → comportamiento idéntico al actual (sin regresiones).
- `--hasta foo` → error antes de cualquier llamada LLM, mensaje con valores válidos.
- `--hasta mapper:1` sin `--debug` → pipeline se detiene igual, sin error, sin archivo debug.

---

## Fuera de alcance

- Resume automático desde checkpoint (spec futuro).
- `--hasta` en los comandos `plan` y `narrate` (solo aplica a `generate`).
- Interfaz API REST (solo CLI en este spec).

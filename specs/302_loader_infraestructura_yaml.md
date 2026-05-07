# Spec-302: Fix — CLI `generate --input <yaml>` persiste historia con campos vacíos

## Metadata

| Campo | Valor |
|-------|-------|
| **Status** | Draft |
| **Tipo** | Bugfix (regresión de specs 222/230/300/301) |
| **Slice base** | S0 |
| **Fecha** | 2026-05-05 |
| **Owner** | Backend / CLI |
| **Spec relacionado** | 217 (export-yaml — round-trip), 300, 301 |

---

## 1. Objetivo

Restaurar el flujo `uv run python -m src generate --input input_stories/<archivo>.yaml`
de modo que la historia persistida en `stories.db` quede **completa y consistente** con
el YAML de entrada (round-trip con `export-yaml`), corrigiendo la regresión introducida
durante los specs 222/230/300/301.

---

## 2. Contexto y Motivación

### Estado actual (bug confirmado)

Al ejecutar:

```bash
uv run python -m src generate --input input_stories/el_monte_prohibido.yaml
```

el pipeline corre hasta el final pero la fila `story` en SQLite queda con **todos los
campos string vacíos** (`title=''`, `protagonista=''`, `relator=''`, `sinopsis=''`,
`atmosfera=''`, `narrative_brief=''`, `storyteller_config=NULL`, `personajes='[]'`),
aunque su `status` queda marcada como `completed`.

Verificación realizada (última row, 2026-05-05):

```text
id          : 165f11fc-6a53-4522-baa2-00d61d39f39a
title       : ''
protagonista: ''
relator     : ''
sinopsis    : ''
atmosfera   : ''
status      : 'completed'
```

### Causa raíz

1. `src/cli/runner.py` (líneas 144–158) acepta `--input` y reenvía a
   `commands.generate(title="", protagonista="", ..., input_file=args.input, ...)`.
2. `src/cli/commands.py::generate()` declara `input_file: str | None = None` en su
   firma pero **nunca lo lee**: el archivo YAML no se abre, no se parsea, no se
   desempaca en los campos del DTO.
3. Los strings vacíos viajan a `_generate_async()` → `StoryRunner.run_full()` →
   `CreateStoryUseCase.execute(dto)` y se persisten tal cual.
4. El comando inverso (`export-yaml`, Spec-217) sí existe
   (`src/infrastructure/exporters/yaml_exporter.py::YamlStoryExporter`), pero su
   contraparte de **import** nunca se completó o quedó huérfana después de las
   refactorizaciones del Spec-300 (`GeneratedNarrative`) y Spec-301 (limpieza
   markdown).

### Impacto

- Imposible generar historias desde YAML (flujo principal documentado en CLAUDE.md
  y referido por la propia ayuda del flag: `--input <archivo>`).
- La generación produce beats narrados sobre **una historia vacía**: el LLM recibe
  protagonista/sinopsis/atmósfera vacíos, contaminando la salida y los embeddings
  de los beats.
- Las dos historias creadas hoy quedan basura en la BD y deben recrearse tras el
  fix.

### Por qué se introdujo

Los specs 222 (journal relacional), 230 (lifecycle) y especialmente 300/301
reorganizaron entry-points y eliminaron código (`export_service`,
`markdown_renderer`, `markdown_parser`). El loader de YAML para `--input` no
estaba aún implementado en una clase explícita — vivía probablemente como código
inline en `commands.generate()` junto con la lógica markdown — y se eliminó como
parte de la limpieza, pero el parámetro `input_file` quedó en la firma sin uso.

---

## 3. Scope

### In Scope

- Implementar un **YamlStoryLoader** (clase de infrastructure) que lea un
  archivo YAML del directorio `input_stories/` y devuelva un `StoryCreateDTO`
  válido.
- Cablear el loader en `src/cli/commands.py::_generate_async()` cuando
  `input_file` está presente.
- Validación de campos obligatorios del YAML (`title`, `sinopsis`,
  `atmosfera`, etc.) con error claro si falta alguno.
- Defensa en profundidad: `Field(min_length=1)` en `Story` y
  `StoryCreateDTO` para campos obligatorios.
- Tests de costura entre CLI y orquestador (no e2e con subprocess).
- Tests unitarios del loader contra los YAML reales en `input_stories/`
  (`el_monte_prohibido.yaml`, `la_ofrenda.yaml`).
- Test de round-trip: `export-yaml story_id` → re-importar con `--input`
  produce DTO equivalente.
- Sincronización de los tres diagramas de
  `docs/estandar_diseno_architectural.md` (ERD, colaboración, secuencia)
  y eliminación del archivo duplicado `estandar_diseno_arquitectural.md`
  tras fusionar su contenido único.

### Out of Scope

- Modificar el formato del YAML canónico (lo define Spec-217, sigue siendo el
  contrato).
- Tocar `YamlStoryExporter` (sólo se consume como referencia del formato).
- Refactorizar `runner.py` o `commands.py` más allá del cableado mínimo.
- Otros bugs introducidos por specs 222/230/300/301 (van en specs separados).

---

## 4. Diseño

### 4.1 Nueva clase `YamlStoryLoader`

Ubicación: `src/infrastructure/loaders/yaml_loader.py` (módulo nuevo).

```python
class YamlStoryLoader:
    """Lee un YAML canónico (Spec-217) y produce un StoryCreateDTO.

    Inverso simétrico de YamlStoryExporter. Sin LLM, sin I/O de DB.
    """

    def load_from_file(self, path: Path) -> StoryCreateDTO: ...
    def load_from_dict(self, data: dict) -> StoryCreateDTO: ...
```

Responsabilidades:

- Resolver el path: si `path` no es absoluto, resolver contra
  `settings.input_dir` (`input_stories/`).
- Validar que existe y es legible. Error explícito si no.
- Parsear con `yaml.safe_load`.
- Validar campos obligatorios. Mínimos: `title`, `sinopsis`, `atmosfera`,
  `protagonista`. Opcionales con defaults: `relator`, `escenarios`, `reglas`,
  `personajes_full`, `storyteller_config`.
- Mapear las claves YAML al DTO:

| YAML key | DTO field | Conversión |
|---|---|---|
| `title` | `title` | passthrough (obligatorio) |
| `protagonista` | `protagonista` | passthrough (obligatorio) |
| `relator` | `relator` | passthrough; default `"tercera_persona"` |
| `atmosfera` | `atmosfera` | passthrough (obligatorio) |
| `sinopsis` | `sinopsis` | passthrough (obligatorio) |
| `storyteller_config.scenarios` | `escenarios: list[str]` | `[s["name"] for s in scenarios]` — **no usar el string top-level** |
| `reglas` (list[str]) | `reglas` | passthrough; default `[]` |
| `personajes_full` (list[dict]) | `personajes_full` | passthrough; default `[]` |
| `storyteller_config` (dict) | `storyteller_config` | passthrough completo; default `None` |
| `storyteller_config.rules` (list[{id, text, type}]) | `typed_rules: list[dict]` | **renombrar `text → content`** por dict |

**Decisiones de mapeo (verificadas contra YAML reales y exporter):**

1. **`escenarios` top-level es derivado, no fuente.** El YAML canónico
   tiene un string `'Casa: desc; Otra: desc'` en la raíz, pero la
   verdad estructural vive en `storyteller_config.scenarios` (lista
   de dicts con `id/order/name/description`). El loader **ignora** el
   string top-level y construye `dto.escenarios` desde
   `storyteller_config.scenarios[].name`. Confirmado en
   `YamlStoryExporter._derive_escenarios_str` (línea 84–95).

2. **Renombrado `text → content` para typed_rules.** El exporter
   escribe `{id, text, type}` (línea 180), pero
   `CreateStoryUseCase.execute()` lee `r.get("content", "")` (línea
   43). Sin esta conversión, el round-trip persiste reglas con
   `content=""`. El loader debe construir cada dict de
   `typed_rules` como
   `{"id": r["id"], "content": r.get("text") or r.get("content", ""),
   "type": r.get("type")}`.

### 4.2 Cableado en `commands.py`

Modificar `_generate_async()` para detectar `input_file` y delegar al loader
**antes** de instanciar el container:

```python
async def _generate_async(..., input_file: str | None = None, ...):
    await _init_database()

    if input_file:
        from src.infrastructure.loaders import YamlStoryLoader
        loader = YamlStoryLoader()
        dto = loader.load_from_file(Path(input_file))
        title = dto.title
        protagonista = dto.protagonista
        relator = dto.relator
        escenarios = dto.escenarios
        sinopsis = dto.sinopsis
        atmosfera = dto.atmosfera
        reglas = dto.reglas
        storyteller_config = dto.storyteller_config
        typed_rules = dto.typed_rules
        personajes_full = dto.personajes_full

    container = CLIContainer(...)
    runner = container.story_runner(output_dir)
    story = await runner.run_full(title=title, protagonista=protagonista, ...)
```

`generate()` (síncrona) debe propagar `input_file` a `_generate_async()` —
hoy no lo hace (bug secundario en la línea 77–95 de `commands.py`).

### 4.3 Reglas

- **No tocar** `runner.run_full` ni `CreateStoryUseCase`: el contrato sigue
  igual, sólo cambia la fuente de los argumentos.
- El loader vive en infrastructure (parsea YAML, file I/O); commands.py es
  presentation/CLI y sólo orquesta.
- Validación dura: si falta `title` o `sinopsis` el loader lanza
  `ValidationError` con el campo faltante. El runner CLI traduce esto a
  `sys.exit(1)` con mensaje claro.

### 4.4 Defensa en profundidad: validación en la entidad de dominio

El bug se coló silenciosamente porque `Story` y `StoryCreateDTO` aceptan
strings vacíos en campos obligatorios. Si Pydantic los rechazara en el
constructor, el bug habría explotado en `CreateStoryUseCase` con un
`ValidationError` ruidoso, antes de tocar la BD.

Cambios:

```python
# src/domain/models.py
class Story(BaseModel):
    title: str = Field(..., min_length=1)
    protagonista: str = Field(..., min_length=1)
    relator: str = Field(..., min_length=1)
    sinopsis: str = Field(..., min_length=1)
    atmosfera: str = Field(..., min_length=1)
    ...

# src/application/dto/story_dto.py — mismo patrón
```

Equivalente con `@field_validator` si se quiere normalizar (`.strip()`)
antes de comparar — preferido si hay datos legacy con whitespace.

**Convención:** sólo los campos que en el dominio tienen sentido como
no-vacíos llevan `min_length=1`. `escenarios`, `reglas`,
`personajes_full`, `narrative_brief` y `storyteller_config` quedan como
están (admiten lista/dict vacíos).

### 4.4.1 Decisiones tomadas (consultas previas a IMPLEMENT)

Resueltas tras inspección directa de código y YAML reales — quedan
apuntadas para que IMPLEMENT no se desvíe ni reabra discusiones:

| # | Pregunta | Decisión | Evidencia |
|---|---|---|---|
| Q1 | Formato de `escenarios` en YAML — ¿string con `;` o lista? | **String con `;`** en YAML, pero el loader lo ignora y usa `storyteller_config.scenarios` (la lista rica) como fuente de verdad. | `el_monte_prohibido.yaml:44`; `la_ofrenda.yaml:21`; `yaml_exporter.py:84-95` |
| Q2 | ¿`StoryRunner.run_full` acepta DTO? | **No.** Acepta 11 params individuales y construye el DTO internamente. Para este spec **no se cambia su firma**. El loader devuelve DTO; `_generate_async` lo desempaca en kwargs. Refactor a `run_full_from_dto(dto)` queda fuera de scope, candidato a futuro spec de limpieza. | `core/orchestrator.py:45-95` |
| Q3 | ¿Todos los campos del DTO existen y se mapean limpio? | **Sí**, con dos matices: (a) `escenarios` viene de `storyteller_config.scenarios`, no del top-level; (b) `typed_rules` requiere renombrar `text → content` (el exporter escribe `text`, el use case lee `content`). | `dto/story_dto.py:8-20`; `create_story.py:43`; `yaml_exporter.py:180` |
| Q4 | ¿`min_length=1` rompe fixtures existentes? | **No, blast radius = 0.** `grep -rn 'title=""'` (idem para los 5 campos) sobre `tests/` devuelve 0 hits. Los 11 hits de `=""` están en `MockLLMAdapter.fixed_response` y campos de `NarrativeJournal`, no en `Story`/`StoryCreateDTO`. S1-T4 queda como red de seguridad pero probablemente sea no-op. | grep en `tests/` |

Detalle adicional detectado pero **fuera de scope**: `Story` no
tiene campo `escenarios` en `models.py:173`; algunos tests le pasan
`escenarios="Location"` por costumbre y Pydantic los descarta
silenciosamente (default `extra="ignore"`). Esos tests pasan por
accidente. No requiere acción acá; candidato a spec separado de
limpieza de fixtures.

### 4.5 Filosofía de tests: costura entre capas, no e2e

No se persigue cobertura e2e con `subprocess` (lento, frágil, prueba
demasiado). El bug vive **en las costuras** entre tres componentes:

```
argparse  ─[1]─→  commands.generate  ─[2]─→  _generate_async / loader  ─[3]─→  StoryRunner.run_full
```

El bug se manifestó en la costura **[2]**: `generate()` no propaga
`input_file` y `_generate_async()` ni siquiera lo recibe. Los tests
correctos son contratos en cada costura, con doubles del lado del
componente vecino:

| Costura | Test | Double |
|---|---|---|
| [1] argparse → handler | runner.main(["generate","--input",X]) llama a `commands.generate(input_file=X, ...)` con los kwargs esperados | spy/mock sobre `commands.generate` |
| [2] handler → orquestador | `_generate_async(input_file=X)` termina invocando `StoryRunner.run_full(title=NO_VACÍO, sinopsis=NO_VACÍA, ...)` con los datos del YAML | mock de `StoryRunner.run_full`; loader real; YAML temp |
| [3] loader puro | `YamlStoryLoader.load_from_file(X)` → DTO completo | sin doubles, lectura de YAML real (`input_stories/*.yaml`) |

Cualquiera de los tres habría matado el bug por sí solo. Combinados:
imposible reintroducirlo sin que rompan tests rápidos (<1s cada uno).

---

## 5. Slices

> **Orden quirúrgico — racional.** La validación de dominio (S1) va
> *primero* para que cualquier slice posterior trabaje sobre una entidad
> `Story` que ya rechaza strings vacíos. Si el loader (S2) tuviera un
> bug pasando un campo en blanco, Pydantic explotaría dentro del test
> del loader, no se filtraría al wire-up. La defensa en profundidad
> está activa **durante** el fix, no sólo al final.

### Slice S0 — Reproducción y baseline (no-code)

- [ ] S0-T1: Borrar `data/stories.db` y recrear con `./scripts/bash/init_db.sh`
  (recordar memoria: no migrar, recrear).
- [ ] S0-T2: Confirmar que el comando falla del modo descrito ejecutando
  `uv run python -m src generate --input input_stories/la_ofrenda.yaml` con
  `--mock`, y validando con SELECT que la fila queda vacía.
- [ ] S0-T3: Snapshot del estado pre-fix:
  - `pytest tests -v` → registrar tests verdes/rojos actuales (algunos
    pueden estar rojos por `MarkdownStoryParser` eliminado).
  - Anotar el set de tests verdes como **baseline**: ningún slice
    posterior puede dejarlos rojos.

### Slice S1 — Validación en la entidad de dominio (defensa en profundidad)

**Por qué primero:** activa Pydantic como red de seguridad para todo lo
que viene después. Cualquier `Story(title="")` o
`StoryCreateDTO(sinopsis="")` —incluyendo los que aún no escribimos—
explotará con `ValidationError` ruidoso.

- [ ] S1-T1: Agregar `Field(..., min_length=1)` (o `@field_validator`
  con `.strip()`) a `Story` (`src/domain/models.py`) en: `title`,
  `protagonista`, `relator`, `sinopsis`, `atmosfera`.
- [ ] S1-T2: Mismo patrón en `StoryCreateDTO`
  (`src/application/dto/story_dto.py`).
- [ ] S1-T3: Tests en `tests/unit/domain/test_story_validation.py`:
  - `Story(title="", ...)` lanza `pydantic.ValidationError`.
  - `Story(title="   ", ...)` lanza `ValidationError` (sólo si se
    elige el camino `@field_validator` + `.strip()`).
  - `StoryCreateDTO(title="", sinopsis="...", ...)` también lanza.
  - Crear con todos los campos válidos no lanza.
- [ ] S1-T4: Reparar fixtures rotas. Estrategia:
  1. Correr `pytest tests/unit/ -v --tb=line`.
  2. Para cada falla con `ValidationError` en `Story` o
     `StoryCreateDTO`, completar la fixture con valores no vacíos
     (placeholders semánticamente neutrales: `title="t"`,
     `protagonista="p"`, etc.).
  3. **No** aflojar la validación para acomodar fixtures legacy.
- [ ] S1-T5: `pytest tests/unit/ -v` verde. Suite completa
  (`pytest tests -v`) **al menos** en el mismo estado que el baseline
  de S0-T3 (no peor).

### Slice S2 — YamlStoryLoader + tests unitarios

- [ ] S2-T1: Crear `src/infrastructure/loaders/__init__.py` y
  `src/infrastructure/loaders/yaml_loader.py` con `YamlStoryLoader`
  según diseño §4.1. Implementación específica:
  - **Escenarios:** ignorar el string top-level `escenarios`; leer
    `storyteller_config.scenarios` y construir
    `dto.escenarios = [s["name"] for s in scenarios]`. Si
    `storyteller_config` o `storyteller_config.scenarios` faltan,
    `dto.escenarios = []`.
  - **Typed rules:** mapear cada `r` de
    `storyteller_config.rules` a
    `{"id": r["id"], "content": r.get("text") or r.get("content", ""),
    "type": r.get("type")}`. La preferencia es `text` (formato canónico
    Spec-217) con fallback a `content` por compatibilidad.
  - **Storyteller config:** passthrough completo del dict del YAML;
    `dto.storyteller_config = data.get("storyteller_config")`.
  - **Personajes:** passthrough de la lista
    `data.get("personajes_full", [])`.
  - **Reglas planas:** passthrough de `data.get("reglas", [])` —
    convive con `typed_rules`.
- [ ] S2-T2: Tests en `tests/unit/infrastructure/test_yaml_loader.py`.
  Aprovechando que Pydantic ya bloquea strings vacíos (S1), los tests
  se simplifican:
  - Carga de `el_monte_prohibido.yaml` produce DTO con todos los
    campos esperados.
  - Carga de `la_ofrenda.yaml` produce DTO válido.
  - **Test específico Q1:** `dto.escenarios` tiene 4 elementos
    (`Casa de María`, `Estancia de la fiesta`, `Monte de los
    Espinillos`, `Casa de María (regreso)`), tomados de
    `storyteller_config.scenarios[].name`, NO del split del string
    top-level.
  - **Test específico Q3:** cada item de `dto.typed_rules` tiene
    clave `content` (no `text`) con el contenido de la regla.
  - YAML que omite `title` → el DTO no se construye, sale
    `ValidationError` (Pydantic, no validación manual del loader).
  - YAML con `title: ""` o `title: "   "` → idem.
  - Path inexistente → `FileNotFoundError` envuelto en
    `ValidationError` con mensaje claro del path.
  - YAML mal formado (`yaml.YAMLError`) → envuelto en
    `ValidationError`.
- [ ] S2-T3: `pytest tests/unit/infrastructure/test_yaml_loader.py -v`
  verde.

### Slice S3 — Cableado en CLI

- [ ] S3-T1: Pasar `input_file` desde `generate()` a
  `_generate_async()` en `src/cli/commands.py` (bug secundario:
  hoy la firma lo recibe pero no lo reenvía).
- [ ] S3-T2: En `_generate_async()`, si `input_file` está, cargar DTO
  con `YamlStoryLoader` y sobrescribir variables locales antes de
  `runner.run_full(...)`.
- [ ] S3-T3: Captura de `ValidationError` en `src/cli/runner.py`
  (try/except alrededor del despacho) con mensaje amigable y
  `sys.exit(1)`. No filtrar el traceback Pydantic crudo al usuario.

### Slice S4 — Tests de costura (CLI ↔ orquestador)

Tres tests rápidos, cada uno aislando una costura. Filosofía: ver §4.5.

- [ ] S4-T1: `tests/unit/cli/test_runner_argparse.py` — costura [1]:
  - Patch `src.cli.commands.generate` con un `Mock`.
  - Llamar `runner.main()` con `sys.argv = ["narrative", "generate",
    "--input", "input_stories/la_ofrenda.yaml", "--mock"]`.
  - Assert: `commands.generate.assert_called_once()` con
    `kwargs["input_file"] == "input_stories/la_ofrenda.yaml"` y
    `kwargs["use_mock"] is True`.
  - Test paralelo con `--story-id` y con args explícitos para
    verificar que las otras ramas del `if/elif/else` siguen
    funcionando (regresión sobre el cableado completo de argparse).

- [ ] S4-T2: `tests/unit/cli/test_commands_generate_input.py` —
  costura [2]:
  - Crear YAML temp con `tmp_path` (campos completos mínimos).
  - Patch `src.core.orchestrator.StoryRunner.run_full` con
    `AsyncMock` que devuelve un `Story` válido.
  - Patch también `src.cli.commands.init_db` y
    `container.story_repo.update_status` (no interesa la BD aquí).
  - Llamar `await _generate_async(title="", ...,
    input_file=str(tmp_yaml))`.
  - Assert positivo: `run_full.assert_called_once()` con `title`,
    `protagonista`, `sinopsis`, `atmosfera`, `relator` **no vacíos**
    y coincidentes con el YAML.
  - Assert defensivo: `init_db.assert_called_once()` —protege contra
    refactorizaciones futuras que muevan o eliminen `init_db` y
    rompan silenciosamente la inicialización.
  - Variante negativa: si el YAML carece de `title`,
    `_generate_async` debe propagar `ValidationError` **antes** de
    tocar `run_full` (assert `run_full.assert_not_called()`).

- [ ] S4-T3: Reparar o eliminar
  `tests/integration/test_slice8_e2e_monte.py`:
  - Importa `MarkdownStoryParser` (eliminado en Spec-301).
  - Opción A (preferida): reescribir con `YamlStoryLoader` ya
    disponible tras S2.
  - Opción B: eliminar el archivo si la cobertura queda cubierta por
    los tests de costura + el loader unit.

### Slice S5 — Verificación manual y limpieza

- [ ] S5-T1: Borrar y recrear `stories.db`
  (`./scripts/bash/db_clean.sh && ./scripts/bash/init_db.sh`).
- [ ] S5-T2:
  `uv run python -m src generate --input input_stories/el_monte_prohibido.yaml --mock`
  termina con exit-code 0.
- [ ] S5-T3: SELECT sobre `story`: `title`, `protagonista`,
  `sinopsis`, `atmosfera`, `relator`, `personajes`,
  `storyteller_config` no vacíos y coinciden con el YAML. 4 filas en
  `scenario`, 1 en `narrative_anchors`, 5 en `macro_beat`.
- [ ] S5-T4: `ruff check . && ruff format .` verde.
- [ ] S5-T5: `pytest tests -v` verde y al menos el baseline de S0-T3.
- [ ] S5-T6 (opcional): Round-trip `export-yaml <id>` →
  `generate --input <export>` → DTO equivalente.

### Slice S6 — Sincronización de documentación arquitectural

**Objetivo:** Que `docs/estandar_diseno_architectural.md` refleje el
estado real del código *después* de S0–S5 (loader nuevo, validación de
dominio endurecida, repos completos del Spec-300, etc.). Trabajo de
documentación puro: sin código de producción, sin tests adicionales.

**Pre-requisito:** S0–S5 cerrados. Los diagramas se generan contra la
verdad del código en `main`/branch ya verificado.

- [ ] S6-T1: Reemplazar el bloque mermaid del **ERD (§4)** con uno
  completo y verificado contra la DB real:
  - Entidades: `STORY`, `MACRO_BEAT`, `NARRATIVE_ANCHORS`,
    `NARRATIVE_JOURNAL`, `SCENARIO`, `RULE`, `MACRO_BEAT_RULE`,
    `GENERATED_NARRATIVE` (8 totales).
  - Cardinalidades correctas:
    - `STORY ||--o{ MACRO_BEAT`
    - `STORY ||--|| NARRATIVE_ANCHORS`
    - `STORY ||--o{ NARRATIVE_JOURNAL` *(antes 1..1, corregir a 1..N
      por `beat_number`)*
    - `STORY ||--o{ SCENARIO`
    - `STORY ||--o{ RULE`
    - `STORY ||--o{ GENERATED_NARRATIVE` *(novedad Spec-300)*
    - `MACRO_BEAT }o--|| SCENARIO` *(FK active_scenario_id)*
    - `MACRO_BEAT }o--o{ RULE` *(vía MACRO_BEAT_RULE)*
  - Campos clave por entidad (FK explícitas; los campos completos los
    domina `PRAGMA table_info`).
  - **Validación:** cada FK del diagrama debe existir en
    `PRAGMA foreign_key_list(<tabla>)`.

- [ ] S6-T2: Reemplazar el bloque mermaid del **diagrama de
  colaboración entre clases (§2)** con uno agrupado por capa
  (`subgraph Presentation`, `Application`, `Infrastructure`,
  `Domain`) que incluya los nodos faltantes:
  - `CreateStoryUseCase`, `GenerateNarrativesUseCase`
  - `YamlStoryLoader` *(nuevo, Spec-302)*
  - `CLIContainer` *(Spec-250)* como inyector
  - `PromptBuilder`, `ResponseNormalizer`, `NarrativeAuditor`
  - Repos concretos: `SQLStoryRepository`, `SQLBeatRepository`,
    `SQLGeneratedNarrativeRepository`
  - FastAPI (`presentation/routers/{story,beat,narrative,stream}_router.py`)
    como entry-point paralelo a la CLI
  - Arco `MemoryJournalist → narrative_journal` (vía repo)
  - **Validación:** cada nodo del diagrama debe existir como archivo
    real bajo `src/` (`grep -r "class <NodeName>"`).

- [ ] S6-T3: Reemplazar el bloque mermaid del **diagrama de
  secuencia (§3)** con la cadena completa de **17 llamadas LLM**
  (consistente con CLAUDE.md):
  - `Analyst.extract_anchors()` (1 LLM)
  - `RuleScenarioResolverService.resolve_distribution()` (1 LLM)
  - Loop 1..5: `Mapper.map_one()` (1) +
    `PromptBuilder.build_narrative_context()` (sin LLM) +
    `Voz.narrate()` (1) + `Journalist.extract()` (1) =
    3 LLM × 5 beats = 15.
  - Total = 1 + 1 + 15 = **17**.
  - **Validación:** contar mensajes con flecha `->>LLM` en el bloque
    mermaid; debe sumar 17.

- [ ] S6-T4: Fusionar y eliminar duplicado
  `docs/estandar_diseno_arquitectural.md` (con "q"):
  - **Pre-check de referencias** (antes de tocar nada):
    `grep -rn "estandar_diseno_arquitectural" . --include="*.md"
    --include="*.py" --include="*.txt" --include="*.json"`.
    Listar todos los hits y planificar reemplazo a la versión con
    "ch".
  - Migrar al archivo principal lo único que no está duplicado:
    - §1 bullets de "Trazabilidad / Validación Humana / Documentación
      de Decisiones".
    - §2 mención de `CLIContainer` (Spec-250) + DI.
    - §3 párrafos de variantes de prompting (compact/frontier) y
      `NarrativeAuditor`.
    - §4 estándares técnicos (Python 3.12+, naming, manejo de
      errores).
    - §5 workflow del desarrollador (`make install/test/lint`,
      `init_db.sh`).
  - Actualizar las referencias detectadas en el pre-check para que
    apunten a `estandar_diseno_architectural.md`.
  - `git rm docs/estandar_diseno_arquitectural.md`.
  - **Validación final:** segundo
    `grep -rn "estandar_diseno_arquitectural" .` devuelve cero hits
    (sin "q") fuera del propio comando.

### Slice S7 — Curaduría asertiva de tests (estado actual post-301/302)

**Objetivo:** reducir deuda de suite eliminando pruebas sin valor actual y
concentrando la cobertura en contratos reales del sistema.

**Criterio de decisión (obligatorio, en este orden):**

1. **KEEP** si el test valida un contrato de negocio vigente o una costura crítica
   (CLI→UseCase, UseCase→Repo, parser/loader→DTO, broadcaster SSE, etc.).
2. **REWRITE** si el objetivo sigue vigente pero el test depende de artefactos
   eliminados (ej. `MarkdownStoryParser`, `MarkdownRenderer`) o de internals
   que cambiaron.
3. **DELETE** si el test:
   - cubre comportamiento removido del producto,
   - duplica señal ya cubierta por tests más focalizados,
   - o tiene assertions débiles/no determinísticas que no detectan regresiones reales.

**Regla anti-ruido:** ningún test debe existir solo para inflar cobertura o por
inercia histórica.

- [x] S7-T1: Inventariar tests rotos/legacy por categoría:
  - dependencias removidas (`markdown_parser`, `markdown_renderer`, módulos movidos),
  - assertions triviales (ej. “no vacío” sin contrato),
  - duplicados funcionales.
- [x] S7-T2: Aplicar matriz KEEP/REWRITE/DELETE en `tests/integration` y `tests/unit/cli`.
- [x] S7-T3: Reescribir los que queden como **contract tests**:
  - inputs concretos,
  - un solo motivo de falla por test,
  - asserts sobre salidas observables (DTO persistido, kwargs de invocación, estado DB/repo, eventos SSE).
- [x] S7-T4: Eliminar tests de pipeline E2E antiguos que dependían del parser markdown
  si su señal queda cubierta por:
  - `tests/unit/infrastructure/test_yaml_loader.py`,
  - `tests/unit/cli/test_runner_argparse.py`,
  - `tests/unit/cli/test_commands_generate_input.py`,
  - y verificación manual S5.
- [x] S7-T5: Exigir assertions “asertivas” mínimas por test:
  - debe validar al menos un dato semántico de negocio (no solo tipos/longitud),
  - debe fallar si se revierte el fix 302,
  - debe evitar mocks globales innecesarios.
- [x] S7-T6: Correr `make lint` + `make test` y registrar delta:
  - tests eliminados,
  - tests reescritos,
  - nuevos riesgos aceptados (si aplica).

**Resultado esperado S7:** suite más pequeña pero más estricta; cero referencias
a componentes eliminados y cero tests “zombie”.

#### S7-T1 — Inventario inicial (2026-05-05)

| Archivo | Decisión propuesta | Motivo |
|---|---|---|
| `tests/integration/test_stream_broadcaster.py` | **KEEP** | Cubre contrato vigente de `StreamSessionManager` (productor único, replay, cleanup, error propagation). Señal alta y no depende de componentes removidos. |
| `tests/integration/test_slice8_e2e_monte.py` | **REWRITE (ya aplicado)** | Antes dependía de `MarkdownStoryParser` removido; se migró a smoke de `YamlStoryLoader` para validar input real vigente. |
| `tests/unit/cli/test_commands_generate_input.py` | **KEEP + endurecer** | Es costura crítica del fix 302 (`_generate_async` con `input_file`). Agregar caso negativo: YAML inválido no debe invocar `run_full`. |
| `tests/unit/cli/test_runner_argparse.py` | **KEEP + endurecer** | Verifica cableado `argparse → commands.generate` y firma pública. Falta eliminar `if mock_gen.called` y afirmar invocación explícita (`assert_called_once`). |
| `tests/unit/cli/test_commands.py` | **REWRITE/REDUCE** | Sigue siendo útil para `_write_markdown`, pero hoy tiene énfasis cosmético. Conservar 3-4 asserts de contrato (crea archivo, sanitiza nombre, incluye contenido beats) y eliminar redundancia. |
| `tests/unit/cli/test_progress.py` | **KEEP** | Contrato de UX CLI vigente (`ProgressReporter`/`SilentReporter`). Señal estable y bajo mantenimiento. |
| `tests/unit/cli/test_logger.py` | **KEEP (revisar granularidad)** | Cubre logging utilitario activo. Mantener mientras valide formato/ruta y no detalles frágiles de timestamps. |
| `tests/unit/cli/test_exceptions.py` | **KEEP** | Contrato básico de excepciones públicas CLI; costo bajo, regresión útil. |

**Observaciones asertivas detectadas:**
- Evitar asserts débiles tipo “no vacío” cuando se pueda validar semántica concreta (campos exactos, kwargs exactos, estados esperados).
- Evitar `try/except SystemExit: pass` sin assert posterior; reemplazar por aserciones explícitas de llamada/exit.
- Priorizar contrato observable sobre estructura interna (no testear implementación de mocks).

#### S7-T6 — Reporte de cierre (2026-05-05)

**Estado de ejecución**
- `make lint`: ✅ verde.
- `make test`: ✅ verde.

**Delta de suite (foco S7)**
- `tests/integration/test_slice8_e2e_monte.py`: **REWRITE** drástico de test legacy acoplado a parser removido hacia smoke integration de `YamlStoryLoader`.
- `tests/unit/cli/test_commands.py`: **REDUCE** de casos redundantes a contratos mínimos de `_write_markdown`.
- Total observado en diff de foco: `19 insertions`, `308 deletions` (suite más pequeña y específica).
- Conteo total de tests ejecutados: de `501` a `498` (reducción neta: `-3`, esperada por eliminación de casos redundantes).

**Riesgo residual aceptado**
- El test de integración del “monte” dejó de validar el pipeline narrativo completo y ahora valida integración de carga YAML.
- Esta pérdida de amplitud se compensa por:
  - costuras CLI (`test_runner_argparse.py`, `test_commands_generate_input.py`),
  - unit del loader (`test_yaml_loader.py`),
  - y verificación manual S5 sobre generación completa.

---

## 6. Tests de Regresión

Todos los tests automatizados son rápidos (<1s cada uno). Sin
`subprocess`, sin LLM real, sin BD persistente. La única excepción es
la verificación manual de S5, que sí toca DB y MockLLM y se corre a
mano una sola vez.

| Tipo | Test | Criterio |
|------|------|----------|
| Unit dominio | `tests/unit/domain/test_story_validation.py` | `Story(title="")` lanza `ValidationError` |
| Unit loader | `tests/unit/infrastructure/test_yaml_loader.py` | YAML real → DTO completo; faltantes lanzan `ValidationError` |
| Costura [1] argparse | `tests/unit/cli/test_runner_argparse.py` | `runner.main(...)` invoca `commands.generate(input_file=X, ...)` |
| Costura [2] handler→runner | `tests/unit/cli/test_commands_generate_input.py` | `_generate_async(input_file=X)` llama `run_full(...)` con campos no vacíos |
| Verificación manual | `python -m src generate --input ... --mock` + SELECT | story completa en DB |
| Round-trip (opcional) | export-yaml → generate --input | DTO equivalente |
| Suite completa | `pytest tests -v` | sin regresiones |
| Doc — ERD | grep cada FK del diagrama vs `PRAGMA foreign_key_list` | 100% coincidencia |
| Doc — colaboración | grep cada nodo vs `class <Name>` en `src/` | 100% existe |
| Doc — secuencia | contar `->>LLM` en bloque mermaid | == 17 |
| Curaduría suite | inventario KEEP/REWRITE/DELETE por archivo | sin tests zombie / sin imports removidos |

---

## 7. Breaking Changes

Ninguno hacia adelante. Es un bugfix puro: el flujo `--input` sólo está roto
hoy, así que repararlo no rompe nada. Las historias creadas vacías por el bug
se descartan recreando la DB (consistente con la política del proyecto: no
migration scripts).

---

## 8. Commands de Verificación

```bash
# Limpiar y recrear DB
./scripts/bash/db_clean.sh
./scripts/bash/init_db.sh

# Reproducir el bug ANTES del fix (debería persistir story vacía)
uv run python -m src generate --input input_stories/la_ofrenda.yaml --mock
uv run python -c "
import sqlite3
c = sqlite3.connect('data/stories.db'); c.row_factory = sqlite3.Row
for r in c.execute('SELECT id, title, protagonista, sinopsis FROM story').fetchall():
    print(dict(r))
"

# Después del fix: title/protagonista/sinopsis no vacíos
```

---

## 9. Notas

- Este spec ataca **uno** de varios breaking changes detectados tras los
  specs 222/230/300/301. Los siguientes (a especificar en 303, 304…) se
  abordarán por separado para mantener slices pequeños.
- Memoria del proyecto: no proponer scripts de migración; cuando el esquema
  o la data quedan inconsistentes, recrear `stories.db`.
- Memoria del proyecto: cumplimiento estricto SDD — **no avanzar a
  IMPLEMENT sin OK explícito** en este spec.

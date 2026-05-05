# Spec-310: Limpieza arquitectural post-Spec-302

## Metadata

| Campo | Valor |
|-------|-------|
| **Status** | Draft |
| **Tipo** | Refactor / Cleanup + Hardening (no funcional) |
| **Slice base** | S0 |
| **Fecha** | 2026-05-05 |
| **Owner** | Backend |
| **Depende de** | Spec-302 cerrado y mergeado |
| **Bloquea** | Nada (cosmético / hardening) |

---

## 1. Objetivo

Eliminar focos de deuda detectados durante la auditoría
del Spec-302 que quedaron explícitamente fuera de scope para no inflar
el bugfix:

1. La firma de `StoryRunner.run_full` recibe 11 parámetros sueltos y
   construye internamente el DTO. Es una API ruidosa que invita a
   olvidar parámetros (justo lo que pasó en el bug del 302).
2. Los tests pasan `escenarios=...` al constructor de `Story` cuando
   ese campo **no existe** en el modelo. Pydantic los descarta
   silenciosamente. Los tests pasan por accidente.
3. Blindar el dominio para que esto no vuelva a pasar: `extra="forbid"`
   en `Story` y `StoryCreateDTO` como requisito de cierre.

Estos cambios son **mejoras de higiene/hardening**, no bugfixes funcionales. El producto
no cambia su comportamiento observable.

---

## 2. Contexto

Durante el análisis del Spec-302 se descubrió:

### 2.1 `run_full` con explosión de parámetros

`src/core/orchestrator.py:45-58` define:

```python
async def run_full(
    self,
    title: str,
    protagonista: str,
    relator: str,
    escenarios: list[str] | str,
    sinopsis: str,
    atmosfera: str,
    reglas: list[str] | None = None,
    stop_after: str | None = None,
    storyteller_config: dict | None = None,
    typed_rules: list[dict] | None = None,
    personajes_full: list[dict] | None = None,
) -> Story:
    ...
    dto = StoryCreateDTO(title=title, protagonista=protagonista, ...)
    story = await create_story.execute(dto)
```

**Síntoma:** la firma duplica la información que `StoryCreateDTO` ya
encapsula. Cualquier campo nuevo del DTO obliga a tocar la firma de
`run_full`, su contrato con `commands.py`, y todos los tests que la
invocan.

**Riesgo demostrado:** el bug del Spec-302 fue exactamente esto —
`commands.generate()` pasaba strings vacíos a `run_full(...)` y nadie
notaba. Si el contrato hubiera sido un DTO, Pydantic habría rechazado
el `Story` vacío en `CreateStoryUseCase`.

**Call sites totales:** 4 (`src/cli/commands.py` y
`tests/unit/core/test_orchestrator.py`). Todos en este
repo. Cero clientes externos.

### 2.2 Fixtures con `escenarios=...` ignorado

`Story` (`src/domain/models.py:173-193`) tiene `scenarios:
list[Scenario] = []`, **no** `escenarios`. Pero hay 40+ ocurrencias
en `tests/` con patrones tipo:

```python
story = Story(
    title="Test",
    protagonista="P",
    relator="r",
    escenarios="Location",   # ← Pydantic lo ignora, es ruido
    sinopsis="S",
    atmosfera="A",
)
```

Pydantic v2 con configuración default es `extra="ignore"`, así que
estos tests **pasan por accidente**: el campo se descarta sin error.
Los tests que de verdad necesitan escenarios cargados los inicializan
después con `story.scenarios = [Scenario(...)]`.

**Riesgo latente:** cualquier cambio futuro a `extra="forbid"` en
`Story` (algo razonable para hardening) hace estallar 40+ tests de
golpe.

**Hits encontrados (grep `escenarios=` en `tests/`, 2026-05-05):**

| Archivo | Ocurrencias |
|---|---|
| `tests/unit/application/test_director_legacy_plan.py` | 8 |
| `tests/unit/application/test_narrate_beat.py` | 6 |
| `tests/unit/application/test_prompt_builder.py` | 6 |
| `tests/unit/infrastructure/test_story_repository.py` | 5 |
| `tests/unit/infrastructure/test_template_mapper.py` | 4 |
| `tests/unit/infrastructure/test_story_repository.py` | 5 |
| `tests/unit/core/test_orchestrator.py` | 3 |
| `tests/unit/cli/test_commands_generate_input.py` | 3 (`escenarios=[]` en contrato viejo) |
| `tests/unit/domain/test_models.py` | 2 |
| `tests/unit/application/test_*` (varios) | ~15 |
| `tests/unit/cli/test_commands.py` | 1 |
| `tests/fixtures/__init__.py` | 1 (factory compartida) |

Hay también un caso atípico: `test_read_use_cases.py:129` pasa
`escenarios=["Bosque"]` (lista, no string) — también ignorado.

---

## 3. Scope

### In Scope

- Agregar `StoryRunner.run_full_from_dto(dto: StoryCreateDTO,
  stop_after: str | None = None) -> Story` como punto de entrada
  preferido.
- Refactorizar `commands.py::_generate_async` para usar el método
  nuevo. Cuando `--input` está, el loader ya devuelve un DTO; cuando
  no, se construye uno explícito en commands.
- Mantener `run_full` actual como wrapper deprecado (delega en
  `run_full_from_dto`).
- Limpieza completa de `escenarios=...` en `tests/` (criterio duro: 0 hits).
- Verificar que las fixtures que de verdad necesitan escenarios
  inicialicen `story.scenarios = [Scenario(...)]` (no inventar — sólo
  si ya lo hacen y conviven con el `escenarios=` ignorado).
- Endurecimiento obligatorio: `model_config = {"extra": "forbid"}` en
  `Story` y `StoryCreateDTO`.
- Excluir el test e2e legacy del alcance de este spec (se elimina y no
  se reemplaza aquí con un nuevo e2e de pipeline).

### Out of Scope

- Cualquier cambio funcional al pipeline LLM, prompts, BD o UI.
- Cambios al YAML canónico (Spec-217) o al loader (Spec-302).
- Refactor de otros use cases o servicios.
- Migración de fixtures fuera de `tests/`.
- Revivir o rediseñar un nuevo test e2e del pipeline narrativo completo
  (se difiere a spec futuro).

---

## 4. Diseño

### 4.1 `StoryRunner.run_full_from_dto`

Nuevo método en `src/core/orchestrator.py`:

```python
async def run_full_from_dto(
    self,
    dto: StoryCreateDTO,
    stop_after: str | None = None,
) -> Story:
    """Punto de entrada preferido: recibe el DTO ya validado.

    Equivalente a run_full(...), pero sin el contrato ruidoso. El DTO
    ya pasó por Pydantic, así que sus campos son consistentes por
    construcción.
    """
    if stop_after is not None:
        validate(stop_after)
    # ... resto idéntico al run_full actual, leyendo del DTO
```

`run_full(...)` queda como **wrapper deprecado**:

```python
async def run_full(
    self, title: str, protagonista: str, ...
) -> Story:
    """Deprecado: usar run_full_from_dto. Se mantiene como adapter."""
    dto = StoryCreateDTO(
        title=title, protagonista=protagonista, ...
    )
    return await self.run_full_from_dto(dto, stop_after=stop_after)
```

**Beneficios:**
- Cero breaking changes para los 4 call sites existentes.
- El código de orquestación queda con un único punto de entrada
  bien tipado.
- Cuando `commands.py` migre, los tests legacy de
  `test_orchestrator.py` siguen verdes contra `run_full`.

### 4.2 Migración de `commands.py`

```python
async def _generate_async(...):
    ...
    if input_file:
        dto = YamlStoryLoader().load_from_file(Path(input_file))
    else:
        dto = StoryCreateDTO(
            title=title, protagonista=protagonista, ...
        )

    container = CLIContainer(...)
    runner = container.story_runner(output_dir)
    story = await runner.run_full_from_dto(dto, stop_after=hasta)
    await container.story_repo.update_status(...)
```

**Resultado:** una única ruta de datos `args → DTO → run_full_from_dto`.
No hay más "12 strings sueltos" cruzando capas.

### 4.3 Limpieza de fixtures

Estrategia: **eliminar el kwarg `escenarios=` cuando es ruido.**

Algoritmo manual (no script automatizado — 40 sitios son revisables):

Para cada hit de `escenarios=...` dentro de un constructor de
`Story(...)`:
1. Verificar si el test usa `story.scenarios` o `story.escenarios`
   más adelante. Si **no**, simplemente borrar el kwarg.
2. Si sí (caso atípico — el test depende del valor que se pierde),
   reemplazar por
   `story.scenarios = [Scenario(story_id=story.id, order_index=0,
   name="Location")]` después del constructor.

**Factory compartida** (`tests/fixtures/__init__.py:15`): tratamiento
especial. Si la factory expone `escenarios=` como parámetro,
investigar si algún consumidor lo lee. Eliminarlo del factory si
ningún consumidor lo necesita; mantenerlo como `scenarios=` (correcto)
si alguno sí lo usa.

**Caso `escenarios=["Bosque"]`** (lista): mismo tratamiento. Es ruido.

### 4.4 Endurecimiento obligatorio `extra="forbid"`

Si se decide blindar permanentemente, agregar a `Story` y
`StoryCreateDTO`:

```python
class Story(BaseModel):
    model_config = {"extra": "forbid"}
    ...
```

**Hacerlo SÓLO después** de S2 (limpieza de fixtures). Si se hace
antes, todos los tests con `escenarios=` explotan en cascada.

Activar `extra="forbid"` como S3 final es requisito de cierre de este spec.

---

## 5. Slices

> **Pre-requisito:** Spec-302 cerrado y mergeado. La validación
> `min_length=1` y el `YamlStoryLoader` ya viven en el código.

### Slice S0 — Baseline

- [ ] S0-T1: `pytest tests -v` verde sobre `main` post-302. Snapshot
  del set de tests verdes — ninguno puede caer en S1–S3.
- [ ] S0-T2: Confirmar que `git grep -n 'escenarios=' tests/`
  reproduce los ~40 hits documentados en §2.2.

### Slice S1 — Refactor `run_full` con DTO

- [ ] S1-T1: Agregar `StoryRunner.run_full_from_dto(dto, stop_after)`
  según diseño §4.1. Lógica idéntica al `run_full` actual, leyendo
  del DTO.
- [ ] S1-T2: Reescribir `run_full(...)` como wrapper que arma el DTO
  y delega en `run_full_from_dto`. Marcar con docstring
  "deprecado, usar run_full_from_dto".
- [ ] S1-T3: Tests en
  `tests/unit/core/test_orchestrator_from_dto.py`:
  - `run_full_from_dto(dto)` produce `Story` equivalente al
    `run_full(...)` con los mismos datos.
  - `run_full_from_dto(dto, stop_after="analyst")` respeta el
    checkpoint.
  - `run_full(...)` sigue funcionando (regresión sobre el wrapper).
- [ ] S1-T4: Migrar `src/cli/commands.py::_generate_async` a usar
  `run_full_from_dto`. Construir DTO antes de instanciar el runner.
- [ ] S1-T5: `pytest tests -v` verde, sin regresiones.

### Slice S2 — Limpieza de fixtures

- [ ] S2-T1: Recorrer cada archivo listado en §2.2 y eliminar el
  kwarg `escenarios=` de los constructores `Story(...)`. Aplicar
  algoritmo §4.3.
- [ ] S2-T2: Tratamiento del factory compartido
  `tests/fixtures/__init__.py:15`:
  - Si ningún consumidor lee el valor → eliminar el parámetro.
  - Si alguno sí → renombrar a `scenarios=` y construir
    `[Scenario(...)]` correctamente.
- [ ] S2-T3: Tratamiento del caso atípico
  `test_read_use_cases.py:129` (`escenarios=["Bosque"]`).
- [ ] S2-T4: `pytest tests -v` verde — ningún test debería romperse,
  porque el campo ya estaba siendo ignorado.
- [ ] S2-T5: Verificación final:
  `git grep -n 'escenarios=' tests/` → 0 hits.
- [ ] S2-T6: Eliminar `tests/integration/test_slice8_e2e_monte.py` del
  árbol de tests (legacy de parser markdown; fuera de alcance revivirlo aquí).

### Slice S3 — Endurecimiento `extra="forbid"` (obligatorio)

- [ ] S3-T1: Agregar `model_config = {"extra": "forbid"}` a `Story`
  (`src/domain/models.py:173`) y `StoryCreateDTO`
  (`src/application/dto/story_dto.py:8`).
- [ ] S3-T2: Tests en `tests/unit/domain/test_story_extra_forbid.py`:
  - `Story(title="t", ..., escenarios="x")` lanza
    `pydantic.ValidationError` mencionando el campo extra.
  - `StoryCreateDTO(title="t", ..., desconocido=1)` también lanza.
- [ ] S3-T3: `pytest tests -v` verde. Si **algún** test rompe acá,
  significa que S2 dejó un `escenarios=` u otro extra; volver a S2 y
  cerrarlo bien.

### Slice S4 — Limpieza final

- [ ] S4-T1: `ruff check . && ruff format .` verde.
- [ ] S4-T2: `pytest tests -v` verde y al menos el baseline de S0-T1.
- [ ] S4-T3: Considerar deprecar `run_full(...)` con
  `warnings.warn(DeprecationWarning, ...)` en el wrapper, para que
  futuros call sites se desincentiven. Decisión a discutir con el
  usuario antes de aplicar.

---

## 6. Tests

| Tipo | Test | Criterio |
|------|------|----------|
| Unit refactor | `tests/unit/core/test_orchestrator_from_dto.py` | `run_full_from_dto` ≡ `run_full` |
| Regresión wrapper | `tests/unit/core/test_orchestrator.py` | Tests existentes verdes |
| Limpieza | `git grep 'escenarios=' tests/` | 0 hits tras S2 |
| Hardening | `tests/unit/domain/test_story_extra_forbid.py` | `extra="forbid"` activo (S3 obligatorio) |
| Hygiene | `test ! -f tests/integration/test_slice8_e2e_monte.py` | test e2e legacy removido |
| Suite completa | `pytest tests -v` | sin regresiones |

---

## 7. Breaking Changes

**Externos:** ninguno. `run_full(...)` sigue funcionando como antes,
sólo delega internamente.

**Internos (en este repo):**

- Si S3 se aplica, cualquier código futuro que pase un kwarg extra a
  `Story` o `StoryCreateDTO` (por error o legacy) explota con
  `ValidationError`. Es el comportamiento deseado.

- El wrapper `run_full(...)` queda marcado como deprecado pero
  funcional. No se elimina en este spec; queda candidato para un
  spec futuro de retirada definitiva una vez que todos los call
  sites internos estén migrados.

---

## 8. Notas

- Este spec depende **estrictamente** de que Spec-302 esté cerrado.
  Si se ejecuta antes, los slices S1–S2 trabajan contra una versión
  de `Story`/`StoryCreateDTO` aún sin `min_length=1`, y se pierde la
  red de seguridad que Pydantic provee durante el refactor.
- Memoria del proyecto: cumplimiento estricto SDD — **no avanzar a
  IMPLEMENT sin OK explícito** en este spec.
- Memoria del proyecto: no proponer scripts de migración. La
  limpieza de fixtures es manual (40 sitios, revisables).
- S3 (`extra="forbid"`) es obligatorio en este spec por decisión de
  hardening post-302.

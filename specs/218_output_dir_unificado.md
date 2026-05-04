# Spec-218: Output Dir Unificado por Configuración

## Estado
IMPLEMENTADO — T1-T6 completados. CA1, CA4, CA5, CA6 verificados automáticamente. CA2 y CA3 requieren smoke manual (consumo LLM / docker).

### Notas de implementación

- `src/application/services/export_service.py:38` mantiene el literal `f"output_stories/{filename}"` como **path URL** retornado para `story.file_path`. Coherente porque el frontend Express sirve estáticamente `public/output_stories/`. Si en el futuro se quisiera desacoplar también el segmento URL del nombre del directorio, sería un spec aparte.
- Los 3 tests `failed` y 15 `errors` que aparecen en `pytest tests` son **pre-existentes** (verificado con `git stash`): buscan `input_stories/el_monte_prohibido.md` que ya no existe (proyecto migró a `.yaml` con Spec-217).

---

## Problema

La ruta donde se escriben los `.md` exportados está **hardcodeada en tres lugares distintos** y la variable de entorno definida en `.env` (`OUTPUT_DIR`) **no la lee nadie**.

| Lugar | Valor actual | Tipo |
|---|---|---|
| `.env:23` | `OUTPUT_DIR=./output_stories` | env (no consumida) |
| `src/config.py:88` | `output_dir: str = "output_stories"` | `Settings` field (no consumido) |
| `src/cli/runner.py` (4 ocurrencias: 23, 76, 86, 108) | `Path("output_stories/")` | hardcoded |
| `src/application/services/export_service.py:13` | `Path("frontend/public/output_stories")` | hardcoded (¡distinto al CLI!) |
| `src/core/orchestrator.py:130` | `f"output_stories/debug_{title}_{cp_ordinal}.md"` | hardcoded |
| `docker-compose.yml:16` | `OUTPUT_DIR=/app/output_stories` (override) | env override decorativa |

Consecuencias:
1. CLI ejecutado en host → escribe en `./output_stories/` (raíz).
2. Stream API en contenedor → escribe en `frontend/public/output_stories/` (vía mount, ahora que se corrigió en docker-compose).
3. Debug MD del orchestrator → cae siempre en `./output_stories/debug_*.md`.
4. Cambiar la ruta exige tocar 3 archivos de código + `.env` + `docker-compose.yml`.

---

## Solución

**Principio:** una única ruta canónica leída desde `Settings.output_dir`, configurable vía `.env` o env var `OUTPUT_DIR`. Cero hardcode en código de aplicación.

### Comportamiento esperado

| Componente | Lectura |
|---|---|
| CLI (`runner.py`) | `Path(settings.output_dir)` como default de argparse |
| `ExportService` | `_DEFAULT_OUTPUT_DIR = Path(settings.output_dir)` |
| `orchestrator.py` debug MD | `Path(settings.output_dir) / f"debug_{title}_{cp_ordinal}.md"` |
| `.env` (host) | `OUTPUT_DIR=./frontend/public/output_stories` |
| `docker-compose.yml` (contenedor) | `OUTPUT_DIR=/app/output_stories` (override) + bind `./frontend/public/output_stories:/app/output_stories` |

Resultado: CLI en host y contenedor escriben al mismo directorio del proyecto (`frontend/public/output_stories/`), sin cambiar código si en el futuro se quiere mover.

---

## Assumptions (corregir antes de avanzar)

1. La ruta canónica unificada es **`frontend/public/output_stories/`** (lo que el frontend Express ya sirve).
2. El override del `docker-compose.yml` se **mantiene** (`OUTPUT_DIR=/app/output_stories`) porque el contenedor necesita un path absoluto interno; el bind hace que ambos apunten a la misma carpeta del host.
3. **Alcance limitado a `output_dir`**. No se tocan `input_dir`, `prompts_dir` ni `beats_definition_file` aunque también se exponen en `Settings`.
4. El debug MD (`orchestrator.py:130`) comparte directorio con los exports definitivos. Si se quisiera separar (ej. `output_stories/_debug/`), se haría en otro spec.
5. Migración de los `.md` ya generados en `./output_stories/` raíz → **fuera de alcance**. El usuario decide si los mueve manualmente.

---

## Cambios requeridos

### Slice A — Config: hacer que `Settings.output_dir` sea fuente de verdad

**Archivo:** `src/config.py`

- Verificar que `Settings.output_dir` ya está expuesto (línea 88) — sí lo está.
- Sin cambios de código, solo confirmar que pydantic-settings auto-mapea `OUTPUT_DIR` env → `output_dir` field.

### Slice B — CLI: leer del settings

**Archivo:** `src/cli/runner.py`

- Importar `from src.config import settings`.
- Reemplazar las 4 ocurrencias de `default=Path("output_stories/")` (líneas 23, 76, 86, 108) por `default=Path(settings.output_dir)`.

### Slice C — ExportService: leer del settings

**Archivo:** `src/application/services/export_service.py`

- Línea 13: `_DEFAULT_OUTPUT_DIR = Path("frontend/public/output_stories")` → reemplazar por lectura de `settings.output_dir`.
- Mantener la firma del constructor (`output_dir: Path | None = None`) — el override sigue funcionando.

### Slice D — Orchestrator debug MD

**Archivo:** `src/core/orchestrator.py`

- Línea 130: reemplazar literal `"output_stories/debug_..."` por `Path(settings.output_dir) / f"debug_{title}_{cp_ordinal}.md"`.

### Slice E — `.env` y `docker-compose.yml`

- `.env:23` → `OUTPUT_DIR=./frontend/public/output_stories` (alineado con el bind del compose).
- `docker-compose.yml:16` → mantener `OUTPUT_DIR=/app/output_stories` (override interno del contenedor; el bind ya apunta al mismo lugar del host tras el cambio anterior).

---

## Archivos afectados

| Archivo | Cambio |
|---|---|
| `src/config.py` | Sin cambios (verificación) |
| `src/cli/runner.py` | 4 defaults → `settings.output_dir` |
| `src/application/services/export_service.py` | `_DEFAULT_OUTPUT_DIR` → `settings.output_dir` |
| `src/core/orchestrator.py` | Path del debug MD → `settings.output_dir` |
| `.env` | Apuntar a `./frontend/public/output_stories` |
| `docker-compose.yml` | Sin cambios (ya consistente tras el ajuste previo) |

---

## Tests potencialmente afectados

A relevar en fase PLAN (ripgrep `output_stories` en `tests/`). Si algún test asume `./output_stories/` raíz como path absoluto, hay que parametrizarlo o usar `tmp_path`.

---

## Criterios de Aceptación

| # | Criterio | Verificación |
|---|---|---|
| CA1 | `grep -rn 'output_stories' src/` no devuelve literales hardcoded en defaults (solo lecturas de `settings`) | grep manual |
| CA2 | CLI ejecutado en host con default genera `.md` en `frontend/public/output_stories/` | `uv run python -m src generate --input ...` |
| CA3 | Stream API en contenedor sigue generando `.md` en `frontend/public/output_stories/` (visible al frontend) | Generar historia desde UI |
| CA4 | Cambiar `OUTPUT_DIR` en `.env` reubica todos los outputs sin tocar código | Override temporal + ejecutar CLI |
| CA5 | Pasar `--output otra/ruta/` por CLI sigue funcionando como override puntual | Smoke test |
| CA6 | Tests existentes pasan: `pytest tests -v` | CI |

---

## Tareas

- [ ] **T1: Verificar mapeo `OUTPUT_DIR` env → `Settings.output_dir`**
  - Acceptance: confirmado que pydantic-settings auto-mapea sin código adicional.
  - Verify: `uv run python -c "from src.config import settings; print(settings.output_dir)"` con `OUTPUT_DIR=/tmp/x` exportado → imprime `/tmp/x`.
  - Files: ninguno (solo lectura).

- [ ] **T2: CLI runner usa `settings.output_dir` como default**
  - Acceptance: las 4 ocurrencias `default=Path("output_stories/")` reemplazadas por `default=Path(settings.output_dir)`. Import de `settings` agregado al top del archivo.
  - Verify: `uv run python -m src generate --help` muestra el default desde el `.env`. Override por `--output otra/ruta/` sigue funcionando.
  - Files: `src/cli/runner.py`.

- [ ] **T3: ExportService default desde `settings.output_dir`**
  - Acceptance: `_DEFAULT_OUTPUT_DIR` lee `settings.output_dir`. Constructor mantiene firma `output_dir: Path | None = None`.
  - Verify: instanciar `ExportService()` sin args y confirmar `_output_dir == Path(settings.output_dir)`. `pytest tests/unit -v -k export` pasa.
  - Files: `src/application/services/export_service.py`.

- [ ] **T4: Orchestrator debug MD usa `settings.output_dir`**
  - Acceptance: literal `"output_stories/debug_..."` reemplazado por `Path(settings.output_dir) / f"debug_{title}_{cp_ordinal}.md"`. Reusar el import `cfg` ya existente (línea 67) o agregar uno a nivel módulo si conviene.
  - Verify: `grep -n "output_stories" src/core/orchestrator.py` devuelve 0 hits literales. `pytest tests/unit -v -k orchestrator` pasa.
  - Files: `src/core/orchestrator.py`.

- [ ] **T5: `.env` apunta a la ruta canónica**
  - Acceptance: `OUTPUT_DIR=./frontend/public/output_stories` en `.env`.
  - Verify: `uv run python -c "from src.config import settings; print(settings.output_dir)"` imprime `./frontend/public/output_stories`.
  - Files: `.env`.

- [ ] **T6: Verificación integral**
  - Acceptance: CA1–CA6 cumplidos.
  - Verify:
    - `grep -rn 'output_stories' src/` solo muestra lecturas vía `settings`, no literales en defaults (CA1).
    - `uv run python -m src generate --input input_stories/el_monte_prohibido.yaml` → `.md` en `frontend/public/output_stories/` (CA2).
    - `docker compose down && docker compose up -d` + generar desde UI → `.md` aparece en `frontend/public/output_stories/` (CA3).
    - Override temporal `OUTPUT_DIR=/tmp/out uv run python -m src generate ...` → `.md` en `/tmp/out/` (CA4).
    - `--output otra/ruta/` por CLI → `.md` en `otra/ruta/` (CA5).
    - `pytest tests -v` pasa (CA6).
  - Files: ninguno (solo verificación).

---

## Plan técnico

### Componentes y dependencias

```
[Slice A] config.py — verificación (sin cambios)
       │
       ▼
[Slice B] cli/runner.py        ┐
[Slice C] export_service.py    ├── Cambios independientes entre sí
[Slice D] orchestrator.py      ┘   (todos importan settings + 1 reemplazo)
       │
       ▼
[Slice E] .env + docker-compose.yml — independiente del código
```

### Orden de implementación

Recomendado (single sesión de IMPLEMENT, ~15 min):

1. **Slice A** — verificación rápida (`grep` para confirmar pydantic-settings auto-mapea `OUTPUT_DIR` → `output_dir`).
2. **Slices B + C + D en paralelo** — son cambios análogos: agregar `from src.config import settings` (ya importado en `orchestrator.py:67`) + reemplazar literal por `settings.output_dir`.
3. **Slice E** — editar `.env` y verificar `docker-compose.yml`.
4. **Verificación integral** — correr `pytest tests -v`, smoke CLI, smoke API.

### Análisis de riesgos

| # | Riesgo | Probabilidad | Mitigación |
|---|---|---|---|
| R1 | Tests con `output_stories` hardcoded fallan | **Baja** — verificado: solo 1 hit en `tests/unit/cli/test_progress.py:60` y es un display string, no toca filesystem | Sin acción |
| R2 | Import circular al traer `settings` en `cli/runner.py` | Baja — `runner.py` está al final de la cadena de imports | Si ocurre, import lazy dentro de `main()` |
| R3 | Default de `Settings` (`"output_stories"`) deja a tests sin `.env` escribiendo a `./output_stories/` raíz | Media | `pytest` setup ya usa `tmp_path` cuando exporta. Verificar en CA6 |
| R4 | `ExportService` se instancia en tests con `output_dir=None` y rompe al perder el constante de módulo | Baja | Mantener firma del constructor (`output_dir: Path \| None = None`) intacta |

### Verificaciones intermedias

- Tras Slice B: `uv run python -m src generate --help` muestra el default correcto en `--output`.
- Tras Slice C: smoke desde UI — generar historia y confirmar archivo en `frontend/public/output_stories/`.
- Tras Slice D: ejecutar CLI con `--debug` y confirmar `debug_*.md` aparece en el mismo dir.
- Tras Slice E: `docker compose down && up -d` + smoke completo.

### Reversibilidad

Todos los cambios son **completamente reversibles** (revert a literales). No hay migraciones de DB, no hay borrado de archivos. Los `.md` ya generados en `./output_stories/` raíz quedan donde están (decisión del usuario si los mueve).

---

## Decisiones cerradas

| # | Decisión | Fuente |
|---|---|---|
| D1 | Ruta canónica única: `frontend/public/output_stories/`. Se elimina el uso de `./output_stories/` raíz. | Usuario — simplificar carpetas |
| D2 | Debug MD del orchestrator comparte directorio con los exports finales (no se crea subdir aparte). | Usuario |
| D3 | `Settings.output_dir` mantiene default agnóstico `"output_stories"`. La ruta canónica se fuerza desde `.env` (`OUTPUT_DIR=./frontend/public/output_stories`). El default solo aplica si `.env` no existe (entornos de test). | Usuario |

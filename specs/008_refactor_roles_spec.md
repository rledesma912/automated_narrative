# Spec: Refactor de Roles (CLI-9 / REF-1)

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Borrador  
> **Owner:** Usuario (Auditor)  
> **Tags:** refactor, naming, roles, clean-architecture

---

## 1. Objetivo

Renombrar los casos de uso para que el código sea un espejo fiel del Spec 001, donde se definen los roles: **Director**, **Voz** y **Journalist**.

**¿Por qué?** El spec 001 define:
- `Director` → `CreateStoryPlanUseCase`
- `Voz` → `NarrateBeatUseCase`

Pero el código actual usa los nombres técnicos (UseCase) en lugar de los nombres de rol. Esto dificulta entender qué hace cada componente.

---

## 2. Tech Stack

- **Python:** 3.12
- **Refactor:** renombrar clases, actualizar imports

---

## 3. Comandos

```bash
make test
make lint
```

---

## 4. Cambios Requeridos

### 4.1 Renombrar Clases

| Nombre Actual | Nuevo Nombre | Ubicación |
|---------------|--------------|-----------|
| `CreateStoryPlanUseCase` | `DirectorUseCase` | `src/application/use_cases/create_story_plan.py` |
| `NarrateBeatUseCase` | `VozUseCase` | `src/application/use_cases/narrate_beat.py` |
| `NarrateBatchUseCase` | `VozBatchUseCase` | `src/application/use_cases/narrate_batch.py` |

### 4.2 Actualizar Imports

Todos los archivos que importen estas clases deben actualizarse:

```python
# Antes
from src.application.use_cases import CreateStoryPlanUseCase, NarrateBeatUseCase

# Después
from src.application.use_cases import DirectorUseCase, VozUseCase
```

### 4.3 Actualizar Tests

```python
# Antes
from src.application.use_cases import CreateStoryPlanUseCase

# Después
from src.application.use_cases import DirectorUseCase
```

### 4.4 Actualizar CLI

```python
# Antes
from src.application.use_cases import CreateStoryPlanUseCase, NarrateBeatUseCase

# Después
from src.application.use_cases import DirectorUseCase, VozUseCase
```

---

## 5. Archivos a Modificar

### 5.1 Clases Principales

| Archivo | Acción |
|---------|--------|
| `src/application/use_cases/create_story_plan.py` | Renombrar clase |
| `src/application/use_cases/narrate_beat.py` | Renombrar clase |
| `src/application/use_cases/narrate_batch.py` | Renombrar clase |
| `src/application/use_cases/__init__.py` | Actualizar exports |

### 5.2 Consumidores

| Archivo | Acción |
|---------|--------|
| `src/core/orchestrator.py` | Actualizar imports |
| `src/cli/commands.py` | Actualizar imports |
| `tests/unit/application/test_create_story_plan.py` | Actualizar imports |
| `tests/unit/application/test_narrate_beat.py` | Actualizar imports |

### 5.3 Specs

| Archivo | Acción |
|---------|--------|
| `specs/001_marco_sdd.md` | Actualizar tabla de clases |

---

## 6. Code Style

### 6.1 Después del Renombrado

```python
# src/application/use_cases/director_use_case.py
class DirectorUseCase:
    """Planificación estructural.
    
    Divide la historia en beats lógicos.
    """

# src/application/use_cases/voz_use_case.py
class VozUseCase:
    """Ejecución narrativa.
    
    Transforma el beat en prosa rica y atmosférica.
    """
```

---

## 7. Estructura del Proyecto (Resultante)

```
src/application/use_cases/
├── __init__.py           # Exports: DirectorUseCase, VozUseCase
├── director_use_case.py  # NUEVO NOMBRE (antes create_story_plan.py)
├── voz_use_case.py       # NUEVO NOMBRE (antes narrate_beat.py)
├── voz_batch_use_case.py # NUEVO NOMBRE (antes narrate_batch.py)
├── create_story.py
└── export_story.py
```

---

## 8. Límites (Boundaries)

### Always

- Mantener backwards-compatible durante transición (opcional: alias)
- Ejecutar `make test` antes de commit
- Ejecutar `make lint` antes de commit

### Ask First

- Cambiar nombres de funciones internas
- Modificar lógica de los use cases

### Never

- Eliminar clases sin actualizar todos los consumidores
- Commitear con tests fallando

---

## 9. Success Criteria

- [ ] Clases renombradas: `DirectorUseCase`, `VozUseCase`, `VozBatchUseCase`
- [ ] Todos los imports actualizados
- [ ] Tests pasan: `make test` sin errores
- [ ] Linting pasa: `make lint` sin errores
- [ ] Spec 001 actualizado con nuevos nombres

---

## 10. Hitos

### Hito 1: Renombrar Clases Principales

**Objetivo:**
- **Qué:** Renombrar las clases de use cases
- **Cómo:** Cambiar nombre de clase y docstring

**Tasks:**
- [ ] T.1.1: Renombrar `CreateStoryPlanUseCase` → `DirectorUseCase`
- [ ] T.1.2: Renombrar `NarrateBeatUseCase` → `VozUseCase`
- [ ] T.1.3: Renombrar `NarrateBatchUseCase` → `VozBatchUseCase`
- [ ] T.1.4: Actualizar `__init__.py`

**Criteria:**
- [ ] Clases existen con nuevos nombres

### Hito 2: Actualizar Consumidores

**Objetivo:**
- **Qué:** Actualizar todos los archivos que usan las clases
- **Cómo:** Actualizar imports

**Tasks:**
- [ ] T.2.1: Actualizar `src/core/orchestrator.py`
- [ ] T.2.2: Actualizar `src/cli/commands.py`
- [ ] T.2.3: Actualizar tests

**Criteria:**
- [ ] Todos los imports funcionan

### Hito 3: Verificación

**Objetivo:**
- **Qué:** Ejecutar tests y linting
- **Cómo:** make test && make lint

**Tasks:**
- [ ] T.3.1: Ejecutar `make test`
- [ ] T.3.2: Ejecutar `make lint`
- [ ] T.3.3: Actualizar spec 001

**Criteria:**
- [ ] 100% tests pasan
- [ ] Linting sin errores
- [ ] Spec actualizado

---

## 11. Preguntas Abiertas

1. ¿Mantener backwards-compatible con alias (ej: `CreateStoryPlanUseCase = DirectorUseCase`?
2. ¿Renombrar también los archivos físicos (`.py`) o solo las clases?

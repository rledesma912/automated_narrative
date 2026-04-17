# Spec: Corrección de Bugs Preexistentes

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Borrador  
> **Owner:** Usuario (Auditor)  
> **Tags:** bugfix, testing, exceptions

---

## 1. Objetivo

Corregir los bugs preexistentes identificados durante el desarrollo del spec `005_template_mapper_spec.md`.

**¿Por qué?** Estos bugs causan que 7 tests fallen, lo cual impide validar correctamente la implementación de nuevos features.

---

## 2. Tech Stack

- **Python:** 3.12
- **Framework:** pytest
- **Linting:** ruff

---

## 3. Comandos

```bash
make test
make lint
```

---

## 4. Bug #1: num_beats no definido en CreateStoryPlanUseCase

### 4.1 Descripción

**Archivo:** `src/application/use_cases/create_story_plan.py:60`

**Error:** `NameError: name 'num_beats' is not defined`

**Causa:** El método `_parse_beats` intenta usar `num_beats` en el fallback de generación automática de beats, pero no tiene acceso a esa variable (está en scope del método `execute`).

### 4.2 Solución

Pasar `num_beats` como parámetro al método `_parse_beats`.

```python
# Antes (línea 60)
for i in range(1, num_beats + 1)

# Después
def _parse_beats(self, text: str, story_id, num_beats: int) -> list[Beat]:
    # ... código existente ...
    
    if not beats:
        beats = [
            Beat(number=i, summary=f"Beat #{i} generado automáticamente", status="pending")
            for i in range(1, num_beats + 1)
        ]
    return beats
```

Y actualizar la llamada en `execute`:

```python
beats = self._parse_beats(response.text, story.id, num_beats)
```

### 4.3 Impacto

- **Archivos modificados:** `src/application/use_cases/create_story_plan.py`
- **Tests afectados:** 
  - `test_create_story_plan.py::test_execute_returns_default_beats_on_parse_failure`
  - `test_orchestrator.py::test_orchestrator_run_full_creates_story`
  - `test_orchestrator.py::test_orchestrator_saves_beats`
  - `test_orchestrator.py::test_orchestrator_narrates_beats`
- **Breaking changes:** No

---

## 5. Bug #2: Mensajes de excepción en español vs inglés

### 5.1 Descripción

**Archivo:** `src/cli/exceptions.py`

**Error:** Los tests esperan mensajes en inglés pero el código tiene mensajes en español.

| Test | Esperado | Actual |
|------|----------|--------|
| `test_validation_error_message` | "Validation error" | "Error de validación: {message}" |
| `test_generation_error_message` | "Generation error" | "Error en la generación: {message}" |
| `test_export_error_message` | "Export error" | "Error en la exportación: {message}" |

### 5.2 Análisis

El código de exceptions está en español (decisión de diseño del proyecto). Los tests están mal escritos — deberían verificar el comportamiento real, no el texto en inglés arbitrario.

### 5.3 Solución

Actualizar los tests para verificar el comportamiento correcto (mensajes contienen la causa del error), no el prefijo en inglés.

```python
# Antes (test_exceptions.py)
def test_validation_error_message(self):
    err = ValidationError("Invalid input")
    assert "Validation error" in err.message

# Después
def test_validation_error_message(self):
    err = ValidationError("Invalid input")
    assert "Invalid input" in err.message  # Verifica el mensaje de error
    assert "validation" in err.message.lower()  # Verifica que es de validación
```

### 5.4 Impacto

- **Archivos modificados:** `tests/unit/cli/test_exceptions.py`
- **Tests afectados:** Los 3 mencionados arriba
- **Breaking changes:** No

---

## 6. Estructura del Proyecto (no cambia)

```
src/
├── application/
│   └── use_cases/
│       └── create_story_plan.py  # Bug #1
└── cli/
    └── exceptions.py             # No se modifica (está correcto)
tests/
└── unit/
    └── cli/
        └── test_exceptions.py    # Bug #2
```

---

## 7. Límites (Boundaries)

### Always

- Ejecutar `make lint` antes de commit
- Verificar que todos los tests pasan después de la corrección

### Ask First

- Modificar lógica de excepciones
- Cambiar comportamiento de los use cases

### Never

- Eliminar tests sin aprobacion
- Commitear con tests fallando

---

## 8. Success Criteria

- [ ] Bug #1 corregido: `num_beats` pasa como parámetro
- [ ] Bug #2 corregido: tests verifican comportamiento real
- [ ] Tests pasan: `make test` sin errores
- [ ] Linting pasa: `make lint` sin errores

---

## 9. Hitos

### Hito 1: Corregir Bug #1 (num_beats)

**Objetivo:**
- **Qué:** Pasar `num_beats` como parámetro a `_parse_beats`
- **Cómo:** Modificar firma del método y llamada en `execute`

**Tasks:**
- [ ] T.1.1: Modificar `_parse_beats` para recibir `num_beats`
- [ ] T.1.2: Actualizar llamada en `execute`
- [ ] T.1.3: Verificar que tests pasan

**Criteria:**
- [ ] `test_execute_returns_default_beats_on_parse_failure` pasa

### Hito 2: Corregir Bug #2 (tests de exceptions)

**Objetivo:**
- **Qué:** Actualizar tests para verificar comportamiento correcto
- **Cómo:** Cambiar assertions para verificar mensajes en español

**Tasks:**
- [ ] T.2.1: Corregir `test_validation_error_message`
- [ ] T.2.2: Corregir `test_generation_error_message`
- [ ] T.2.3: Corregir `test_export_error_message`
- [ ] T.2.4: Verificar que tests pasan

**Criteria:**
- [ ] Los 3 tests de exceptions pasan

---

## 10. Preguntas Abiertas

1. ¿Confirmás que los tests deben validar comportamiento en español (ya que el proyecto está en español)?
2. ¿Hay otros bugs preexistentes que deba corregir en este spec?

# Spec: TemplateMapper (Capa de Traducción)

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Borrador  
> **Owner:** Usuario (Auditor)  
> **Tags:** infrastructure, mapper, i18n

---

## 1. Objetivo

Crear una capa de traducción que transforme los inputs del usuario (en español) al modelo del dominio (en inglés), siguiendo la convención del proyecto donde el código está en inglés.

**¿Por qué?** El sistema está escrito en inglés; los prompts y templates usan español para el usuario. El mapper actúa como adapter entre estas dos capas.

---

## 2. Tech Stack

- **Python:** 3.12
- **Librería:** Pydantic (validación), dataclasses
- **Ubicación:** `src/infrastructure/mappers/`

---

## 3. Comandos

```bash
# Verificación
make lint
make test

# Test específico
pytest tests/unit/infrastructure/test_template_mapper.py -v
```

---

## 4. Estructura del Proyecto

```
src/
├── domain/
│   └── models.py          # Story (actual - campos en español)
├── application/
│   └── services/
│       └── prompt_builder.py
├── infrastructure/
│   ├── mappers/          # NUEVO
│   │   ├── __init__.py
│   │   └── template_mapper.py
│   └── adapters/
└── cli/
```

---

## 5. Code Style

### Dominio (inglés)

```python
# src/domain/models.py - CAMPOS NUEVOS (inglés)
class Story(BaseModel):
    # ... campos existentes ...
    
    # Nuevos campos en inglés
    protagonist: str = ""       # antes: protagonista
    atmosphere: str = ""        # antes: atmosfera
    scenarios: str = ""         # antes: escenarios
    synopsis: str = ""          # antes: sinopsis
```

> **Nota:** Mantener campos backwards-compatible durante transición.

### Mapper

```python
# src/infrastructure/mappers/template_mapper.py
from dataclasses import dataclass
from src.domain.models import Story

@dataclass
class TemplateInput:
    """Input del template (español)."""
    title: str
    protagonista: str
    relator: str
    atmosfera: str
    escenarios: str
    sinopsis: str
    reglas: list[str] = None

class TemplateMapper:
    """Adapter: traduce input español → modelo dominio inglés."""
    
    def map(self, input: TemplateInput) -> Story:
        return Story(
            title=input.title,
            protagonist=input.protagonista,
            atmosphere=input.atmosfera,
            scenarios=input.escenarios,
            synopsis=input.sinopsis,
            relator=self._map_relator(input.relator),
            reglas=input.reglas or [],
        )
    
    def _map_relator(self, relator: str) -> str:
        mapping = {
            "tercera_persona": "third_person",
            "primera_persona": "first_person",
        }
        return mapping.get(relator, relator)
```

---

## 6. Estrategia de Testing

| Nivel | Framework | Ubicación | Cobertura |
|-------|-----------|-----------|-----------|
| Unit | pytest | `tests/unit/infrastructure/` | 100% |

### Casos de Test

```python
def test_map_basic_fields():
    input = TemplateInput(
        title="La Casa Abandonada",
        protagonista="María",
        relator="tercera_persona",
        atmosfera="terror",
        escenarios="Casa embrujada",
        sinopsis="Una historia"
    )
    story = mapper.map(input)
    
    assert story.title == "La Casa Abandonada"
    assert story.protagonist == "María"
    assert story.relator == "third_person"
    assert story.atmosphere == "terror"

def test_map_unknown_relator():
    input = TemplateInput(...)
    story = mapper.map(input)
    
    assert story.relator == "unknown_value"  # se mantiene si no está en mapping
```

---

## 7. Límites (Boundaries)

### Always

- Ejecutar `make lint` antes de commit
- Mantener backwards-compatible el modelo Story
- Agregar tests para cada nuevo mapping

### Ask First

- Cambiar estructura de TemplateInput
- Modificar ubicación del mapper
- Agregar nuevos campos al dominio

### Never

- Commitear sin tests
- Eliminar campos del dominio sin migrar
- Hardcodear secrets en mapper

---

## 8. Success Criteria

- [ ] `TemplateMapper` creado en `infrastructure/mappers/`
- [ ] Modelo `Story` tiene campos en inglés (`protagonist`, `atmosphere`, `scenarios`, `synopsis`)
- [ ] Tests pasan con coverage > 80%
- [ ] Linting pasa sin errores
- [ ] Mapper usado por `PromptBuilder` o CLI

---

## 9. Hitos

### Hito 1: Modelo Domain (Inglés)

**Objetivo:**
- **Qué:** Agregar campos en inglés al modelo Story
- **Cómo:** Añadir campos paralelos al modelo existente, mantener backwards-compatibility

**Tasks:**
- [ ] T.1.1: Agregar campos inglés a Story en `domain/models.py`
- [ ] T.1.2: Crear test unitario para nuevos campos

**Criteria:**
- [ ] Story tiene campos `protagonist`, `atmosphere`, `scenarios`, `synopsis`
- [ ] Tests pasan

### Hito 2: TemplateMapper

**Objetivo:**
- **Qué:** Crear mapper que traduzca input español → Story en inglés
- **Cómo:** Implementar adapter en `infrastructure/mappers/template_mapper.py`

**Tasks:**
- [ ] T.2.1: Crear directorio `infrastructure/mappers/`
- [ ] T.2.2: Implementar `TemplateInput` dataclass
- [ ] T.2.3: Implementar `TemplateMapper.map()`
- [ ] T.2.4: Implementar `_map_relator()`
- [ ] T.2.5: Crear tests unitarios

**Criteria:**
- [ ] Mapper traduce todos los campos correctamente
- [ ] Tests unitarios pasan
- [ ] Linting pasa

---

## 10. Preguntas Abiertas

1. ¿El mapping de `relator` debe ser obligatorio o mantener valor original si no está en mapping?
2. ¿Cuándo se migran los campos español → inglés en el resto del código (PromptBuilder, etc.)?

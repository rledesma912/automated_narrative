# Spec 070 — Domain Behavior: Añadir lógica de dominio a entidades

## Problema

Las entidades del dominio (`Story`, `MacroBeat`, `NarrativeJournal`) son **contenedores de datos Pydantic** sin comportamiento. No hay lógica de negocio encapsulada.

### Estado actual (anémico)

```python
# domain/models.py
class Story(BaseModel):
    id: UUID4
    title: str
    status: StoryStatus
    beats: list[Beat] = []
    # Sin métodos, sin validación, sin invariantes

class MacroBeat(BaseModel):
    number: int
    summary: str
    content: str = ""
    status: str = "pending"  # string plano, no enum
    # Sin métodos de validación
```

### Lógica dispersa en use cases

| Validation/Logic | Ubicación actual |
|------------------|------------------|
| `beat.status = "completed"` | `voz_use_case.py:104` |
| `if beat.number == 1` (primer beat) | `prompt_builder.py:181` |
| `if story.beats` (tiene beats) | `voz_use_case.py:52` |
| `if beat.content` (ya narrado) | `prompt_builder.py:668` |
| `len(beats) > 0` | Múltiples lugares |

### Impacto

1. **Violación de Clean Architecture**: El dominio debería ser el centro, no los use cases
2. **Invariantes inseguras**: Es fácil crear estados inválidos
3. **Tests incompletos**: Solo verifican datos, no comportamiento
4. **Acoplamiento**: Cambios de regla de negocio tocan múltiples archivos

---

## Research: qué agregar

### 1. MacroBeat — métodos de dominio

```python
class MacroBeat(BaseModel):
    # ... existing fields ...
    
    # Métodos de dominio (propuestos)
    def is_narrated(self) -> bool:
        """True si el beat tiene contenido narrativo."""
        return bool(self.content and self.status == "completed")
    
    def is_pending(self) -> bool:
        return self.status == "pending"
    
    def can_be_narrated(self) -> bool:
        """Valida que el beat está listo para narrar."""
        return bool(self.summary and not self.content)
    
    def mark_completed(self) -> None:
        """Marca el beat como completado (mutador)."""
        self.status = "completed"
    
    def has_valid_content(self, min_length: int = 50) -> bool:
        """Verifica contenido mínimo."""
        return len(self.content) >= min_length if self.content else False
```

### 2. Story — métodos de dominio

```python
class Story(BaseModel):
    # ... existing fields ...
    
    def is_valid_for_narration(self) -> bool:
        """La historia tiene beats con contenido válido."""
        return any(b.is_narrated() for b in self.beats) if self.beats else False
    
    def get_pending_beats(self) -> list[Beat]:
        """Retorna solo beats pendientes."""
        return [b for b in self.beats if b.is_pending()]
    
    def get_completed_beats(self) -> list[Beat]:
        return [b for b in self.beats if b.is_narrated()]
    
    def has_beats(self) -> bool:
        return len(self.beats) > 0
    
    def beat_count(self) -> int:
        return len(self.beats)
    
    def add_beat(self, beat: Beat) -> None:
        """Agrega beat validando que no haya duplicados."""
        if any(b.number == beat.number for b in self.beats):
            raise ValueError(f"Beat #{beat.number} ya existe")
        self.beats.append(beat)
    
    def complete(self) -> None:
        """Marca historia como completada."""
        if not self.is_valid_for_narration():
            raise ValueError("No se puede completar sin beats narrados")
        self.status = StoryStatus.COMPLETED
```

### 3. NarrativeJournal — métodos de dominio

```python
class NarrativeJournal(BaseModel):
    # ... existing fields ...
    
    def is_empty(self) -> bool:
        return not (self.last_events or self.unresolved_mysteries or self.physical_emotional_state)
    
    def has_meaningful_data(self) -> bool:
        return bool(self.last_events)
    
    def merge_with(self, other: "NarrativeJournal") -> "NarrativeJournal":
        """Combina dos journals (pararesume)."""
        return NarrativeJournal(
            last_events=other.last_events or self.last_events,
            unresolved_mysteries=f"{self.unresolved_mysteries}\n{other.unresolved_mysteries}" if self.unresolved_mystories else other.unresolved_mysteries,
            physical_emotional_state=other.physical_emotional_state or self.physical_emotional_state,
        )
```

---

## Decisión de diseño

**Acción mínima viable**: Agregar métodos de consulta (`is_narrated()`, `has_beats()`, etc.) **sin mutadores** que cambien el modelo actual.

### Por qué sin mutadores

1. Los use cases ya manejan el estado explícitamente
2. Agregar mutadores requiere cambiar todos los call sites
3. Mantiene backward compatibility total
4. Reduces blast radius

###Métodos a agregar (v1)

| Entidad | Método | Retorno |
|---------|--------|---------|
| `MacroBeat` | `is_narrated()` | `bool` |
| `MacroBeat` | `is_pending()` | `bool` |
| `MacroBeat` | `has_content()` | `bool` |
| `Story` | `has_beats()` | `bool` |
| `Story` | `beat_count()` | `int` |
| `Story` | `get_pending_beats()` | `list[Beat]` |
| `Story` | `get_completed_beats()` | `list[Beat]` |
| `NarrativeJournal` | `is_empty()` | `bool` |

---

## Plan de slices

```
Slice A — MacroBeat behavior
          + is_narrated(), is_pending(), has_content()
          + tests

Slice B — Story behavior
          + has_beats(), beat_count(), get_pending_beats(), get_completed_beats()
          + tests

Slice C — NarrativeJournal behavior
          + is_empty()
          + tests

Slice D — Refactorizar use cases para usar métodos de dominio
          + Reemplazar "if beat.content" por "if beat.has_content()"
          + Reemplazar "len(story.beats) > 0" por "story.has_beats()"

Slice E — lint + test completo
```

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `src/domain/models.py` | Agregar métodos a las 3 entidades |
| `src/application/use_cases/*.py` | Usar métodos de dominio en lugar de acceso directo |
| `tests/unit/domain/test_models.py` | Agregar tests para nuevos métodos |

## Archivos a NO tocar

- Repositorios (persistencia intacta)
- Routers (API sin cambios)
- CLI commands

---

## Testing

### Tests nuevos

```python
class TestMacroBeatBehavior:
    def test_is_narrated_returns_true_when_content_and_completed(self):
        beat = MacroBeat(number=1, summary="Test", content="Prosa", status="completed")
        assert beat.is_narrated() is True
    
    def test_is_narrated_returns_false_when_pending(self):
        beat = MacroBeat(number=1, summary="Test")
        assert beat.is_narrated() is False
    
    def test_has_content_true_when_content_exists(self):
        beat = MacroBeat(number=1, summary="Test", content="Prosa")
        assert beat.has_content() is True

class TestStoryBehavior:
    def test_has_beats_true_when_beats_exist(self):
        story = Story(beats=[MacroBeat(number=1, summary="Test")])
        assert story.has_beats() is True
    
    def test_get_completed_beats_filters_correctly(self):
        beats = [
            MacroBeat(number=1, summary="A", content="X", status="completed"),
            MacroBeat(number=2, summary="B"),
        ]
        story = Story(beats=beats)
        assert len(story.get_completed_beats()) == 1

class TestNarrativeJournalBehavior:
    def test_is_empty_true_when_no_data(self):
        journal = NarrativeJournal()
        assert journal.is_empty() is True
```

---

## Success Criteria

1. Entidades tienen métodos de consulta sin mutar estado
2. Use cases usan métodos de dominio
3. Tests verifican comportamiento de entidades
4. `make test` pasa
5. `make lint` pasa
6. Zero breaking changes (API unchanged)
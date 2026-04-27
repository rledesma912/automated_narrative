# Spec 080 — Story Decomposition: De God Object a Aggregate Root

## Problema

`Story` en `domain/models.py` es un **God Object** con 15+ campos que mezcla conceptos distintos:

```python
class Story(BaseModel):
    # Identidad
    id: UUID4
    title: str
    
    # Metadata narrativa (del input)
    protagonista: str
    relator: str
    sinopsis: str
    atmosfera: str
    
    # Contenido generado
    beats: list[Beat] = []      # ⚠️ Relación 1:N - debería estar en tabla separada
    scenarios: list[Scenario]   # ⚠️ Relación 1:N
    
    # Estado del pipeline
    journal: NarrativeJournal   # ⚠️ Composición fuerte
    status: StoryStatus
    narrative_brief: str
    
    # Configuración
    reglas: list[str] = []      # ⚠️ Duplicado - typed_rules tiene lo mismo
    storyteller_config: Optional[dict]
    typed_rules: list[TypedRule]
```

### Problemas causados

| Problema | Impacto |
|----------|---------|
| **SRP violado** | Cambios en "metadatos de input" tocan la misma clase que "estado del pipeline" |
| **Relaciones 1:N en memoria** | `beats` y `scenarios` son listas, no referencias a tablas |
| **Campos mezclados** | `reglas` y `typed_rules` son duplicados semánticos |
| **Testing difícil** | Crear un Story para test requiere ~10 campos |

### DB actual

```
story table:
  - id, title, protagonista, relator, sinopsis, atmosfera
  - narrative_brief, storyteller_config, status, created_at
  ⚠️ beats, scenarios, journal, reglas NO están aquí (están desnormalizados)

macro_beat table:
  - story_id (FK), number, summary, content, status, etc.

scenario table:
  - story_id (FK), order_index, name
```

---

## Research: Solución de decompose

### Opción 1: Descomposición completa (风险: alto)

Crear 3 entidades nuevas:
- `StoryCore` — identidad + metadata de input
- `StoryState` — status, narrative_brief, journal
- `StoryContent` — beats, scenarios, reglas

**Problema**: Requiere migración de DB, cambios en todos los repos, routers, tests. Blast radius muy alto.

### Opción 2: Value Objects + Composición (风险: medio)

Crear value objects que encapsulen grupos de campos:

```python
class StoryMetadata(BaseModel):
    """Datos del input del usuario."""
    protagonista: str
    relator: str
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []
    storyteller_config: Optional[dict] = None

class StoryContent(BaseModel):
    """Contenido narrativo generado."""
    beats: list[Beat] = []
    scenarios: list[Scenario] = []
    narrative_brief: str = ""

class Story(BaseModel):
    """Aggregate root - orquesta los value objects."""
    id: UUID4
    title: str
    metadata: StoryMetadata
    content: StoryContent
    status: StoryStatus = StoryStatus.PENDING
    journal: NarrativeJournal
    typed_rules: list[TypedRule] = []
    created_at: datetime
```

**Problema**: Afecta todos los call sites que usan `story.beats`, `story.protagonista`, etc.

### Opción 3: Backward-Compatible Wrapper (风险: bajo) - **ELEGIDA**

Mantener `Story` con los mismos campos pero:
1. Agregar propiedades que delegan a value objects
2. Crear value objects como entidades separadas (opcionales de usar)
3. Los campos existentes siguen funcionando igual

```python
class StoryMetadata(BaseModel):
    """Value object para metadata de input."""
    protagonista: str
    relator: str
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []
    storyteller_config: Optional[dict] = None
    
    @classmethod
    def from_story(cls, story: "Story") -> "StoryMetadata":
        return cls(
            protagonista=story.protagonista,
            relator=story.relator,
            sinopsis=story.sinopsis,
            atmosfera=story.atmosfera,
            reglas=story.reglas,
            storyteller_config=story.storyteller_config,
        )

class Story(BaseModel):
    # ... campos originales ...
    
    # Propiedades de conveniencia (backward compatible)
    @property
    def metadata(self) -> StoryMetadata:
        return StoryMetadata.from_story(self)
    
    @property
    def has_content(self) -> bool:
        return bool(self.beats and any(b.content for b in self.beats))
    
    # Métodos de dominio
    def get_beat_by_number(self, n: int) -> Beat | None:
        return next((b for b in self.beats if b.number == n), None)
```

---

## Decisión de diseño

**Opción 3**: Value objects con backward compatibility máxima.

### Objetivos del spec

1. Crear `StoryMetadata` como value object
2. Agregar métodos de consulta a `Story`
3. Mantener 100% backward compatibility
4. No modificar DB schema (evitar migración)
5. Preparar para futuro Spec 061 (agregar comportamiento)

---

## Value Objects a crear

### StoryMetadata

```python
class StoryMetadata(BaseModel):
    """Metadata de input - todo lo que viene del usuario."""
    protagonista: str
    relator: str
    sinopsis: str
    atmosfera: str
    reglas: list[str] = []
    storyteller_config: Optional[dict] = None
    
    @classmethod
    def from_story(cls, story: Story) -> "StoryMetadata":
        return cls(...)
    
    def has_rules(self) -> bool:
        return bool(self.reglas or self.storyteller_config)
```

### Métodos a agregar en Story

| Método | Descripción |
|--------|-------------|
| `get_beat_by_number(n)` | Retorna beat específico o None |
| `has_beats()` | True si hay beats |
| `beat_count()` | Cantidad de beats |
| `get_pending_beats()` | Beats sin completar |
| `get_completed_beats()` | Beats narrados |
| `has_content()` | True si algún beat tiene content |
| `get_first_beat()` | Beat #1 |
| `get_last_beat()` | Último beat |

---

## Plan de slices

```
Slice A — Crear StoryMetadata value object
          + class StoryMetadata
          + from_story() factory
          + tests

Slice B — Agregar métodos de consulta a Story
          + get_beat_by_number(), has_beats(), beat_count()
          + get_pending_beats(), get_completed_beats()
          + tests

Slice C — Agregar propiedades de conveniencia
          + has_content(), get_first_beat(), get_last_beat()
          + tests

Slice D — Opcional: Agregar TypedRules como value object
          + TypedRules.from_list(reglas)
          + Solo si hay tiempo

Slice E — lint + test completo
```

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `src/domain/models.py` | Agregar StoryMetadata, métodos a Story |
| `tests/unit/domain/test_models.py` | Tests para StoryMetadata y métodos |

## Archivos a NO tocar

- Repositorios (persistencia igual)
- Routers (sin cambios de API)
- Use cases (Backward compatible)
- DB schema

---

## Testing

### Tests para StoryMetadata

```python
class TestStoryMetadata:
    def test_from_story_copia_campos(self):
        story = Story(
            protagonista="María",
            relator="tercera_persona",
            sinopsis="Una historia",
            atmosfera="terror",
            reglas=["regla1"],
        )
        metadata = StoryMetadata.from_story(story)
        
        assert metadata.protagonista == "María"
        assert metadata.relator == "tercera_persona"
        assert metadata.sinopsis == "Una historia"
        assert metadata.atmosfera == "terror"
        assert metadata.reglas == ["regla1"]
    
    def test_has_rules_true_con_reglas(self):
        metadata = StoryMetadata(reglas=["x"])
        assert metadata.has_rules() is True
```

### Tests para métodos de Story

```python
class TestStoryMethods:
    def test_get_beat_by_number_existe(self):
        beats = [MacroBeat(number=1, summary="A"), MacroBeat(number=2, summary="B")]
        story = Story(beats=beats)
        
        beat = story.get_beat_by_number(2)
        assert beat.summary == "B"
    
    def test_get_beat_by_number_no_existe(self):
        story = Story(beats=[MacroBeat(number=1, summary="A")])
        
        assert story.get_beat_by_number(5) is None
    
    def test_get_completed_beats_filtra(self):
        beats = [
            MacroBeat(number=1, content="X", status="completed"),
            MacroBeat(number=2, summary="Y"),
        ]
        story = Story(beats=beats)
        
        completed = story.get_completed_beats()
        assert len(completed) == 1
        assert completed[0].number == 1
```

---

## Success Criteria

1. `StoryMetadata` existe y tiene `from_story()` factory
2. Story tiene métodos: `get_beat_by_number`, `has_beats`, `beat_count`, `get_pending_beats`, `get_completed_beats`
3. Story tiene propiedades: `has_content`, `metadata`
4. Todos los campos originales de Story siguen funcionando igual (backward compatible)
5. `make test` pasa
6. `make lint` pasa
7. Zero breaking changes
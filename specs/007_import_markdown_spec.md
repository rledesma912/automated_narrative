# Spec: Importar Historia desde Markdown

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Implementado (--input funciona correctamente)  
> **Owner:** Usuario (Auditor)  
> **Tags:** CLI, input, markdown, parser

---

## 1. Objetivo

Permitir que el CLI lea una historia desde un archivo Markdown en lugar de recibir múltiples argumentos por línea de comandos.

**¿Por qué?** El archivo `input_stories/el_monte_prohibido.md` contiene la historia completa en un formato legible. El usuario quiere usarlo como input para la generación.

---

## 2. Tech Stack

- **Python:** 3.12
- **Librería:** re (regex), pathlib
- **Ubicación:** `src/infrastructure/parsers/`

---

## 3. Comandos

```bash
# Con archivo
python -m src generate --input el_monte_prohibido.md --beats 10

# Con argumentos (actual)
python -m src generate --title "X" --protagonist "Y" ...
```

---

## 4. Formato del Archivo Input

### 4.1 Estructura Actual

```markdown
# Contexto del relato

**Protagonistas**: Ricardo 35 padre, hombre valiente.
Irene 34 madre, mujer creyente
Mariano 10 hijo
Soledad bebe de meses
María 50 madre de Ricardo, abuela supersticiosa
**relator**: Irene
**Escenarios**: Casa de campo de la abuela
Casa de campo donde ocurre una fiesta
Camino sinuoso en el monte
**Sinopsis**: Una familia concurre una fiesta...

---

## Las reglas de la historia

- Ricardo es esceptico de todo lo paranormal
- La abuela les advierte que no pasen por el monte prohibido
- ...

---

**Acto 1 (Situación inicial)**
Presentación de los personajes...

**Acto 2 (Conflicto inicial)**
...
```

### 4.2 Parser Propuesto

El parser debe extraer:

| Campo en Archivo | Variable | Notas |
|------------------|----------|-------|
| `**Protagonistas**` | `protagonista` | Texto libre |
| `**relator**` | `relator` | primera_persona / tercera_persona |
| `**Escenarios**` | `escenarios` | Texto libre |
| `**Sinopsis**` | `sinopsis` | Texto libre |
| `## Las reglas de la historia` | `reglas` | Lista de items |
| `**Acto N**` | `beats` | Opcional - predefinir actos |

---

## 5. Estructura del Proyecto

```
src/
├── cli/
│   ├── commands.py           # MODIFICAR: agregar --input flag
│   └── runner.py             # MODIFICAR: validar archivo
├── infrastructure/
│   ├── parsers/              # NUEVO
│   │   ├── __init__.py
│   │   └── markdown_parser.py
│   └── mappers/
│       └── template_mapper.py  # EXISTE
```

---

## 6. Code Style

### Parser

```python
# src/infrastructure/parsers/markdown_parser.py
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass
class MarkdownStoryData:
    """Datos extraídos del markdown."""
    title: str
    protagonista: str
    relator: str
    escenarios: str
    sinopsis: str
    reglas: list[str]


class MarkdownStoryParser:
    """Parser para archivos de historia markdown."""
    
    def __init__(self, input_dir: Path | None = None):
        self.input_dir = input_dir or Path("input_stories")
    
    def parse(self, filename: str) -> MarkdownStoryData:
        """Parsea un archivo markdown y extrae los datos."""
        file_path = self.input_dir / filename
        content = file_path.read_text(encoding="utf-8")
        
        return self._extract_data(content, file_path.stem)
    
    def _extract_data(self, content: str, default_title: str) -> MarkdownStoryData:
        """Extrae los campos del contenido."""
        # Extraer protagonista
        protagonista = self._extract_field(content, "Protagonistas", "**Sinopsis**")
        
        # Extraer relator
        relator_match = re.search(r'\*\*relator\*\*:\s*(\w+)', content, re.IGNORECASE)
        relator = relator_match.group(1) if relator_match else "tercera_persona"
        
        # Extraer escenarios
        escenarios = self._extract_field(content, "Escenarios", "**Sinopsis**")
        
        # Extraer sinopsis
        sinopsis = self._extract_field(content, "**Sinopsis**", "---")
        
        # Extraer reglas
        reglas = self._extract_list(content, "Las reglas de la historia")
        
        return MarkdownStoryData(
            title=default_title,
            protagonista=protagonista,
            relator=self._normalize_relator(relator),
            escenarios=escenarios,
            sinopsis=sinopsis,
            reglas=reglas,
        )
    
    def _extract_field(self, content: str, start_marker: str, end_marker: str) -> str:
        """Extrae texto entre dos marcadores."""
        pattern = re.escape(start_marker) + r'(.*?)' + re.escape(end_marker)
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""
    
    def _extract_list(self, content: str, section: str) -> list[str]:
        """Extrae lista de items de una sección."""
        pattern = re.escape(section) + r'\n(.*?)(?:\n---|\n\*\*Acto)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if not match:
            return []
        
        items = re.findall(r'^- (.+)', match.group(1), re.MULTILINE)
        return [item.strip() for item in items]
    
    def _normalize_relator(self, relator: str) -> str:
        """Normaliza relator a valores válidos."""
        relator_lower = relator.lower().strip()
        if "primera" in relator_lower:
            return "primera_persona"
        return "tercera_persona"
```

### Integración con CLI

```python
# En commands.py - función generate
def generate(
    title: str | None = None,
    input_file: str | None = None,  # NUEVO
    # ... resto de args
):
    # Si hay input_file, usar el parser
    if input_file:
        parser = MarkdownStoryParser()
        story_data = parser.parse(input_file)
        # Mapear a Story usando TemplateMapper
        mapper = TemplateMapper()
        # ... crear Story
```

---

## 7. Estrategia de Testing

| Nivel | Framework | Ubicación |
|-------|-----------|------------|
| Unit | pytest | `tests/unit/infrastructure/test_markdown_parser.py` |

### Casos de Test

```python
def test_parse_protagonistas():
    content = "**Protagonistas**: Juan, Pedro"
    data = parser._extract_field(content, "Protagonistas", "**Sinopsis**")
    assert "Juan" in data

def test_parse_relator_primera():
    assert parser._normalize_relator("Irene") == "primera_persona"

def test_parse_relator_tercera():
    assert parser._normalize_relator("tercera persona") == "tercera_persona"

def test_parse_reglas():
    content = "## Las reglas de la historia\n- Regla 1\n- Regla 2"
    reglas = parser._extract_list(content, "Las reglas de la historia")
    assert reglas == ["Regla 1", "Regla 2"]
```

---

## 8. Límites (Boundaries)

### Always

- Mantener compatibilidad con CLI existente (argumentos vs archivo)
- Usar TemplateMapper para traducción español → inglés
- Validar que el archivo existe antes de procesar

### Ask First

- Cambiar formato del archivo markdown
- Agregar nuevos campos al parser

### Never

- Commitear sin tests
- Modificar archivos originales en input_stories/

---

## 9. Success Criteria

- [ ] Parser extrae todos los campos del markdown
- [ ] CLI acepta `--input <archivo>.md`
- [ ] Historia se genera correctamente desde archivo
- [ ] Tests pasan con coverage > 80%
- [ ] Linting pasa sin errores

---

## 10. Hitos

### Hito 1: Parser Markdown

**Objetivo:**
- **Qué:** Crear parser que extraiga datos del archivo markdown
- **Cómo:** Implementar regex y extracción de campos en `infrastructure/parsers/`

**Tasks:**
- [ ] T.1.1: Crear directorio `infrastructure/parsers/`
- [ ] T.1.2: Implementar `MarkdownStoryParser`
- [ ] T.1.3: Implementar `_extract_field`, `_extract_list`, `_normalize_relator`
- [ ] T.1.4: Crear tests unitarios

**Criteria:**
- [ ] Parser extrae protagonista, relator, escenarios, sinopsis, reglas
- [ ] Tests unitarios pasan

### Hito 2: Integración CLI

**Objetivo:**
- **Qué:** Agregar flag `--input` al CLI y conectar con parser
- **Cómo:** Modificar `cli/commands.py` y `cli/runner.py`

**Tasks:**
- [x] T.2.1: Agregar argumento `--input` en runner
- [x] T.2.2: Integrar parser en función `generate`
- [x] T.2.3: Test end-to-end con archivo existente

**Criteria:**
- [x] `python -m src generate --input el_monte_prohibido.md --beats 10` funciona

---

## 12. Nota de Estado Actual

El parser `MarkdownStoryParser` está implementado y funciona correctamente. El flag `--input` está integrado en el CLI.

1. ¿El título debeExtraerse del nombre del archivo o del contenido?
2. ¿Los actos (Acto 1, Acto 2) deben convertirse en beats predefinidos?
3. ¿Validar formato estricto o tolerar variaciones?

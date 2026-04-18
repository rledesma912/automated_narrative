# SPEC 024: Robustez del Parser de Input Markdown

## Estado

> Borrador — pendiente OK del usuario para avanzar a PLAN

---

## 1. Problema

`MarkdownStoryParser` tiene tres fragilidades que causan pérdida silenciosa de datos:

### A — `synopsis: | texto` en la misma línea (el bug reportado)

YAML inválido: el operador `|` (literal block scalar) requiere que el contenido comience en la **línea siguiente** indentado. Si el usuario escribe `synopsis: | texto...`, PyYAML lanza `YAMLError`, el parser cae al fallback regex, que busca formato `**Protagonistas**:` (Markdown), no encuentra nada, y devuelve una historia con todos los campos vacíos. La generación continúa sin error visible.

**Variantes del mismo problema:**
- `synopsis: | texto` — texto en la misma línea que `|`
- `synopsis: > texto` — ídem con folded scalar
- Indentación inconsistente en el bloque multilinea

### B — Fallback silencioso

Cuando el YAML falla, el parser cae al regex sin avisar. El usuario no sabe por qué su historia se genera vacía.

### C — Campos obligatorios no validados

Si `title`, `protagonist`/`protagonista` o `synopsis`/`sinopsis` están vacíos tras el parseo, la generación continúa igual. No hay validación en el parser.

---

## 2. Solución

### 2.1 Pre-procesamiento del frontmatter antes de parsear YAML

Antes de llamar a `yaml.safe_load()`, aplicar un paso de saneamiento al string del frontmatter que detecte y corrija `key: | texto_en_misma_linea`:

```python
def _sanitize_frontmatter(self, raw: str) -> str:
    """
    Detecta 'key: | texto' y lo convierte a bloque YAML válido:
    
    key: |
      texto
    """
    lines = raw.split("\n")
    result = []
    for line in lines:
        match = re.match(r'^(\s*\w[\w\s]*?):\s*[|>]\s+(.+)$', line)
        if match:
            key_part = match.group(1)
            value_part = match.group(2)
            result.append(f"{key_part}: |")
            result.append(f"  {value_part}")
        else:
            result.append(line)
    return "\n".join(result)
```

Este paso se aplica solo antes de `yaml.safe_load()`, no modifica el archivo original.

### 2.2 Continuar el bloque multilinea si las líneas siguientes pertenecen al mismo campo

Si hay líneas subsiguientes sin clave (párrafos continuos de la sinopsis), deben quedar bajo la misma clave. El `|` de YAML ya maneja esto si la indentación es correcta — el saneamiento en 2.1 lo garantiza.

### 2.3 Logging de warning cuando ocurre fallback

```python
except yaml.YAMLError as e:
    logger.warning(
        f"[Parser] YAML inválido en frontmatter: {e}. "
        "Usando fallback regex. Verificar formato del archivo."
    )
```

### 2.4 Validación de campos obligatorios post-parseo

```python
def _validate(self, data: MarkdownStoryData, source: str) -> None:
    """Lanza ValueError si faltan campos obligatorios."""
    missing = []
    if not data.title:
        missing.append("title")
    if not data.protagonista:
        missing.append("protagonist / protagonista")
    if not data.sinopsis:
        missing.append("synopsis / sinopsis")
    if missing:
        raise ValueError(
            f"[Parser] Campos obligatorios faltantes en '{source}': {', '.join(missing)}. "
            "Verificar formato del archivo de input."
        )
```

---

## 3. Formato de Input Documentado

El parser soportará estos formatos para campos de texto largo:

**Formato A — bloque literal (recomendado para multilinea):**
```yaml
synopsis: |
  Primera línea del texto.

  Segundo párrafo.
```

**Formato B — texto en la misma línea del `|` (saneado automáticamente):**
```yaml
synopsis: | Primera línea del texto. Segundo párrafo separado por espacios.
```
*→ el parser lo convierte al Formato A internamente.*

**Formato C — string entre comillas (para texto sin saltos de línea):**
```yaml
synopsis: "Texto en una sola línea sin saltos."
```

---

## 4. Archivos Afectados

| Archivo | Cambio |
|---|---|
| `src/infrastructure/parsers/markdown_parser.py` | Agregar `_sanitize_frontmatter()`, mejorar warning en except, agregar `_validate()` |
| `input_stories/el_monte_prohibido.md` | Corregir `synopsis: | texto` → Formato A (bloque correcto) |

---

## 5. Criterios de Éxito

- [ ] `el_monte_prohibido.md` parsea correctamente con sinopsis multilinea completa
- [ ] `synopsis: | texto en misma línea` se sana automáticamente sin error
- [ ] YAML inválido genera `logger.warning`, no falla silenciosamente
- [ ] Campos obligatorios vacíos lanzan `ValueError` con mensaje claro
- [ ] Tests existentes del parser pasan sin modificación

---

## 6. Boundaries

| Categoría | Regla |
|---|---|
| **Always Do** | Sanear antes de parsear, nunca modificar el archivo original |
| **Always Do** | Validar campos obligatorios tras parseo (title, protagonista, sinopsis) |
| **Never Do** | Continuar la generación con campos vacíos — mejor fallar explícito |

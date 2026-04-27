# SPEC-081: Resonancia de Freytag y Unificación de Nomenclatura

**Estado:** IMPLEMENTANDO
**Fecha:** 2026-04-26
**Autor:** Gemini CLI (Senior Engineer & Professional Writer)
**Relacionado con:** SPEC-038 (Anclajes Originales), SPEC-043 (Semantic Narrative Model)

## 1. Problema Narratológico y Técnico

El sistema actual utiliza la **Pirámide de Freytag** (5 actos) como su esqueleto estructural, pero existe una desconexión entre la teoría literaria y la implementación técnica:

1.  **Asimetría de Datos (4 vs 5):** Existen solo 4 campos de anclaje (`initial_state`, `threat_nature`, `horror_peak`, `spatial_anchor`) para alimentar 5 actos. Esto obliga a reutilizar el estado inicial en el desenlace, ignorando la evolución del personaje y dejando el cierre de la historia sin un "pilar" propio.
2.  **Disonancia Terminológica:** El código utiliza nombres genéricos/técnicos que no inspiran a la VOZ. Un modelo de lenguaje genera mejor prosa cuando recibe conceptos evocadores ("El Espejo Fisurado") que cuando recibe etiquetas descriptivas ("Estado inicial").
3.  **Lógica de Distribución Frágil:** El YAML actual (`llm_beats_definition.yaml`) gestiona prioridades cruzadas de anclajes, lo cual es innecesario si cada acto de Freytag tiene su propia resonancia intrínseca.

## 2. Propuesta: El Analista como Curador de Resonancia

Redefinimos el componente `StoryAnalyst` para que actúe como un curador literario experto. Su objetivo no es resumir la sinopsis, sino extraer la **resonancia sensorial y psicológica** de cada uno de los 5 estadios de Freytag.

### 2.1 Unificación de Nomenclatura (Resonancia Aristotélica)

| Variable en Código | Estadio Freytag (Asociado) | Concepto Literario (Resonancia) |
| :--- | :--- | :--- |
| **`resonance_hamartia`** | Exposition | **El Espejo Fisurado:** La vulnerabilidad psicológica. |
| **`resonance_hybris`** | Rising Action | **La Transgresión:** El inicio de la infección de lo cotidiano. |
| **`resonance_anagnorisis`** | Climax | **La Violación de lo Sagrado:** El detalle sensorial insoportable. |
| **`resonance_peripeteia`** | Falling Action | **La Trampa Espacial:** El entorno como cómplice. |
| **`resonance_residual`** | Resolution | **La Mancha Residual:** El daño permanente o nueva normalidad. |

## 3. Cambios Técnicos Requeridos

### 3.1 Dominio y Configuración Literaria

Se utiliza el archivo `config/llm_narrative_definition.yaml` como fuente de verdad. Este archivo define el esquema de los **5 Pilares de la Resonancia Narrativa**:

```yaml
resonance_pillars:
  - beat: 1
    field: "resonance_hamartia"
    concept: "El Espejo Fisurado"
    ...
```

La entidad `NarrativeAnchors` en `src/domain/models.py` y la tabla en DB usarán exclusivamente estos nombres:

```python
class NarrativeAnchors(BaseModel):
    story_id: UUID4
    resonance_hamartia: str
    resonance_hybris: str
    resonance_anagnorisis: str
    resonance_peripeteia: str
    resonance_residual: str
```


### 3.2 Redefinición del Paso 4 (Resolución Determinística)

El **Paso 4** del proceso de generación (`docs/gen_proc.md`) se redefine por completo:
- **Antes:** Buscaba en el YAML qué 2 anclajes de los 4 disponibles asignar como "principal" y "contexto".
- **Ahora:** Realiza un mapeo directo 1:1. El Beat N recibe el anclaje de resonancia N definido en `llm_narrative_definition.yaml`.
- **Impacto:** Se elimina la complejidad de "prioridades de anclaje". El contexto que recibe la VOZ es ahora más puro y enfocado en la fase narrativa actual.

### 3.3 Elevación del Analista (`story_analyst_compact.md`)

Se reescriben las instrucciones del Analista para exigir un nivel de interpretación literaria superior. Debe buscar el "subtexto" y la "imagen" más que la "acción", basándose en los conceptos aristotélicos.

## 4. Refactorización Arquitectónica y Desacoplamiento

Para evitar que el código sea rígido y dependa de términos literarios específicos, se implementarán los siguientes cambios de diseño:

### 4.1 Analista Agnostico (Data-Driven)
- Se elimina la constante `_ANCHOR_KEYS` del `StoryAnalystService`.
- El servicio cargará las claves de anclaje dinámicamente desde `llm_narrative_definition.yaml`.
- El parser de respuestas LLM se adaptará automáticamente a cualquier número de pilares definidos en el YAML (en este caso, 5).

### 4.2 Registro de Conocimiento Narrativo
- Se centraliza la unión entre `llm_beats_definition.yaml` (estructura) y `llm_narrative_definition.yaml` (sustancia) en el `PromptBuilder` o un servicio de registro dedicado.
- Se elimina la función `resolve_beat_anchors` de `models.py` para evitar lógica de negocio en el archivo de entidades.

### 4.3 Maximización del Tuning Humano (Variables Expuestas)
- Se garantiza que los 5 pilares de resonancia (`resonance_hamartia`, `resonance_hybris`, etc.) estén disponibles como variables de sustitución en **todos** los archivos de prompt (`.md`).
- El `PromptBuilder` inyectará estas variables en el diccionario de contexto global antes de cada llamada al LLM.
- El usuario podrá referenciar cualquier anclaje en cualquier beat mediante la sintaxis `{variable}` en los archivos markdown, permitiendo una experimentación fluida sin modificar el código Python.

## 5. Plan de Implementación (Slices)

### Slice A — Infraestructura, Modelos y Desacoplamiento
- [ ] Actualizar `NarrativeAnchors` en `src/domain/models.py`.
- [ ] Modificar tabla `narrative_anchors` en DB (SQLite).
- [ ] **Refactor:** Hacer que `StoryAnalystService` cargue sus claves desde el YAML.
- [ ] **Habilitación:** Asegurar que `PromptBuilder` exponga los 5 anclajes como variables globales de contexto para los prompts `.md`.

### Slice B — Lógica del Pipeline y Configuración
- [ ] Actualizar `llm_beats_definition.yaml` a v3.0 eliminando `anchor_priorities`.
- [ ] **Redefinir Paso 4:** Actualizar `StoryAnalystService.resolve_beat_anchors` para el mapeo 1:1 directo (Beat N -> Resonance N).
- [ ] Ajustar `PromptBuilder` para ensamblar el `narrative_context` con los nuevos campos de resonancia.

### Slice C — Inteligencia Literaria (Prompts)
- [ ] Rediseñar `story_analyst_compact.md` y su system prompt bajo el nuevo paradigma de "Resonancia".
- [ ] Validar que la extracción genere texto altamente sensorial.

### Slice D — Coherencia Documental y Enfoque Teórico
- [ ] Crear `docs/teoria_resonancia.md` detallando el mapeo entre Aristóteles, Freytag y el sistema.
- [ ] **Documentar Enfoque de Compresión Semántica:** Explicar por qué usamos términos académicos (Hamartia, Hybris) para activar el conocimiento previo del LLM y reducir tokens/alucinaciones.
- [ ] Actualizar `docs/gen_proc.md` para reflejar el proceso de 5 anclajes.

## 5. Criterios de Aceptación

1.  **Validación de Datos:** Cada historia generada debe tener 5 anclajes únicos en DB.
2.  **Coherencia de Cierre:** El desenlace (Beat 5) debe recibir un contexto basado en `freytag_resolution` (la secuela del horror) y no en el estado inicial de la historia.
3.  **Calidad de Prosa:** El prompt enviado al VOZ debe contener frases evocadoras extraídas por el Analista, reduciendo el uso de adjetivos genéricos por parte del modelo.
4.  **Integridad:** `make test` debe pasar tras la actualización del esquema de dominio.

# Spec 030: SynopsisBeatMapper — Mapeo Extractivo de Sinopsis a Estructura de Beats

## Objetivo

Introducir un nuevo use case, `SynopsisBeatMapper`, que reemplaza a `DirectorUseCase`
en el pipeline de planificación. Su responsabilidad: tomar la sinopsis y mapear cada
sección de ella a los beats estructurales definidos en `llm_beats_definition.yaml`,
produciendo summaries que son **extractivos** (anclados en la sinopsis real) y
**estructuralmente alineados** (respetan el intent/must/must_not de cada acto).

### El problema que resuelve

`DirectorUseCase` es **generativo**: inventa beats a partir de la sinopsis.
El modelo puede desviarse, inventar eventos no mencionados, o ignorar la estructura
narrativa al generar. Un approach extractivo es más confiable porque:

1. El modelo no inventa — extrae lo que ya está en la sinopsis.
2. Cada beat queda explícitamente anclado al momento narrativo que le corresponde.
3. La Voz recibe un summary que describe una escena real, no una aspiración.

### Diferencia fundamental con DirectorUseCase

| | `DirectorUseCase` | `SynopsisBeatMapper` |
|---|---|---|
| Enfoque | Generativo ("crear beats para esta historia") | Extractivo ("¿qué dice la sinopsis en este momento narrativo?") |
| Contexto del prompt | Sinopsis + estructura como guías de creación | Sinopsis como fuente de verdad; estructura como lente de análisis |
| Resultado | Beats que el modelo imagina | Beats que la sinopsis describe |
| Riesgo | Invención, desviación | Sínopsis demasiado corta (mitigable) |

---

## Arquitectura

### Posición en el flujo

```
StoryRunner._run_plan():
  ANTES: DirectorUseCase.execute(story) → StoryPlan
  DESPUÉS: SynopsisBeatMapper.map(story)  → list[Beat]
```

El cambio es quirúrgico: solo se modifica `StoryRunner._run_plan()`. Nada más cambia.

### Diagrama de componentes

```
config/llm_beats_definition.yaml
        │ (lee beats_spec via PromptBuilder)
        ▼
SynopsisBeatMapper
  ├── PromptBuilder._format_beats_spec()      (ya existe)
  ├── PromptBuilder._format_beats_spec_compact() (NUEVO — versión abreviada)
  ├── LLMProvider.generate(role="director")   (reutiliza config del director)
  ├── ResponseNormalizer.normalize()          (ya existe)
  └── _parse_beats()                          (lógica compartida con DirectorUseCase)
        │
        ▼
  list[Beat] con summaries extractivos
        │
        ▼
  BeatRepository.save() × N  (desde StoryRunner, igual que antes)
```

### Reutilización de código existente

- **Parser**: `_BEAT_PATTERNS` y la lógica de `_parse_beats()` se mueven a un módulo
  compartido `src/application/services/beat_parser.py` para que tanto `SynopsisBeatMapper`
  como `DirectorUseCase` (deprecated pero mantenido) lo importen.
- **LLM config**: usa `role_config("director")` del perfil activo. No se añade un nuevo
  rol al YAML — el mapeo es una planificación y comparte parámetros con el Director.
- **PromptBuilder**: se le añaden dos métodos nuevos para construir los prompts del mapper.

---

## Diseño de prompts

### `synopsis_mapper.md` — variante `frontier`

```markdown
# TAREA DEL DRAMATURGO

Analizas sinopsis narrativas e identificas qué ocurre en cada momento del arco
dramático. Tu producto son {num_beats} frases, una por acto, que describen con
precisión qué sucede en la sinopsis durante ese momento.

## Historia

- Título: {title}
- Protagonistas: {protagonistas}
- Escenarios: {escenarios}
- Atmósfera: {atmosfera}
- Reglas: {reglas}

## Sinopsis completa

{sinopsis}

## Estructura de actos

{beats_spec}

## Instrucciones

Para cada acto:
- Identifica en la sinopsis el pasaje que corresponde a ese momento narrativo.
- Escribe UNA oración que describe qué ocurre, usando los eventos y personajes
  reales de la sinopsis. No inventes nada que no esté en ella.
- Si la sinopsis no detalla explícitamente ese acto, infiere la conclusión lógica
  más coherente con lo que sí describe.
- La oración debe respetar el `intent` del acto y no violar su `must_not`.

Responde SOLO con {num_beats} líneas numeradas:
1. [oración del acto 1 extraída de la sinopsis]
2. [oración del acto 2 extraída de la sinopsis]
```

### `synopsis_mapper_compact.md` — variante `compact`

```markdown
Analiza esta sinopsis y describe en UNA oración qué ocurre en cada acto.
Usa solo lo que dice la sinopsis. Escribe exactamente {num_beats} líneas.

Sinopsis: {sinopsis}
Protagonistas: {protagonistas}
Atmósfera: {atmosfera}

Actos:
{beats_spec_compact}

Formato — solo estas {num_beats} líneas:
1. [qué pasa en este acto según la sinopsis]
2. [qué pasa en este acto según la sinopsis]
```

`{beats_spec_compact}` es una versión abreviada del YAML: solo `id`, `name` e `intent`.

---

## Hitos

### Hito 1 — `beat_parser.py`: módulo compartido

Crear `src/application/services/beat_parser.py` con:

```python
_BEAT_PATTERNS: list[re.Pattern] = [...]  # mover desde director_use_case.py

def parse_beats(text: str, num_beats: int, story_id=None) -> list[Beat]:
    """Parser defensivo compartido. Activa FALLBACK si ningún patrón matchea."""
    ...
```

Actualizar `director_use_case.py` para importar `parse_beats` en vez de definirlo
localmente. Los tests de Spec 028 no cambian — prueban el comportamiento, no la ubicación.

### Hito 2 — `SynopsisBeatMapper`

Crear `src/application/use_cases/synopsis_beat_mapper.py`:

```python
class SynopsisBeatMapper:
    """Mapea la sinopsis a beats estructurales de forma extractiva."""

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        normalizer: ResponseNormalizer | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer or ResponseNormalizer()

    async def map(self, story: Story) -> list[Beat]:
        """Genera los beats mapeando la sinopsis a la estructura de actos."""
        num_beats = self.prompt_builder.num_beats
        role_cfg = settings.role_config("director")
        model = role_cfg.get("model") or settings.llm_model

        prompt = self.prompt_builder.build_synopsis_mapper_prompt(story)
        system_prompt = self.prompt_builder.build_synopsis_mapper_system(story)

        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=role_cfg.get("temperature", 0.3),
            role="director",
        )

        clean_text = self.normalizer.normalize(response.text, model_name=model)
        beats = parse_beats(clean_text, num_beats, story.id)

        logger.debug(f"[MAPPER] {len(beats)} beats mapeados: {[b.summary[:60] for b in beats]}")
        return beats
```

La temperatura del mapper se fija baja (0.3) porque el objetivo es extracción fiel,
no creatividad. Si `role_cfg` define otra temperatura, se respeta; si no, se usa 0.3.

### Hito 3 — `PromptBuilder`: métodos del mapper

Agregar a `PromptBuilder`:

```python
def _format_beats_spec_compact(self) -> str:
    """Versión abreviada de beats_spec: solo id, name e intent."""
    lines = []
    for beat in self._beats_spec:
        lines.append(
            f"Acto {beat['id']} ({beat['name']}): {beat.get('intent', '')}"
        )
    return "\n".join(lines)

def build_synopsis_mapper_prompt(self, story: Story) -> str:
    """Prompt principal del SynopsisBeatMapper, selecciona variante por perfil."""
    variant = self._get_prompt_variant()         # compact | frontier
    template_file = (
        "synopsis_mapper_compact.md" if variant == "compact"
        else "synopsis_mapper.md"
    )
    template = self._load_prompt(template_file)

    reglas_str = "\n".join([f"- {r}" for r in story.reglas]) if story.reglas else "Ninguna"
    beats_spec = self._format_beats_spec()
    beats_spec_compact = self._format_beats_spec_compact()

    return template.format(
        title=story.title,
        sinopsis=story.sinopsis,
        protagonistas=story.protagonista,
        escenarios=story.escenarios,
        atmosfera=story.atmosfera,
        reglas=reglas_str,
        num_beats=self.num_beats,
        beats_spec=beats_spec,
        beats_spec_compact=beats_spec_compact,
    )

def build_synopsis_mapper_system(self, story: Story) -> str | None:
    """System prompt para el mapper. None en variante compact."""
    if self._get_prompt_variant() == "compact":
        return None     # compact es un solo bloque, sin system separado
    return self.build_system_prompt(story)
```

### Hito 4 — Reemplazar en `StoryRunner`

Modificar `StoryRunner._run_plan()`:

```python
async def _run_plan(self, story: Story) -> list[Beat]:
    """Genera el plan de beats via SynopsisBeatMapper."""
    from src.application.use_cases import SynopsisBeatMapper

    mapper = SynopsisBeatMapper(self.llm, self.prompt_builder, normalizer=self.normalizer)
    t0 = time.perf_counter()
    beats = await mapper.map(story)
    elapsed = time.perf_counter() - t0

    for beat in beats:
        await self.beat_repo.save(beat, story.id)

    self.reporter.plan_done(len(beats), elapsed)
    logger.info(f"[MAPPER] Plan guardado: {len(beats)} beats mapeados", ...)

    return beats
```

`DirectorUseCase` queda como deprecated en `__init__.py` — se mantiene para que los
tests y comandos `plan` de CLI sigan funcionando, pero ya no es el paso principal.

### Hito 5 — Prompts: crear los dos archivos

Crear `config/prompts_generation/synopsis_mapper.md` y
`config/prompts_generation/synopsis_mapper_compact.md` siguiendo el diseño de §Prompts.

### Hito 6 — Tests

`tests/unit/application/test_synopsis_beat_mapper.py` (nuevo):

```python
# test_map_returns_beats_list
# test_map_uses_director_role_config
# test_map_normalizes_response
# test_map_respects_num_beats_from_yaml
# test_map_fallback_on_unreadable_response
# test_compact_variant_omits_system_prompt
```

`tests/unit/application/test_prompt_builder.py` (agregar):

```python
# test_build_synopsis_mapper_prompt_frontier
# test_build_synopsis_mapper_prompt_compact
# test_format_beats_spec_compact_no_must_no_must_not
# test_synopsis_mapper_system_none_for_compact
```

---

## Archivos involucrados

| Archivo | Hito | Operación |
|---|---|---|
| `src/application/services/beat_parser.py` | 1 | Crear — parser compartido |
| `src/application/use_cases/director_use_case.py` | 1 | Importar desde beat_parser |
| `src/application/use_cases/synopsis_beat_mapper.py` | 2 | Crear |
| `src/application/use_cases/__init__.py` | 2 | Exportar `SynopsisBeatMapper` |
| `src/application/services/prompt_builder.py` | 3 | Agregar métodos del mapper |
| `src/application/services/__init__.py` | 3 | Exportar `BeatParser` si aplica |
| `src/core/orchestrator.py` | 4 | Reemplazar DirectorUseCase por SynopsisBeatMapper |
| `config/prompts_generation/synopsis_mapper.md` | 5 | Crear |
| `config/prompts_generation/synopsis_mapper_compact.md` | 5 | Crear |
| `tests/unit/application/test_synopsis_beat_mapper.py` | 6 | Crear |

---

## Criterios de aceptación

- [ ] `pytest tests/ -q` — sin FAILED
- [ ] El log de generación muestra `[MAPPER]` en vez de `[DIRECTOR]` para la planificación
- [ ] Los beats generados tienen summaries reales que mencionan eventos de la sinopsis
  (no "Beat #X generado automáticamente")
- [ ] Con compact (`ollama-llama31`): el system_prompt es `None` en la llamada al LLM
- [ ] Con frontier (`anthropic-sonnet`): el system_prompt es el de `system.md`

---

## Fuera de alcance

- Llamadas LLM individuales por beat (una por cada acto) — puede implementarse si
  la calidad de una sola llamada es insuficiente para sinopsis muy largas.
- Validación de que el summary generado cita texto real de la sinopsis — requiere
  un paso de verificación separado.
- Deprecación formal de `DirectorUseCase` con `DeprecationWarning` — puede hacerse
  en una versión futura.
- Rol `mapper` separado en el YAML — se usa `director` por ahora; si los parámetros
  óptimos divergen, se agrega en un spec de config.

---

## Relación con specs previos

- **Spec 029**: `SynopsisBeatMapper` selecciona la variante de prompt
  (`compact`/`frontier`) igual que `PromptBuilder` para la Voz.
- **Spec 026/027**: no hay cambios al YAML de perfiles ni a `Settings`.
  El mapper reutiliza `role_config("director")`.

---

## Boundaries

| Categoría | Regla |
|---|---|
| **Always Do** | Leer `num_beats` del YAML vía `prompt_builder.num_beats` — nunca hardcodear el número de beats |
| **Always Do** | Usar `role_config("director")` del perfil activo para los parámetros LLM del mapper |
| **Ask First** | Agregar un rol `mapper` separado al YAML (impacta todos los perfiles) |
| **Never Do** | Hardcodear paths al YAML de beats — siempre via `settings.beats_definition_file` |

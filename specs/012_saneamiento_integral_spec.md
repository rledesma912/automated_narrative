# Spec 012: Saneamiento Integral del Sistema

## Objetivo

Revisión total del sistema para sanear código legacy, documentar inconsistencias y normalizar configuración. Esta spec es de **revisión y análisis**, sin fase de testing.

---

## 1. Prompts Obsoletos a Eliminar

### 1.1 Prompts en desuso

| Archivo | Estado | Acción |
|---------|--------|--------|
| `config/prompts_generation/planner_prompt_narrative.md` | ❌ Legacy | Eliminar - fue reemplazado por lógica dinámica |
| `config/prompts_generation/planner_prompt.md` | ❌ Sin uso | Eliminar - no se carga en código |
| `config/prompts_generation/system_prompt.md` | ❌ Sin uso | Eliminar - no se carga en código |
| `config/prompts_sanitize/*` | ❌ Nunca implementado | Eliminar directorio completo |
| `templates/story_script_output.md.j2` | ❌ Sin uso | Eliminar - no se usa en el flujo actual |
| `templates/story_prompt.input.md.j2` | ❌ Sin uso | Eliminar - no se usa en el flujo actual |

### 1.2 Prompts activos

| Archivo | Uso actual | Estado |
|---------|------------|--------|
| `config/prompts_generation/voice.md` | ✅ VozUseCase | **Activo** - usado en `prompt_builder.py` |
| `config/prompts_generation/system.md` | ✅ PromptBuilder | **Activo** - usado en `build_system_prompt()` |
| `config/prompts_generation/journal.md` | ✅ MemoryJournalist | **Activo** - usado en `memory_journalist.py` |

---

## 2. Componentes en Uso vs Legacy

### 2.1 Componentes Activos ( Flow )

```
StoryRunner (orchestrator.py)
    ├── CreateStoryUseCase (create_story.py)
    ├── DirectorUseCase (director_use_case.py)
    │       └── PromptBuilder.build_planner_prompt()
    │              └── [templates: NONE - fallback dinámico]
    ├── VozUseCase (voz_use_case.py)
    │       └── PromptBuilder.build_beat_prompt()
    │              └── templates/prompts_generation/voice.md ✅
    │       └── PromptBuilder.build_voice_prompt()
    │              └── templates/prompts_generation/system.md ✅
    └── MemoryJournalist (memory_journalist.py)
            └── PromptBuilder.build_journal_prompt()
                   └── templates/prompts_generation/journal.md ✅
```

### 2.2 Componentes Legacy/No usados

| Componente | Archivo | Estado | Notas |
|------------|---------|--------|-------|
| TemplateMapper | `infrastructure/mappers/template_mapper.py` | ❌ Legacy | No se usa en flow actual |
| Normalizer | `infrastructure/normalizers/response_normalizer.py` | ❌ Legacy | No se usa en flow actual |
| VozBatchUseCase | `application/use_cases/voz_batch_use_case.py` | ❌ Legacy | No instanciado en orchestrator |
| ExportStoryUseCase | `application/use_cases/export_story.py` | ⚠️ Parcial | Usado por CLI commands.py |

### 2.3 Acción

- [x] Eliminar: `config/prompts_sanitize/`
- [x] Eliminar: `templates/story_script_output.md.j2`
- [x] Eliminar: `templates/story_prompt.input.md.j2`
- [ ] Evaluar: `infrastructure/mappers/template_mapper.py` (sin uso) - **MANTENER por ahora**
- [ ] Evaluar: `infrastructure/normalizers/response_normalizer.py` (sin uso) - **MANTENER por ahora**
- [ ] Evaluar: `application/use_cases/voz_batch_use_case.py` (sin uso) - **MANTENER por ahora**

---

## 3. Inconsistencias Documentación vs Código

### 3.1 Spec 001 vs Código

| Item | Spec 001 dice | Código tiene | Status |
|------|--------------|--------------|--------|
| Modelo principal | `qwen3.5:9b` | `llama3.1:8b` / `natsumura` | ⚠️ Desactualizado |
| Modelo alternativo | `gemma4:e4b` | `mistral:latest` | ⚠️ Desactualizado |
| Modelo codificación | `qwen2.5-coder:7b-instruct` | ✅ Igual | OK |
| Puerto API | 8010 | ✅ 8010 | OK |
| Puerto UI | 3010 | ✅ 3010 | OK |
| Puerto Ollama | 11434 | ✅ 11434 | OK |
| Director | `DirectorUseCase` | ✅ Implementado | OK |
| Voz | `VozUseCase` | ✅ Implementado | OK |
| Journalist | `MemoryJournalist` | ✅ Implementado | OK |

### 3.2 Specs No Finalizadas

| Spec | Estado | Notas |
|------|--------|-------|
| 004_cli_robust_spec.md | 🔄 Parcial | CLI funciona pero specs de "estado" no actualizadas |
| 005_template_mapper_spec.md | 🔄 Borrador | Mapper no usado - revisar si eliminar |
| 006_bugs_preexistentes_spec.md | 🔄 Borrador | Pendiente análisis |
| 007_gemini_provider_spec.md | 🔄 Draft | Gemini no implementado en producción |
| 007_import_markdown_spec.md | 🔄 Borrador | Parser implementado pero specs desactualizadas |
| 008_refactor_roles_spec.md | 🔄 Borrador | Pendiente |
| 008_gemini_cli_spec.md | 🔄 Draft | Pendiente |
| 009_beats_narrativos_spec.md | 🔄 Borrador | Pendiente |
| 010_testing_segmentado_spec.md | 🔄 Borrador | Pendiente |
| 011_beat_parsing_spec.md | 🔄 Recientemente implementada | Sin testing formal |

### 3.3 Acción

- [ ] Actualizar spec 001 con modelos actuales: `llama3.1:8b` o `natsumura`
- [ ] Marcar specs obsoletas como "Deprecated" o eliminarlas
- [ ] Consolidar specs 007 (dos specs con mismo número)

---

## 4. Hardcoding a Variables de Entorno

### 4.1 Hardcodings encontrados

| Ubicación | Hardcoded | Sugerido |
|-----------|-----------|----------|
| `prompt_builder.py` | Fallback prompts hardcodeados | ⚠️ Los prompts themselves podrían estar en .env |
| `config/prompts_dir` | `"config/prompts"` | ✅ Ya en settings, no hardcoded |
| `config/output_dir` | `"output_stories"` | ✅ Ya en settings |
| `input_stories` | hardcoded en `markdown_parser.py:26` | `PROMPTS_DIR` o `INPUT_DIR` en .env |

### 4.2 Nombres de archivos de prompts

Los nombres de archivos de prompts están **hardcodeados** en el código:

```python
# prompt_builder.py
self._voice_template = self._load_prompt("voice.md")
self._system_template = self._load_prompt("system.md")
self._journal_template = self._load_prompt("journal.md")
self._planner_template = self._load_prompt("planner.md")
```

**Propuesta de variables en .env:**

```env
# Nombres de archivos de prompts (opcional, default si no existen)
PROMPT_FILE_VOICE=voice.md
PROMPT_FILE_SYSTEM=system.md
PROMPT_FILE_JOURNAL=journal.md
PROMPT_FILE_PLANNER=planner.md
```

### 4.3 Acción

- [ ] Agregar `PROMPT_FILE_VOICE`, `PROMPT_FILE_SYSTEM`, `PROMPT_FILE_JOURNAL` a .env
- [ ] Agregar `INPUT_DIR` a .env (currently hardcoded "input_stories" in parser)
- [ ] Modificar `PromptBuilder` para leer nombres de archivos desde settings
- [ ] Modificar `MarkdownStoryParser` para usar setting de input_dir

---

## 5. Templates Input/Output - Análisis de Mapeo

### 5.1 Input: YAML Frontmatter vs Código

**Archivo input:** `input_stories/el_monte_prohibido.md`

```yaml
---
title: "El Monte Prohibido"
protagonist: "..."         # ✓ usado (parser traduce a protagonista)
storyteller: "Irene"       # ❌ NO USADO en parser
atmosphere: "terror..."    # ✓ usado (parser traduce a atmosfera)
scenarios: "..."           # ✓ usado
synopsis: "..."            # ✓ usado
rules:                     # ✓ usado
  - "..."
---
```

| Campo YAML | Parser | Uso en Generación | Notas |
|------------|--------|-------------------|-------|
| title | ✅ | ✅ | OK |
| protagonist | ✅ → protagonista | ✅ | OK |
| storyteller | ❌ | ❌ | **No mapeado** - podría setear relator |
| atmosphere | ✅ → atmosfera | ✅ | OK |
| scenarios | ✅ → escenarios | ✅ | OK |
| synopsis | ✅ → sinopsis | ✅ | OK |
| rules | ✅ → reglas | ✅ | OK |

### 5.2 Output: Markdown Export

El export usa `MarkdownRenderer` (renderer.py) que genera:

```markdown
# {title}

**Protagonistas:** {protagonista}
**Relator:** {relator}
**Escenario:** {escenarios}
**Atmósfera:** {atmosfera}

_{sinopsis}_

---

## 1. {beat.summary}
{beat.content}

## 2. {beat.summary}
{beat.content}
...
```

| Campo | En Output | Notas |
|-------|----------|-------|
| title | ✅ | OK |
| protagonista | ✅ | OK |
| relator | ✅ | OK |
| escenarios | ✅ | OK |
| atmosfera | ✅ | OK |
| sinopsis | ✅ | OK |
| reglas | ❌ | **No se exportan** - podría incluirse |

### 5.3 Matching Input → Output

| Input (YAML) | Output (Markdown) | Match |
|-------------|-------------------|-------|
| title | # title | ✅ |
| protagonist | **Protagonistas:** | ✅ |
| storyteller | **Relator:** | ⚠️ Input usa "storyteller", código usa "relator" |
| atmosphere | **Atmósfera:** | ✅ |
| scenarios | **Escenario:** | ✅ |
| synopsis | _sinopsis_ | ✅ |
| rules | (no exportado) | ❌ |

### 5.4 Acción

- [ ] Agregar mapeo `storyteller` → `relator` en parser (si storyteller existe, usarlo)
- [ ] Incluir `reglas` en el output del export
- [ ] Normalizar nombres: input usa inglés (storyteller), output usa español (Relator)

---

## 6. Resumen de Cambios Recomendados

### 6.1 Eliminación (Limpieza)

```bash
# Prompts legacy
rm config/prompts_generation/planner_prompt_narrative.md
rm config/prompts_generation/planner_prompt.md
rm config/prompts_generation/system_prompt.md
rm -rf config/prompts_sanitize/

# Templates no usados
rm templates/story_script_output.md.j2
rm templates/story_prompt.input.md.j2
```

### 6.2 Configuración (.env)

```env
# Agregar
INPUT_DIR=./input_stories
PROMPT_FILE_VOICE=voice.md
PROMPT_FILE_SYSTEM=system.md
PROMPT_FILE_JOURNAL=journal.md
PROMPT_FILE_PLANNER=planner.md
```

### 6.3 Código

1. Actualizar `config.py` para incluir nuevos settings
2. Modificar `prompt_builder.py` para usar settings de nombres de archivos
3. Modificar `markdown_parser.py` para usar `settings.input_dir`
4. Modificar `markdown_renderer.py` para incluir reglas en output
5. Eliminar/evaluar componentes legacy (template_mapper, normalizer, voz_batch)

### 6.4 Documentación

1. Actualizar spec 001 con modelos actuales
2. Marcar specs obsoletas como deprecated
3. Consolidar specs duplicadas (007)

---

## 7. Notas Adicionales

- El sistema actual **funciona correctamente** para el flujo básica: generate → plan → narrate → export
- Los problemas de refusals son del modelo (Llama3.1), no del código
- El parsing de beats ya fue arreglado en spec 011
- La generación con Tohur/natsumura funciona pero es más lenta (~40s/beat vs ~10s/beat)
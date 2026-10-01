# SPEC-620: Los prompts viven en Markdown, no en el código

**Fecha:** 2026-09-30
**Tipo:** SDD, deuda técnica (refactor sin cambio de comportamiento)
**Estado:** IMPLEMENT — S0 ✅, S1 ✅, S2 ✅ (2026-10-01)
**Rama:** `refactor/spec-620-prompts-en-markdown` (desde `development`, `3753205`). Va antes de la 610 (Spec-610 D12).
**Origen:** observación del usuario (2026-09-30): «los prompts están hardcodeados en vez de vivir en un markdown que se inyecta».

---

## PRINCIPIO

**Todo texto que lee un LLM vive en `config/prompts_generation/`.** El código Python calcula **datos** (qué hechos van, qué rasgos, qué avisos, qué personajes) y elige **qué plantilla** se usa; nunca escribe la redacción de una instrucción ni el título de una sección.

**Todo texto que lee una persona y sale del Core vive en `config/`**, igual que ya viven las opciones (`authoring_options.yaml`) y los criterios del taller (`workshop_criteria.yaml`).

**El refactor no cambia ni una letra de lo que ve el LLM.** Se verifica con el snapshot de los prompts (`tests/fixtures/snapshots/pipeline_prompts.json`), que tiene que quedar **idéntico**, byte a byte.

---

## 1. DIAGNÓSTICO (medido el 2026-09-30)

Las **plantillas principales** ya están en Markdown: 12 archivos en `config/prompts_generation/` (system y user de Consultor, Planificador, Verificador, Voz y Memoria, más `voice_craft.md` y `voice_cliches.txt`) cargados por `TemplateLoader`. Lo que **no** está en Markdown son las **secciones dinámicas**: los bloques que aparecen o no según los datos de la historia se arman en Python, con título e instrucción incluidos.

### 1.1 Texto para el LLM escrito en Python

| Archivo | Textos | Ejemplos | Desde |
|---|---|---|---|
| `authoring/outline_narrator.py` (Voz y Memoria) | ~10 | «LA HISTORIA, PARA QUE CONOZCAS A … (no cuentes nada de acá…)», «CÓMO ESTÁ … AHORA (no lo contradigas)», «ASÍ ES … (mantenelo; podés sumar)», «ASÍ TERMINÓ EL ACTO ANTERIOR…», «CÓMO SE LLEGA A ESTE ACTO…», «EN LA VERSIÓN ANTERIOR DE ESTE ACTO PASÓ ESTO — NO LO VUELVAS A HACER», «AMENAZA EN ESTE ACTO…», «NO REVELES TODAVÍA», los avisos de `_avoid()` («Tenía N oraciones cortadas…: escribí oraciones completas») | Spec-530, 560 y **590** |
| `authoring/context.py` (asistente) | ~6 | «(DECIDIDO POR EL AUTOR: no se discute ni se cambia)», «EFECTO QUE BUSCA EL AUTOR…», «CÓMO TIENE QUE PEGAR…» | Spec-530, 560 |
| `authoring/planner.py` | ~5 | «LO QUE EL AUTOR ESCRIBIÓ PARA CADA ACTO (respetalo…)», «PROBLEMAS QUE MARCÓ LA REVISIÓN…» | Spec-560, 570 |
| `prompt_builder.py` | ~4 | «CÓMO LLAMÁS A CADA PERSONAJE (sos …)» | Spec-470 |
| `narrator_retry_generator.py` | 2 | `_REPHRASE_HINT`, en inglés («ATTENTION: Write naturally…») | anterior a la 530 |

**Por qué pasó:** cada spec sumó una sección chica y condicional («si hay premisa», «si hay rasgos»), y lo más corto era escribirla junto al `if` que la decide. Ninguna spec lo prohibió y ningún test lo detecta. La Spec-590 (S1 y S3) sumó varias de estas secciones: es deuda de este mismo proyecto, no heredada.

### 1.2 Texto para personas escrito en Python

| Archivo | Qué | Ejemplos |
|---|---|---|
| `authoring/workshop_rules.py` | Mensajes del cierre de cada ronda de preguntas | «Tu historia ya tiene todo lo que hace falta. Ya podés armar los actos.» |
| `authoring/verifier.py` | Avisos por regla de la escaleta | los de `sin_hechos`, `sin_cambio`, `sin_puente`, elenco, siembras |
| `adapters/anthropic_adapter.py` | Mensajes de la Spec-600 D3 (`_UNAVAILABLE`) | «La IA que escribe el relato se quedó sin crédito…» |

### 1.3 Lo que se pierde hoy

- **Ajustar el tono o una instrucción obliga a tocar código** y a pasar por tests de Python, cuando es un cambio de texto.
- **No se ve el prompt entero en un lugar:** para saber qué recibe la Voz hay que leer `outline_voice.md` **y** seguir ~10 funciones de `outline_narrator.py`.
- **No hay versión por perfil:** la Spec-600 S2 (un prompt más liviano para Claude) necesita plantillas por perfil; con secciones en Python eso significa ramas de código.
- **El guion de la Spec-610** va a sumar prompts nuevos: si nace con el mismo patrón, la deuda crece.

---

## 2. PROPUESTA

### 2.1 Fragmentos en Markdown

Cada sección condicional pasa a un **fragmento** en `config/prompts_generation/fragments/<rol>/<seccion>.md`, con sus placeholders (`{narrador}`, `{hechos}`…). El código decide **si** la sección va y con **qué datos**; la redacción sale del fragmento:

```python
# Antes (outline_narrator.py)
return f"CÓMO ESTÁ {_upper(narrator)} AHORA (no lo contradigas): {' '.join(parts)}\n"

# Después
return self.templates.fragment("voz/como_esta", narrador=_upper(narrator), estado=" ".join(parts))
```

```markdown
<!-- config/prompts_generation/fragments/voz/como_esta.md -->
CÓMO ESTÁ {narrador} AHORA (no lo contradigas): {estado}
```

`TemplateLoader.fragment(nombre, **datos)` carga, cachea y formatea igual que `load()`. Un fragmento sin datos no se llama: la condición sigue en Python, que es donde corresponde (es lógica, no texto).

### 2.2 Textos para personas en YAML

`config/core_messages.yaml`, por clave (`workshop.listo`, `workshop.max_rondas`, `verifier.sin_hechos`, `llm.sin_credito`…), cargado una vez como `authoring_options.yaml`. Mismo tono coloquial (Spec-580).

### 2.3 Un test que no deja volver atrás

`test_prompts_fuera_del_codigo.py`: recorre con `ast` los módulos que arman prompts o mensajes (`application/services/**`, `adapters/**`) y falla si encuentra un literal de texto con espacios de más de N caracteres que no sea docstring, log, SQL ni clave. Es el mismo enfoque que `sin-jerga.view.test.ts` en el frontend. Mientras dura el refactor, una lista de pendientes explícita que se achica slice a slice hasta quedar vacía.

### 2.4 Lo que no entra

- **Cambiar la redacción de ningún prompt.** Si al moverlo se ve algo para mejorar, se anota para otra spec.
- Un motor de plantillas con lógica (Jinja2), salvo que D1 lo decida.
- Los textos de las vistas del frontend (ya viven en `.ejs` y los cubre `sin-jerga`).

---

## 3. PLAN

Inventario medido el 2026-09-30 con un recorrido `ast` de `src/` (literales con espacios, sin docstrings ni logs). Criterio: **texto para el LLM → fragmento `.md`; texto que llega a la pantalla → `core_messages.yaml`; texto técnico** (404 de desarrollo, logs, SQL, regex, listas de palabras de `repetition_check`) **→ queda en el código**.

| Slice | Qué | Archivos | Verificación |
|---|---|---|---|
| S0 | `TemplateLoader.fragment()` y `MessageCatalog` (`core_messages.yaml`); test guardián con la lista de pendientes | `template_loader.py`, `core_messages.py` (nuevo), `test_prompts_fuera_del_codigo.py` | Guardián en verde listando ~45 pendientes |
| S1 | La Voz y la Memoria: 19 textos de `outline_narrator.py`, 4 de `prompt_builder.py`, el `_REPHRASE_HINT` de `narrator_retry_generator.py`; se borran `format_compact` / `format_for_beat` de `beat_spec_repository.py` (código muerto: solo los usan sus tests) | `fragments/voz/*.md`, `fragments/memoria/*.md` | **Snapshot idéntico** |
| S2 | El asistente: 13 de `context.py`, 7 de `planner.py` (los 2 de validación pasan a mensajes) y los 2 de `verifier.py` que van al LLM («Todavía no se cuenta…») | `fragments/asistente/*.md` | **Snapshot idéntico** |
| S3 | Mensajes: `workshop_rules.py` (7), los avisos por regla de `verifier.py` (7), `_UNAVAILABLE` del adapter (5), etiquetas de etapa de `streaming_service.py` (5), errores de `jobs.py` (3), los 409/422 que se ven en la UI (`job_router`, `authoring_router`, `regenerate_beat_voz_use_case`) | `config/core_messages.yaml` | Tests de vistas, del router y del adapter **sin cambios de texto** |
| S4 | Lista de pendientes vacía; CLAUDE.md («Prompt System» y regla); regla en `010_marco_sdd.md`; `fragments/README.md` | docs | Todo en verde, `make dev-status` |

**Diseño:**

- **`TemplateLoader.fragment(name, **datos) -> str`:** carga `fragments/<name>.md` con caché y `str.format(**datos)`. A diferencia de `load()`, **no hace `strip()`**: quita solo el último salto de línea del archivo y respeta los saltos de línea que la sección necesita (muchas secciones terminan en `\n`). Un fragmento con un placeholder que falta es un `KeyError` (falla en los tests, nunca en silencio).
- **Fragmentos por rol:** `fragments/voz/` (puente, final_anterior, historia, como_esta, asi_es, meta, cambio, no_revelar, amenaza, version_anterior, ya_paso_vacio…), `fragments/memoria/`, `fragments/asistente/` (contexto, efecto, decisiones, escaleta_autor, problemas_revision…). `fragments/README.md` dice en qué orden arma cada rol su prompt.
- **`MessageCatalog`** (`src/application/services/core_messages.py`): carga `config/core_messages.yaml` una vez, `messages.get("workshop.listo", **datos)`. Claves por área: `workshop.*`, `verifier.*`, `llm.*`, `stage.*`, `job.*`, `api.*`. Si falta una clave, `KeyError` (lo atrapa un test que recorre todas las claves usadas).
- **Plurales** (`Te queda{n}`, `quedan N preguntas`): dos claves (`…_uno` / `…_varios`); el código elige cuál. Nada de lógica de idioma en el YAML.
- **Test guardián** (`tests/unit/test_prompts_fuera_del_codigo.py`): recorre con `ast` `src/application`, `src/infrastructure/adapters` y `src/presentation/routers`; falla con un literal de más de 18 caracteres con espacios que no sea docstring, argumento de `logger.*`, SQL, regex (`re.compile`) ni una constante de una lista permitida explícita (con motivo por entrada). Mientras dure el refactor, `PENDIENTES` lista lo que falta; el test también falla si algo de `PENDIENTES` ya no está (para que la lista solo se achique).

## 4. RIESGOS

| Riesgo | Mitigación |
|---|---|
| Un espacio o salto de línea de más cambia el prompt | Snapshot byte a byte; los fragmentos se cargan sin `strip()` salvo el salto final, igual que `load()`. |
| Llaves `{}` literales en un fragmento rompen `str.format` | Test de carga de todos los fragmentos con datos de ejemplo. |
| Muchos archivos chicos, difíciles de recorrer | Una carpeta por rol y un `README.md` en `fragments/` con el orden en que arman el prompt. |

---

## 5. DECISIONES

| # | Decisión | Estado |
|---|---|---|
| D1 | ¿Fragmentos con `str.format` o Jinja2? | ✅ (usuario, 2026-09-30) **Fragmentos + `str.format`**: sin dependencias nuevas, la lógica queda en Python. |
| D2 | ¿Cuándo? | ✅ (usuario, 2026-09-30) **Antes de la 610.** |
| D3 | ¿Los mensajes para personas entran acá? | ✅ (usuario, 2026-09-30) **Sí, a `config/core_messages.yaml`** (S3). |

---

## 6. TASKS

Cada slice cierra con `make lint`, `make test`, `cd frontend && npm test`, `npx playwright test` en verde (output filtrado) y `make dev-status`. Commit por slice. Sin llamadas a ningún LLM: el snapshot compara los prompts sin generar.

### S0 — Mecanismo y guardián
- [x] T0.1 `TemplateLoader.fragment()` (sin `strip`, quita solo el `\n` final, caché, `KeyError` si falta un dato). Tests: saltos de línea, caché, dato faltante.
- [x] T0.2 `MessageCatalog` + `config/core_messages.yaml` (vacío con la estructura). Tests: carga, formato, clave faltante.
- [x] T0.3 Test guardián (`tests/unit/test_prompts_fuera_del_codigo.py`) con `PENDIENTES` = 107 textos (S1: 32, S2: 22, S3: 53) y `PERMITIDOS` = 48 técnicos, cada uno con su motivo (404 técnicos, encabezados HTTP, progreso del CLI, observabilidad, listas de palabras de `repetition_check`); los mocks quedan fuera por archivo. S3 suma los 422 de `create_story.py` y los 409 de `story_router`/`stream_router`, que la UI muestra (`asistente.js` lee el `detail`). Un test prueba que detecta textos y saltea docstrings, logs y regex.

### S1 — La Voz y la Memoria
- [x] T1.1 `outline_narrator.py`: los 19 textos a `fragments/voz/` y `fragments/memoria/`.
- [x] T1.2 `prompt_builder.py`: «Sos … y contás…», «CÓMO LLAMÁS A CADA PERSONAJE…» a fragmentos.
- [x] T1.3 `narrator_retry_generator.py`: `_REPHRASE_HINT` a fragmento (se mantiene el texto tal cual; traducirlo cambiaría el prompt: va anotado para otra spec).
- [x] T1.4 `beat_spec_repository.py`: borrar `format_compact` / `format_for_beat` y sus tests (código muerto).
- [x] T1.5 Snapshot **idéntico** (sin `SNAPSHOT_UPDATE`); `PENDIENTES` −32 (todo S1).
- [x] T1.6 (sumado al implementar) Los nombres de los actos que ve la Voz («Exposición», «Clímax»…) pasan de `_ACT_NAMES` a `label` en `llm_beats_definition.yaml`; los textos cortos que el guardián no detecta (`(no se indica)`, `(nada todavía)`, `EL PROTAGONISTA`, `sin rol`, «Qué es», «Límites»…) también van a fragmentos. `repetition_check.ActRepetition.repeated` pasa a datos `(frase, acto)`: el panel los formatea con `message("repeticion.frase")` y la Voz con `voz/evitar/repetida` (la API devuelve el mismo texto). Las funciones de sección de `outline_narrator.py` pasan a métodos (usan el `TemplateLoader` inyectado, sin globales). 38 fragmentos en `fragments/voz/` y `fragments/memoria/`.

### S2 — El asistente
- [x] T2.1 `context.py`: 13 textos a `fragments/asistente/`.
- [x] T2.2 `planner.py`: 5 textos de prompt a fragmentos; los 2 de validación («la escaleta tiene que tener los actos…», «actos sin hechos…») a `core_messages.yaml`.
- [x] T2.3 `verifier.py`: «Todavía no se cuenta…» y «(se revela en el acto N)» a fragmentos.
- [x] T2.4 Snapshot **idéntico**; `PENDIENTES` −22 (todo S2).
- [x] T2.5 (sumado al implementar) **El snapshot del pipeline no cubría** el Consultor ni varias secciones del asistente y de la Voz (decisiones con pregunta, receta del efecto, borradores, problemas de la revisión, la amenaza, parentescos, final del autor…). Dos snapshots nuevos con historias que activan todas las secciones (`assistant_prompts.json`, `voice_prompts.json`), **generados con el código anterior** (worktrees de `28d06e1` y `dca5c25`) y verificados con el nuevo: idénticos. Cada uno trae un test que falla si una sección deja de aparecer. `context.py`: las funciones de texto reciben el `TemplateLoader` como parámetro (sin globales); `OBJETIVO` → `context.objective()`. 37 fragmentos en `fragments/asistente/`; los nombres de los actos del Planificador también salen de `label`.

### S3 — Mensajes para personas
- [ ] T3.1 `workshop_rules.py` (cierre de ronda, con plurales en dos claves) y avisos por regla de `verifier.py` (las claves estables de los avisos, Spec-550 H10, no cambian).
- [ ] T3.2 `anthropic_adapter.py` (`_UNAVAILABLE` → `llm.*`), `streaming_service.py` (`stage.*`), `jobs.py` (`job.*`).
- [ ] T3.3 Los 409/422 visibles de `job_router`, `authoring_router` y `regenerate_beat_voz_use_case` (`api.*`); los 404 técnicos quedan.
- [ ] T3.4 Tests de vistas, routers y adapter **sin cambiar textos esperados**; `sin-jerga` y `gramatica-visual` en verde.

### S4 — Cierre
- [ ] T4.1 `PENDIENTES` vacía y el guardián sin lista temporal.
- [ ] T4.2 `config/prompts_generation/fragments/README.md` (orden de armado por rol).
- [ ] T4.3 CLAUDE.md («Prompt System»: plantillas + fragmentos, `core_messages.yaml`, la regla y el guardián) y regla en `010_marco_sdd.md`.
- [ ] T4.4 PR a `development`. Sin pase a prod obligatorio (no cambia nada visible); va con la 610.


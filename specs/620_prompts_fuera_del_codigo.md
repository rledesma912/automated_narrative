# SPEC-620: Los prompts viven en Markdown, no en el código

**Fecha:** 2026-09-30
**Tipo:** SDD, deuda técnica (refactor sin cambio de comportamiento)
**Estado:** SPECIFY, borrador para iterar con el usuario (decisiones abiertas en §5)
**Rama:** a definir (propuesta: `refactor/spec-620-prompts-en-markdown`, desde `development`, **después de cerrar la Spec-600 y antes de la 610**)
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

## 3. PLAN (borrador)

| Slice | Qué | Verificación |
|---|---|---|
| S0 | `TemplateLoader.fragment()` + test de §2.3 con la lista de pendientes completa (inventario de §1) | El test pasa listando todo lo pendiente |
| S1 | Voz y Memoria (`outline_narrator.py`, `prompt_builder.py`, `narrator_retry_generator.py`) | Snapshot idéntico; pendientes −16 |
| S2 | Asistente (`context.py`, `planner.py`, partes del `verifier.py` que van al LLM) | Snapshot idéntico |
| S3 | Mensajes para personas (§1.2) a `core_messages.yaml` | Tests de vistas y del router sin cambios de texto |
| S4 | Lista de pendientes vacía; CLAUDE.md («Prompt System»: nada de texto de prompt en Python); regla en `010_marco_sdd.md` | Todo en verde |

Sin llamadas pagas ni al modelo local: el snapshot compara los prompts sin generar.

---

## 4. RIESGOS

| Riesgo | Mitigación |
|---|---|
| Un espacio o salto de línea de más cambia el prompt | Snapshot byte a byte; los fragmentos se cargan sin `strip()` salvo el salto final, igual que `load()`. |
| Llaves `{}` literales en un fragmento rompen `str.format` | Test de carga de todos los fragmentos con datos de ejemplo. |
| Muchos archivos chicos, difíciles de recorrer | Una carpeta por rol y un `README.md` en `fragments/` con el orden en que arman el prompt. |

---

## 5. DECISIONES ABIERTAS (de a una)

| # | Decisión | Recomendación |
|---|---|---|
| D1 | ¿Fragmentos con `str.format` (lo que ya se usa) o Jinja2 (condicionales dentro de la plantilla)? | **`str.format` + fragmentos.** Cero dependencias nuevas, mismo mecanismo que hoy, y la lógica queda en Python donde se testea. Jinja2 permitiría ver el prompt entero en un solo archivo, a cambio de lógica en las plantillas. |
| D2 | ¿Cuándo? | **Después de cerrar la Spec-600 y antes de la 610**, para que el guion nazca con el patrón correcto. |
| D3 | ¿Los mensajes para personas (§1.2) entran acá o en otra spec? | **Acá (S3):** es el mismo problema y es chico. |

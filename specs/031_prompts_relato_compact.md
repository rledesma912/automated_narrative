# Spec 031: Prompts Compact orientados al Relato

## Problema

Los prompts compact actuales generan una **historia** (qué ocurre, estructura de actos, eventos).
El objetivo del sistema es generar un **relato**: prosa literaria en primera persona, atmósferico,
con voz narrativa propia. La diferencia no es cosmética — es de intención generativa.

| | Historia (actual) | Relato (objetivo) |
|---|---|---|
| Foco | Eventos / qué ocurre | Experiencia del narrador / cómo se siente |
| Forma | Resumen estructural | Prosa literaria continua |
| Tiempo verbal | Cualquiera | Pasado (recuerdo narrado) |
| Instrucción al modelo | "Escribe el Acto N de M" | "Escribe como si recordaras lo vivido" |
| Anclaje | Estructura narrativa | Voz + atmósfera + momento |

## Archivos a modificar

| Archivo | Cambio |
|---|---|
| `config/prompts_generation/voice_compact.md` | Reescritura total — orientado a relato literario |
| `config/prompts_generation/synopsis_mapper_compact.md` | Reescritura — beats como momentos del narrador |
| `config/prompts_generation/planner_compact.md` | Reescritura — beats como momentos vividos |
| `src/application/services/prompt_builder.py` | Agregar log del template cargado (validación) |

---

## Diseño de prompts

### `voice_compact.md` — nuevo

```markdown
{relator} narra en primera persona lo que vivió esa noche.
Atmósfera: {atmosphere}
Personajes: {protagonistas}
Escenarios: {escenarios}
Reglas del relato: {reglas}

--- LO QUE PASÓ ANTES ---
{previous_context}

--- ESTADO DEL RELATO ---
{journal_context}

--- ESCRIBE EL SIGUIENTE FRAGMENTO ---
Lo que ocurre en este momento: {beat_summary}

Escribe 150-250 palabras en primera persona, tiempo pasado, prosa literaria.
Sin títulos. Sin aclaraciones. Continúa el relato:
```

Cambios respecto al actual:
- Quitado "Acto N de M" — el modelo no ve numeración estructural
- "narra en primera persona lo que vivió" reemplaza "Escribe el Acto"
- "tiempo pasado" ancla la voz (recuerdo narrado)
- "prosa literaria" reemplaza "prosa continua en español"
- "Continúa el relato" reemplaza "Continúa" (ancla al relato, no a completar texto)

### `synopsis_mapper_compact.md` — nuevo

```markdown
Sos el dramaturgo de este relato. Describí en UNA oración el momento que vive el narrador en cada fragmento.
Usá solo lo que dice la sinopsis. Exactamente {num_beats} líneas.

Sinopsis: {sinopsis}
Narrador: {protagonistas}
Atmósfera: {atmosfera}

Fragmentos del relato:
{beats_spec_compact}

Formato — solo estas {num_beats} líneas numeradas:
1. [momento que vive el narrador en este fragmento]
2. [momento que vive el narrador en este fragmento]
```

Cambios:
- "dramaturgo de este relato" en lugar de "Analiza esta sinopsis"
- "momento que vive el narrador" en lugar de "qué pasa en este acto"
- "Fragmentos del relato" en lugar de "Actos"

### `planner_compact.md` — nuevo

```markdown
Sos el director de "{title}". Escribí exactamente {num_beats} líneas describiendo el momento que vive el narrador en cada fragmento del relato.

Sinopsis: {sinopsis}
Narrador/Protagonistas: {protagonistas}
Atmósfera: {atmosfera}
Reglas: {reglas}

Fragmentos que debés cubrir:
{beats_spec}

Escribí solo las {num_beats} líneas numeradas, sin texto adicional:
1. [momento concreto que vive el narrador en este fragmento]
2. [momento concreto que vive el narrador en este fragmento]
```

Cambios:
- "momento que vive el narrador en cada fragmento del relato" reemplaza "qué ocurre en cada acto"
- "Fragmentos" reemplaza "Actos"
- "Narrador/Protagonistas" reemplaza "Protagonistas" (pone al narrador al frente)

---

## Validación: log del template cargado

En `PromptBuilder._load_prompt()`, agregar log con el nombre del archivo cargado y su longitud:

```python
logger.debug(f"[PB] template loaded: {filename} ({len(content)} chars)")
```

Esto permite verificar en el log qué template se usó en cada generación sin ambigüedad.

---

## Criterios de aceptación

- [ ] `pytest tests/ -q` — sin FAILED
- [ ] El log muestra `[PB] template loaded: voice_compact.md` para perfiles compact
- [ ] El prompt de Voz no contiene "Acto N de M"
- [ ] El prompt de Voz contiene "primera persona" y "tiempo pasado"
- [ ] El beat_summary sigue siendo la última instrucción antes de "Continúa"
- [ ] Los beats del mapper describen "momentos del narrador", no solo eventos

---

## Fuera de alcance

- Cambios en `voice.md` o `synopsis_mapper.md` (frontier) — esos prompts funcionan bien
- Nuevas variables de template — se reusan las existentes
- Cambio en el número de palabras objetivo (150-250 se mantiene)

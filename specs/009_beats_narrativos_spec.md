# Spec: Estructura de Beats Narrativos para Relatos de Terror

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Borrador  
> **Owner:** Usuario (Auditor)  
> **Tags:** beats, narrative, terror, structure, save-the-cat

---

## 1. Objetivo

Redefinir la estructura de beats del sistema para que se adapte a **narrativa literaria de terror** en lugar de guión cinematográficothe. El sistema debe generar relatos immersivos con profundidad atmosférica, usando una estructura de 6 beats optimizada pararelatos.

**¿Por qué?** Save the Cat está diseñado para guiones (110 páginas). Para relatos de terror narrativo, necesitamos una estructura más simple que permita:
- Profundizar en atmósfera
- Describir sensaciones físicas
- Crear tensión sin acción constante
- Mantener coherencia narrativa

---

## 2. Estructura de Beats Narrativos (Propuesta)

### 2.1 Los 6 Beats para Relatos de Terror

| Beat | Nombre | Porcentaje | Descripción |
|------|--------|------------|-------------|
| 1 | **Apertura** | 1-10% | El mundo ordinario. El miedo sutil existe pero no domina. Establecer escenario, personajes, tensión latente. |
| 2 | **Incidente** | 10-20% | Algo rompe la normalidad. Primera señal de lo paranormal. El protagonista nota que algo está mal. |
| 3 | **Subida** | 20-50% | Tensión crescente. Las señales se multiplican. Apariciones sutiles, sonidos inexplicables, malaise. |
| 4 | **Crisis** | 50-75% | El mundo se vuelve hostil. Apariciones klaras, fenómenos paranormales, el horror se manifiesta. |
| 5 | **Cumbre** | 75-85% | Todo parece perdido. El protagonista enfrenta el horror máximo. Punto más oscuro. |
| 6 | **Desenlace** | 85-100% | Resolución. Escapan del horror (o no). El precio del encounters. Amanecer, salida, cierre. |

### 2.2 Diferencias Clave con Save the Cat

| Aspecto | Save the Cat (Guión) | Beats Narrativos (Relato) |
|--------|---------------------|---------------------------|
| Cantidad | 15 beats | 6 beats |
| Longitud | 110 páginas ~90-100K palabras | Flexible (3K-15K palabras) |
| Énfasis | Acción, giros | Atmósfera, sensations |
| Estructura | Rigidez (% exactos) | Flexibilidad (rangos) |
| B Story | Importante | No necesario |

---

## 3. Assumptions

1. El sistema usa un LLM local (Ollama) para generar contenido
2. El sistema persiste en SQLite y exporta a Markdown
3. El CLI permite generar desde archivo input_stories/
4. El Director genera beats y la Voz narra cada uno

---

## 4. Tech Stack

- **Python:** 3.12
- **Framework:** FastAPI + CLI
- **LLM:** Ollama (qwen3.5:9b)
- **DB:** SQLite (aiosqlite)
- **Testing:** pytest + pytest-asyncio

---

## 5. Comandos

```bash
# Generación con archivo
python -m src generate --input el_monte_prohibido.md --beats 6 --real

# Generación con argumentos
python -m src generate --title "X" --protagonist "Y" --beats 6 --real

# Exportar
python -m src export --story-id <UUID> --format markdown
```

---

## 6. Estructura del Proyecto

```
src/
├── application/
│   ├── services/
│   │   └── prompt_builder.py    # MODIFICAR: nuevos prompts
│   └── use_cases/
│       └── director_use_case.py  # MODIFICAR: 6 beats
├── infrastructure/
│   └── parsers/
│       └── markdown_parser.py   # MEJORAR: limpiar **
└── cli/
    └── runner.py                # FIX: --input no requiere args
input_stories/
└── [template].md                 # NUEVO: template con 6 beats
```

---

## 7. Code Style

### 7.1 Nuevo Formato de Input (input_stories/template.md)

```markdown
# El Monte Prohibido

**Protagonista**: Ricardo 35 padre, Irene 34 madre, Mariano 10 hijo
**Relator**: Irene
**Atmósfera**: terror psicológico

---

## Apertura (Beat 1)

La familia se prepara para ir a una fiesta en casa de campo. 
Diálogos cotidianos. La abuela advierte sobre el monte prohibido.

---

## Incidente (Beat 2)

Salen de madrugada. Tormenta. El caballo se empaca.
Se ven obligados a tomar el camino del monte.

---

## Subida (Beat 3)

Primeras sombras. Ruidos inexplicables. El viento aúlla.
Irene siente presencia.

---

## Crisis (Beat 4)

Apariciones claras. Familiares que no deberían estar.
El caballo huye. Mariano ve algo en el bosque.

---

## Cumbre (Beat 5)

Todos perdido. El monte no deja salir.
Irene ora. Las apariciones se intensifican.

---

## Desenlace (Beat 6)

La oración funciona. Salen del monte.
Amanecer. Lecciones aprendidas.
```

### 7.2 Prompts del Director

```markdown
# DIRECTOR DE NARRATIVA DE TERROR (6 Beats)

Eres un experto escritor de relatos de terror en español.

CONTEXTO:
- Protagonista: {protagonista}
- Relator: {relator}
- Atmósfera: {atmosfera}
- Escenarios: {escenarios}

TAREA:
Genera una escaleta de EXACTAMENTE 6 BEATS para un relato de terror.
Cada beat debe seguir esta estructura:

1. **Apertura** (1-10%): Mundo ordinario, miedo sutil
2. **Incidente** (10-20%): Algo rompe la normalidad
3. **Subida** (20-50%): Tensión crescente, señales de lo paranormal
4. **Crisis** (50-75%): El mundo se vuelve hostil
5. **Cumbre** (75-85%): Todo parece perdido
6. **Desenlace** (85-100%): Resolución

FORMATO:
Responde solo con los 6 beats numerados.
Cada beat: "X. [Nombre]: [Descripción breve de 1-2 oraciones]"
```

### 7.3 Prompts de la Voz

El prompt actual (system_prompt.md) ya es correcto:
- ✅ Primera persona
- ✅ Tiempo pasado
- ✅ Show don't tell
- ✅ Densidad sensorial
- ✅ Prosa pura

---

## 8. Testing Strategy

### 8.1 Tests Unitarios

| Test | Ubicación | Cobertura |
|------|-----------|-----------|
| Parser limpiar `**` | `tests/unit/infrastructure/test_markdown_parser.py` | >80% |
| Director genera 6 beats | `tests/unit/application/test_director_use_case.py` | >80% |
| Export sin duplicados | `tests/unit/infrastructure/test_markdown_renderer.py` | >80% |

### 8.2 Tests de Integración

```bash
# Test end-to-end
python -m src generate --input template.md --beats 6 --real
python -m src export --story-id <UUID> --format markdown
# Verificar: 6 beats en output, sin duplicados
```

### 8.3 Coverage

- Target: >80%
- Mínimo aceptable: 70%

---

## 9. Límites (Boundaries)

### Always

- Usar la estructura de 6 beats para relatos
- Mantener backwards-compatible con existentes
- Ejecutar `make test` antes de commit
- Ejecutar `make lint` antes de commit

### Ask First

- Cambiar cantidad de beats (de 6 a otro número)
- Modificar nombres de beats
- Agregar nuevos campos al input

### Never

- Commitear con tests fallando
- Modificar archivos de input_stories/ sin backup
- Hardcodear secrets

---

## 10. Success Criteria

- [ ] Parser limpia `**` del markdown
- [ ] Director genera exactamente 6 beats
- [ ] CLI acepta `--input` sin argumentos obligatorios
- [ ] Export no duplica beats
- [ ] Tests pasan con coverage >80%
- [ ] Linting pasa sin errores

---

## 11. Hitos

### Hito 1: Fix Parser (Limpiar **)

**Objetivo:**
- **Qué:** El parser debe limpiar los `**` del markdown antes de generar
- **Cómo:** Modificar `MarkdownStoryParser` para limpiar markdown

**Tasks:**
- [ ] T.1.1: Modificar parser para limpiar `**`
- [ ] T.1.2: Agregar test para limpiar `**`
- [ ] T.1.3: Verificar que tests pasan

**Criteria:**
- [ ] `**Protagonistas**: texto` → `texto`
- [ ] Tests pasan

### Hito 2: Fix Export (Sin Duplicados)

**Objetivo:**
- **Qué:** El export no debe duplicar beats
- **Cómo:** Corregir MarkdownRenderer

**Tasks:**
- [ ] T.2.1: Investigar causa de duplicación
- [ ] T.2.2: Corregir render
- [ ] T.2.3: Testear con historia existente

**Criteria:**
- [ ] Cada beat aparece solo una vez
- [ ] Export genera archivo limpio

### Hito 3: Nuevo Prompt Director (6 Beats)

**Objetivo:**
- **Qué:** Actualizar planner_prompt para generar 6 beats narrativos
- **Cómo:** Modificar template en config/prompts_generation/

**Tasks:**
- [ ] T.3.1: Crear nuevo planner_prompt_narrative.md
- [ ] T.3.2: Actualizar PromptBuilder para usar nuevo prompt
- [ ] T.3.3: Test de generación con 6 beats

**Criteria:**
- [ ] Director genera 6 beats con estructura: Apertura, Incidente, Subida, Crisis, Cumbre, Desenlace

### Hito 4: Fix CLI (--input sin args)

**Objetivo:**
- **Qué:** --input funciona sin argumentos obligatorios
- **Cómo:** Verificar que runner.py permite solo --input

**Tasks:**
- [ ] T.4.1: Testear comando: `python -m src generate --input X.md`
- [ ] T.4.2: Verificar que no pide más argumentos

**Criteria:**
- [ ] `--input` funciona solo
- [ ] No requiere --title, --protagonist, etc.

### Hito 5: Template Input (Nuevo Formato)

**Objetivo:**
- **Qué:** Crear template de input_stories con 6 beats
- **Cómo:** Documentar el nuevo formato

**Tasks:**
- [ ] T.5.1: Crear input_stories/template_narrative.md
- [ ] T.5.2: Documentar formato en spec

**Criteria:**
- [ ] Template documenta los 6 beats
- [ ] Parser puede extraer los beats

---

## 12. Preguntas Abiertas

1. ¿Los 6 beats son suficientes para un relato largo (10K+ palabras)?
2. ¿El sistema debe permitir configurar cantidad de beats (ej: 8, 10)?
3. ¿Los actos del documento actual se deben mapear a beats o ignorar?

---

## 13. Roadmap de Implementación

```
Hito 1: Fix Parser      → Inmediato
Hito 2: Fix Export      → Inmediato  
Hito 3: Nuevo Prompt    → Prioridad alta
Hito 4: Fix CLI         → Prioridad media
Hito 5: Template        → Documentación
```

---

## 14. Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| LLM no sigue estructura de 6 beats | Alto | Prompt más específico, few-shot |
| Parser no limpian ** | Medio | Regex más robusto |
| Export duplica beats | Medio | Deduplicar antes de render |

---

*Documento generado para especificación de beats narrativos.*

# Spec: Testing Segmentado del Core y Comunicación con Ollama

> **Versión:** 1.0.0  
> **Fecha:** 2026-04-16  
> **Estado:** Borrador  
> **Owner:** Usuario (Auditor)  
> **Tags:** testing, core, ollama, mock, integration

---

## 1. Objetivo

Establecer una estrategia de testing segmentado que permita validar el flujo completo del sistema desde el input hasta el output, usando mocks para desarrollo rápido y tests de integración para validar comunicación real con Ollama.

**¿Por qué?** El sistema tiene bugs que no se detectaron porque:
- No hay tests end-to-end para el flujo completo
- Los mocks no reflejan el comportamiento real del Ollama
- No hay validación segmentada entre componentes

---

## 2. Problemas Identificados

### 2.1 Bugs Actuales

| Bug | Descripción | Impacto |
|-----|-------------|---------|
| **Datos no llegan al Director** | El parser lee el markdown pero los datos no se mapean correctamente al story | Historia sin contexto |
| **Beat Duplicados** | En DB hay beats duplicados (11 en vez de 6) | Export incorrecto |
| **Beats vacíos** | Algunos beats tienen content="" | Relato incompleto |
| **Timeout en generación** | El proceso se corta antes de completar | Historia truncada |

### 2.2 Falta de Cobertura

- ❌ Test end-to-end con input real
- ❌ Test de integración con Ollama real
- ❌ Test segmentado por componente
- ❌ Validación de flujo Parser → Director → Voz → Export

---

## 3. Arquitectura de Testing Propuesta

### 3.1 Capas de Testing

```
┌─────────────────────────────────────────────────────┐
│                 E2E TESTS (Reales)                  │
│  Input → Parser → Director → Voz → Export → MD      │
└─────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────┐
│            INTEGRATION TESTS (Mock + Real)           │
│  Parser → MockLLM → MockRepo → Export               │
└─────────────────────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────┐
│                UNIT TESTS (Mocks)                   │
│  DirectorUseCase.test_generate_beats()              │
│  VozUseCase.test_narrate_beat()                     │
│  MarkdownParser.test_clean_markdown()               │
└─────────────────────────────────────────────────────┘
```

### 3.2 Estrategia de Mocks

| Componente | Mock Disponible | Estado |
|------------|-----------------|--------|
| **LLM (Ollama)** | `MockLLMAdapter` | ✅ Implementado |
| **Repository** | `MockStoryRepository`, `MockBeatRepository` | ❌ Falta |
| **PromptBuilder** | `MockPromptBuilder` | ❌ Falta |

---

## 4. Comandos de Test

```bash
# Tests unitarios
make test

# Tests con coverage
PYTHONPATH=. uv run pytest tests/unit/ --cov=src --cov-report=term-missing

# Test específico de parser
PYTHONPATH=. uv run pytest tests/unit/infrastructure/test_markdown_parser.py -v

# Test de integración (mock)
PYTHONPATH=. uv run pytest tests/integration/ -v

# Test E2E (real)
PYTHONPATH=. uv run pytest tests/e2e/ -v
```

---

## 5. Estructura de Tests Propuesta

```
tests/
├── unit/
│   ├── application/
│   │   ├── test_director_use_case.py      # UNIT: test parse beats
│   │   └── test_voz_use_case.py           # UNIT: test narrate
│   ├── infrastructure/
│   │   ├── test_markdown_parser.py        # UNIT: test parser
│   │   └── test_markdown_renderer.py     # UNIT: test export
│   └── cli/
│       └── test_commands.py                # UNIT: test CLI
├── integration/
│   ├── test_core_flow.py                   # INTEGRATION: flujo completo con mocks
│   ├── test_parser_to_director.py          # INTEGRATION: parser → director
│   └── test_director_to_voz.py             # INTEGRATION: director → voz
└── e2e/
    └── test_generate_story.py              # E2E: generate real con Ollama
```

---

## 6. Hitos

### Hito 1: Tests Unitarios del Parser

**Objetivo:**
- **Qué:** Validar que el parser limpia markdown y extrae datos correctamente
- **Cómo:** Tests unitarios existentes expandir

**Tasks:**
- [ ] T.1.1: Test limpiar ** del markdown
- [ ] T.1.2: Test extraer campos (protagonista, relator, etc.)
- [ ] T.1.3: Test archivos no existentes

**Criteria:**
- [ ] 100% tests del parser pasan

### Hito 2: Tests Unitarios del Director

**Objetivo:**
- **Qué:** Validar que el Director genera beats correctamente
- **Cómo:** Test con MockLLMAdapter

**Tasks:**
- [ ] T.2.1: Test _parse_beats con respuesta conocida
- [ ] T.2.2: Test generar 6 beats
- [ ] T.2.3: Test fallback cuando LLM falla

**Criteria:**
- [ ] Director genera beats esperados

### Hito 3: Tests Unitarios de Voz

**Objetivo:**
- **Qué:** Validar que la Voz narra beats correctamente
- **Cómo:** Test con MockLLMAdapter

**Tasks:**
- [ ] T.3.1: Test narrar beat con contexto
- [ ] T.3.2: Test narrar beat sin contexto
- [ ] T.3.3: Test actualizar journal

**Criteria:**
- [ ] Voz genera contenido esperado

### Hito 4: Tests de Integración (Parser → Director → Voz)

**Objetivo:**
- **Qué:** Validar el flujo completo con mocks
- **Cómo:** Tests de integración con MockLLMAdapter

**Tasks:**
- [ ] T.4.1: Test flujo Parser → Director
- [ ] T.4.2: Test flujo Director → Voz
- [ ] T.4.3: Test flujo completo: Parser → Director → Voz → Export

**Criteria:**
- [ ] Flujo completo funciona con mocks
- [ ] Coverage > 70%

### Hito 5: Tests E2E con Ollama Real

**Objetivo:**
- **Qué:** Validar el sistema con Ollama real
- **Cómo:** Tests E2E que generan historias reales

**Tasks:**
- [ ] T.5.1: Test generar historia con 6 beats
- [ ] T.5.2: Test exportar a markdown
- [ ] T.5.3: Test verificar contenido generado

**Criteria:**
- [ ] Historia completa generada
- [ ] 6 beats con contenido
- [ ] Export correcto

---

## 7. Criterios de Éxito

- [ ] Tests unitarios del Parser: 100% passing
- [ ] Tests unitarios del Director: 100% passing
- [ ] Tests unitarios de Voz: 100% passing
- [ ] Tests de integración: >70% coverage
- [ ] Tests E2E con Ollama real: Historia completa

---

## 8. Preguntas Abiertas

1. ¿Cuántos tests de integración necesitamos?
2. ¿Los tests E2E deben correr en CI?
3. ¿Necesitamos mock para PromptBuilder?

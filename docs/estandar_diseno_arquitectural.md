# Estándar de Diseño Arquitectural (EDA)

> **Enfoque:** Spec-Driven Development (SDD) — La especificación es la fuente de verdad.

## 1. Metodología de Desarrollo (SDD)
NarrativeForge opera bajo el ciclo obligatorio: **Spec → Plan → Task → Implementation**.
- **Trazabilidad:** Cada cambio en el código debe rastrear a un Hito y una Task definida en un Spec en `specs/`.
- **Validación Humana:** No se cierra un hito sin ejecución de tests y checklist de calidad.
- **Documentación de Decisiones:** Las decisiones arquitecturales se registran en Specs antes de codificar.

## 2. Arquitectura del Sistema (Clean Architecture)
El código se organiza en capas concéntricas donde las dependencias solo fluyen hacia adentro:

1. **Domain:** Entidades (Story, MacroBeat, Anchors), Interfaces (LLMProvider, Repository) y Excepciones.
2. **Application:** Casos de Uso (Director, Voz, CreateStory) y Servicios (PromptBuilder, Auditor).
3. **Infrastructure:** Adapters (Ollama, Anthropic, SQLite), Normalizers y Renderers.
4. **Presentation/CLI:** Entrada de usuario y orquestación inicial (`StoryRunner`).

### Inyección de Dependencias (Spec-250)
La CLI usa `CLIContainer` para resolver todas las dependencias (LLM, repositorios, renderers, parsers), eliminando instanciación directa y facilitando testing unitario.

## 3. El Pipeline de Inteligencia (LLM)
- **Fuente de Verdad:** `config/llm_core_definitions.yaml` gobierna perfiles, modelos y parámetros.
- **Variantes de Prompting:**
  - `compact`: Prompts directivos para modelos locales.
  - `frontier`: Prompts ricos en contexto para modelos de alto rendimiento.
- **Prompting Asertivo (Spec-170):** Uso de `NarrativeAuditor` para detectar boilerplate o falta de sensorialidad, disparando reintentos automáticos.
- **Normalización:** `ResponseNormalizer` limpia razonamientos internos (`<think>`) y ruido conversacional sin alterar el Markdown válido.

## 4. Estándares Técnicos y Calidad
- **Python:** 3.12+, tipado estricto (Type Hints), `pydantic` para validación.
- **Naming:** `PascalCase` para clases, `snake_case` para funciones/variables, `MAYUSCULAS_SNAKE` para constantes.
- **Testing:** `pytest` con cobertura > 80%. Cada task de lógica requiere su task de test unitario.
- **Persistencia:** SQLite asíncrono (`aiosqlite`). El principio es: **YAML inicializa la estructura, la DB gobierna el estado de la historia.**
- **Manejo de Errores:** Jerarquía clara basada en `DomainException` e `InfrastructureException`. Spec-250 introdujo `LLMResponseError` (respuestas vacías/inválidas del LLM) y `DatabaseError` (fallos de persistencia).

## 5. Workflow del Desarrollador (Scripts)
- `make install`: Sincroniza dependencias con `uv`.
- `make test`: Ejecuta la suite completa de pruebas.
- `make lint`: Verifica estilo y formato con `ruff`.
- `bash scripts/bash/init_db.sh`: Recrea la base de datos desde cero.

---
*Este documento es complementario al [README.md](../README.md), el cual contiene la visión del producto y manual de usuario.*

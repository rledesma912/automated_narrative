# NarrativeForge Agent Configuration

## Project Context

NarrativeForge es una API REST + WebSocket en Python/FastAPI para generación automática de relatos de terror usando Ollama (LLMs locales).

**Stack:** Python 3.12, FastAPI, SQLite, Ollama, Clean Architecture

## Skills

Referencia los skills del directorio `.opencode/skills/` para cada fase:

```markdown
# Phase → Skill
Define      → .opencode/skills/spec-driven-development
Plan        → .opencode/skills/planning-and-task-breakdown  
Build      → .opencode/skills/incremental-implementation
Build      → .opencode/skills/test-driven-development
Build      → .opencode/skills/api-and-interface-design
Verify     → .opencode/skills/debugging-and-error-recovery
Review     → .opencode/skills/code-review-and-quality
Review     → .opencode/skills/security-and-hardening
Ship       → .opencode/skills/git-workflow-and-versioning
```

## Core Operating Behaviors

### 1. Surface Assumptions
Antes de implementar algo no-trivial, declarar explícitamente:
```
ASSUMPTIONS:
1. [suposición sobre requirements]
2. [suposición sobre arquitectura]
→ Corrígeme ahora o procedo con estas.
```

### 2. Manage Confusion
Cuando hay inconsistencias o requisitos confusos:
1. **STOP.** No proceedas con un guess.
2. Nombrar la confusión específica.
3. Presentar el tradeoff o pregunta.
4. Esperar resolución antes de continuar.

### 3. Push Back When Warranted
No sos un yes-machine. Cuando un enfoque tiene problemas claros:
- Point out the issue directly
- Explicar el downside concreto
- Proponer alternativa
- Aceptar la decisión del humano si override con info completa

### 4. Enforce Simplicity
Resistir la sobreingeniería. Antes de terminar:
- ¿Puede hacerse en menos líneas?
- ¿Las abstracciones merecen su complejidad?
- ¿Un staff engineer diría "por qué no simplemente..."?

### 5. Verify, Don't Assume
Cada skill incluye verification step. "Seems right" ≠ suficiente.
Debe haber evidencia: passing tests, build output, runtime data.

## Development Workflow

Para este proyecto, seguir esta secuencia:

```markdown
1. .opencode/skills/spec-driven-development  → PRD antes de código
2. .opencode/skills/planning-and-task-breakdown → Tasks verificables
3. .opencode/skills/incremental-implementation  → Thin slices
4. .opencode/skills/test-driven-development    → Tests primero
5. .opencode/skills/code-review-and-quality    → Review antes de commit
6. .opencode/skills/git-workflow-and-versioning → Commits atómicos
```

## Quality Gates

Antes de cada commit:
- [ ] Tests passing (`make test`)
- [ ] Lint passing (`make lint`)
- [ ] Code reviewed
- [ ] Changes < ~100 líneas por commit

## Important Files

```
src/
├── domain/models.py          # Entidades (Story, Act, State)
├── application/use_cases/   # Lógica de negocio
├── infrastructure/          # Adapters, DB, Normalizers
├── presentation/api/        # FastAPI routes
config/
├── sanitization.yaml       # Reglas de limpieza LLM
.env                        # API_HOST, OLLAMA_HOST
Makefile                    # dev, test, lint, clean
```

## Commands Útiles

```bash
make dev          # Levanta API con hot-reload
make test         # Run tests con coverage
make lint         # Ruff check + format
```
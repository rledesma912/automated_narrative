# Proceso de Saneamiento — `sanitize`

Flujo macro del sistema de saneamiento narrativo. Documento fuente de verdad a nivel estructural.

El objetivo del proceso es **evaluar, corregir y optimizar relatos existentes** manteniendo coherencia narrativa, consistencia de voz y densidad sensorial, mediante un pipeline iterativo con intervención humana.

---

## Objetivo

- Detectar issues narrativos críticos
- Aplicar reescrituras controladas
- Permitir validación humana antes de persistir
- Garantizar que el resultado final no tenga issues críticos

---

## Alcance

Incluye:
- Auditoría local (beat) y global (relato)
- Planificación de correcciones
- Reescritura parcial (párrafo / beat)
- Validación iterativa
- Interacción usuario (aprobación de cambios)

No incluye (v1):
- Reescritura completa de historia
- Autonomía total sin validación humana

---

## Naturaleza del Pipeline

A diferencia de `generate`, este flujo es **cíclico**:

```
Audit → Plan → Patch → Validate → (Loop)
```

Condiciones de corte:
- No existen issues críticos
- Máximo 3 iteraciones

---

## Paso 0 — Ingesta del relato

**Componente:** `SanitizeStoryUseCase`
**LLM:** ninguno

**Qué hace:**
- Recupera historia existente desde DB
- Segmenta en beats y párrafos

---

## Paso 1 — Auditoría

**Componente:** `NarrativeAuditor++`
**LLM:** sí (local + global)

**Qué hace:**
- Detecta issues en:
  - coherencia
  - voz
  - densidad sensorial

**Scope:**
- Local (por beat)
- Global (relato completo)

**Output:**
- Lista de `SanitizationIssue`

---

## Paso 2 — Normalización de issues

**Componente:** `IssueProjector`
**LLM:** ninguno

**Qué hace:**
- Convierte issues globales en issues aplicables a beats

---

## Paso 3 — Planificación de patches

**Componente:** `IssueResolver`
**LLM:** opcional

**Qué hace:**
- Agrupa issues
- Define estrategia de intervención

**Output:**
- `PatchSet`

---

## Paso 4 — Generación de reescritura

**Componente:** `Rewriter`
**LLM:** sí

**Qué hace:**
- Reescribe texto afectado
- Mantiene eventos y continuidad

---

## Paso 5 — Interacción usuario

**Componente:** API + SSE
**LLM:** ninguno

**Qué hace:**
- Presenta:
  - texto original (izquierda)
  - issues (centro)
  - propuesta (derecha)
- Usuario puede:
  - editar
  - aprobar
  - rechazar

---

## Paso 6 — Aplicación de patch

**Componente:** `PatchApplier`
**LLM:** ninguno

**Qué hace:**
- Sobrescribe contenido aprobado

---

## Paso 7 — Validación

**Componente:** `Validator`
**LLM:** sí

**Qué hace:**
- Re-evalúa zonas modificadas
- Verifica eliminación de issues críticos

---

## Paso 8 — Loop

**Componente:** `SanitizationDirector`

**Qué hace:**
- Decide continuar o finalizar

---

## Estado del sistema

`SanitizationState`:
- issues_detected
- patches_pending
- patches_applied
- iteration_count

---

## Persistencia

- Sobrescritura directa del contenido
- No versionado en DB (v1)

---

## Interacción y Streaming

Eventos SSE:
- issue_detected
- patch_proposed
- patch_preview
- patch_applied
- validation_result

---

## Relación con `generate`

| Generación | Saneamiento |
|----------|------------|
| Lineal | Cíclico |
| Construye | Corrige |
| Autónomo | Interactivo |
| 17 llamadas fijas | Dinámico |

Ambos comparten:
- Arquitectura (Clean Architecture)
- LLM Providers
- Modelo de beats

---

## Nota

Documento intencionalmente minimalista.
Se expandirá en paralelo a los specs (`Spec-SAN-XXX`).


# SPEC-170: Prompting Asertivo y Auditoría de Alfabetismo Narrativo

**Estado:** APROBADO
**Fecha:** 2026-04-26
**Autor:** Gemini CLI (Architect & Senior Engineer)
**Relacionado con:** SPEC-081 (Resonancia), SPEC-160 (Freytag Resonance)

## 1. Problema Narratológico y Técnico

El sistema actual subestima la capacidad de los LLMs modernos al incluir definiciones pedagógicas extensas sobre teoría narrativa (Aristóteles/Freytag) en cada prompt. Esto genera:
1. **Desperdicio de Tokens:** ~30% del prompt de sistema es ruido explicativo.
2. **Dilución de Atención:** El modelo procesa la definición en lugar de centrarse en el subtexto de la historia.
3. **Falta de Control de Calidad:** No hay un mecanismo que valide si el modelo realmente "entiende" los conceptos o si solo está repitiendo patrones superficiales.

## 2. Propuesta: Activación de Esquemas y Auditoría

Pasar de un enfoque **Descriptivo** a uno **Asertivo**, utilizando la terminología técnica para activar el entrenamiento previo del modelo, respaldado por un componente de auditoría independiente.

### 2.1 Niveles de Prompting (Tiers)
- **Tier 1 (Assertive):** Usa términos técnicos puros (Hamartia, Hybris, Anagnórisis). Sin explicaciones.
- **Tier 2 (Descriptive):** Incluye definiciones y guías de apoyo (Modo Resiliente).

### 2.2 El Auditor Narrativo (Componente de Calidad)
Se introduce un **Narrative Auditor** desacoplado (SRP) que evalúa la respuesta del modelo antes de aceptarla.
- **Heurística de Boileplate:** Detecta si el modelo explica el concepto en lugar de aplicarlo.
- **Heurística de Sensorialidad:** Mide la densidad de imágenes concretas vs. abstracciones.
- **Heurística de Entropía:** Valida que el resultado no sea un calco literal de la sinopsis.

## 3. Arquitectura y Diseño (Clean Arch / SOLID)

### 3.1 Dominio
- `INarrativeValidator` (Interface): Contrato para la validación de alfabetismo.
- `NarrativeLiteracyError` (Exception): Error lanzado cuando un modelo falla la validación en modo estricto.

### 3.2 Aplicación
- `NarrativeAuditor`: Servicio que implementa la lógica de auditoría.
- `StoryAnalystService`: Orquestador que ahora incluye el ciclo de "Extracción -> Validación -> Reintento (opcional)".

### 3.3 Configuración
- `PROMPTING_STRATEGY`: `assertive` (estricto), `auto` (fallback inteligente), `descriptive` (legacy).

## 4. Plan de Implementación (Slices)

### Slice A: Cimientos y Auditoría
- [ ] Implementar `INarrativeValidator` y `NarrativeAuditor`.
- [ ] Definir excepciones de dominio.
- [ ] Tests unitarios para las heurísticas de validación.

### Slice B: Prompting Multinivel
- [ ] Crear variantes de prompts `_assertive.md`.
- [ ] Actualizar `PromptBuilder` para selección dinámica de plantillas.
- [ ] Adaptar `llm_narrative_definition.yaml` para etiquetas técnicas cortas.

### Slice C: Resiliencia y Fallback
- [ ] Refactorizar `StoryAnalystService` para integrar el ciclo de reintento.
- [ ] Limpiar `NarrativeContextAssembler` para eliminar ruido visual en modo asertivo.

## 5. Criterios de Aceptación
1. Reducción verificable de tokens de input (>25%) en modo asertivo.
2. El sistema debe ser capaz de detectar y rechazar una respuesta "pedagógica" (explicativa) de un LLM.
3. Integridad total de la suite de tests (`make test`).

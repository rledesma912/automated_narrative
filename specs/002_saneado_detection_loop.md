# Spec 002: Flujo de Saneado - Detection por Acto

**Versión:** 1.0  
**Fecha:** 2026-04-06  
**Estado:** Propuesto  
**Proyecto:** automated_narrative

---

## 1. Contexto

El flujo actual de saneado (`sanitize_short_narrative.json`) tiene una estrategia híbrida:
- **Corrección**: Por acto (loop)
- **Detection**: Global (sobre texto completo)

**Problema**: El modelo qwen2.5:32b tiene limitaciones de VRAM/tokenes cuando procesa el texto completo de una historia. Esto causa timeouts o respuestas incompletas.

**Solución propuesta**: Detection también por acto, manteniendo contexto previo.

---

## 2. Requerimiento

Hacer detection en un loop que itere sobre cada acto validando:
1. Consistencia interna del acto
2. Consistencia con actos anteriores (usando memoria)

---

## 3. Arquitectura Propuesta

```
[Input: actos corregidos] → SplitInBatches (por acto)
                              ↓
                    build_detection_prompt
                    (inyectar: acto + memoria_acumulada)
                              ↓
                    Ollama (gemma2:9b)
                    (detection_prompt.md)
                              ↓
                    parse_detection
                              ↓
                    Merge (recolectar issues)
                              ↓
                    [Output: lista de issues por acto]
```

---

## 4. Détalles del Prompt de Detection

El prompt debe recibir:
- `{{text}}`: Capítulo del acto actual
- `{{memory}}`: Resumen de actos anteriores

```markdown
Sos un auditor narrativo especializado en consistencia de historias de terror.

Analizá el siguiente acto de la historia y detectá inconsistencias respecto al contexto previo.

## CONTEXTO PREVIO (actos anteriores):
{{memory}}

## ACTO ACTUAL:
{{text}}

TIPOS DE PROBLEMAS A DETECTAR:
- Continuidad (eventos que se contradicen)
- Personajes (nombres, rasgos, roles)
- Temporalidad (saltos de tiempo)
- Espacio (lugares contradictorios)

REGLAS:
- Solo detectar problemas REALES (no inventar)
- Referenciar ubicación exacta

SALIDA (JSON):
{
  "issues": [
    {
      "type": "continuidad",
      "location": "párrafo/oración específica",
      "severity": "baja/media/alta",
      "description": "problema"
    }
  ]
}
```

---

## 5. Consideraciones de Implementación (n8n Best Practices)

### 5.1 Modularidad
- Extraer la lógica de build_detection_prompt a un sub-workflow
- Nombre sugerido: `sub.build_detection_prompt`

### 5.2 Contratos
- Validar que cada acto tenga `chapter` y `memory` antes de procesar
- Fallar temprano si datos incompletos

### 5.3 Idempotencia
- Verificar si el acto ya fue procesados (por act_number + id_story)
- Evitar re-procesar en re-ejecuciones

### 5.4 Manejo de Errores
- Si detection falla por timeout → reintentar con modelo más liviano
- Guardar estado en PostgreSQL para recuperación

---

## 6. Estimación de Recursos

| Fase | Modelo | Tiempo estimado |
|------|--------|------------------|
| Correction (5 actos) | gemma2:9b | ~30s |
| Detection (5 actos) | gemma2:9b | ~40s |
| Resolution | qwen2.5:32b | ~60s |
| Validation | gemma2:9b | ~20s |

**Total**: ~2.5 min por historia (vs ~5 min con detection global)

---

## 7. Próximo Paso

1. [ ] Aprobar este spec
2. [ ] Implementar detection por acto en n8n
3. [ ] Testear con historia de prueba
4. [ ] Comparar resultados vs approach global

---

*Spec-driven development: cada cambio es un spec*
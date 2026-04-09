# Spec: Automated Narrative System

**Versión:** 1.0  
**Fecha:** 2026-04-06  
**Tipo:** Requerimientos del Proyecto

---

## 1. Objetivo del Proyecto

Plataforma para generar relatos de terror automáticamente usando LLMs locales (Ollama), con flujos de n8n para orquestación y un sistema de saneado (post-procesamiento) para garantizar calidad narrativa.

## 2. Estado Actual

### Componentes Implementados

| Componente | Tech Stack | Estado |
|------------|------------|--------|
| Interfaz Web (Story Form) | Node.js, Express, EJS, SQLite | ✅ Funcional |
| Flujos n8n - Generación | JSON workflows | ✅ Implementado |
| Flujos n8n - Saneado | JSON workflows | ✅ Implementado |
| Base de datos | PostgreSQL | ✅ Esquema listo |
| Modelos IA | Ollama (qwen2.5:32b, gemma2:9b) | ✅ Configurado |

### Estructura de Archivos

```
/
├── story-form/              # App web
├── flujos_n8n/              # Workflows JSON
├── prompts_historias/       # Templates de historias
├── prompts_generacion/     # System prompts
├── prompts_saneadores/     # Prompts de saneado
├── output_stories/         # Relatos generados
├── historias_saneadas/     # Relatos corregidos
├── scripts_db/             # SQL PostgreSQL
└── docker-compose.yml     # Contenedor web
```

## 3. Requerimientos Funcionales

### 3.1 Generación de Relatos

- **Input:** Archivo Markdown con plantilla de historia (prompts_historias/)
- **Proceso:**
  1. n8n dispara flujo con id_story
  2. Por cada acto: LLM genera capítulo consultando memoria narrativa
  3. PostgreSQL almacena: chapter, summary, memory
- **Output:** Relato completo en output_stories/

### 3.2 Saneado de Narrativa

Pipeline de 4 fases:
1. **Corrección:** Ortografía, gramática (gemma2)
2. **Detección:** Inconsistencias, contradicciones (qwen2.5)
3. **Resolución:** Corregir issues detectados (qwen2.5)
4. **Validación:** Verificar calidad final (gemma2)

### 3.3 Interfaz Web

- Listar historias generadas
- Previsualizar prompts
- Configurar actos/capítulos

## 4. Requerimientos No Funcionales

- **Privacidad:** Todo corre local (sin APIs externas)
- **Consistencia:** Memoria narrativa en PostgreSQL
- **Calidad:** Saneado automático con versiónado

## 5. Tech Stack

- **IA:** Ollama + modelos qwen2.5:32b, gemma2:9b
- **Orquestación:** n8n (self-hosted)
- **Web:** Node.js, Express, EJS
- **Datos:** SQLite (metadatos), PostgreSQL (memoria narrativa)
- **Contenedores:** Docker + Docker Compose

## 7. n8n Best Practices (Aplicados)

Basado en patrones de producción-grade automation:

### 7.1 Arquitectura Modular
- ✅ Flujos separados: generación vs saneado
- ⚠️ **Pendiente:** Extraer lógica repetitiva a sub-workflows
- ⚠️ **Pendiente:** Naming convention: `domain.purpose.trigger`

### 7.2 Validación (Contracts Over Vibes)
- ⚠️ **Pendiente:** Validar schema de entrada en cada trigger
- ⚠️ **Pendiente:** Fallar temprano si datos incompletos

### 7.3 Manejo de Errores
- ⚠️ **Pendiente:** Dead Letter Queue para fallos
- ⚠️ **Pendiente:** Paths de error explícitos en cada nodo crítico

### 7.4 Idempotencia
- ⚠️ **Pendiente:** Verificar si `id_story` ya fue procesado antes de generar
- ⚠️ **Pendiente:** Evitar duplicados en re-ejecuciones

### 7.5 Observabilidad
- ⚠️ **Pendiente:** Logging estructurado
- ⚠️ **Pendiente:** Runbook por cada flujo crítico

### 7.6 Versionado
- ⚠️ **Pendiente:** Exportar workflows JSON a Git
- ⚠️ **Pendiente:** Historial de versiones

---

## 8. Próximos Pasos (Roadmap Priorizado)

1. [ ] **Verificar estado actual** - Levantar componentes y probar flujo
2. [ ] **Identificar gap más crítico** - El saneado está estancado
3. [ ] **Aplicar patrones n8n** - Modularizar, validar, agregar manejo de errores
4. [ ] **Documentar** - Crear runbook del flujo de saneado

---

*Spec-driven development: cada feature futura será un nuevo spec en `specs/`*
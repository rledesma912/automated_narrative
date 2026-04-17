# 🎨 NarrativeForge - UI Specification

> **Versión:** 1.0  
> **Fecha:** 2026-04-15  
> **Estado:** Specification  
> **Parent:** [Granular Beat Spec](./granular_beat_spec.md)

---

## 📋 SDD REFERENCE (Marco de Desarrollo)

> Estas definiciones son obligatorias para todo desarrollo. Referencia: [Marco SDD](./marco_sdd.md)

### Núcleos Requeridos

| # | Área | En Spec | Descripción |
|---|-----|--------|-------------|
| 1 | **Objective** | §1-3 | User stories + propósito |
| 2 | **Project Structure** | §Project Structure | frontend/ con Express + EJS |
| 3 | **Code Style** | §JS Code Style | camelCase, PascalCase, kebab-case |
| 4 | **Boundaries** | §Boundaries | Always/Ask/Never |
| 5 | **Open Questions** | §Open Questions | Por resolver |

### Definiciones Críticas

| Definición | Valor |
|-----------|-------|
| **Frontend Stack** | Node.js + Express + EJS |
| **Puerto** | 3010 |
| **API Base** | http://localhost:8010 |
| **Naming JS** | `camelCase` variables, `PascalCase` clases, `kebab-case` archivos |
| **Vistas** | EJS templates en /views |
| **HTTP Client** | fetch API |

---

## 📌 ASSUMPTIONS (Referencia SSoT: [001 Marco SDD](./001_marco_sdd.md))

1. **Frontend:** Node.js + Express.js + EJS (Puerto 3010)
2. **API:** Backend en puerto 8010 (REST API)
3. **WebSockets:** Implementación en fase posterior (Roadmap)

---

## 🎯 OBJECTIVE

Interfaz de usuario para el sistema de generación granular de relatos de terror.

### User Stories

| # | Como | Quiero | Para |
|---|------|--------|------|
| 1 | Usuario | Ver lista de historias | Elegir cual editar/ver |
| 2 | Usuario | Crear nueva historia | Iniciar generación |
| 3 | Usuario | Editar beats antes de narrar | Controlar dirección |
| 4 | Usuario | Ver progreso en tiempo real | Saber qué se genera |
| 5 | Usuario | Descargar relato en Markdown | Leer/compartir offline |

---

## 💻 TECH STACK

| Componente | Tecnología |
|-----------|-------------|
| Runtime | Node.js |
| Framework | Express.js |
| Template | EJS |
| HTTP Client | fetch (browser) |
| CSS | Vanilla + CSS Variables |

---

## 📂 PROJECT STRUCTURE

```
frontend/
├── app.js                   # Express entrypoint
├── public/
│   ├── css/
│   │   └── style.css       # Estilos
│   └── js/
│       ├── app.js        # Lógica principal
│       └── api.js       # Cliente API
├── views/                  # Plantillas EJS
│   ├── layout.ejs       # Layout base
│   ├── index.ejs       # Lista historias
│   ├── new.ejs        # Crear historia
│   ├── edit-beats.ejs # Editar beats
│   ├── generate.ejs   # Panel progreso
│   └── story.ejs       # Ver relato
├── services/
│   └── api.js         # Cliente API
├── .env                # Config local
└── package.json        # Dependencias
```

---

## 🖥️ VISTAS REQUERIDAS

| Vista | Ruta | Descripción |
|-------|-----|-------------|
| **Inicio** | `/` | Lista de historias + botón nuevo |
| **Crear** | `/new` | Formulario 3 pasos |
| **Editar Beats** | `/stories/:id/edit` | Beats editables |
| **Generar** | `/stories/:id/generate` | Panel de progreso |
| **Ver** | `/stories/:id` | Relato completo |

---

## 📝 FORMULARIO 3 PASOS

### Paso 1: Contexto

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `protagonistas` | textarea | "¿Quiénes son los personajes?" |
| `relator` | select | "¿Quién narra?" (primera_persona, tercera_persona) |
| `escenarios` | textarea | "¿Dónde ocurre la historia?" |

### Paso 2: Sinopsis

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sinopsis` | textarea | "De qué va la historia" |
| `atmosfera` | select | Tono (terror, suspenso, gótico, psicológico) |
| `reglas` | array | Reglas narrativas (add/remove) |

### Paso 3: Revisar

- Resumen de toda la info ingresada
- Botón "Guardar y Crear"

---

## 🔌 API CALLS

| View | Endpoint | Método |
|------|----------|--------|
| Index | `/api/v1/stories` | GET |
| New | `/api/v1/stories` | POST |
| Edit | `/api/v1/stories/{id}` | GET |
| Edit | `/api/v1/stories/{id}` | PUT |
| Edit | `/api/v1/stories/{id}/beats` | PUT |
| Generate | WebSocket `/api/v1/ws/stories/{id}` | WS |
| Generate | `/api/v1/stories/{id}/generate` | POST |
| View | `/api/v1/stories/{id}` | GET |
| Export | `/api/v1/stories/{id}/export` | GET |

---

## 🧠 WEBSOCKET EVENTS

| Evento | Datos | Descripción |
|--------|-------|-------------|
| `plan_generated` | `{beats: [], story_id}` | Plan creado |
| `beat_started` | `{beat_number, summary}` | Iniciando beat |
| `beat_completed` | `{beat_number, content, word_count}` | Beat listo |
| `job_completed` | `{story_id, beats_count, total_words}` | Historia completa |
| `job_failed` | `{error, beat_number}` | Error |

---

## 🎨 WIREFRAME

### Index (ListaHistorias)

```
┌──────────────────────────────────────────┐
│  🏠 NarrativeForge              [Mis Hist.] │
├──────────────────────────────────────────┤
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ 📖 El Pueblo Olvidado             │  │
│  │ 8 beats • 2000 palabras • ✅      │  │
│  │ [Ver] [Editar] [Exportar]        │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ 📖 La Casa Abandonada             │  │
│  │ 10 beats • ⏳ generating          │  │
│  │ [Ver] [Cancelar]                  │  │
│  └────────────────────────────────────┘  │
│                                          │
│  [+ Nueva Historia]                     │
└──────────────────────────────────────────┘
```

### Edit Beats

```
┌──────────────────────────────────────────┐
│  🏠 NarrativeForge        [Historia: ...]  │
├──────────────────────────────────────────┤
│  Título: El Pueblo Olvidado               │
│                                          │
│  ┌─ Beat 1 ─────────────────────────┐   │
│  │ 1. Los hermanos llegan           │   │
│  │ [✏️ Editar] [🗑️ Eliminar]        │   │
│  └────────────────────────────────────┘   │
│                                          │
│  ┌─ Beat 2 ─────────────────────────┐   │
│  │ 2. La casa natal                │   │
│  │ [✏️ Editar] [🗑️ Eliminar]        │   │
│  └────────────────────────────────────┘   │
│                                          │
│  [ + Añadir Beat ]                        │
│                                          │
│  [ Guardar ]  [ Generar Relato ]          │
└──────────────────────────────────────────┘
```

### Generate (Progreso)

```
┌──────────────────────────────────────────┐
│  🏠 NarrativeForge        [Generando...]    │
├──────────────────────────────────────────┤
│                                          │
│  ████████████░░░░░░  50%                │
│  Beat 5/10: La Confrontación Final         │
│                                          │
│  ┌──���───────────────────────────────┐   │
│  │ "El viento soplaba con..."        │   │
│  └──────────────────────────────────┘   │
│                                          │
│  [ Cancelar ]                            │
└──────────────────────────────────────────┘
```

---

## 🎨 COMPONENTES UI

| Componente | Descripción | Estados |
|------------|-------------|---------|
| `StoryCard` | Card de historia en lista | default, hover, selected |
| `BeatItem` | Beat individual editable | editable, readonly, pending, completed |
| `ProgressBar` | Barra de progreso | idle, generating, complete |
| `StepWizard` | Formulario de pasos | step-1, step-2, step-3 |
| `MarkdownViewer` | Renderizador de markdown | - |
| `RuleTag` | Tag de regla narrativa | add, remove |

---

## 🎯 JS CODE STYLE

| Tipo | Naming | Ejemplo |
|------|--------|--------|
| Variables | `camelCase` | `const storyTitle = ...` |
| Constantes | `UPPER_SNAKE` | `const API_PORT = 3010` |
| Funciones | `camelCase` | `function fetchStories() {}` |
| Clases | `PascalCase` | `class StoryService {}` |
| Archivos | `kebab-case` | `story-service.js` |
| Vistas | `kebab-case` | `story-view.ejs` |

---

## ✅ CHECKLIST UI

- [ ] Index con lista de historias
- [ ] Formulario 3 pasos funcional
- [ ] Validación de campos
- [ ] Editar beats antes de generar
- [ ] WebSocket para progreso
- [ ] Progress baranimated
- [ ] Vista de relato completo
- [ ] Exportar a Markdown

---

## 📚 REFERENCES

- [Granular Beat Spec](./granular_beat_spec.md) - Backend
# Spec-300: Dominio de Generación de Relatos y Gestión de Variantes

**Estado:** Vivo / Referencia
**Prioridad:** Alta
**Metodología:** SDD, Clean Architecture

## 1. Visión General

Este documento define el dominio de datos y la orquestación para la generación de múltiples variantes narrativas (relatos) a partir de una única historia plantilla. NarrativeForge permite que una misma historia sea narrada múltiples veces, preservando cada versión como un registro independiente.

## 2. Modelo de Datos y Cardinalidad

El sistema implementa una relación **uno-a-muchos** entre la historia (plantilla) y los relatos generados.

### 2.1 GeneratedNarrative (`src/domain/models.py`)
Entidad que representa una variante narrativa consolidada.
- `id: UUID4` (PK)
- `story_template_id: UUID4` (FK a `story.id`)
- `title: str`: Título descriptivo (ej: "Título · 2026-05-05 14:41")
- `content: str`: Prosa completa consolidada (formato Markdown con separadores de Beats).
- `status: StoryStatus` (COMPLETED, FAILED)
- `created_at: datetime`

### 2.2 Consolidación de Contenido
Un relato se deriva de la unión de los contenidos de sus `MacroBeat` asociados. 
- **Separadores:** Cada beat se precede con un encabezado `## Beat N - [Resumen]` para asegurar claridad visual tanto en el archivo `.md` como en la vista web.

## 3. Orquestación y Persistencia Automática

### 3.1 Flujo de Generación (CLI y Streaming)
La persistencia en `generated_narrative` ocurre de forma automática al finalizar exitosamente la generación de todos los beats (D1.c).
1. El `DirectorUseCase` completa los 5 beats.
2. `StoryRunner` o `stream_story` invocan `GenerateNarrativesUseCase.consolidate_and_save(story)`.
3. Se crea una nueva variante con un UUID único y un título determinístico (incluyendo timestamp).

### 3.2 Streaming SSE
El evento `DONE` del stream incluye el `narrative_id` generado para permitir al frontend redirigir directamente al relato.
```json
{"story_id": "...", "total_beats": 5, "narrative_id": "..."}
```

## 4. Gestión de Historias en la Galería

### 4.1 Acciones de Card
- **Ver Relato:** Abre la vista de relatos generados de la historia.
- **Eliminar historia:** Realiza un borrado en cascada (Hard Delete) de la historia, sus beats, anclajes, journal y todos sus relatos generados.
- **Estado Processing:** Durante la generación, la card solo muestra el CTA "Ver avance" para reconectar al modo monitor, deshabilitando acciones destructivas o de edición.

### 4.2 Interfaz de Relatos (`relatos.ejs`)
- Provee un **switcher superior** para navegar entre las distintas variantes generadas de una misma historia.
- El panel de lectura cuenta con **scroll interno** y los encabezados de los beats están estilizados para mejorar la navegación del contenido largo.

## 5. Gestión de Datos y Seguridad
- **Borrado selectivo:** El script `db-clean.sh` soporta el parámetro `story_id` para eliminar datos de una historia específica sin afectar al resto de la base de datos.
- **Integridad:** Se utiliza `FOREIGN KEY (story_template_id) REFERENCES story(id) ON DELETE CASCADE` para asegurar que no queden relatos huérfanos.

# NarrativeForge

> Sistema de generación granular de relatos de terror atmosférico mediante orquestación multi-agente.

NarrativeForge construye historias cohesivas usando una estrategia **beat-by-beat**: la narrativa se divide en 5 actos estructurales, procesados secuencialmente para garantizar profundidad literaria y coherencia a largo plazo.

## 1. El Manifiesto Narrativo (El Qué)

El sistema no genera texto masivo; construye una experiencia basada en la **Resonancia Narrativa** (Unificación Freytag/Aristóteles).

### Los 5 Pilares de Resonancia
Cada historia se ancla en cinco puntos de inflexión extraídos una sola vez al inicio (Spec-160):
1. **Hamartia (Exposición):** La grieta psicológica o vulnerabilidad del protagonista.
2. **Hybris (Acción Ascendente):** La transgresión; la lógica que permite cruzar la frontera.
3. **Anagnórisis (Clímax):** La violación de lo sagrado; el detalle sensorial insoportable.
4. **Peripeteia (Acción Descendente):** La trampa espacial; el entorno como antagonista.
5. **Residual (Desenlace):** La mancha; el daño observable que permanece tras el horror.

### Estructura de Generación (5 Beats)
La historia fluye a través de 5 macro-beats definidos en `config/llm_beats_definition.yaml`. Un **Beat** es la unidad mínima de narración (~300-500 palabras) con su propio contexto, reglas y escenario activo.

## 2. El Equipo de Agentes
Cinco roles especializados colaboran en el pipeline:
- **Analyst:** Extrae los 5 Pilares de Resonancia de la sinopsis.
- **Resolver:** Distribuye dinámicamente reglas y escenarios a cada beat.
- **Mapper:** Mapea eventos de la sinopsis al escenario y pilar correspondiente.
- **Voz:** Transforma el contexto técnico en prosa literaria de alta calidad.
- **Journal:** Mantiene la memoria viva (misterios, estados, eventos) entre beats.

## 3. Puesta en Marcha

### Instalación
```bash
make install          # instala dependencias Python (uv) y Node (npm)
make db               # inicializa SQLite
```

### Modo Web (recomendado — Spec-200)

Levanta ambos componentes con un solo comando:

```bash
make dev-all
```

O en terminales separadas:

```bash
# Terminal 1 — Core API (Python/FastAPI)
make dev              # → http://localhost:8010

# Terminal 2 — Frontend (Node/Express)
make ui               # → http://localhost:3000
```

| Componente | URL | Descripción |
|---|---|---|
| Frontend | http://localhost:3000 | Wizard + Streaming Room |
| Core API | http://localhost:8010 | REST + SSE |
| API Docs | http://localhost:8010/docs | Swagger UI |
| Debug panel | http://localhost:3000/debug | Estado del sistema |

### Modo CLI (avanzado)

```bash
python -m src generate --input input_stories/historia.md   # generación completa
python -m src plan <story_id>      # solo Analyst + Resolver + Mapper
python -m src narrate <story_id>   # solo Voz + Journal
python -m src generate ... --debug # exporta pipeline de prompts y respuestas
python -m src generate ... --hasta voz:3   # detiene en checkpoint específico
```

### Configuración
- **Perfiles LLM:** `config/llm_core_definitions.yaml` — activa un perfil con `active_profile:` o `LLM_PROFILE=<nombre>`.
- **Entorno:** `.env` exclusivo para secretos (`ANTHROPIC_API_KEY`) y rutas del sistema.
- **Frontend:** `frontend/.env` — `PORT` y `CORE_API_URL`.

## 4. Manual de Operaciones (CLI)

### Comandos Make
```bash
make test             # pytest con cobertura
make lint             # ruff check + format
make db-clean         # limpia registros de la DB
make list             # lista todas las historias
make generate ARG=<id>
make export   ARG=<id>
```

---
*Para detalles técnicos sobre arquitectura y estándares de desarrollo, consultar [docs/estandar_diseno_arquitectural.md](docs/estandar_diseno_arquitectural.md).*

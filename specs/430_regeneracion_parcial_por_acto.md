# SPEC-430: Regeneración Parcial por Acto (solo Voz)

**Fecha:** 2026-09-21
**Tipo:** SDD (Spec-Driven Development)
**Estado:** DONE (todas las tareas marcadas; estado actualizado 2026-09-24, Spec-520)

---

## ASSUMPTIONS

1. **Alcance confirmado con el usuario:** regenerar un acto significa **re-narrar solo la Voz** (1 llamada LLM). No se re-ejecuta el Mapper ni el Journal de ese acto — el `summary`, `active_scenario_id` y el journal posterior a ese acto quedan intactos. Cero riesgo de romper la continuidad con los actos siguientes, porque nada de lo que ellos leyeron cambia.
2. **Destino confirmado con el usuario:** el cambio actualiza **en el lugar** la variante (`generated_narrative`) que la familia está mirando en la galería — no crea una fila nueva. Esto es viable sin nueva infraestructura: `SQLGeneratedNarrativeRepository.save()` ya hace `INSERT OR REPLACE` por `id`, así que reconsolidar y volver a guardar con el mismo `id` alcanza.
3. El endpoint `POST /stories/{story_id}/beats/{beat_number}` (`beat_router.py:65-84`) existe pero está **muerto** (no lo llama el frontend — verificado por grep) y **roto** (hardcodea `OllamaAdapter` ignorando el perfil activo, y usa `VozUseCase.execute()` — el método legacy — sin pasarle `previous_beats` ni `journal`, generando el beat sin ningún contexto). Se **reescribe** este endpoint en vez de crear uno nuevo.
4. Falta `get_narrative_anchors(story_id)` en `SQLStoryRepository` — hoy `save_narrative_anchors()` persiste los anclajes pero nunca se releen. Se agrega siguiendo el mismo patrón que `get_journal()`.
5. Todo lo demás que necesita el prompt del beat ya es recuperable sin LLM: `beat.summary` y `beat.active_scenario_id` están en `macro_beat` (cargados por `story_repo.get_by_id()`), `active_rules` es determinístico (`story.active_rules_for_beat()`), `previous_journal` se lee de `narrative_journal` vía `get_journal(story_id, beat_number - 1)`.
6. El botón "Regenerar este acto" vive en `relatos.ejs`, junto a cada bloque `## Acto N` (trabajo de Spec-410, en curso sin commitear, agrega el título "Acto N"). Este spec toca `relatos.ejs` en una sección distinta (el bloque de acciones por acto, no el parseo de títulos) — **ask first** si al implementar aparece conflicto real con esos cambios.
7. La llamada es **síncrona** (request/response HTTP normal, no SSE): al ser 1 sola llamada LLM (segundos a ~1 minuto en local), no se justifica la complejidad de otro canal SSE. El botón se deshabilita y muestra spinner mientras espera.
8. Si el acto pedido no tiene `generated_act` aún (no debería ocurrir sobre una variante ya consolidada) o la historia no tiene `narrative_anchors` persistidos, el endpoint responde 400 con mensaje claro.
9. El `journal` interno del sistema (para el acto regenerado y los siguientes) **no cambia** — es justamente lo que hace segura esta regeneración parcial.

---

## OBJECTIVE

Hoy, si a la familia no le gusta cómo quedó escrito un acto, la única opción es "Iniciar regeneración": borra la historia completa y vuelve a correr las 17 llamadas LLM desde cero (`streaming-room.ejs:234-245`). Esto es lento y, para ese caso de uso puntual ("no me gustó cómo suena este acto"), desproporcionado.

**Objetivo:** agregar un botón "Regenerar este acto" en la vista de relatos que dispare **una sola llamada LLM** (solo la Voz), reutilizando todo lo demás ya persistido (eventos del acto, escenario, reglas, journal), y que el resultado reemplace ese acto en la variante que se está viendo — sin tocar el resto de la historia.

**Éxito se ve como:**
- Click en "Regenerar este acto" → nueva prosa para ese acto en 1 llamada LLM (no 17).
- Los demás actos de la historia quedan exactamente igual.
- La variante en la galería se actualiza con el nuevo texto (mismo `narrative_id`, mismo lugar en la UI).
- Si se regenera dos veces seguidas el mismo acto, cada resultado reemplaza al anterior (no se acumulan variantes fantasma).

---

## COMMANDS

```bash
uv run pytest tests/unit/application/use_cases/test_regenerate_beat_voz_use_case.py -v
uv run pytest tests/unit/infrastructure/database/ -v -k "narrative_anchors or generated_narrative"
make lint
make test
cd frontend && npm test   # si aplica a los controllers nuevos
make dev                  # verificación manual end-to-end
```

---

## PROJECT STRUCTURE

### Backend

```
src/infrastructure/database/repositories/
├── story_repository.py                # + get_narrative_anchors()

src/application/use_cases/
├── regenerate_beat_voz_use_case.py     # NUEVO — orquesta la regeneración de un acto
├── generate_narratives_use_case.py     # + update_content(narrative_id, story)

src/presentation/
├── routers/beat_router.py              # reescribe POST /stories/{id}/beats/{n}
├── schemas/request.py                  # + BeatRegenerateRequest
├── schemas/response.py                 # + BeatRegenerateResponse
```

### Frontend

```
frontend/src/controllers/
├── relatos.controller.ts               # + regenerarActoAction

frontend/src/routes/
├── index.ts                            # + POST /historia/:storyId/relatos/:narrativeId/actos/:actoNumero/regenerar

frontend/src/views/
├── relatos.ejs                         # + botón "Regenerar este acto" por acto (HTMX)
```

---

## 1. BACKEND — `get_narrative_anchors()` (StoryRepository)

### Código estilo

Simétrico a `get_journal()` (`story_repository.py:315-348`) y usa el mismo patrón de columnas que `save_narrative_anchors()` (`story_repository.py:398-431`):

```python
async def get_narrative_anchors(self, story_id: UUID) -> NarrativeAnchors | None:
    """Lee los 5 anclajes de resonancia persistidos (Spec-081/Spec-430)."""
    conn = await get_connection()
    cursor = await conn.execute(
        "SELECT * FROM narrative_anchors WHERE story_id = ?", (str(story_id),)
    )
    row = await cursor.fetchone()
    await conn.close()

    if not row:
        return None

    return NarrativeAnchors(
        story_id=story_id,
        resonance_hamartia=row["resonance_hamartia"],
        resonance_hybris=row["resonance_hybris"],
        resonance_anagnorisis=row["resonance_anagnorisis"],
        resonance_peripeteia=row["resonance_peripeteia"],
        resonance_residual=row["resonance_residual"],
    )
```

---

## 2. BACKEND — `update_content()` (GenerateNarrativesUseCase)

### Código estilo

Reutiliza `_consolidate_content()` ya existente (`generate_narratives_use_case.py:29-34`). No hace falta tocar el repo: `save()` ya es `INSERT OR REPLACE` por `id`.

```python
async def update_content(self, narrative_id: UUID, story: Story) -> GeneratedNarrative:
    """Reconsolida `story.beats` y sobrescribe una variante existente (Spec-430).

    A diferencia de consolidate_and_save() (que siempre crea fila nueva), este
    método preserva id/título/fecha — pensado para regeneración parcial por acto.
    """
    narrative = await self.narrative_repo.get_by_id(narrative_id)
    if not narrative:
        raise ValueError(f"Relato generado no encontrado: {narrative_id}")
    if narrative.story_template_id != story.id:
        raise ValueError(f"El relato {narrative_id} no pertenece a la historia {story.id}")

    narrative.content = self._consolidate_content(story)
    return await self.narrative_repo.save(narrative)
```

---

## 3. BACKEND — `RegenerateBeatVozUseCase` (nuevo)

### Código estilo

```python
class RegenerateBeatVozUseCase:
    """Re-narra la Voz de un único acto ya generado, sin tocar Mapper ni Journal (Spec-430)."""

    def __init__(
        self,
        llm: LLMProvider,
        prompt_builder: PromptBuilder,
        story_repo: SQLStoryRepository,
        beat_repo: SQLBeatRepository,
        narrative_use_case: GenerateNarrativesUseCase,
        voz_use_case: VozUseCase | None = None,
    ):
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.story_repo = story_repo
        self.beat_repo = beat_repo
        self.narrative_use_case = narrative_use_case
        self.voz = voz_use_case or VozUseCase(llm, prompt_builder=prompt_builder)

    async def execute(
        self, story_id: UUID, beat_number: int, narrative_id: UUID
    ) -> tuple[MacroBeat, GeneratedNarrative]:
        story = await self.story_repo.get_by_id(story_id)
        if not story:
            raise StoryNotFoundError(f"Historia no encontrada: {story_id}")

        beat = next((b for b in story.beats if b.number == beat_number), None)
        if not beat or not beat.has_content():
            raise ValueError(f"Acto {beat_number} no encontrado o no narrado aún")

        anchors = await self.story_repo.get_narrative_anchors(story_id)
        if not anchors:
            raise ValueError(f"Historia {story_id} no tiene anclajes narrativos persistidos")

        analyst = StoryAnalystService(self.llm, self.prompt_builder)
        beat_anchors = analyst.resolve_beat_anchors(anchors, beat_number)

        previous_journal = None
        if beat_number > 1:
            previous_journal = await self.story_repo.get_journal(story_id, beat_number - 1)

        active_rules = story.active_rules_for_beat(beat_number)

        beat.user_prompt = self.prompt_builder.build_narrative_context(
            beat, beat_anchors, previous_journal, story=story, active_rules=active_rules
        )

        beat, _elapsed = await self.voz.narrate(beat, story)
        await self.beat_repo.update(beat, story_id)

        story.beats = [beat if b.number == beat_number else b for b in story.beats]
        narrative = await self.narrative_use_case.update_content(narrative_id, story)

        return beat, narrative
```

---

## 4. BACKEND — Endpoint (reescribe `beat_router.py`)

### Antes (muerto/roto, `beat_router.py:65-84`)

```python
@router.post("/stories/{story_id}/beats/{beat_number}", response_model=BeatResponse)
async def generate_beat(story_id: str, beat_number: int):
    from src.infrastructure.adapters import OllamaAdapter
    ...
    llm = OllamaAdapter()  # ignora el perfil activo
    use_case = VozUseCase(llm)
    generated_beat, _ = await use_case.execute(story, beat)  # sin contexto ni journal
```

### Después

```python
class BeatRegenerateRequest(BaseModel):
    narrative_id: UUID

class BeatRegenerateResponse(BaseModel):
    beat: BeatResponse
    narrative_id: UUID
    narrative_content: str


def get_regenerate_beat_use_case(...) -> RegenerateBeatVozUseCase:
    return RegenerateBeatVozUseCase(
        llm=LLMFactory.get_provider(),
        prompt_builder=PromptBuilder(),
        story_repo=SQLStoryRepository(),
        beat_repo=SQLBeatRepository(),
        narrative_use_case=GenerateNarrativesUseCase(),
    )


@router.post("/stories/{story_id}/beats/{beat_number}/regenerate-voz", response_model=BeatRegenerateResponse)
async def regenerate_beat_voz(
    story_id: str,
    beat_number: int,
    request: BeatRegenerateRequest,
    use_case: RegenerateBeatVozUseCase = Depends(get_regenerate_beat_use_case),
):
    try:
        beat, narrative = await use_case.execute(
            UUID(story_id), beat_number, request.narrative_id
        )
    except StoryNotFoundError:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return BeatRegenerateResponse(
        beat=BeatResponse(
            number=beat.number, summary=beat.summary,
            content=beat.generated_act, status=beat.status,
        ),
        narrative_id=narrative.id,
        narrative_content=narrative.content,
    )
```

Nota: se usa una ruta nueva `.../regenerate-voz` (no se reescribe la URL `POST /stories/{id}/beats/{n}` a secas) para no romper el contrato existente por si algo externo lo invoca, aunque el grep no encontró consumidores. El handler viejo (`generate_beat`) se **elimina** junto con su bug de `OllamaAdapter` hardcodeado.

---

## 5. FRONTEND — Botón "Regenerar este acto"

### Ubicación

En `relatos.ejs`, dentro del loop que renderiza cada `## Acto N` (línea ~77-78 actual), junto al heading:

```ejs
<div class="flex items-center justify-between mt-10 mb-4">
  <h3 class="heading-forge-lg !text-2xl !text-forge-accent"><%= mapBeatTitle(sections[i]) %></h3>
  <button
    class="btn-forge-sm"
    hx-post="/historia/<%= story.id %>/relatos/<%= relato.id %>/actos/<%= extractActNumber(sections[i]) %>/regenerar"
    hx-target="#relato-content-<%= relato.id %>"
    hx-swap="outerHTML"
    hx-confirm="¿Regenerar este acto? Se reemplazará el texto actual."
  >
    <i data-lucide="refresh-cw" class="w-4 h-4"></i> Regenerar este acto
  </button>
</div>
```

### Controller (`relatos.controller.ts`)

```ts
export const regenerarActoAction = async (req: Request, res: Response) => {
  const { storyId, narrativeId, actoNumero } = req.params;
  try {
    await axios.post(
      `${CORE_API_URL}/api/v1/stories/${storyId}/beats/${actoNumero}/regenerate-voz`,
      { narrative_id: narrativeId },
      { timeout: 120000 },
    );
    const story = await getStoryById(storyId);
    const relatos = await getRelatosForStory(storyId);
    // Re-renderiza solo el panel del relato afectado (partial HTMX)
    res.render("partials/relato_panel", { story, relato: relatos.find(r => r.id === narrativeId) });
  } catch (error) {
    console.error("Error al regenerar acto:", error);
    res.status(500).send("No se pudo regenerar el acto.");
  }
};
```

Requiere extraer el bloque `<div id="relato-content-...">...</div>` de `relatos.ejs` a un partial reusable (`partials/relato_panel.ejs`) para poder swapearlo completo tras el POST — hoy vive inline en el loop principal.

---

## PLAN

### Hito 1: Backend — lectura de anclajes + actualización de variante
1. `get_narrative_anchors()` en `SQLStoryRepository`
2. Tests: guarda anclajes → los lee de vuelta, historia sin anclajes → `None`
3. `update_content()` en `GenerateNarrativesUseCase`
4. Tests: reconsolida y sobrescribe con mismo `id`; narrative_id inexistente → `ValueError`; narrative de otra historia → `ValueError`

### Hito 2: Backend — caso de uso de regeneración
5. `RegenerateBeatVozUseCase` completo
6. Tests: beat inexistente/no narrado → `ValueError`; sin anclajes → `ValueError`; beat 1 (sin journal previo) vs beat >1 (con journal previo); verifica que `journal` de la historia NO se toca; verifica que solo el acto pedido cambia en `narrative.content`

### Hito 3: Backend — endpoint
7. Nuevo `BeatRegenerateRequest`/`BeatRegenerateResponse` en schemas
8. Nuevo endpoint `POST /stories/{id}/beats/{n}/regenerate-voz`, elimina el handler viejo `generate_beat` y su import de `OllamaAdapter`
9. Test de integración del router (mock del use case)

### Hito 4: Frontend
10. Extraer `partials/relato_panel.ejs` del loop de `relatos.ejs`
11. Botón "Regenerar este acto" con HTMX (`hx-post`, `hx-confirm`, `hx-target`)
12. `regenerarActoAction` en `relatos.controller.ts` + ruta en `routes/index.ts`
13. Verificación manual: `make dev`, generar una historia, regenerar un acto, confirmar que solo ese acto cambia y que no dispara las 17 llamadas

---

## TASKS

- [x] **T1:** `get_narrative_anchors(story_id)` en `SQLStoryRepository`
  - Acceptance: retorna `NarrativeAnchors` si existen, `None` si no
  - Files: `src/infrastructure/database/repositories/story_repository.py`

- [x] **T2:** Tests de `get_narrative_anchors`
  - Files: `tests/unit/infrastructure/database/test_story_repository.py` (o el archivo equivalente existente)

- [x] **T3:** `update_content(narrative_id, story)` en `GenerateNarrativesUseCase`
  - Acceptance: mismo `id`/`title`/`created_at`, `content` reconsolidado; `ValueError` si no existe o no pertenece a la historia
  - Files: `src/application/use_cases/generate_narratives_use_case.py`

- [x] **T4:** Tests de `update_content`
  - Files: `tests/unit/application/use_cases/test_generate_narratives_use_case.py`

- [x] **T5:** `RegenerateBeatVozUseCase`
  - Acceptance: 1 sola llamada LLM (a `voz.narrate`); no llama a `MemoryJournalist`; no llama al Mapper; actualiza `macro_beat` y la variante
  - Files: `src/application/use_cases/regenerate_beat_voz_use_case.py` (nuevo)

- [x] **T6:** Tests de `RegenerateBeatVozUseCase` (casos: beat 1 sin journal previo, beat >1 con journal previo, beat inexistente, sin anclajes, narrative_id inválido)
  - Files: `tests/unit/application/use_cases/test_regenerate_beat_voz_use_case.py` (nuevo)

- [x] **T7:** Reescribir `beat_router.py`: nuevo endpoint `POST /stories/{id}/beats/{n}/regenerate-voz`, elimina `generate_beat` viejo
  - Acceptance: 404 si historia no existe, 400 si beat no narrado o sin anclajes, 200 con `BeatRegenerateResponse`
  - Files: `src/presentation/routers/beat_router.py`, `src/presentation/schemas/request.py`, `src/presentation/schemas/response.py`

- [x] **T8:** Test de integración del endpoint
  - Files: `tests/unit/presentation/routers/test_beat_router.py` (o equivalente)

- [x] **T9:** Extraer `partials/relato_panel.ejs` de `relatos.ejs`
  - Acceptance: la vista principal se ve idéntica tras el refactor
  - Files: `frontend/src/views/relatos.ejs`, `frontend/src/views/partials/relato_panel.ejs` (nuevo)

- [x] **T10:** Botón "Regenerar este acto" (HTMX) + `regenerarActoAction` + ruta
  - Acceptance: click regenera solo ese acto, swap actualiza el panel, confirm dialog antes de disparar
  - Files: `frontend/src/views/relatos.ejs`, `frontend/src/controllers/relatos.controller.ts`, `frontend/src/routes/index.ts`

- [x] **T11:** Verificación manual end-to-end (`make dev`)
  - Acceptance: regenerar un acto no dispara las 17 llamadas, solo cambia ese acto, la galería refleja el cambio sin crear variante nueva

---

## BOUNDARIES

- **Always:** `make lint` y `make test` tras cada hito.
- **Ask first:**
  - Si al tocar `relatos.ejs` aparece conflicto real con los cambios sin commitear de Spec-410 (título "Acto N", cards resaltadas).
  - Si `beat_repo.update()` o el esquema de `macro_beat` no se comportan como lo documentado acá (verificar antes de asumir).
  - Antes de eliminar el endpoint viejo `generate_beat`, confirmar que efectivamente no lo usa nada (re-grep en frontend/tests antes de implementar, por si cambió desde esta investigación).
- **Never:** Tocar `MemoryJournalist`/`SynopsisBeatMapper` en este spec — la regeneración parcial es deliberadamente solo-Voz. Si más adelante se quiere regenerar eventos, es un evolutivo aparte (fuera de alcance, ya evaluado y descartado por costo/riesgo de cascada).

---

## SUCCESS CRITERIA

- Regenerar un acto dispara exactamente 1 llamada LLM (verificable con `DebugCollector`/logs).
- El `narrative_journal` de la historia no cambia tras la regeneración.
- La variante (`generated_narrative`) mostrada conserva su `id`; solo cambia `content`.
- Los demás 4 actos permanecen byte-por-byte iguales en el `content` consolidado.
- `make test` y `make lint` pasan.

---

## OPEN QUESTIONS

Ninguna — alcance y destino del cambio confirmados con el usuario. Pendiente de aprobación del documento completo antes de pasar a IMPLEMENT.

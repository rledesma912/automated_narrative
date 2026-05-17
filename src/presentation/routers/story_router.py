"""Story router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from src.application.dto import StoryCreateDTO
from src.application.services.narrator_config_sanitizer import sanitize_narrator_config
from src.application.services.observability_service import observability
from src.application.use_cases import GetStoryByIdUseCase, ListStoriesUseCase
from src.application.use_cases.create_story import CreateStoryUseCase
from src.domain.models import StoryStatus
from src.infrastructure.database.repositories import SQLStoryRepository
from src.presentation.schemas.request import StoryCreateRequest
from src.presentation.schemas.response import StoryResponse

router = APIRouter(tags=["Stories"])


def _story_repo() -> SQLStoryRepository:
    return SQLStoryRepository()


def get_create_story_use_case(repo=Depends(_story_repo)) -> CreateStoryUseCase:
    return CreateStoryUseCase(repo)


def get_list_stories_use_case(repo=Depends(_story_repo)) -> ListStoriesUseCase:
    return ListStoriesUseCase(repo)


def get_story_by_id_use_case(repo=Depends(_story_repo)) -> GetStoryByIdUseCase:
    return GetStoryByIdUseCase(repo)


def _request_to_dto(req: StoryCreateRequest) -> StoryCreateDTO:
    """Traduce StoryCreateRequest (capa presentación) → StoryCreateDTO (capa aplicación).

    Resuelve incompatibilidades entre capas:
    1. escenarios: str → list[str]  (usa narrator_config.scenarios si existe)
       y escenarios_full con description desde narrator_config.scenarios
    2. typed_rules: ausente en request → list[dict] desde narrator_config.rules
    3. rules[].text → content  (campo renombrado entre frontend y use case)
    4. narrator_config persistido se depura (Spec-190 §4.3).
    """
    sc: dict = req.narrator_config or {}

    # 1. Escenarios: preferir estructura rica de narrator_config, fallback al string
    raw_scenarios: list[dict] = sc.get("scenarios") or []
    escenarios_full: list[dict] = []
    if raw_scenarios:
        escenarios_list = [s.get("name", "") for s in raw_scenarios if s.get("name")]
        escenarios_full = [
            {"name": s.get("name", ""), "description": s.get("description", "")}
            for s in raw_scenarios
            if s.get("name")
        ]
    else:
        escenarios_list = [
            chunk.split(":")[0].strip()
            for chunk in (req.escenarios or "").split(";")
            if chunk.strip()
        ]

    # 2. Typed rules: desde narrator_config.rules, mapeando text → content
    raw_rules: list[dict] = sc.get("rules") or []
    typed_rules = [
        {
            "id": r.get("id", ""),
            "content": r.get("text") or r.get("content", ""),
            "type": r.get("type", ""),
        }
        for r in raw_rules
        if r.get("text") or r.get("content")
    ]

    return StoryCreateDTO(
        title=req.title,
        protagonista=req.protagonista,
        relator=req.relator,
        escenarios=escenarios_list,
        escenarios_full=escenarios_full,
        sinopsis=req.sinopsis,
        genero=req.genero,
        subgenero=req.subgenero,
        tono=req.tono,
        reglas=req.reglas,
        narrator_config=sanitize_narrator_config(req.narrator_config),
        typed_rules=typed_rules,
        personajes_full=req.personajes_full,
    )


@router.post("/stories", response_model=StoryResponse, status_code=201)
async def create_story(
    request: StoryCreateRequest,
    action: str = "generate",
    use_case: CreateStoryUseCase = Depends(get_create_story_use_case),
):
    """Create a new story. action=save → draft; action=generate → draft (inicia proceso)."""
    try:
        dto = _request_to_dto(request)
        # Consolidado: todo inicia en DRAFT. El proceso de stream cambiará a PROCESSING.
        initial_status = StoryStatus.DRAFT
        story = await use_case.execute(dto, initial_status=initial_status)

        observability.record(
            category="database",
            message=f"Historia '{story.title}' guardada como {action}",
            story_id=str(story.id),
            story_title=story.title,
        )

        return StoryResponse(
            id=str(story.id),
            title=story.title,
            status=story.status.value,
            created_at=story.created_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stories", response_model=list[StoryResponse])
async def list_stories(
    use_case: ListStoriesUseCase = Depends(get_list_stories_use_case),
):
    """List all stories."""
    stories = await use_case.execute()
    return [
        StoryResponse(
            id=str(s.id),
            title=s.title,
            status=s.status.value,
            created_at=s.created_at,
            genero=s.genero,
            subgenero=s.subgenero,
            tono=s.tono,
            protagonista=s.protagonista,
        )
        for s in stories
    ]


_PATCHABLE_STATUSES = {"draft", "pending", "failed", "processing"}


@router.patch("/stories/{story_id}/status", status_code=200)
async def update_story_status(
    story_id: str,
    body: dict,
    repo: SQLStoryRepository = Depends(_story_repo),
):
    """Actualiza el status de una historia. Solo permite transiciones a estados seguros.

    Si la transición es a `processing` (regeneración), se ejecuta limpieza inmediata
    de artefactos ANTES del UPDATE de status (Spec-216).
    """
    new_status = body.get("status", "")
    if new_status not in _PATCHABLE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Status '{new_status}' no permitido. Válidos: {sorted(_PATCHABLE_STATUSES)}",
        )
    story = await repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    if new_status == "processing":
        await repo.clear_story_artifacts(story.id)
        observability.record(
            category="generation",
            message=f"Limpieza completa para regeneración — story_id={story_id}",
            story_id=story_id,
        )

    await repo.update_status(story.id, new_status)
    return {"id": story_id, "status": new_status}


@router.patch("/stories/{story_id}", response_model=StoryResponse, status_code=200)
async def update_story(
    story_id: str,
    request: StoryCreateRequest,
    repo: SQLStoryRepository = Depends(_story_repo),
):
    """Actualiza datos de una historia en estado draft (Spec-214 F2)."""
    from uuid import uuid4

    from src.domain.models import RuleType, Scenario, TypedRule

    story = await repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")
    if story.status != StoryStatus.DRAFT:
        raise HTTPException(
            status_code=422, detail="Solo se pueden editar historias en estado draft"
        )

    dto = _request_to_dto(request)
    story.title = dto.title
    story.protagonista = dto.protagonista
    story.relator = dto.relator
    story.sinopsis = dto.sinopsis
    story.genero = dto.genero
    story.subgenero = dto.subgenero
    story.tono = dto.tono
    story.reglas = dto.reglas
    story.narrator_config = dto.narrator_config
    story.personajes_full = dto.personajes_full or []

    if dto.escenarios_full:
        story.scenarios = [
            Scenario(
                story_id=story.id,
                order_index=i,
                name=s.get("name", ""),
                description=s.get("description", ""),
            )
            for i, s in enumerate(dto.escenarios_full)
        ]
    elif dto.escenarios:
        story.scenarios = [
            Scenario(story_id=story.id, order_index=i, name=name)
            for i, name in enumerate(dto.escenarios)
        ]

    if dto.typed_rules:
        typed = []
        for r in dto.typed_rules:
            raw_type = r.get("type")
            try:
                rule_type = RuleType(raw_type) if raw_type else None
            except ValueError:
                rule_type = None
            typed.append(
                TypedRule(
                    id=r.get("id") or str(uuid4()),
                    story_id=story.id,
                    content=r.get("content", ""),
                    type=rule_type,
                    intensity=r.get("intensity"),
                )
            )
        story.typed_rules = typed

    await repo.save(story)
    return StoryResponse(
        id=str(story.id), title=story.title, status=story.status.value, created_at=story.created_at
    )


@router.delete("/stories/{story_id}", status_code=204)
async def delete_story(
    story_id: str,
    repo: SQLStoryRepository = Depends(_story_repo),
):
    """Hard delete: borra historia y beats."""
    story = await repo.get_by_id(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")

    await repo.delete(UUID(story_id))
    observability.record(
        "database", f"Historia '{story.title}' eliminada de DB", type="warning", story_id=story_id
    )
    return Response(status_code=204)


@router.get("/stories/{story_id}", response_model=StoryResponse)
async def get_story(
    story_id: str,
    use_case: GetStoryByIdUseCase = Depends(get_story_by_id_use_case),
):
    """Get a story by ID."""
    story = await use_case.execute(UUID(story_id))
    if not story:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")
    return StoryResponse(
        id=str(story.id),
        title=story.title,
        status=story.status.value,
        created_at=story.created_at,
        genero=story.genero,
        subgenero=story.subgenero,
        tono=story.tono,
        protagonista=story.protagonista,
        relator=story.relator,
        sinopsis=story.sinopsis,
        narrator_config=story.narrator_config,
        personajes_full=story.personajes_full,
    )

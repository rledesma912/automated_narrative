"""API del asistente de autoría (Spec-530 S3): Dirección, Taller y Escaleta.

Las llamadas a la IA no están acá: son jobs (`POST /stories/{id}/jobs` con
`consult`, `plan_outline` o `verify_outline`). Acá se guarda lo que escribe el
autor y se lee el estado. Con un job activo, todo guardado responde 409 (el
modal bloquea la página, pero la API no confía en eso).
"""

import sqlite3
from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.application.dto import StoryCreateDTO
from src.application.services.authoring import catalog, context, workshop_rules
from src.application.use_cases.create_story import CreateStoryUseCase, ensure_valid_genre
from src.domain.exceptions import InvalidStoryInputError
from src.domain.models import (
    ActOutline,
    CharacterKind,
    CriterionStatus,
    Direction,
    Story,
    WorkshopItem,
    WorkshopLevel,
)
from src.infrastructure.database.repositories import (
    SQLGenreRepository,
    SQLJobRepository,
    SQLStoryRepository,
)
from src.presentation.runtime import job_manager
from src.presentation.schemas.authoring import ActForm, DirectionForm, WorkshopAction

router = APIRouter(prefix="/authoring", tags=["authoring"])

_PLACEHOLDER_SYNOPSIS = "(todavía sin contar)"


# ── Opciones ───────────────────────────────────────────────────────────────


@router.get("/options")
async def get_options() -> dict:
    """Efectos, «cómo lo cuenta» y criterios del taller (fuente única: `config/`)."""
    return {
        "effects": [o.__dict__ for o in catalog.effects()],
        "tellings": [o.__dict__ for o in catalog.tellings()],
        "criteria": [c.__dict__ for c in catalog.direction_criteria()],
    }


# ── Dirección ──────────────────────────────────────────────────────────────


@router.post("/stories", status_code=201)
async def create_authoring_story(form: DirectionForm) -> dict:
    """Crea el borrador desde la Dirección (primer guardado de «Nuevo relato»)."""
    repo = SQLStoryRepository()
    dto = StoryCreateDTO(
        **_story_fields(form, existing=None), direction=_direction(form).model_dump()
    )
    try:
        story = await CreateStoryUseCase(repo, SQLGenreRepository()).execute(dto)
    except (InvalidStoryInputError, sqlite3.IntegrityError) as e:
        raise _unprocessable(e) from e
    return await _state(await repo.get_by_id(story.id))


@router.put("/stories/{story_id}/direction")
async def update_direction(story_id: str, form: DirectionForm) -> dict:
    """Guardado automático de la Dirección. No toca el taller ni la escaleta."""
    repo = SQLStoryRepository()
    story = await _editable(story_id)
    try:
        await ensure_valid_genre(SQLGenreRepository(), form.genero, form.subgenero)
    except InvalidStoryInputError as e:
        raise _unprocessable(e) from e
    for key, value in _story_fields(form, existing=story).items():
        setattr(story, key, value)
    await repo.update_inputs(story)
    await repo.update_direction(story.id, _direction(form))
    return await _state(await repo.get_by_id(story.id))


# ── Estado completo ────────────────────────────────────────────────────────


@router.get("/stories/{story_id}")
async def get_authoring_state(story_id: str) -> dict:
    return await _state(await _story(story_id))


# ── Taller ─────────────────────────────────────────────────────────────────


@router.patch("/stories/{story_id}/workshop/{criterion}")
async def act_on_criterion(story_id: str, criterion: str, body: WorkshopAction) -> dict:
    """Responder, «Decidí vos», «Es así a propósito» o reabrir un criterio (sin IA)."""
    story = await _editable(story_id)
    item = next(
        (
            w
            for w in story.workshop
            if w.level == WorkshopLevel.DIRECCION and w.criterion == criterion
        ),
        None,
    )
    if item is None:
        if catalog.criterion(criterion) is None:
            raise HTTPException(status_code=404, detail=f"Criterio desconocido: {criterion}")
        item = WorkshopItem(criterion=criterion)
    try:
        updated = _apply(item, body)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    await SQLStoryRepository().save_workshop_items(story.id, [updated])
    return await _state(await _story(story_id))


def _apply(item: WorkshopItem, body: WorkshopAction) -> WorkshopItem:
    if body.action == "answer":
        if not body.text.strip():
            raise ValueError("La respuesta está vacía")
        return workshop_rules.answer(item, body.text)
    if body.action == "decide":
        return workshop_rules.decide_for_me(item)
    if body.action == "intentional":
        return workshop_rules.mark_intentional(item, body.text)
    # reopen: vuelve a evaluarse en la próxima ronda.
    return item.model_copy(update={"status": CriterionStatus.FALTA, "answer": ""})


# ── Escaleta ───────────────────────────────────────────────────────────────


@router.put("/stories/{story_id}/outline/{number}")
async def update_act(story_id: str, number: int, form: ActForm) -> dict:
    """Guardado automático de un acto. Los avisos de la revisión quedan hasta revisar de nuevo."""
    if not 1 <= number <= 5:
        raise HTTPException(status_code=404, detail=f"Acto inexistente: {number}")
    story = await _editable(story_id)
    previous = next((a for a in story.outline if a.number == number), None)
    act = ActOutline(
        number=number,
        **{k: _clean(v) for k, v in form.model_dump().items()},
        warnings=previous.warnings if previous else [],
    )
    await SQLStoryRepository().save_act(story.id, act)
    return await _state(await _story(story_id))


# ── Helpers ────────────────────────────────────────────────────────────────


async def _story(story_id: str) -> Story:
    try:
        story = await SQLStoryRepository().get_by_id(UUID(story_id))
    except ValueError:
        story = None
    if story is None:
        raise HTTPException(status_code=404, detail=f"Historia no encontrada: {story_id}")
    return story


async def _editable(story_id: str) -> Story:
    story = await _story(story_id)
    active = await SQLJobRepository().get_active_for_story(story.id)
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail="La IA está trabajando en esta historia: esperá a que termine",
            headers={"X-Job-Id": str(active.id)},
        )
    return story


def _unprocessable(e: Exception) -> HTTPException:
    message = e.message if isinstance(e, InvalidStoryInputError) else f"Datos rechazados: {e}"
    return HTTPException(status_code=422, detail=message)


def _direction(form: DirectionForm) -> Direction:
    return Direction(
        premise=form.premise.strip(),
        effect=form.effect,
        effect_other=form.effect_other.strip(),
        ending=form.ending.strip(),
        ending_intentional=form.ending_intentional,
        telling=form.telling,
    )


def _story_fields(form: DirectionForm, existing: Story | None) -> dict:
    """Campos de `Story` que se derivan de la Dirección (el resto del dominio no cambia)."""
    name = form.protagonist_name.strip() or "Protagonista"
    role = form.protagonist_role.strip()
    narrator = form.narrator.strip() or name
    cast = [dict(p) for p in (existing.personajes_full if existing else [])]
    lead = {"id": "P1", "name": name, "role": role, "kind": CharacterKind.PERSONA.value}
    cast = [{**(cast[0] if cast else {}), **lead}, *cast[1:]]
    config = dict((existing.narrator_config if existing else None) or {})
    config.update(
        storyteller_id=next(
            (p.get("id") or f"P{i}" for i, p in enumerate(cast, 1) if p["name"] == narrator), "P1"
        ),
        storyteller_name=narrator,
        voice={"person": "primera", "tense": "pasado"},
    )
    return {
        "title": form.title.strip(),
        "genero": form.genero,
        "subgenero": form.subgenero,
        "protagonista": f"{name}: {role}" if role else name,
        "relator": f"Primera persona en pasado. Narrador: {narrator}.",
        "sinopsis": form.premise.strip() or _PLACEHOLDER_SYNOPSIS,
        "personajes_full": cast,
        "narrator_config": config,
    }


def _form(story: Story) -> dict:
    d = story.direction or Direction()
    lead = (story.personajes_full or [{}])[0]
    return {
        **DirectionForm(
            title=story.title,
            genero=story.genero,
            subgenero=story.subgenero,
            premise=d.premise,
            effect=d.effect,
            effect_other=d.effect_other,
            ending=d.ending,
            ending_intentional=d.ending_intentional,
            telling=d.telling,
            protagonist_name=lead.get("name", ""),
            protagonist_role=lead.get("role", ""),
            narrator=(story.narrator_config or {}).get("storyteller_name", ""),
        ).model_dump()
    }


async def _state(story: Story) -> dict:
    """Todo lo que necesitan las tres vistas del asistente."""
    items = [w for w in story.workshop if w.level == WorkshopLevel.DIRECCION]
    by_id = {w.criterion: w for w in items}
    ordered = [by_id[c.id] for c in catalog.direction_criteria() if c.id in by_id]
    if ordered:
        f = workshop_rules.finish(ordered)
        finish = {"kind": f.kind, "text": f.text, "open_questions": f.open_questions}
    else:
        finish = {
            "kind": "sin_analizar",
            "text": "Todavía no analizaste la historia: apretá «Analizar mi historia».",
            "open_questions": 0,
        }
    used = {d for a in story.outline for d in a.decisions}
    active = await SQLJobRepository().get_active_for_story(story.id)
    return {
        "story_id": str(story.id),
        "status": story.status.value,
        "direction": _form(story),
        "workshop": {
            "round": workshop_rules.current_round(ordered),
            "max_rounds": workshop_rules.MAX_ROUNDS,
            "finish": finish,
            "items": [
                {**w.model_dump(mode="json"), "nombre": c.nombre, "por_que": c.por_que}
                for w, c in (
                    (by_id[c.id], c) for c in catalog.direction_criteria() if c.id in by_id
                )
            ],
        },
        "outline": {
            "acts": [a.model_dump(mode="json") for a in story.outline],
            "decisions": [
                {"id": cid, "nombre": nombre, "integrada": cid in used}
                for cid, nombre, _ in context.decisions(story)
            ],
        },
        "characters": [
            {
                "name": p.get("name", ""),
                "kind": p.get("kind", "persona"),
                "relation": p.get("relation", ""),
            }
            for p in story.personajes_full or []
        ],
        # Los de la historia y los que la escaleta sumó: opciones rápidas en cada acto.
        "scenarios": list(
            dict.fromkeys(
                [s.name for s in story.scenarios]
                + [a.scenario for a in story.outline if a.scenario]
            )
        ),
        "active_job": await job_manager.payload(active) if active else None,
    }


def _clean(value):
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return [" ".join(v.split()) for v in value if isinstance(v, str) and v.strip()]
    return value

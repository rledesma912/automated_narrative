"""API del asistente de autoría (Spec-530 S3): Dirección, Taller y Escaleta.

Las llamadas a la IA no están acá: son jobs (`POST /stories/{id}/jobs` con
`consult`, `plan_outline` o `verify_outline`). Acá se guarda lo que escribe el
autor y se lee el estado. Con un job activo, todo guardado responde 409 (el
modal bloquea la página, pero la API no confía en eso).
"""

import sqlite3
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException

from src.application.dto import StoryCreateDTO
from src.application.services.authoring import catalog, context, workshop_rules
from src.application.services.beat_spec_repository import BeatSpecRepository
from src.application.use_cases.create_story import (
    CreateStoryUseCase,
    build_entities,
    ensure_valid_entities,
    ensure_valid_genre,
)
from src.domain.exceptions import InvalidStoryInputError
from src.domain.models import (
    ActOutline,
    CharacterKind,
    CriterionStatus,
    Direction,
    Scenario,
    Story,
    TypedRule,
    WorkshopItem,
    WorkshopLevel,
)
from src.infrastructure.database.repositories import (
    SQLGenreRepository,
    SQLJobRepository,
    SQLStoryRepository,
)
from src.messages import message
from src.presentation.runtime import job_manager
from src.presentation.schemas.authoring import (
    ActForm,
    CharacterForm,
    DirectionForm,
    NameForm,
    ScenarioForm,
    StructureForm,
    WarningDismiss,
    WorkshopAction,
)

router = APIRouter(prefix="/authoring", tags=["authoring"])


# ── Opciones ───────────────────────────────────────────────────────────────


@router.get("/options")
async def get_options() -> dict:
    """Efectos, «cómo lo cuenta» y criterios del taller (fuente única: `config/`)."""
    return {
        "effects": [o.__dict__ for o in catalog.effects()],
        "tellings": [o.__dict__ for o in catalog.tellings()],
        "criteria": [c.for_story("").__dict__ for c in catalog.direction_criteria()],
        # Spec-650: largos posibles («¿Qué tan largo?»).
        "structures": [
            {"id": e.id, "label": e.label, "acts": e.num_actos}
            for e in (_estructuras().estructura(sid) for sid in _estructuras().structure_ids)
        ],
    }


# ── Dirección ──────────────────────────────────────────────────────────────


@router.post("/stories", status_code=201)
async def create_authoring_story(form: DirectionForm) -> dict:
    """Crea el borrador desde la Dirección (primer guardado de «Nuevo relato»)."""
    repo = SQLStoryRepository()
    dto = StoryCreateDTO(
        **_story_fields(form, existing=None),
        direction=_direction(form).model_dump(),
        entities=_threat(form),
        structure=form.structure,  # Spec-650: se elige al crear
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
    genres = SQLGenreRepository()
    try:
        await ensure_valid_genre(genres, form.genero, form.subgenero)
        # La amenaza reemplaza a la entidad principal; las demás (del wizard) quedan.
        threat = build_entities(story.id, _threat(form))
        entities = threat + [e for e in story.entities if e.order_index > 0]
        for i, e in enumerate(entities):
            e.order_index = i
        await ensure_valid_entities(genres, form.genero, entities)
    except InvalidStoryInputError as e:
        raise _unprocessable(e) from e
    for key, value in _story_fields(form, existing=story).items():
        setattr(story, key, value)
    story.entities = entities
    await repo.update_inputs(story)
    await repo.update_direction(story.id, _direction(form))
    return await _state(await repo.get_by_id(story.id))


@router.put("/stories/{story_id}/structure")
async def change_structure(story_id: str, body: StructureForm) -> dict:
    """Spec-650 §2.5: cambia el largo. Los actos armados se borran (son de la otra
    estructura) y las reglas de cada acto pasan al acto equivalente (D10). Lo respondido
    en las preguntas y las versiones del relato quedan. Mismo largo = no hace nada."""
    story = await _editable(story_id)
    if body.structure == story.structure:
        return await _state(story)
    old = _estructuras().estructura(story.structure)
    new = _estructuras().estructura(body.structure)
    rules = [
        r.model_copy(
            update={"applies_to_beat": new.reubicar(r.applies_to_beat, old)}
            if r.applies_to_beat
            else {}
        )
        for r in story.typed_rules
    ]
    await SQLStoryRepository().change_structure(story.id, body.structure, rules)
    return await _state(await _story(story_id))


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
            raise ValueError(message("api.respuesta_vacia"))
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
    story = await _editable(story_id)
    # Spec-650: solo los actos de su estructura (una pestaña vieja no crea un acto de más).
    if not _estructuras().estructura(story.structure).tiene(number):
        raise HTTPException(status_code=404, detail=f"Acto inexistente: {number}")
    previous = next((a for a in story.outline if a.number == number), None)
    fields = {k: _clean(v) for k, v in form.model_dump(exclude={"rules"}).items()}
    act = ActOutline(
        number=number,
        **fields,
        warnings=previous.warnings if previous else [],
        draft=previous.draft if previous else False,  # un borrador importado sigue siéndolo
        synopsis=previous.synopsis if previous else "",
    )
    repo = SQLStoryRepository()
    await repo.save_act(story.id, act)
    # Las reglas del acto viven en `rule` con `applies_to_beat` (Spec-190 §4.4).
    rules = _clean(form.rules)
    current = [r.content for r in story.typed_rules if r.applies_to_beat == number]
    if rules != current:
        others = [r for r in story.typed_rules if r.applies_to_beat != number]
        story.typed_rules = others + [
            TypedRule(id=str(uuid4()), story_id=story.id, content=r, applies_to_beat=number)
            for r in rules
        ]
        story.reglas = [r.content for r in story.typed_rules]
        await repo.update_inputs(story)
    return await _state(await _story(story_id))


@router.post("/stories/{story_id}/outline/{number}/warnings/dismiss")
async def dismiss_warning(story_id: str, number: int, body: WarningDismiss) -> dict:
    """«Ignorar» un aviso: queda guardado como ignorado y no vuelve al revisar (H10)."""
    return await _set_dismissed(story_id, number, body.key, True)


@router.post("/stories/{story_id}/outline/{number}/warnings/restore")
async def restore_warning(story_id: str, number: int, body: WarningDismiss) -> dict:
    """«Volver a mostrar» un aviso ignorado."""
    return await _set_dismissed(story_id, number, body.key, False)


async def _set_dismissed(story_id: str, number: int, key: str, dismissed: bool) -> dict:
    story = await _editable(story_id)
    act = next((a for a in story.outline if a.number == number), None)
    if act is None:
        raise HTTPException(status_code=404, detail=f"Acto inexistente: {number}")
    if not any(w.key == key for w in act.warnings):
        raise HTTPException(status_code=404, detail="Aviso inexistente")
    warnings = [
        w.model_copy(update={"dismissed": dismissed}) if w.key == key else w for w in act.warnings
    ]
    await SQLStoryRepository().save_act(story.id, act.model_copy(update={"warnings": warnings}))
    return await _state(await _story(story_id))


@router.post("/stories/{story_id}/outline/{number}/warnings/resolve")
async def resolve_warning(story_id: str, number: int, body: WarningDismiss) -> dict:
    """Spec-630 B2: aplicar la sugerencia de un aviso lo resuelve: se quita (no pasa a ignorados)."""
    story = await _editable(story_id)
    act = _act(story, number)
    if not any(w.key == body.key for w in act.warnings):
        raise HTTPException(status_code=404, detail=message("api.aviso_inexistente"))
    warnings = [w for w in act.warnings if w.key != body.key]
    await SQLStoryRepository().save_act(story.id, act.model_copy(update={"warnings": warnings}))
    return await _state(await _story(story_id))


@router.post("/stories/{story_id}/characters")
async def add_character(story_id: str, body: CharacterForm) -> dict:
    """Suma un personaje al elenco (desde un acto o desde un aviso de la revisión).

    Spec-630 B2: con `act`, además queda en «Quiénes están» de ese acto.
    """
    story = await _editable(story_id)
    name = " ".join(body.name.split())
    existing = _find(story.personajes_full or [], name, key=lambda p: p.get("name", ""))
    repo = SQLStoryRepository()
    if existing is None:
        story.personajes_full = [
            *story.personajes_full,
            {
                "id": _next_character_id(story.personajes_full),
                "name": name,
                "role": "",
                "kind": body.kind,
                "relation": body.relation.strip(),
            },
        ]
        await repo.update_inputs(story)
    else:
        name = existing["name"]
    if body.act is not None:
        act = _act(story, body.act)
        if not any(_same(n, name) for n in act.on_stage):
            await repo.save_act(
                story.id, act.model_copy(update={"on_stage": [*act.on_stage, name]})
            )
    return await _state(await _story(story_id))


@router.post("/stories/{story_id}/characters/remove")
async def remove_character(story_id: str, body: NameForm) -> dict:
    """Spec-630 B7: borra un personaje del elenco y de «Quiénes están» de todos los actos."""
    story = await _editable(story_id)
    existing = _find(story.personajes_full or [], body.name, key=lambda p: p.get("name", ""))
    if existing is None:
        raise HTTPException(
            status_code=404, detail=message("api.personaje_inexistente", nombre=body.name)
        )
    if _same(existing["name"], context.narrator(story)):
        raise HTTPException(
            status_code=422, detail=message("api.quien_narra_no_se_borra", nombre=existing["name"])
        )
    repo = SQLStoryRepository()
    story.personajes_full = [p for p in story.personajes_full if p is not existing]
    await repo.update_inputs(story)
    for act in story.outline:
        on_stage = [n for n in act.on_stage if not _same(n, existing["name"])]
        if on_stage != act.on_stage:
            await repo.save_act(story.id, act.model_copy(update={"on_stage": on_stage}))
    return await _state(await _story(story_id))


@router.post("/stories/{story_id}/scenarios")
async def add_scenario(story_id: str, body: ScenarioForm) -> dict:
    """Spec-630 B6: suma un lugar a la historia (opción en todos los actos); con `act`,
    queda elegido en ese acto."""
    story = await _editable(story_id)
    name = " ".join(body.name.split())
    repo = SQLStoryRepository()
    existing = _find(story.scenarios, name, key=lambda s: s.name)
    if existing is None:
        used = _find([a.scenario for a in story.outline if a.scenario], name, key=lambda n: n)
        name = used or name  # un lugar que ya usaba algún acto entra con su nombre
        story.scenarios = [
            *story.scenarios,
            Scenario(story_id=story.id, order_index=len(story.scenarios), name=name),
        ]
        await repo.update_inputs(story)
    else:
        name = existing.name
    if body.act is not None:
        act = _act(story, body.act)
        if act.scenario != name:
            await repo.save_act(story.id, act.model_copy(update={"scenario": name}))
    return await _state(await _story(story_id))


@router.post("/stories/{story_id}/scenarios/remove")
async def remove_scenario(story_id: str, body: NameForm) -> dict:
    """Spec-630 B7: borra un lugar de la historia y lo saca de los actos que lo usan."""
    story = await _editable(story_id)
    in_story = [s for s in story.scenarios if _same(s.name, body.name)]
    in_acts = [a for a in story.outline if a.scenario and _same(a.scenario, body.name)]
    if not in_story and not in_acts:
        raise HTTPException(
            status_code=404, detail=message("api.lugar_inexistente", nombre=body.name)
        )
    repo = SQLStoryRepository()
    if in_story:
        story.scenarios = [
            s.model_copy(update={"order_index": i})
            for i, s in enumerate(s for s in story.scenarios if s not in in_story)
        ]
        await repo.update_inputs(story)
    for act in in_acts:
        await repo.save_act(story.id, act.model_copy(update={"scenario": ""}))
    return await _state(await _story(story_id))


# ── Helpers ────────────────────────────────────────────────────────────────


def _same(a: str, b: str) -> bool:
    """Mismo personaje o lugar: sin importar mayúsculas, espacios ni la aclaración
    entre paréntesis que a veces suma el Planificador («Rubén (su tío)»)."""

    def norm(x: str) -> str:
        return " ".join(x.split("(")[0].split()).casefold()

    return norm(a) == norm(b)


def _find(items, name: str, key):
    return next((x for x in items if _same(key(x), name)), None)


def _next_character_id(cast: list[dict]) -> str:
    """P<n> que no choque con ninguno (al borrar un personaje, `len + 1` repetiría un id)."""
    nums = [
        int(p["id"][1:])
        for p in cast
        if str(p.get("id", "")).startswith("P") and p["id"][1:].isdigit()
    ]
    return f"P{max(nums, default=0) + 1}"


def _estructuras() -> BeatSpecRepository:
    return BeatSpecRepository()


def _act(story: Story, number: int) -> ActOutline:
    act = next((a for a in story.outline if a.number == number), None)
    if act is None:
        raise HTTPException(status_code=404, detail=f"Acto inexistente: {number}")
    return act


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
            detail=message("api.ia_trabajando"),
            headers={"X-Job-Id": str(active.id)},
        )
    return story


def _unprocessable(e: Exception) -> HTTPException:
    text = (
        e.message
        if isinstance(e, InvalidStoryInputError)
        else message("api.datos_rechazados", error=e)
    )
    return HTTPException(status_code=422, detail=text)


def _direction(form: DirectionForm) -> Direction:
    return Direction(
        premise=form.premise.strip(),
        effect=form.effect,
        effect_other=form.effect_other.strip(),
        ending=form.ending.strip(),
        ending_intentional=form.ending_intentional,
        telling=form.telling,
    )


def _threat(form: DirectionForm) -> list[dict]:
    t = form.threat
    return [t.model_dump()] if t and t.nature.strip() else []


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
        "relator": message("historia_nueva.relator", narrador=narrator),
        "sinopsis": form.premise.strip() or message("historia_nueva.sinopsis"),
        "personajes_full": cast,
        "narrator_config": config,
    }


def _form(story: Story) -> dict:
    """La Dirección como la lee la vista. Sin validar: una historia vieja puede
    exceder los topes del formulario (p. ej. una sinopsis larga)."""
    d = story.direction or Direction()
    lead = (story.personajes_full or [{}])[0]
    return {
        "title": story.title,
        "genero": story.genero,
        "subgenero": story.subgenero,
        # Sin dirección (historia importada): la sinopsis es su «¿de qué trata?».
        "premise": d.premise if story.direction else story.sinopsis,
        "effect": d.effect,
        "effect_other": d.effect_other,
        "ending": d.ending,
        "ending_intentional": d.ending_intentional,
        "telling": d.telling,
        "protagonist_name": lead.get("name", ""),
        "protagonist_role": lead.get("role", ""),
        "narrator": (story.narrator_config or {}).get("storyteller_name", ""),
        "threat": _threat_form(story),
    }


def _threat_form(story: Story):
    lead = next((e for e in story.entities if e.order_index == 0), None)
    if lead is None:
        return None
    return {
        "name": lead.name,
        "nature": lead.nature_id,
        "description": lead.description,
        "manifestations": lead.manifestations,
        "limits": lead.limits,
        "reveal_level": lead.reveal_level.value,
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
            "text": message("workshop.sin_analizar"),
            "open_questions": 0,
        }
    used = {d for a in story.outline for d in a.decisions}
    active = await SQLJobRepository().get_active_for_story(story.id)
    return {
        "story_id": str(story.id),
        "status": story.status.value,
        "direction": _form(story),
        # Spec-650: el largo y sus actos (la UI arma las tarjetas y los nombres con esto).
        "structure": story.structure,
        "structure_acts": [
            {"number": a["id"], "name": a["nombre_ui"], "intensity": a["intensity"]}
            for a in _estructuras().estructura(story.structure).actos
        ],
        "workshop": {
            "round": workshop_rules.current_round(ordered),
            "max_rounds": workshop_rules.MAX_ROUNDS,
            "finish": finish,
            "items": [
                {**w.model_dump(mode="json"), "nombre": c.nombre, "por_que": c.por_que}
                for w, c in (
                    (by_id[c.id], c.for_story(context.protagonist(story)))
                    for c in catalog.direction_criteria()
                    if c.id in by_id
                )
            ],
        },
        "outline": {
            "acts": [
                {
                    **a.model_dump(mode="json"),
                    "rules": [
                        r.content for r in story.typed_rules if r.applies_to_beat == a.number
                    ],
                }
                for a in story.outline
            ],
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
                # Spec-630 B7: en qué actos está (lo dice la confirmación de borrar).
                "acts": [
                    a.number
                    for a in story.outline
                    if any(_same(n, p.get("name", "")) for n in a.on_stage)
                ],
            }
            for p in story.personajes_full or []
        ],
        # Los de la historia y los que la escaleta sumó: opciones rápidas en cada acto,
        # con los actos que los usan (Spec-630 B7).
        "scenarios": [
            {
                "name": name,
                "acts": [a.number for a in story.outline if a.scenario and _same(a.scenario, name)],
            }
            for name in dict.fromkeys(
                [s.name for s in story.scenarios]
                + [a.scenario for a in story.outline if a.scenario]
            )
        ],
        "active_job": await job_manager.payload(active) if active else None,
    }


def _clean(value):
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        return [" ".join(v.split()) for v in value if isinstance(v, str) and v.strip()]
    return value

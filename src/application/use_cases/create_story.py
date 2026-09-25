"""CreateStoryUseCase - crea una nueva historia."""

from uuid import UUID, uuid4

from pydantic import ValidationError

from src.application.dto import StoryCreateDTO
from src.domain.exceptions import InvalidAuthoringError, InvalidEntityError, InvalidGenreError
from src.domain.interfaces import GenreRepository, StoryRepository
from src.domain.models import (
    MAX_ENTITIES,
    ActOutline,
    BeatType,
    CharacterKind,
    Direction,
    Entity,
    MacroBeat,
    RevealLevel,
    RuleType,
    Scenario,
    Story,
    StoryStatus,
    TypedRule,
    WorkshopItem,
)


class CreateStoryUseCase:
    """Caso de uso para crear una historia."""

    def __init__(
        self,
        story_repository: StoryRepository,
        genre_repository: GenreRepository | None = None,
    ):
        self.story_repository = story_repository
        self.genre_repository = genre_repository

    async def execute(
        self, dto: StoryCreateDTO, initial_status: StoryStatus = StoryStatus.DRAFT
    ) -> Story:
        """Crea una nueva historia.

        Raises:
            InvalidGenreError: el par género/subgénero no está en el catálogo.
            InvalidEntityError: entidades inválidas (cantidad, largo, naturaleza).
        """
        await ensure_valid_genre(self.genre_repository, dto.genero, dto.subgenero)
        story = Story(
            title=dto.title,
            protagonista=dto.protagonista,
            relator=dto.relator,
            sinopsis=dto.sinopsis,
            genero=dto.genero,
            subgenero=dto.subgenero,
            tono=dto.tono,
            reglas=dto.reglas,
            status=initial_status,
            narrator_config=dto.narrator_config,
            personajes_full=dto.personajes_full,
        )
        story.entities = build_entities(story.id, dto.entities)
        story.direction, story.workshop, story.outline = build_authoring(dto)
        await ensure_valid_entities(self.genre_repository, dto.genero, story.entities)

        # Crear objetos Scenario. Si el DTO trae escenarios_full (con
        # description), se prefiere; si no, se cae a la lista de nombres.
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

        # Crear TypedRule si el DTO trae reglas tipadas
        if dto.typed_rules:
            typed = []
            for r in dto.typed_rules:
                raw_type = r.get("type")
                rule_type = RuleType.from_raw(raw_type)
                typed.append(
                    TypedRule(
                        id=r.get("id") or str(uuid4()),
                        story_id=story.id,
                        content=r.get("content", ""),
                        type=rule_type,
                        intensity=r.get("intensity"),
                        # Spec-530: las reglas se cargan dentro de un acto.
                        applies_to_beat=r.get("applies_to_beat"),
                    )
                )
            story.typed_rules = typed

        # Pre-crear los 5 MacroBeat desde los actos del YAML (Spec-190 T7.1)
        if dto.actos:
            beats = []
            for act in dto.actos:
                number = act.get("number", 1)
                beat_type_str = act.get("type", "")
                try:
                    beat_type = BeatType(beat_type_str) if beat_type_str else None
                except ValueError:
                    beat_type = None
                beats.append(
                    MacroBeat(
                        number=number,
                        summary=f"Acto {number}: {beat_type_str}",
                        beat_type=beat_type,
                        synopsis_beat=act.get("synopsis", ""),
                    )
                )
            story.beats = beats

        return await self.story_repository.save(story)


async def ensure_valid_genre(
    genre_repository: GenreRepository | None, genero: str, subgenero: str
) -> None:
    """Valida contra el catálogo antes de persistir (Spec-440 §2).

    La FK de `story` es la última línea de defensa; esto da un error legible.
    Sin repositorio (tests, usos sin catálogo) no valida.
    """
    if genre_repository is None:
        return
    if not await genre_repository.exists(genero, subgenero):
        valid_genre = await genre_repository.exists(genero)
        raise InvalidGenreError(genero, subgenero if valid_genre else "")


_ENTITY_FIELD_LABELS = {
    "name": "«Nombre»",
    "nature_id": "«Naturaleza»",
    "description": "«Descripción»",
    "manifestations": "«Manifestaciones»",
    "limits": "«Límites»",
    "reveal_level": "«Nivel de revelación»",
}


def build_authoring(
    dto: StoryCreateDTO,
) -> tuple[Direction | None, list[WorkshopItem], list[ActOutline]]:
    """Dirección, taller y escaleta desde el DTO (Spec-530). Raises InvalidAuthoringError."""
    direction = _validate(Direction, dto.direction, "dirección") if dto.direction else None
    workshop = [
        _validate(WorkshopItem, w, f"taller, elemento {i}") for i, w in enumerate(dto.workshop, 1)
    ]
    outline = [
        _validate(ActOutline, a, f"escaleta, elemento {i}") for i, a in enumerate(dto.outline, 1)
    ]
    kinds = {k.value for k in CharacterKind}
    for p in dto.personajes_full:
        if p.get("kind") and p["kind"] not in kinds:
            raise InvalidAuthoringError(
                f"Tipo de personaje inválido para «{p.get('name', '')}»: {p['kind']}"
            )
    numbers = [a.number for a in outline]
    if len(numbers) != len(set(numbers)):
        raise InvalidAuthoringError("La escaleta repite un número de acto")
    return direction, workshop, outline


def _validate(model, raw: dict, where: str):
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        first = e.errors()[0]
        field = ".".join(str(p) for p in first["loc"])
        raise InvalidAuthoringError(f"Dato inválido en {where} ({field}): {first['msg']}") from e


def build_entities(story_id: UUID, raw: list[dict]) -> list[Entity]:
    """Entidades desde el formato de autoría (wizard/YAML) (Spec-450 §1).

    La primera es la principal. Raises InvalidEntityError con un mensaje legible.
    """
    if len(raw) > MAX_ENTITIES:
        raise InvalidEntityError(
            f"Una historia admite hasta {MAX_ENTITIES} entidades (llegaron {len(raw)})"
        )
    entities = []
    for i, r in enumerate(raw):
        try:
            entities.append(
                Entity(
                    story_id=story_id,
                    order_index=i,
                    name=r.get("name") or "",
                    nature_id=r.get("nature") or "",
                    description=r.get("description") or "",
                    manifestations=r.get("manifestations") or "",
                    limits=r.get("limits") or "",
                    reveal_level=r.get("reveal_level") or RevealLevel.INSINUADA,
                )
            )
        except ValidationError as e:
            raise InvalidEntityError(f"Entidad {i + 1}: {_entity_error(e)}") from e
    return entities


def _entity_error(e: ValidationError) -> str:
    err = e.errors()[0]
    label = _ENTITY_FIELD_LABELS.get(str(err["loc"][0]), str(err["loc"][0]))
    if err["type"] == "string_too_long":
        return f"{label} supera los {err['ctx']['max_length']} caracteres"
    if err["type"] == "string_too_short":
        return f"falta {label}"
    if err["type"] == "enum":
        levels = ", ".join(level.value for level in RevealLevel)
        return f"{label} no es válido (opciones: {levels})"
    return f"{label}: {err['msg']}"


async def ensure_valid_entities(
    genre_repository: GenreRepository | None, genero: str, entities: list[Entity]
) -> None:
    """Cada naturaleza debe corresponder al género (Spec-450 §1). Sin repositorio no valida.

    De paso completa `nature_label` desde el catálogo: la historia recién creada
    (sin releerla de la base) ya lleva la etiqueta que usan los prompts.
    """
    if genre_repository is None:
        return
    labels = {n.id: n.label for n in await genre_repository.natures_of(genero)} if genero else {}
    for e in entities:
        e.nature_label = labels.get(e.nature_id, e.nature_label)
        if not await genre_repository.nature_allowed(genero, e.nature_id):
            where = f"al género '{genero}'" if genero else "a ninguna del catálogo"
            raise InvalidEntityError(
                f"Entidad {e.order_index + 1}: la naturaleza '{e.nature_id}' no corresponde {where}"
            )
